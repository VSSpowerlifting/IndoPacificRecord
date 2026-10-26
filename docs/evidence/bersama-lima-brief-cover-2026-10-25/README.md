# Staged Bersama Lima Brief cover (context image)

**Disposition:** staged. After the preview and 720 × 480 crop (focal `68% 70%`) were
shown, the owner's October 25, 2026 instruction referred to the "approved HMS Tamar
context cover"; the DECISION_LOG entry is recorded at release approval. The earlier
"Proceed and then publish" direction alone did not accept an unseen cover. The
paired catalogue admission awaits the existing issue-numbering step. No
publication, issue assignment, merge or deployment is asserted here.

## Source and editorial fit

- Publisher: [DVIDS, photo 7379876](https://www.dvidshub.net/image/7379876/hms-tamar-p233-sails-into-puerto-princesa-pacific-partnership-2022),
  *HMS Tamar (P233) sails into Puerto Princesa, Pacific Partnership 2022*.
- VIRIN: `220811-N-AU520-1096`. Photographer: Mass Communication Specialist
  2nd Class Jacob Woitzel, U.S. Navy. Date taken: August 11, 2022.
- The photograph shows the Royal Navy patrol ship HMS Tamar at Puerto Princesa,
  Philippines, during Pacific Partnership 2022. It is **context** for the Brief's
  subject (Tamar's 2026 role), **not** an image of Exercise Bersama Lima 2026 or
  of any 2026 activity. The caption and `date_note` say so on the page.

## Retrieval and its limit

The retained file is the publisher's publicly served `2000w_q95.jpg` preview,
**2000 × 1331 pixels**, not the advertised full-resolution master. The master
download link required a DVIDS sign-in and an anonymous request returned
HTTP 403; it was not retried, and no authentication, session or user-agent
spoofing was attempted (see `cdn-response-headers.txt` for the successful
preview response). The CDN `robots.txt` returned 404, i.e. no explicit refusal;
the main `dvidshub.net/robots.txt` returned HTTP 502 twice and could not be
read. Requests used an identifying IPR review agent. The exact URL, time, HTTP
status, ETag, byte count and SHA-256 are in `retrieval.json`. Retained source
digest: `a04b7b7a50aa80fd795e4b8bdc3b427acc7512796f7227418192a870f48b939d`.

## Reuse review

The DVIDS page marks the photograph **PUBLIC DOMAIN** and credits an
official-duty U.S. Navy photographer. DVIDS's [copyright notice](https://www.dvidshub.net/about/copyright)
(read October 25–26, 2026) separates official-duty government work from
third-party material and permits historical/newsworthy use subject to its
non-endorsement and other stated restrictions. The existing exact DVIDS
non-endorsement notice in `core/source_terms.py` is carried on the image. This
use is limited to editorial publication, not IPR advertising, fundraising or any
endorsement. Government origin is not used to license unrelated photographs.

## Treatment and remaining action

Unaltered source bytes are in `site/assets/editorial/hms-tamar-puerto-princesa-2022.jpg`.
Article derivatives come from `scripts/build_brief_cover.py`; the IPR gradient
is CSS only, with no retouching, upscaling or colour edits. The proposed focal
point for the 3:2 catalogue crop is `68% 70%` (hull and bridge); that crop and
the article rendering are for the owner to inspect.

Remaining, in order: (1) DECISION_LOG entry for the accepted cover;
(2) the numbering command assigns the issue; (3) add the paired catalogue
admission for that number, set `surfaces` to article + catalogue, and run
`build_catalogue_media.py --write` and `--check`; (4) the pair, hash and credit
checks. Do not declare this article-only staging a completed paired cover.
