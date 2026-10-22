"""Read preserved MPS feeds, optionally recover from exact provider-digested ZIPs.

No extraction to disk, original article import, clock rewrite, or historical
success reclassification. ZIPs are explicitly supplied outside repositories;
their GitHub digest, workflow attempt and ledger provenance are checked afresh.
The ordinary collector fetches the selected official articles under today's
robots rules and unchanged request budget.
"""
import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.attest_vietnam_run_state import PREFIX, utc
from scripts.publish_shadow_review import strict_loads
from scraper.sources.vn_shadow_http import Raw, MAX_BODY_BYTES

MPS = "vn_mps_foreign_affairs_vi"
WORKFLOW = ".github/workflows/vietnam_ministry_shadow.yml"
MEMBER = "vn-ministry-state/" + MPS + "/state/"


def need(ok, why):
    if not ok:
        raise ValueError(why)


def snapshot(adapter, cap, payload):
    need(cap["role"] in ("listing", "recovery_listing")
         and cap["url"] == adapter.profile.listing and cap["http_status"] == 200
         and len(payload) == cap["payload_bytes"] <= MAX_BODY_BYTES
         and hashlib.sha256(payload).hexdigest() == cap["payload_sha256"],
         "RSS capture hash or scope differs")
    utc(cap["retrieved_at"])
    raw = Raw(cap["url"], cap["http_status"], {"content-type": cap["content_type"]},
              payload, False, cap["retrieved_at"])
    items, _ = adapter._rss(raw)
    need(bool(items), "empty preserved RSS")
    return {"items": items, "retrieved_at": cap["retrieved_at"],
            "sha256": cap["payload_sha256"]}, raw


def stored(adapter, state):
    # The caller verifies the complete source state using the existing reviewer.
    result = []
    for path in sorted((Path(state) / "ledger").glob("*.json")):
        row = strict_loads(path.read_text(), "MPS ledger")
        need(row["source_slug"] == MPS, "foreign RSS history")
        for cap in row["captures"]:
            if cap["role"] in ("listing", "recovery_listing"):
                payload = (Path(state) / "captures" / (cap["payload_sha256"] + ".bin")).read_bytes()
                item, _ = snapshot(adapter, cap, payload)
                result.append(item)
    # Retain the latest bounded history; a missing starting boundary still fails.
    return result[-48:]


def recovery(adapter, directory, api):
    try:
        return _recovery(adapter, directory, api)
    except (KeyError, TypeError, AttributeError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError("malformed authenticated MPS recovery evidence") from None


def _recovery(adapter, directory, api):
    directory = Path(directory)
    need(directory.is_dir() and not directory.is_symlink()
         and not any((p / ".git").exists() for p in (directory, *directory.parents)),
         "recovery ZIP directory must be external")
    paths = sorted(directory.iterdir())
    need(0 < len(paths) <= 6, "one to six exact recovery ZIPs required")
    result, provenance = [], []
    for path in paths:
        match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)\.zip", path.name)
        need(match is not None and path.is_file() and not path.is_symlink()
             and path.stat().st_size <= 20_000_000, "invalid recovery ZIP")
        rid, attempt = map(int, match.groups())
        run = api.get(PREFIX + "/actions/runs/%d/attempts/%d" % (rid, attempt))
        need(run.get("id") == rid and run.get("run_attempt") == attempt
             and run.get("event") == "schedule" and run.get("path") == WORKFLOW
             and run.get("status") == "completed" and run.get("conclusion") == "failure",
             "recovery is limited to genuine failed scheduled ministry attempts")
        artifacts = api.get(PREFIX + "/actions/runs/%d/artifacts?per_page=100" % rid)
        need(artifacts.get("total_count", 101) <= 100, "recovery artifact index truncated")
        matches = [a for a in artifacts.get("artifacts", [])
                   if a.get("name") == "vietnam-ministry-shadow-%d-%d" % (rid, attempt)]
        payload = path.read_bytes()
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        need(len(matches) == 1 and matches[0].get("digest") == digest
             and matches[0].get("expired") is False
             and matches[0].get("size_in_bytes") == len(payload),
             "provider recovery ZIP digest differs or expired")
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            names = z.namelist()
            need(len(names) == len(set(names)) and len(names) <= 2000,
                 "ambiguous recovery archive")
            ledgers = [n for n in names if n.startswith(MEMBER + "ledger/")
                       and n.endswith("-%d-%d.json" % (rid, attempt))]
            need(len(ledgers) == 1 and z.getinfo(ledgers[0]).file_size <= 250000,
                 "exact failed MPS ledger missing")
            row = strict_loads(z.read(ledgers[0]).decode(), "failed MPS ledger")
            need(row.get("run_id") == "%d-%d" % (rid, attempt)
                 and row.get("source_slug") == MPS and row.get("health") == "fail"
                 and row.get("collector_commit") == run.get("head_sha")
                 and row.get("target_date_source") == "schedule-slot",
                 "failed RSS ledger provenance differs")
            caps = [c for c in row["captures"] if c["role"] == "listing"]
            need(len(caps) == 1, "failed RSS snapshot missing")
            cap = caps[0]
            name = MEMBER + "captures/" + cap["payload_sha256"] + ".bin"
            need(z.getinfo(name).file_size <= MAX_BODY_BYTES, "oversized recovered RSS")
            item, raw = snapshot(adapter, cap, z.read(name))
            need(utc(run["run_started_at"]) <= utc(raw.retrieved_at) <= utc(run["updated_at"]),
                 "RSS capture outside authenticated attempt")
            result.append(item)
            adapter._keep("recovery_listing", raw)
            provenance.append({"run_id": row["run_id"], "historical_health": "fail",
                               "artifact_id": matches[0]["id"], "zip_digest": digest,
                               "listing_sha256": item["sha256"]})
    return result, provenance


def download(attempts, output, api):
    """Fetch only explicit GitHub artifact ZIPs; never request a ministry URL."""
    import subprocess
    directory = Path(output)
    ids = attempts.split()
    need(0 < len(ids) <= 6 and len(set(ids)) == len(ids)
         and all(re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*", i) for i in ids),
         "invalid explicit recovery attempts")
    need(not directory.exists() and not directory.is_symlink(), "recovery output must be new")
    directory.mkdir(mode=0o700)
    for ident in ids:
        rid = ident.split("-")[0]
        data = api.get(PREFIX + "/actions/runs/" + rid + "/artifacts?per_page=100")
        need(data.get("total_count", 101) <= 100, "artifact index truncated")
        matches = [a for a in data.get("artifacts", [])
                   if a.get("name") == "vietnam-ministry-shadow-" + ident]
        need(len(matches) == 1 and matches[0].get("expired") is False
             and 0 < matches[0].get("size_in_bytes", 0) <= 20_000_000,
             "recovery artifact unavailable")
        artifact = matches[0]
        with (directory / (ident + ".zip")).open("xb") as stream:
            subprocess.run(["gh", "api", PREFIX + "/actions/artifacts/%d/zip" % artifact["id"]],
                           stdout=stream, check=True)
        payload = (directory / (ident + ".zip")).read_bytes()
        need("sha256:" + hashlib.sha256(payload).hexdigest() == artifact.get("digest"),
             "downloaded recovery artifact digest differs")


if __name__ == "__main__":
    import argparse
    import os
    from scripts.attest_vietnam_run_state import GithubRead
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--attempts", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    download(args.attempts, args.out_dir,
             GithubRead(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")))
