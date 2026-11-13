"""Standing-rights qualification of JCG custody rows before model input or signing.

Every ``jp_jcg_press_en`` row that leaves private custody, whether toward the
model (``processing.daily_intake``) or toward a signed link-only parent
(``scripts/japan_jcg_links.py sign``), passes through
``core.japan_jcg_links.links_from_custody``. That function calls
``qualify_rows`` here, and a row that does not qualify carries a
``jcg_scope_hold``: ``core.daily_sources._jcg_known_hold`` then keeps it from
the model, and ``core.japan_jcg_links.sign_links`` never signs it.

Qualification is the standing contract
``core.standing_source_rights.qualify_standing_text`` with three verifiers.
All three read only the pinned custody revision, never the network:

source replay
    The collector ledger for the row's own run must record a GET of the
    canonical article URL that returned HTTP 200 text/html, was not
    redirected and has the row's capture hash. Those raw bytes must be
    present at the pinned commit with that hash, and re-extracting them with
    the collector's own parser must reproduce the stored title, text, date,
    identity and extraction profile exactly. Only then is the stored text
    bound to authenticated publisher HTML.

policy replay
    The latest successful collector run at the pinned commit must have
    captured the JCG terms page (the collector fetches it in every run). The
    capture must be intact, carry the reviewed PDL 1.0 clauses and no
    conflicting restriction, and be at most seven days old. A stale, missing,
    altered or changed policy holds every row. There is no fallback to an
    older capture.

exception replay
    The release body (the region the extractor reads, minus scripts and
    styles) and the extracted prose are screened for item-specific
    exceptions: a rights or credit notation, separate terms, quoted
    third-party prose or a privacy or secrecy marker. Any match holds the row.
    The screens are deliberately conservative and are reviewed against the
    preserved genuine releases. A match is a hold for human review, not a
    finding that the release is unlicensed.

Hold codes are fixed strings prefixed ``jcg_rights_``. Publisher bytes are
never echoed into a code. Any per-row failure, a git or parser error
included, becomes a hold rather than an exception, because this runs inside
the shared Daily alongside other desks.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Tuple

FAMILY = "jp_jcg_press_en"
POLICY_URL = "https://www.kaiho.mlit.go.jp/questions/post-1.html"
POLICY_ID = "jcg-english-html-text-pdl1"
MAX_POLICY_BYTES = 2_000_000
MAX_CAPTURE_BYTES = 5_000_000

# Reviewed clauses of the JCG site-use rules (observed 2026-11-13): first-party
# copyright unless otherwise noted, PDL 1.0 unless a rights notation says
# otherwise, attribution, disclosure of editing, no presentation as an
# unedited government work, and the exclusions (content under other rules,
# the JCG logo). All must remain for the standing licence to apply.
POLICY_CLAUSES = (
    "特記されていない限り海上保安庁に帰属し",
    "権利表記の記載がない限り",
    "公共データ利用規約（第1.0版）",
    "(PDL1.0)が適用されています",
    "本コンテンツを利用する際は出典を記載してください",
    "編集・加工等を行ったこと及びその主体を記載してください",
    "あたかも国(又は府省等)が作成した未加工のままであるかのような態様で公表・利用してはいけません",
    "本利用ルールが適用されないコンテンツについて",
    "JCGロゴマーク",
    "別の利用ルールの適用を明示しているコンテンツ",
)
# None of these appears in the reviewed page; any of them means the terms
# changed in a way that needs a fresh human review.
POLICY_CONFLICTS = ("禁止", "禁じ", "無断転載", "All rights reserved",
                    "公共データ利用規約（第2")

# Item exceptions. Calibrated against the preserved genuine releases 9465,
# 9477 and 9519, which must pass. Bare "provided by" (a programme provided
# by JICA) and "joint statement" (a cited Leaders' Joint Statement) are
# ordinary first-party prose there, so they are deliberately not screens.
RIGHTS_NOTATION = re.compile(
    r"©|\(c\)\s*\d{4}|\bcopyright\b|all rights reserved|\bcourtesy of\b"
    r"|\bphoto(?:graph)?s?\s*(?:by|credit|courtesy|provided by)\b"
    r"|\bimages?\s*(?:by|credit|courtesy)\b|\bcredit\s*:"
    r"|\blicen[cs]ed under\b|creative commons|\bterms of use\b"
    r"|無断転載|転載禁止|写真提供|提供\s*[:：]|出典\s*[:：]|権利表記", re.I)
THIRD_PARTY_PROSE = re.compile(
    r"\b(?:statement|remarks|message|address|speech|letter|op-ed)\s+(?:by|of|from)\b"
    r"|\breprinted\b|\bexcerpts?\b|\bquoted?\s+(?:from|by)\b"
    r"|\bthe following is\b|\bfull text of\b", re.I)
QUOTATION = re.compile(r"[\"“”]([^\"“”]{1,4000})[\"“”]")
QUOTED_WORDS = 12
PRIVACY = re.compile(
    r"\bpersonal information\b|\bconfidential\b|\bclassified\b|\bsecret\b"
    r"|\bembargo(?:ed)?\b|\bnot for (?:publication|release)\b|個人情報|秘密", re.I)
QUOTE_TAGS = ("blockquote", "q", "cite")


class RightsHold(Exception):
    """A fixed hold code; never carries publisher text."""


def now_utc() -> str:
    """Current instant in the contract's form. Patched by offline tests."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instant(retrieved_at) -> str:
    """Ledger ``retrieved_at`` (ISO with offset) as the contract's ``...Z`` form."""
    when = datetime.fromisoformat(retrieved_at)
    if when.tzinfo is None or when.utcoffset().total_seconds() != 0:
        raise RightsHold("jcg_rights_capture_clock_untrusted")
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Custody:
    """Read-only view of one pinned custody revision: ledgers and captures."""

    def __init__(self, repo, commit):
        self.repo, self.commit = str(repo), commit
        self._ledgers = None

    def _git(self, *args) -> bytes:
        return subprocess.run(["git", "-C", self.repo, *args], check=True,
                              capture_output=True).stdout

    def ledgers(self) -> List[dict]:
        if self._ledgers is None:
            try:
                names = self._git("ls-tree", "--name-only", self.commit + ":state/ledger")
            except subprocess.CalledProcessError:
                names = b""
            out = []
            for name in sorted(names.decode("utf-8").split()):
                if not name.endswith(".json"):
                    continue
                try:
                    entry = json.loads(self._git("show", self.commit + ":state/ledger/" + name))
                except (subprocess.CalledProcessError, ValueError):
                    continue
                if type(entry) is dict and type(entry.get("requests")) is list:
                    out.append(entry)
            out.sort(key=lambda e: str(e.get("finished_utc") or ""))
            self._ledgers = out
        return self._ledgers

    def capture(self, digest: str, missing: str, mismatch: str) -> bytes:
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RightsHold(missing)
        try:
            raw = self._git("show", self.commit + ":state/captures/" + digest + ".bin")
        except subprocess.CalledProcessError:
            raise RightsHold(missing) from None
        if _sha(raw) != digest:
            raise RightsHold(mismatch)
        return raw


def _successful(entry) -> bool:
    from core.collection import status as st
    return st.is_success(entry.get("result"))


def _html_request(request, url) -> bool:
    return (type(request) is dict and request.get("requested_url") == url
            and request.get("final_url") == url and request.get("method") == "GET"
            and request.get("form") is None and request.get("http_status") == 200
            and str(request.get("content_type") or "").lower().startswith("text/html"))


def _normalized(raw: bytes, missing: str):
    from bs4 import BeautifulSoup
    try:
        page = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise RightsHold(missing) from None
    return BeautifulSoup(page, "html.parser")


def _policy_text(raw: bytes) -> str:
    if not 500 <= len(raw) <= MAX_POLICY_BYTES:
        raise RightsHold("jcg_rights_policy_capture_missing")
    soup = _normalized(raw, "jcg_rights_policy_capture_missing")
    for element in soup(("script", "style", "noscript")):
        element.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def verify_policy(custody: Custody) -> dict:
    """The contract's policy receipt from the latest custody capture of the terms."""
    from core.collection import status as st
    latest, failed = None, False
    for entry in custody.ledgers():
        report = entry.get("listing_report")
        terms = report.get("site_terms") if type(report) is dict else None
        if terms is not None and terms != st.OK:
            # A newer failed attempt, in any run, supersedes every earlier
            # capture until a later successful run captures the terms again.
            failed = True
            continue
        if not _successful(entry):
            continue
        hits = [r for r in entry["requests"]
                if type(r) is dict and r.get("requested_url") == POLICY_URL]
        if hits:
            latest, failed = hits[-1], False
    if failed:
        raise RightsHold("jcg_rights_policy_capture_failed")
    if latest is None:
        raise RightsHold("jcg_rights_policy_capture_missing")
    if not _html_request(latest, POLICY_URL):
        raise RightsHold("jcg_rights_policy_capture_not_authenticated")
    raw = custody.capture(latest.get("capture_sha256"), "jcg_rights_policy_capture_missing",
                          "jcg_rights_policy_capture_hash_mismatch")
    text = _policy_text(raw)
    if not all(clause in text for clause in POLICY_CLAUSES):
        raise RightsHold("jcg_rights_policy_terms_changed_or_incomplete")
    if any(marker in text for marker in POLICY_CONFLICTS):
        raise RightsHold("jcg_rights_policy_conflicting_restriction")
    return {
        "policy_id": POLICY_ID,
        "official_policy_url": POLICY_URL,
        "observed_at_utc": _instant(latest.get("retrieved_at")),
        "publisher_policy_sha256": _sha(raw),
        "text_reproduction_permitted": True,
        "derivatives_permitted": True,
        "third_party_exclusions_preserved": True,
        "policy_changed_or_withdrawn": False,
    }


def _article_request(custody: Custody, row: dict) -> dict:
    for entry in custody.ledgers():
        if entry.get("run_id") != row["first_seen_run"] or not _successful(entry):
            continue
        for request in entry["requests"]:
            if (_html_request(request, row["url"])
                    and request.get("capture_sha256") == row["capture_sha256"]):
                return request
    raise RightsHold("jcg_rights_capture_not_authenticated")


def _body_region(raw: bytes):
    soup = _normalized(raw, "jcg_rights_capture_not_utf8")
    bodies = soup.select("main article.main-article section.topics.topics-article "
                         "div.topics-article__main.tich-text")
    if len(bodies) != 1:
        raise RightsHold("jcg_rights_stored_text_not_bound_to_capture")
    body = bodies[0]
    for node in body.select("script, style, noscript, template"):
        node.decompose()
    return body


def item_exceptions(raw: bytes, text: str) -> Optional[str]:
    """Reason the release itself is outside the standing licence, or None."""
    body = _body_region(raw)
    # Rights notations anywhere in the release body, captions and media
    # attributes included: a credited photo can signal separate terms.
    notes = [body.get_text(" ", strip=True), text]
    for node in body.find_all(True):
        for attr in ("alt", "title", "aria-label"):
            if type(node.get(attr)) is str:
                notes.append(node[attr])
    if any(RIGHTS_NOTATION.search(n) for n in notes):
        return "jcg_rights_item_rights_notation"
    if body.find(QUOTE_TAGS) is not None or THIRD_PARTY_PROSE.search(text) or any(
            len(m.group(1).split()) >= QUOTED_WORDS for m in QUOTATION.finditer(text)):
        return "jcg_rights_item_third_party_text"
    if PRIVACY.search(text):
        return "jcg_rights_item_privacy_or_secrecy"
    return None


def _parser():
    from scraper.sources.jp_jcg_en import JCGEnglishAdapter
    adapter = JCGEnglishAdapter.__new__(JCGEnglishAdapter)
    adapter.source = SimpleNamespace(slug=FAMILY, enabled=True)
    adapter.slug = FAMILY
    return adapter


def qualify_row(custody: Custody, row: dict, policy, *, now: str,
                parser=None) -> Optional[str]:
    """None when the row qualifies under the standing contract, else a hold code.

    ``row`` holds the custody columns: source_identity, url, published_date,
    first_seen_run, capture_sha256, content_sha256, title_original,
    metadata_json, text_original. ``policy`` is the receipt from
    ``verify_policy`` or the ``RightsHold`` it raised.
    """
    from core import japan_jcg_links as links
    from core.standing_source_rights import StandingLicenseHold, qualify_standing_text

    text = row["text_original"]
    clean_sha = _sha(text.encode("utf-8"))
    if row["content_sha256"] != clean_sha:
        return "jcg_rights_stored_text_hash_mismatch"
    state: Dict[str, bytes] = {}

    def source_replay(source):
        request = _article_request(custody, row)
        raw = custody.capture(row["capture_sha256"], "jcg_rights_capture_missing",
                              "jcg_rights_capture_hash_mismatch")
        if len(raw) > MAX_CAPTURE_BYTES:
            raise RightsHold("jcg_rights_capture_missing")
        try:
            page = raw.decode("utf-8", "strict")
            doc = (parser or _parser()).parse_article(page, request["final_url"])
        except (UnicodeError, ValueError):
            raise RightsHold("jcg_rights_stored_text_not_bound_to_capture") from None
        meta = json.loads(row["metadata_json"] or "{}")
        if (doc.url != row["url"] or doc.title_original != row["title_original"]
                or doc.text_original != text or doc.published_date != row["published_date"]
                or doc.extra.get("source_identity") != row["source_identity"]
                or doc.extra.get("extraction_profile") != meta.get("extraction_profile")):
            raise RightsHold("jcg_rights_stored_text_not_bound_to_capture")
        state["raw"] = raw
        return {"source_git_commit": custody.commit,
                "source_capture_sha256": row["capture_sha256"],
                "entire_clean_original_text_sha256": clean_sha,
                "original_custody_authenticated": True,
                "source_text_complete": True}

    def policy_replay(_policy):
        if isinstance(policy, RightsHold):
            raise policy
        return policy

    def exception_replay(source, _policy):
        reason = item_exceptions(state["raw"], text)
        if reason:
            raise RightsHold(reason)
        return {"first_party_official_text": True,
                "third_party_text_present": False,
                "separate_terms_apply": False,
                "privacy_or_secrecy_exception": False,
                # The released Record is a text-only machine explanation.
                "released_artifact_embeds_media": False,
                "entire_source_text_version_sha256": clean_sha}

    source = {"desk": "japan", "source_family": FAMILY,
              "source_identity": row["source_identity"], "official_url": row["url"],
              "source_git_commit": custody.commit,
              "source_capture_sha256": row["capture_sha256"],
              "publisher_posted_date": row["published_date"], "language": "en"}
    try:
        qualify_standing_text(source, kind="original_text", proposed_sha256=clean_sha,
                              attribution=links.attribution(row["url"]), now_utc=now,
                              source_replay=source_replay, policy_replay=policy_replay,
                              exception_replay=exception_replay)
    except RightsHold as exc:
        return str(exc)
    except StandingLicenseHold as exc:
        return "jcg_rights_" + str(exc)
    except Exception:  # noqa: BLE001 - a row failure must never abort the shared Daily
        return "jcg_rights_replay_failed"
    return None


def qualify_rows(repo, commit, rows: Iterable[dict], *, now: Optional[str] = None
                 ) -> List[Optional[str]]:
    """Hold codes (or None) for each row, in order, against one pinned revision."""
    rows = list(rows)
    if not rows:
        return []
    custody = Custody(repo, commit)
    now = now or now_utc()
    try:
        policy = verify_policy(custody)
    except RightsHold as exc:
        policy = exc
    except Exception:  # noqa: BLE001
        policy = RightsHold("jcg_rights_policy_replay_failed")
    try:
        parser = _parser()
    except Exception:  # noqa: BLE001
        return ["jcg_rights_replay_failed"] * len(rows)
    return [qualify_row(custody, row, policy, now=now, parser=parser) for row in rows]
