"""Read only permitted shared machine explanations, without source originals."""
import hashlib
import json

from scripts.reconcile_db import read_only
from processing.daily_intake import REFS, digest, load_policy, validate_output


def load(db_path):
    policy = load_policy()
    result = []
    with read_only(str(db_path)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='daily_machine_records'").fetchone():
            return []
        from processing.daily_intake import PUBLIC_FIELDS
        columns = ["categories_json" if k == "categories" else k for k in PUBLIC_FIELDS]
        for values in conn.execute("SELECT " + ",".join(columns) + " FROM daily_machine_records WHERE publication_state='released'"):
            r = dict(zip(PUBLIC_FIELDS, values))
            family = r["source_family"]
            if family not in REFS:
                continue
            p = policy["sources"][family]
            if r["source_identity"] in p["excluded_source_identities"]:
                continue
            if not all(p[k] for k in ("private_model_processing", "public_machine_explanation", "unattended_release")):
                continue
            r["categories"] = json.loads(r["categories"])
            r["model_flagged"] = bool(r["model_flagged"])
            validate_output(r, family, p)
            link = conn.execute("SELECT canonical_official_url,publisher_posted_date,"
                "metadata_version_sha256,official_publisher FROM regional_official_source_links "
                "WHERE source_family=? AND source_identity=?", (family, r["source_identity"])).fetchone()
            if not link or link[2] != r["metadata_version_sha256"]:
                continue
            if family == "ph_nsc_official_statements":
                from core.ph_nsc_official_link_admission import load_policy as nsc_policy
                if not nsc_policy()["category_anomaly_resolved"]:
                    continue
            label = "AFP" if family == "ph_afp_articles" else "NSC"
            path = "record/source-" + hashlib.sha256((family + ":" + r["source_identity"]).encode()).hexdigest()[:24] + ".html"
            result.append({**r, "record_path": path, "source_label": label,
                           "url": link[0], "published_date": link[1],
                           "publisher": ("Armed Forces of the Philippines" if label == "AFP" else "National Security Council"),
                           "issuer": ("Armed Forces of the Philippines" if label == "AFP" else None), "desk_id": "philippines",
                           "machine_only": True})
    return sorted(result, key=lambda r: (r["published_date"], r["source_identity"]), reverse=True)


def archive_rows(records):
    from core.archive_research import projection, ORIGIN
    for r in records:
        yield projection(id="machine:" + r["source_identity"],
            title=r["source_label"] + " official source — machine explanation",
            summary=r["summary"], date=r["published_date"], date_kind="source-stated publication",
            desks=["philippines"], source=r["source_label"], issuer=r["publisher"],
            record_type="machine_explanation", processing="Machine-generated; not human-reviewed. Official account, not independent verification.",
            ipr_url=ORIGIN + "/" + r["record_path"], source_url=r["url"],
            citation="Indo-Pacific Record machine explanation of " + r["source_identity"] + ". " + r["url"])


def editorial_candidates(db_path, start, cutoff, *, limit=2):
    """Existing Sunday supplemental contract, machine-labeled, no originals.

    These are leads for human source verification, never a human source review
    receipt or an automatically approved Brief citation.
    """
    if limit <= 0:
        return []
    limit = min(2, limit)
    result = []
    for r in load(db_path):
        if not start <= r["published_date"] <= cutoff:
            continue
        ident = "PH-DAILY-" + r["source_label"] + "-" + r["content_sha256"][:24]
        result.append(dict(id=ident, desk="philippines", source_name=r["source_label"],
            source_url=r["url"], published_date=r["published_date"], language="en",
            title_original="", source_kind="published-machine-explanation",
            state_commit=r["source_git_commit"], source_content_sha256=r["content_sha256"],
            hash_rule="sha256-utf8-original-body", summary=r["summary"],
            caveats=["Machine-generated reading; verify the official original before human Brief approval.",
                     "An institutional account is not independent validation of events."],
            topics=r["categories"], status="unapproved-source-linked-editorial-candidate",
            copy_scope="private-model-drafting-only-no-source-body"))
        if len(result) >= limit:
            break
    return result
