"""Read only permitted shared machine explanations, without source originals."""
import hashlib
import json

from scripts.reconcile_db import read_only
from core.daily_sources import source_for
from processing.daily_intake import digest, load_policy, validate_output


def _released_visibility_policy(family, policy):
    """Permitted presentation policy for a previously *released* machine Record.

    Singapore's first one-item pilot can stop new model attempts and unattended
    admission while retaining separately authorized public display. The row
    must still carry the hash of the EXACT full-release policy: normalize only
    those two stopped switches and change no owner decision, source exclusion,
    or limit. Any other policy drift fails the usual digest validation.

    Public explanation permission is always an explicit visibility gate;
    source integrity, parent holds, and per-identity exclusions still apply.
    Other desks retain their existing all-three-switch contract.
    """
    if not policy["public_machine_explanation"]:
        return None
    if policy["private_model_processing"] and policy["unattended_release"]:
        return policy
    if (family == "sg_mindef_releases"
            and not policy["private_model_processing"]
            and not policy["unattended_release"]):
        return {**policy, "private_model_processing": True,
                "unattended_release": True}
    return None


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
            source = source_for(family)
            if source is None:
                continue
            p = policy["sources"][family]
            if r["source_identity"] in p["excluded_source_identities"]:
                continue
            display_policy = _released_visibility_policy(family, p)
            if display_policy is None:
                continue
            if (family == "sg_mindef_releases" and display_policy is not p
                    and r["policy_sha256"] != digest(display_policy)):
                # A policy change outside the exact processing-pause transition
                # is a withdrawal from the reader, never a site-render crash.
                continue
            r["categories"] = json.loads(r["categories"])
            r["model_flagged"] = bool(r["model_flagged"])
            validate_output(r, family, display_policy, released=True)  # published record: historical pairs stay readable
            if source.parent:
                # Source-owned parent (DAPA: Korea official link); same version
                # by candidate, text and page hashes, else the record is withheld.
                parent = source.parent_link(conn, r["source_identity"])
                link = parent and (parent["canonical_official_url"], parent["publisher_posted_date"],
                                   parent["metadata_version_sha256"])
                if not parent or any(parent[k] != r[k] for k in ("content_sha256", "capture_sha256")):
                    continue
            else:
                link = conn.execute("SELECT canonical_official_url,publisher_posted_date,"
                    "metadata_version_sha256,official_publisher FROM regional_official_source_links "
                    "WHERE source_family=? AND source_identity=?", (family, r["source_identity"])).fetchone()
            if not link or link[2] != r["metadata_version_sha256"]:
                continue
            if source.release_hold():
                continue
            path = "record/source-" + hashlib.sha256((family + ":" + r["source_identity"]).encode()).hexdigest()[:24] + ".html"
            result.append({**r, "record_path": path, "source_label": source.label,
                           "url": link[0], "published_date": link[1],
                           "publisher": source.publisher,
                           "issuer": source.public_issuer, "desk_id": source.desk_id,
                           "machine_only": True})
    return sorted(result, key=lambda r: (r["published_date"], r["source_identity"]), reverse=True)


def archive_rows(records):
    from core.archive_research import projection, ORIGIN
    for r in records:
        yield projection(id="machine:" + r["source_identity"],
            title=r["source_label"] + " official source — machine explanation",
            summary=r["summary"], date=r["published_date"], date_kind="source-stated publication",
            desks=[r["desk_id"]], source=r["source_label"], issuer=r["publisher"],
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
        if r["desk_id"] != "philippines" or not start <= r["published_date"] <= cutoff:
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
