# Briefs: owner-assigned authorship and contribution credits

This is an optional, per-issue field in the existing `briefs/<slug>.json` sidecar.
The Founder & Executive Director decides credits for each Brief **before final
editorial review and approval**, not through an automated roster or staff title.

```json
"editorial_credits": {
  "authors": ["Benjamin Yang", "Peter Nguyen"],
  "research_and_analysis": ["Dylan Tanzi"],
  "editing": ["Jophy Lin"]
}
```

`authors` is required when the field is present, and its first name must
exactly match the existing `author_name` field. The other two arrays may be
omitted or empty. Each list contains names, not team roles. Use one credit per
person per issue; the validator refuses duplicated names across categories,
unknown credit roles, empty authors, and mixing this new scheme with the
older `research_contributor` field.

**Author(s)** means substantive responsibility for the article's writing or
central intellectual argument. **Research & Analysis** recognizes material
original-source investigation, findings or comparisons without authorship.
**Editing** recognizes substantive editorial improvements; routine proofreading
does not automatically justify named credit. Identity, background and role
titles do not automatically determine assignment. AI tools are not named human
contributors. Unused categories do not render.

The article displays a primary “By” line and, only when assigned, the two small
secondary credits. Its catalogue byline, citation and Atom author metadata
contain **authors only**. Site links use an existing contributor/team profile
when available; otherwise names remain plain text. The older
`research_contributor` presentation and all historically approved sidecars
remain unchanged until independently authorized.

A credit change to a source-linked Brief alters the existing exact-version
fingerprint. Refresh human editorial review and owner policy ruling against the
final sidecar before approval; neither the new field nor rendering constitutes
approval. No form, weekly scheduler, new workflow or automated credit selection
is introduced.
