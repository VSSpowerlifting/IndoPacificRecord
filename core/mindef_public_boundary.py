"""MINDEF public-data boundary. Custody and publication are separate decisions.

Only identity/provenance and historical classification survive projection.
Unknown article fields and evidence-bearing auxiliary tables fail closed.
No network, collector, model call or production mutation lives here.
"""
import hashlib
import json
import sqlite3

from core.mindef_permissions import MINDEF_SOURCE_SLUG

RESTRICTED_COLUMNS = (
    "title_original", "text_original", "title_english", "text_english",
    "summary_english", "relevance_reasoning", "significance_reasoning",
)
EXTRA_RESTRICTED = (
    "processing_reason", "title_translation_claim",
    "title_translation_attempt_source",
)
# Reviewed against every table at the migration baseline. A new table requires
# an explicit boundary review, rather than silently inheriting an exemption.
REVIEWED_TABLES = frozenset({
    "articles", "sources", "institutions", "desks", "categories", "article_categories",
    "scrape_runs", "source_run_results", "schema_migrations", "shadow_promotions",
    "retired_article_urls", "daily_machine_records", "korea_corpus_admissions",
    "korea_official_source_records", "vietnam_article_provenance",
    "regional_official_source_links", "official_document_versions",
    "official_document_collection_runs", "bis_authenticated_official_observations",
    "bis_authenticated_official_source_records", "treasury_official_observations",
    "treasury_official_source_records", "uscc_official_observations",
    "uscc_official_source_records", "mindef_private_record_bindings",
})


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def tables(con):
    return [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def restricted_columns(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(articles)")}
    known = set(RESTRICTED_COLUMNS + EXTRA_RESTRICTED) | {
        "id", "url", "content_hash", "source_id", "scrape_run_id",
        "published_date", "scraped_at", "relevance_score", "passed_relevance",
        "analyzed_at", "is_significant", "model_id", "prompt_version",
        "processing_state", "processing_attempts", "processing_first_failed_at",
        "processing_last_failed_at", "title_translation_source_sha256",
        "title_translation_value_sha256", "title_translation_model",
        "title_translation_prompt", "title_translated_at",
        "title_translation_attempts", "title_translation_state",
        "title_translation_claimed_at",
    }
    if cols - known:
        raise ValueError("unreviewed article columns: " + ",".join(sorted(cols - known)))
    return [c for c in RESTRICTED_COLUMNS + EXTRA_RESTRICTED if c in cols]


def table_digests(con, *, exclude_mindef=False):
    """Every table, including tables without a source/record foreign key."""
    out = {}
    for table in tables(con):
        if exclude_mindef and table == "mindef_private_record_bindings":
            continue
        query = "SELECT * FROM " + quote(table)
        args = ()
        if exclude_mindef and table == "articles":
            query += " WHERE source_id NOT IN (SELECT id FROM sources WHERE slug=?)"
            args = (MINDEF_SOURCE_SLUG,)
        records = sorted(json.dumps(list(r), ensure_ascii=False,
                                   separators=(",", ":"), default=str)
                         for r in con.execute(query, args))
        out[table] = hashlib.sha256("\n".join(records).encode()).hexdigest()
    return out


def expression_probes(con):
    """Private byte probes; never serialize or log these values.

    Probe every nonempty field and overlapping 96-character windows for long
    expression. Generic short machine reasons are excluded from byte probes
    because unrelated rows may legitimately contain the identical disposition.
    Logical NULL assertions cover those fields separately.
    """
    fields = restricted_columns(con)
    probes = set()
    reasoning_fields = [c for c in fields if c not in RESTRICTED_COLUMNS[:5]]
    shared_reasoning = b"\0".join(
        v.encode() for row in con.execute(
            "SELECT " + ",".join(map(quote, reasoning_fields)) +
            " FROM articles WHERE source_id NOT IN "
            "(SELECT id FROM sources WHERE slug=?)", (MINDEF_SOURCE_SLUG,))
        for v in row if isinstance(v, str)) if reasoning_fields else b""
    for row in con.execute("SELECT " + ",".join(map(quote, fields)) +
            " FROM articles WHERE source_id IN (SELECT id FROM sources WHERE slug=?)",
            (MINDEF_SOURCE_SLUG,)):
        for name, value in zip(fields, row):
            if not isinstance(value, str) or not value.strip():
                continue
            if len(value) < 24 or (name in reasoning_fields and len(value) < 96):
                continue
            candidates = ([value.encode()] if len(value) <= 96 else
                [value[start:start + 96].encode()
                 for start in range(0, len(value) - 95, 48)])
            # Identical generic machine-disposition fragments on unrelated
            # rows must survive. All MINDEF reasoning cells are still NULL.
            probes.update(p for p in candidates
                          if name not in reasoning_fields or p not in shared_reasoning)
    return probes


def assert_no_expression_bytes(path, probes):
    raw = path.read_bytes()
    if any(probe in raw for probe in probes):
        raise ValueError("restricted expression remains in public bytes; content withheld")


def project(con, *, evidence=None):
    unknown = set(tables(con)) - REVIEWED_TABLES
    if unknown:
        raise ValueError("unreviewed public schema tables: " + ",".join(sorted(unknown)))
    fields = restricted_columns(con)
    con.execute("""CREATE TABLE IF NOT EXISTS mindef_private_record_bindings (
        article_id INTEGER PRIMARY KEY REFERENCES articles(id),
        original_content_hash TEXT NOT NULL,
        original_body_sha256 TEXT NOT NULL,
        original_title_sha256 TEXT NOT NULL
    )""")
    evidence = con if evidence is None else evidence
    for rid, content_hash, body, title in evidence.execute(
            "SELECT id,content_hash,text_original,title_original FROM articles "
            "WHERE source_id IN (SELECT id FROM sources WHERE slug=?)",
            (MINDEF_SOURCE_SLUG,)).fetchall():
        if body is not None or title is not None:
            current = con.execute("SELECT content_hash FROM articles WHERE id=?", (rid,)).fetchone()
            if not current or current[0] != content_hash:
                raise ValueError("private evidence/public identity mismatch")
            con.execute("INSERT INTO mindef_private_record_bindings VALUES (?,?,?,?) "
                "ON CONFLICT(article_id) DO UPDATE SET "
                "original_content_hash=excluded.original_content_hash, "
                "original_body_sha256=excluded.original_body_sha256, "
                "original_title_sha256=excluded.original_title_sha256",
                (rid, content_hash, hashlib.sha256((body or "").encode()).hexdigest(),
                 hashlib.sha256((title or "").encode()).hexdigest()))
    con.execute("UPDATE articles SET " + ",".join(quote(c) + "=NULL" for c in fields) +
                " WHERE source_id IN (SELECT id FROM sources WHERE slug=?)",
                (MINDEF_SOURCE_SLUG,))
    # Enforce at SQLite's write boundary too: stale reconciliation, future DAO
    # paths and raw SQL cannot repopulate expression after migration.
    for event in ("INSERT", "UPDATE"):
        name = "mindef_public_no_expression_" + event.lower()
        con.execute("DROP TRIGGER IF EXISTS " + quote(name))
        con.execute("CREATE TRIGGER " + quote(name) + " BEFORE " + event +
            " ON articles WHEN NEW.source_id IN "
            "(SELECT id FROM sources WHERE slug='sg_mindef_releases') AND (" +
            " OR ".join("NEW." + quote(c) + " IS NOT NULL" for c in fields) +
            ") BEGIN SELECT RAISE(ABORT,'MINDEF public expression withheld'); END")
        if "daily_machine_records" in tables(con):
            name = "mindef_public_no_machine_" + event.lower()
            con.execute("DROP TRIGGER IF EXISTS " + quote(name))
            con.execute("CREATE TRIGGER " + quote(name) + " BEFORE " + event +
                " ON daily_machine_records WHEN NEW.source_family='sg_mindef_releases' "
                "BEGIN SELECT RAISE(ABORT,'MINDEF machine publication held'); END")
    con.execute("""CREATE TRIGGER IF NOT EXISTS mindef_source_identity_no_update
        BEFORE UPDATE OF id,slug ON sources
        WHEN OLD.slug='sg_mindef_releases' AND (NEW.id!=OLD.id OR NEW.slug!=OLD.slug)
        BEGIN SELECT RAISE(ABORT,'MINDEF source identity is preserved'); END""")
    con.execute("""CREATE TRIGGER IF NOT EXISTS mindef_source_identity_no_delete
        BEFORE DELETE ON sources WHEN OLD.slug='sg_mindef_releases'
        BEGIN SELECT RAISE(ABORT,'MINDEF source identity is preserved'); END""")
    con.commit()


def assert_projected(con):
    fields = restricted_columns(con)
    if con.execute("SELECT 1 FROM articles WHERE source_id IN "
            "(SELECT id FROM sources WHERE slug=?) AND (" +
            " OR ".join(quote(c) + " IS NOT NULL" for c in fields) + ") LIMIT 1",
            (MINDEF_SOURCE_SLUG,)).fetchone():
        raise ValueError("restricted MINDEF public fields populated")


def editorial_hold(sidecar):
    """Withhold the whole signed document; never rewrite its references/digest."""
    from core.mindef_permissions import APPROVED_MINDEF_LINKS
    from urllib.parse import urlsplit
    def walk(value):
        if isinstance(value, dict):
            # A corpus citation needs private original/title reconciliation.
            if value.get("source_id") == MINDEF_SOURCE_SLUG or value.get("source_slug") == MINDEF_SOURCE_SLUG:
                return True
            return any(walk(v) for v in value.values())
        if isinstance(value, list):
            return any(walk(v) for v in value)
        if isinstance(value, str):
            if "mindef.gov.sg" not in value.lower():
                return False
            return (urlsplit(value).hostname or "").lower() not in ("mindef.gov.sg", "www.mindef.gov.sg") or value not in APPROVED_MINDEF_LINKS
        return False
    return walk(sidecar)
