"""Independently recorded owner decisions for Living Dossier publication.

Same trust boundary as DECISION_LOG and the reviewed publication registries:
only an authorized maintainer records actual owner instructions in reviewed
source. Manuscripts, CLI arguments and publisher metadata cannot add entries.
No decision for the Maritime dossier has been supplied. Empty is intentional.

SOURCE_USES maps a real decision reference to {record_id: source_binding}.
source_binding is the complete dossier source identity (including body SHA),
plus `public_fields`: a sorted list drawn from dossiers.PUBLIC_FIELDS.
It authorizes only that projection; never original text, titles or translations.
PUBLICATIONS maps slug to {content_sha256, approval}: exact dossier digest and
exact human approval object. The referenced owner message must explicitly
approve the dossier, rendered review and listed source uses. A hash alone is
integrity, not authority. Add no entry without that external human instruction.
No runtime/environment/file override or synthetic-fixture switch exists.
"""

SOURCE_USES = {}
PUBLICATIONS = {}
