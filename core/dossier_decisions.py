"""Independently recorded owner decisions for Living Dossier publication.

Same trust boundary as DECISION_LOG and the reviewed publication registries:
only an authorized maintainer records actual owner instructions in reviewed
source. Manuscripts, CLI arguments and publisher metadata cannot add entries.
The Maritime revision 2 editorial approval was reaffirmed by Benjamin Yang on
25 October 2026; its actual receipt is recorded below. On the same date he
separately approved the narrow five-source public projection recorded here.
On 26 October 2026 he approved the China–Singapore Naval Cooperation manuscript
at its reviewed draft digest, extended the Maritime grant to that dossier for
its five shared records, and approved its eight other records and nine linked
official pages (x1–x9) for the same narrow projection.

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
    # China–Singapore Naval Cooperation only. 3924, 4102, 4164, 4466 and 4472 extend
    # the Maritime grant to this dossier; x1–x9 are linked official pages, not records.
    "DECISION_LOG.md#2026-10-26--owner-china-singapore-naval-dossier-source-use": {
        3513: {
            "record_id": 3513,
            "desk": "china",
            "source_id": "pla_daily",
            "institution_id": "cn_cmc_political_work",
            "language": "zh-Hans",
            "published_on": "2026-08-25",
            "url": "http://www.81.cn/yw_208727/16481117.html",
            "stored_original_sha256": "fcab651032fe0808adbd0f9b6c9a37c97f7154456ac3379211c6cdef5452cfd1",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        3663: {
            "record_id": 3663,
            "desk": "china",
            "source_id": "pla_daily",
            "institution_id": "cn_cmc_political_work",
            "language": "zh-Hans",
            "published_on": "2026-08-29",
            "url": "http://www.81.cn/yw_208727/16482081.html",
            "stored_original_sha256": "12a4174ad7b0b591b6541702fecb140d37a7719999d20f197f680c0ecba3d744",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
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
        4211: {
            "record_id": 4211,
            "desk": "china",
            "source_id": "pla_daily",
            "institution_id": "cn_cmc_political_work",
            "language": "zh-Hans",
            "published_on": "2026-09-16",
            "url": "http://www.81.cn/yw_208727/16486847.html",
            "stored_original_sha256": "48591c5d3cbce1d4640b6d7d140e14fc63d97a70727989de4cb6afe09847ea47",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4452: {
            "record_id": 4452,
            "desk": "singapore",
            "source_id": "sg_mindef_releases",
            "institution_id": "sg_mindef",
            "language": "en",
            "published_on": "2026-08-29",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/29aug26-nr/",
            "stored_original_sha256": "3f84c0d0c26a900f34b068c4c5f29967fd2864ea41821051323b180e24a15b02",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4454: {
            "record_id": 4454,
            "desk": "singapore",
            "source_id": "sg_mindef_releases",
            "institution_id": "sg_mindef",
            "language": "en",
            "published_on": "2026-07-30",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/30jul26-nr2/",
            "stored_original_sha256": "e7ba778857ecf0fea62e95a7920864650a138227f07f1ae4c52b4edb0d7a8bab",
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
        4849: {
            "record_id": 4849,
            "desk": "singapore",
            "source_id": "sg_mindef_releases",
            "institution_id": "sg_mindef",
            "language": "en",
            "published_on": "2026-10-02",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/2oct26-nr3/",
            "stored_original_sha256": "ced43fd969de5301f2297ec64867b7a2a88e2870b071d743a540ac1e1cb2ef77",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        4911: {
            "record_id": 4911,
            "desk": "singapore",
            "source_id": "sg_mindef_releases",
            "institution_id": "sg_mindef",
            "language": "en",
            "published_on": "2026-10-05",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/05oct26-mq/",
            "stored_original_sha256": "f908abdc4d4759510a5188e970849f3407d9997d12d5ffc3e4bf2ad80139e251",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        5528: {
            "record_id": 5528,
            "desk": "china",
            "source_id": "pla_daily",
            "institution_id": "cn_cmc_political_work",
            "language": "zh-Hans",
            "published_on": "2026-10-23",
            "url": "http://www.81.cn/yw_208727/16495552.html",
            "stored_original_sha256": "147af76b2a9570dcaa07ab2e86bf9da03cb9d7921ab8375482f58d21a76c4170",
            "editorial_admission_ref": "archive:passed_relevance=1",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link",
                "record_link"
            ]
        },
        "x1": {
            "id": "x1",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2015-05-25",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/2015may25-news-releases-02118/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x2": {
            "id": "x2",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2023-04-28",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/28apr23_nr/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x3": {
            "id": "x3",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2024-08-29",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/29aug24_nr/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x4": {
            "id": "x4",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2025-05-09",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/9may25_nr1/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x5": {
            "id": "x5",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2019-10-20",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/20oct19_fs/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x6": {
            "id": "x6",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2023-05-08",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/08may23_pq/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x7": {
            "id": "x7",
            "institution_id": "sg_mindef",
            "publisher": "Singapore Ministry of Defence",
            "language": "en",
            "published_on": "2019-05-29",
            "url": "https://www.mindef.gov.sg/news-and-events/latest-releases/29may19_nr/",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x8": {
            "id": "x8",
            "institution_id": "cn_mnd",
            "publisher": "China Ministry of National Defense",
            "language": "zh-Hans",
            "published_on": "2024-08-29",
            "url": "http://www.mod.gov.cn/gfbw/jsxd/16334500.html",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
            ]
        },
        "x9": {
            "id": "x9",
            "institution_id": "cn_mnd",
            "publisher": "China Ministry of National Defense",
            "language": "zh-Hans",
            "published_on": "2024-09-01",
            "url": "http://www.mod.gov.cn/gfbw/jsxd/ly/16335054.html",
            "retrieved_on": "2026-10-26",
            "public_fields": [
                "attribution",
                "ipr_paraphrase",
                "publication_date",
                "publisher_link"
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
,
    "china-singapore-naval-cooperation": {
        "content_sha256": "9e9471553354ecfb441c387dc12dc958658d10c8b5db04fb060b39d281462a1a",
        "approval": {
            "approved_by": "Benjamin Yang",
            "approved_on": "2026-10-26",
            "reference": "DECISION_LOG.md#2026-10-26--owner-china-singapore-naval-dossier-editorial-approval",
            "content_sha256": "9e9471553354ecfb441c387dc12dc958658d10c8b5db04fb060b39d281462a1a"
        }
    }
}
