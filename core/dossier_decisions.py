"""Independently recorded owner decisions for Living Dossier publication.

Same trust boundary as DECISION_LOG and the reviewed publication registries:
only an authorized maintainer records actual owner instructions in reviewed
source. Manuscripts, CLI arguments and publisher metadata cannot add entries.
The Maritime revision 2 editorial approval was reaffirmed by Benjamin Yang on
25 October 2026; its actual receipt is recorded below. On the same date he
separately approved the narrow five-source public projection recorded here.

SOURCE_USES maps a real decision reference to {record_id: source_binding}.
source_binding is the complete dossier source identity (including body SHA),
plus `public_fields`: a sorted list drawn from dossiers.PUBLIC_FIELDS.
It authorizes only that projection; never original text, titles or translations.
PUBLICATIONS maps slug to {content_sha256, approval}: exact dossier digest and
exact human editorial approval object. Its reference must record actual approval
of the dossier and rendered review; SOURCE_USES independently records the listed
public source uses. Both gates must pass before publication. A hash alone is
integrity, not authority. Add no entry without the corresponding human instruction.
No runtime/environment/file override or synthetic-fixture switch exists.
"""

SOURCE_USES = {
    "DECISION_LOG.md#2026-10-25--owner-maritime-dossier-narrow-five-source-public-projection": {
        3924: {
            "record_id": 3924,
            "desk": "china",
            "source_id": "pla_daily",
            "institution_id": "cn_cmc_political_work",
            "language": "zh-Hans",
            "published_on": "2026-09-06",
            "url": "http://www.81.cn/yw_208727/16483866.html",
            "stored_original_sha256": "b7a6ef0bc4c7c6e63132144ba50577c28f0ec42f7fbf7b4574d22f166d63d7e8",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4102: {
            "record_id": 4102,
            "desk": "china",
            "source_id": "pla_daily",
            "institution_id": "cn_cmc_political_work",
            "language": "zh-Hans",
            "published_on": "2026-09-12",
            "url": "http://www.81.cn/yw_208727/16485244.html",
            "stored_original_sha256": "3b3f2b09fcf6150d570258de6381d8ae9d9dcb8fbb725f2ded912465572b9886",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4164: {
            "record_id": 4164,
            "desk": "china",
            "source_id": "mod_china",
            "institution_id": "cn_mnd",
            "language": "zh-Hans",
            "published_on": "2026-09-14",
            "url": "http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16486365.html",
            "stored_original_sha256": "756ab518a72e86c3c60a20462f22bbc1652d788a0bee3a1fe0b7fccc1a807cac",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4466: {
            "record_id": 4466,
            "desk": "singapore",
            "source_id": "sg_mindef_releases",
            "institution_id": "sg_mindef",
            "language": "en",
            "published_on": "2026-09-05",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/5sep26-nr2/",
            "stored_original_sha256": "ef18634fd29ff57894eb35d35339cd60bf6b1d2339fe6038875bc7b5bea49878",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4472: {
            "record_id": 4472,
            "desk": "singapore",
            "source_id": "sg_mindef_releases",
            "institution_id": "sg_mindef",
            "language": "en",
            "published_on": "2026-09-09",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/9sep26-nr/",
            "stored_original_sha256": "0e4d1a580c8267e9f2b486f742c17e95551761943cac53013fa4f292dc87d078",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
    },
}
PUBLICATIONS = {
    "maritime-cooperation-2026": {
        "content_sha256": "3f774c00ec432fa64fe0a19695e3d4dde3c6b34704264bc752a268a7aa4e7039",
        "approval": {
            "approved_by": "Benjamin Yang",
            "approved_on": "2026-10-25",
            "reference": "DECISION_LOG.md#2026-10-25--owner-maritime-dossier-revision-2-editorial-approval-reaffirmed",
            "content_sha256": "3f774c00ec432fa64fe0a19695e3d4dde3c6b34704264bc752a268a7aa4e7039"
        }
    }
}
