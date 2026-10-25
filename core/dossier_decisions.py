"""Independently recorded owner decisions for Living Dossier publication.

Same trust boundary as DECISION_LOG and the reviewed publication registries:
only an authorized maintainer records actual owner instructions in reviewed
source. Manuscripts, CLI arguments and publisher metadata cannot add entries.
The Maritime revision 2 editorial approval was reaffirmed by Benjamin Yang on
25 October 2026; its actual receipt is recorded below. Source-use authority
remains a separate decision and is not inferred from editorial approval.

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

SOURCE_USES = {}
PUBLICATIONS = {
    "maritime-cooperation-2026": {
        "content_sha256": "5b23f8a1215985e4bd6449dbd27d89ba7edf35caffca56d308b46a90444bab6f",
        "approval": {
            "approved_by": "Benjamin Yang",
            "approved_on": "2026-10-25",
            "reference": "DECISION_LOG.md#2026-10-25--owner-maritime-dossier-revision-2-editorial-approval-reaffirmed",
            "content_sha256": "5b23f8a1215985e4bd6449dbd27d89ba7edf35caffca56d308b46a90444bab6f",
        },
    },
}
