#!/usr/bin/env python3
"""Owner-authorized historical title batches; checkpoint branch only, no publish.

Reserve before ANY paid request in a remote Git checkpoint. A lost response or
process retains the whole reservation. Successful responses settle from usage.
This is a $3 release ledger, not a new account/model spending authorization.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.analyzer import Analyzer
from analysis.pricing import estimate_usage_cost_usd
from config import ANALYSIS_MODEL, ANTHROPIC_API_KEY
from core.title_translation import MAX_TOKENS, SYSTEM, TOOL
from migrations.runner import apply_all, applied_versions, connect, discover
from scripts.reconcile_db import read_only
from storage.title_translation import candidates, ready, run_batch

BRANCH = "ops/china-title-completion-20261018"
LEDGER = Path(".github/state/china_title_completion_20261018.json")
CAP = Decimal("3")
TITLE_ALLOWANCE = Decimal("0.10")
PROBE_ALLOWANCE = Decimal("0.01")
PROBE_MODEL = "claude-haiku-4-5-20251001"


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def checkpoint(message, include_db=False):
    paths = [str(LEDGER)] + (["pla_watch.db"] if include_db else [])
    subprocess.run(["git", "add", "--", *paths], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)
    # Fast-forward only: a moving branch refuses, before further spending.
    subprocess.run(["git", "push", "origin", "HEAD:refs/heads/" + BRANCH], check=True)


def charged(ledger):
    return sum((Decimal(r.get("charged_usd", r["reserved_usd"]))
                for b in ledger["batches"] for r in b["requests"]), Decimal(0))


def reserve(ledger, count):
    allowance = TITLE_ALLOWANCE * count + PROBE_ALLOWANCE
    if charged(ledger) + allowance > CAP:
        raise RuntimeError("Historical $3 ceiling: batch refused before dispatch")
    batch = {"reserved_at": datetime.now(timezone.utc).isoformat(),
             "requests": [{"kind": "probe", "reserved_usd": str(PROBE_ALLOWANCE)}]
             + [{"kind": "title", "reserved_usd": str(TITLE_ALLOWANCE)}
                for _ in range(count)]}
    ledger["batches"].append(batch)
    return batch


def save(ledger):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=2) + "\n")


def settle(entry, response):
    usage = response.usage
    if usage is None or any(type(getattr(usage, k, None)) is not int
                            for k in ("input_tokens", "output_tokens")):
        raise RuntimeError("Missing provider usage; reservation retained")
    fields = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens")
    values = {k: getattr(usage, k, 0) for k in fields}
    for k in fields[2:]:
        if values[k] is None:
            values[k] = 0
    if any(type(v) is not int or v < 0 for v in values.values()):
        raise RuntimeError("Unusable provider usage; reservation retained")
    tier = getattr(usage, "service_tier", None)
    geo = getattr(usage, "inference_geo", None)
    if tier not in (None, "standard"):
        raise RuntimeError("Unexpected billing tier; reservation retained")
    # Respect the existing workspace's residency choice. Sonnet 4.6's US-only
    # inference has a published 1.1x surcharge. Missing geo keeps that premium
    # charged conservatively rather than silently assuming a global invoice.
    uncertain = entry["model"] == "claude-sonnet-4-6" and geo is None
    if entry["model"] == "claude-sonnet-4-6" and geo not in (None, "global", "us"):
        raise RuntimeError("Unknown inference geography; reservation retained")
    base_cost = estimate_usage_cost_usd(entry["model"], **values)
    cost = (None if base_cost is None else round(base_cost *
            (1.1 if entry["model"] == "claude-sonnet-4-6" and geo != "global" else 1), 12))
    if cost is None or Decimal(str(cost)) > Decimal(entry["reserved_usd"]):
        raise RuntimeError("Provider usage exceeds allowance; stop and investigate")
    entry.update(usage=values, base_token_cost_usd=str(base_cost),
                 reported_cost_usd=None if uncertain else str(cost), charged_usd=str(cost),
                 inference_geo=geo, service_tier=tier, pricing_uncertain=uncertain,
                 response_id=response.id)


class ReservedMessages:
    """Only the fixed headline request can use a prepaid title slot.

    No caching/thinking/images/server tools or automatic retries. UTF-8 payload
    <=4096 bytes; free provider count must also be <=4096 input tokens. Each
    $0.10 slot covers 27,000 input tokens plus ALL 512 output tokens, including
    the 1.1x US-residency premium, leaving over 6x the admitted input for framing.
    Ambiguous/network/validation failures never refund their reservation.
    """
    def __init__(self, messages, entries):
        self.messages, self.entries, self.used = messages, entries, 0

    @contextmanager
    def stream(self, **kwargs):
        if self.used >= len(self.entries):
            raise RuntimeError("No reserved request slot")
        if (set(kwargs) != {"model", "system", "messages", "max_tokens",
                            "temperature", "tools", "tool_choice"}
                or kwargs["model"] != "claude-sonnet-4-6"
                or kwargs["max_tokens"] != MAX_TOKENS or MAX_TOKENS != 512
                or kwargs["system"] != [{"type": "text", "text": SYSTEM}]
                or kwargs["tools"] != [TOOL]
                or kwargs["tool_choice"] != {"type": "tool", "name": "emit_title"}
                or kwargs["temperature"] != 0.0
                or len(json.dumps(dict(kwargs, service_tier="standard_only"),
                                  ensure_ascii=False).encode()) > 4096):
            raise RuntimeError("Request outside prepaid headline envelope")
        count_args = {k: v for k, v in kwargs.items()
                      if k not in {"temperature", "max_tokens"}}
        count = self.messages.count_tokens(**count_args).input_tokens
        if type(count) is not int or count < 0 or count > 4096:
            raise RuntimeError("Input token admission refused")
        entry = self.entries[self.used]
        self.used += 1
        entry.update(model=kwargs["model"], counted_input_tokens=count)
        with self.messages.stream(**dict(kwargs, service_tier="standard_only")) as stream:
            response = stream.get_final_message()
            settle(entry, response)
            # The existing Analyzer still validates the tool result and records
            # its normal telemetry. Do not expose another paid dispatch path.
            class Finished:
                def get_final_message(self):
                    return response
            yield Finished()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    if not 1 <= args.limit <= 20:
        ap.error("Only 1–20 titles per reviewed batch")
    if git("branch", "--show-current") != BRANCH or git("status", "--porcelain"):
        ap.error("Requires clean designated checkpoint branch")
    if not ANTHROPIC_API_KEY or ANALYSIS_MODEL != "claude-sonnet-4-6":
        ap.error("Requires existing credential and pinned Sonnet 4.6 model")
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {
        "release": "china-title-completion-20261018", "cap_usd": "3", "batches": []}
    if ledger["cap_usd"] != "3":
        ap.error("Unexpected ledger ceiling")
    with read_only("pla_watch.db") as conn:
        pending = {m.version for m in discover()} - set(applied_versions(conn))
        if pending - {"0012"}:
            ap.error("Incompatible pending migrations")
        rows = [r for r in candidates(conn) if ready(r)]
    count = min(args.limit, len(rows), max(0, int(
        (CAP - charged(ledger) - PROBE_ALLOWANCE) / TITLE_ALLOWANCE)))
    if not count:
        print(json.dumps({"remaining": len(rows), "charged_usd": str(charged(ledger))}))
        return
    batch = reserve(ledger, count)
    save(ledger)
    checkpoint("Reserve capped historical China title batch before API dispatch")
    conn = None
    try:
        import anthropic
        # No opaque SDK retries: every paid attempt must own a durable slot.
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=0, timeout=60)
        probe = batch["requests"][0]
        probe["model"] = PROBE_MODEL
        response = client.messages.create(model=PROBE_MODEL, max_tokens=1, service_tier="standard_only",
                    messages=[{"role": "user", "content": "ping"}])
        settle(probe, response)
        analyzer = Analyzer()
        analyzer._client = type("ReservedClient", (), {"messages":
            ReservedMessages(client.messages, batch["requests"][1:])})()
        conn = connect("pla_watch.db")
        apply_all(conn, sync_config=False)
        result = run_batch(conn, analyzer, rows[:count], ANALYSIS_MODEL)
        batch["result"] = result
        batch["usage"] = analyzer.usage.rows()
        print(json.dumps({"result": result, "usage": batch["usage"]}))
    finally:
        if conn is not None:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        save(ledger)
        checkpoint("Checkpoint historical China titles and reported usage", include_db=True)
        print(json.dumps({"charged_usd": str(charged(ledger)),
                          "allowance_remaining_usd": str(CAP-charged(ledger))}))


if __name__ == "__main__":
    main()
