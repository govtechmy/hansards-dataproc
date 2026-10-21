Author source maintenance
=========================

Preview the one-time Tunku and Lipis author data migration:

```sh
env/bin/python scripts/author_active_years/20261020_correct_author_sources.py --bucket my.gov.parlimen.hsd-dataproc-bucket-dev --profile shared-services --env-file .env
```

Add `--apply` to update the S3 author master, regenerate the seed, and upsert
only authors 1 and 21690 into the selected DB. Rerunning is safe. For production,
use the production bucket/profile and `.env.prod` explicitly. An occupied or
unexpected author identity stops the script for review.

Rebuild derived speaking dates
-----------------------------

Preview using existing speech CSVs and raw extracted text:

```sh
env/bin/python -u scripts/author_active_years/derive_author_active_dates.py \
  --bucket my.gov.parlimen.hsd-dataproc-bucket-dev \
  --speech-bucket my.gov.parlimen.hsd-download-bucket-dev \
  --textract-bucket my.gov.parlimen.hsd-textract-bucket-dev \
  --profile shared-services --env-file .env \
  --report /private/tmp/author-ranges-preview.json
```

Document reads run in parallel (eight workers by default). Use `--workers 1`
for a serial scan, or another value up to 16. Identity and validation rules are
the same in either mode.

Optionally add `--author-ids 1216 1111` to limit the audited authors. All available
sittings inside their existing derived periods are still checked. An author
filter does not reduce document coverage. The unmatched-speaker export is no
longer the input: it misses speakers already matched by the pipeline.

The script inventories saved speech CSVs, OCR layouts, parsed plaintext and DB
sittings. Filename dates are authoritative. OCR header differences are report
warnings only. It reads existing text and never performs OCR or updates the DB.
KKDR committee documents are excluded from this DR/DN inventory; their filenames
are never interpreted as DR sittings.

`derived_years_mentioned` means first and last **confirmed speaking appearances
in the saved data within the original period**. It does not certify a person's
whole career or the absence of earlier unidentified speeches.

For each existing derived history period:

- Reuse `get_author_and_speech` for modern plaintext and `split_speaker` for
  legacy OCR blocks. These are the detectors used by the sitting jobs. Saved
  CSV labels still require independent source-prefix verification; unknown
  boundaries never authorize inheriting the previous speaker.
- Check complete speaker prefixes against raw text, including reconstructed
  split legacy labels. Attendance lists and mentions are not speaking evidence.
- Source-confirmed headings and written question rows do not count as individual
  speaker appearances. Recover a blank/incorrect CSV speaker only when the entire
  row matches a raw-text span with explicit, unambiguous speaker context. CSV row
  order alone is never used. Unknown turns, section/roster boundaries, repeated
  text under different speakers and unmatched text are never assigned an identity.
- Resolve labels through the sitting jobs' shared `perform_author_matching`.
  Deriving history excludes both derived-history statuses from temporal evidence.
  Name and position matching are enabled; constituency fallback is disabled
  because incomplete place data must not select an identity for this rebuild.
  MOHD expansions require the
  entire remaining name to agree. Strip bracketed seat descriptors from personal
  labels, while retaining a person named inside a role label such as Minister [Name].
  Constituency data is never used to select an identity. If a name omits trailing
  tokens or has multiple canonical owners, use independently recorded service
  history covering the filename date to resolve it. Short names require at least
  two normalized tokens anchored at the beginning of the person's name; a father's
  name inside his son's name is not an alias for the son. Derived and unverified
  derived periods cannot support this decision. Overlapping independent matches
  remain ambiguous. The report records supporting history IDs.
  All recorded positions can supply service evidence, including positions before
  becoming PM. A missing service record does not veto an otherwise unambiguous
  exact full-name match. This bootstrap exception establishes missing history;
  a contradictory shared-matcher result remains ambiguous. Approximate name
  matching otherwise uses the pipeline's thresholds and independent date checks.
  Shared name words alone never assign identity.
  Office matching requires a normalized exact registered title and a unique
  holder at the sitting date. It never substitutes a PM for a different ministry,
  a deputy for a minister, or an office holder for an unresolved named person.
- Calculate the earliest/latest verified appearances in the audited period.
- Replace the old bounds when every inventoried sitting in that period was
  checked, its sources were available, and at least one appearance was confirmed.
  Unidentified or ambiguous turns are reported in `identity_issues`; they do not
  count as appearances or prevent using confirmed appearances.
- If no appearance is confirmed, retain the period unchanged for review. Missing
  evidence never automatically deletes, quarantines or proves inactivity.
  Missing sources and incomplete scans still prevent corrections.

`derived_scope_start` and `derived_scope_end` in the master preserve the original
audit window. Rerunning after narrowing a range still checks the same period,
including dates previously rejected. Separate derived periods retain their IDs;
researched roles and non-derived histories are untouched. This audits existing
periods, not previously unknown service outside those periods. Coverage means
all known processed S3/DB documents, not a claim that all historical Hansards
have been digitised or processed.

The JSON report contains the inventory/ETags, evidence locations, old/proposed
ranges and reasons a change is blocked. `--documents dr_1976-04-05 ...` is a
partial diagnostic preview: it cannot apply **any** corrections.

After reviewing a full preview, add `--apply` to write eligible corrections to
`canonical/master/author_history.csv` only. It rechecks inventory/author versions
and uses a conditional history-master write. Blocked rows remain unchanged.
Prepare the author-history seed and load it through the normal pipeline, then
rerun affected sittings for speech rematching. No direct DB speech-link updates.

Deploy the generic unverified-status handling alongside this script before
loading corrected histories. Unchanged source inputs produce unchanged ranges
on subsequent runs. For production, explicitly supply production buckets and
`.env.prod`; the dev command above never selects production automatically.

`20261020_restore_ambiguous_history_extensions.py` is the one-time correction
restoring histories 3181 and 3212 to the September dump's bounds after their
extensions were found ambiguous. It accepts the same explicit bucket/profile/env
arguments, previews by default, and requires `--apply` to write S3 and DB.

Speech rematching is handled by rerunning the sitting pipeline after correcting
the source data and matching code. Do not update speech links directly in the DB.

