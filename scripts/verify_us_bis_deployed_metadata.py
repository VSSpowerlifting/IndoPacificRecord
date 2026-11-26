"""Independently validate three BIS U.S. Desk surfaces: SQLite, Pages Git, CDN.

The workflow caller fetches the production DB, exact gh-pages Git file and
public HTTP response. No writes, no network requests from this module and no
source-body article count changes. Synthetic inputs cannot prove deployment.

The desk lists only the newest GROUP_LINK_LIMITS BIS rows; every admitted BIS
row must also appear exactly once on the U.S. full-index month pages, which
must be byte-identical in the main checkout and the gh-pages checkout. Without
those two site directories, a readback whose rows exceed the desk bound holds.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
from core import official_link_index as link_index
from core.us_bis_authenticated_metadata import load_public_links

DESK="us-indopacific"


class BISReadbackHold(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise BISReadbackHold(reason)


def read_bounded(path, cap=1_000_000):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size <= cap,"invalid_page_file")
    return path.read_bytes()


def desk_rows(rows):
    """The BIS rows the desk page lists: the newest GROUP_LINK_LIMITS."""
    try:
        return link_index.group_latest(DESK,rows)
    except link_index.IndexHold:
        raise BISReadbackHold("bis_rows_not_indexable_by_official_date") from None


def check_refs(refs, expected):
    require(len(refs)==len(expected),"bis_reference_count_wrong")
    for li,row in zip(refs,expected):
        anchor=li.select_one("a[href]")
        timetag=li.select_one("time[datetime]")
        require(anchor is not None and timetag is not None,
                "bis_link_or_date_missing")
        require(len(li.select("a[href]"))==1 and len(li.select("time"))==1,
                "bis_row_has_extra_link_or_date")
        require(li.get("data-us-bis-official-link")==row["source_identity"] and
                anchor["href"]==row["source_url"] and
                anchor.get_text(" ",strip=True)==row["neutral_label"] and
                timetag["datetime"]==row["published_date"] and
                timetag.get_text(" ",strip=True)==row["published_date"],
                "bis_official_reference_disagrees")
        require(anchor.get("target")=="_blank" and
                "noopener" in anchor.get("rel",[]) and
                "noreferrer" in anchor.get("rel",[]),"bis_link_not_safe")
    return len(refs)


def month_pages(site):
    folder=Path(site)/link_index.month_dir(DESK)
    require(folder.is_dir() and not folder.is_symlink(),
            "us_official_link_month_folder_missing")
    pages=sorted(folder.iterdir())
    require(pages and all(p.is_file() and not p.is_symlink() for p in pages),
            "us_official_link_month_folder_invalid")
    return {p.name:p for p in pages}


def verified_index(rows, main_site, pages_site):
    """Every BIS row, hidden from the desk or not, is on its month page once.

    Month pages are compared byte for byte between main and gh-pages; a month
    page without BIS rows must carry none.
    """
    try:
        months=dict(link_index.partition(DESK,rows))
    except link_index.IndexHold:
        raise BISReadbackHold("bis_rows_not_indexable_by_official_date") from None
    main=month_pages(main_site)
    pages=month_pages(pages_site)
    require(sorted(main)==sorted(pages),"github_pages_month_inventory_differs")
    require({m+".html" for m in months}<=set(main),"bis_month_page_missing")
    found=0
    for name,path in main.items():
        raw=read_bounded(path)
        require(raw==read_bounded(pages[name]),"github_pages_month_page_differs")
        try:
            html=raw.decode("utf-8")
        except UnicodeError:
            raise BISReadbackHold("page_not_utf8") from None
        require(all(x not in html for x in (
            "title_original","text_original","body_original")),
            "original_publisher_text_detected")
        refs=BeautifulSoup(html,"html.parser").select("li[data-us-bis-official-link]")
        found+=check_refs(refs,months.get(name[:-len(".html")],[]))
    require(found==len(rows),"bis_full_index_count_wrong")
    return found


def verified_html(raw, expected):
    try:
        html=raw.decode("utf-8")
    except UnicodeError:
        raise BISReadbackHold("page_not_utf8") from None
    soup=BeautifulSoup(html,"html.parser")
    refs=soup.select("li[data-us-bis-official-link]")
    check_refs(refs,desk_rows(expected))
    for selector,count in (

            ("li[data-us-pacom-link] a",9),
            ("li[data-uscc-official-link] a",10),
            ("li[data-us-treasury-official-link] a",10)):
        found=len(soup.select(selector))
        require(found==count if count==9 else found>=count,
                "other_us_reference_missing")
    require("PACOM remains access-blocked" in html and "DVIDS paused" in html,
            "existing_us_source_limitations_missing")
    require(all(x not in html for x in (
        "title_original","text_original","body_original")),
        "original_publisher_text_detected")
    return len(refs)


def verify(db_path, main_page, pages_page, deployed_page, *,
           main_site=None, pages_site=None):
    rows=load_public_links(db_path)
    require(rows,"no_authenticated_bis_live_metadata")
    main=read_bounded(main_page)
    gitpages=read_bounded(pages_page)
    http=read_bounded(deployed_page)
    require(main==gitpages,"github_pages_differs_from_main_us_desk")
    require(http==gitpages,"public_cdn_does_not_match_gh_pages")
    count=verified_html(main,rows)
    require((main_site is None)==(pages_site is None),
            "bis_full_index_readback_needs_both_site_directories")
    indexed=None
    if main_site is not None:
        indexed=verified_index(rows,main_site,pages_site)
    else:
        require(count==len(rows),"hidden_bis_rows_need_full_index_readback")
    return {
        "status":"PASS_BIS_INDEPENDENT_DEPLOYED_READBACK",
        "records":len(rows),
        "desk_records":count,
        "full_index_records":indexed,
        "us_desk_sha256":hashlib.sha256(main).hexdigest(),
        "main_matches_pages_git":True,
        "pages_git_matches_public_http":True,
        "original_bis_text_rehosted":False,
        "complete_bis_publisher_history_claimed":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--production-db",required=True)
    parser.add_argument("--main-page",required=True)
    parser.add_argument("--pages-git-file",required=True)
    parser.add_argument("--public-http-file",required=True)
    parser.add_argument("--main-site-dir",
                        help="Main checkout site directory holding the full index")
    parser.add_argument("--pages-site-dir",
                        help="gh-pages checkout holding the deployed full index")
    args=parser.parse_args(argv)
    try:
        report=verify(args.production_db,args.main_page,
                      args.pages_git_file,args.public_http_file,
                      main_site=args.main_site_dir,pages_site=args.pages_site_dir)
    except (BISReadbackHold,ValueError,OSError) as exc:
        print(json.dumps({"status":"HOLD_BIS_DEPLOYED_READBACK",
                          "reason":str(exc)},sort_keys=True))
        return 2
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
