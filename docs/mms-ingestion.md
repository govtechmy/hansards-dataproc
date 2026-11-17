# MMS as house 3

MMS keeps its existing parser and intermediate artifact paths. Public downloads
use `majlismengangkatsumpah/`; database/API identity is
`majlis-mengangkat-sumpah` (`house=3`). Parlimen/Penggal comes from the website
hierarchy, not the document date. The database migration is required before
running cycle jobs. Backend/frontend changes are required to serve MMS, but
cycle seeding writes directly to DB and does not require the cycle API.

| Value | Example |
| --- | --- |
| Original/partition filename | `MMS-29092026` |
| Normalized filename | `mms_2026-09-29` |
| Public PDF key | `majlismengangkatsumpah/mms_2026-09-29.pdf` |
| API house | `majlis-mengangkat-sumpah` (`3`) |
| Intermediate artifact directory | `parsed_pdf/dewannegara/MMS-29092026/` |

Intermediate directories include MMS to avoid overwriting DN artifacts on the
same date. Existing DR, DN and KKDR paths remain unchanged.

## Parsing and checks

MMS uses the normal Dagster scrape and sitting jobs. Run the parser checks with:

```sh
PYTHONPATH=hansards_pipelines env/bin/python -m pytest tests/test_mms_support.py tests/test_parse_mms.py tests/test_mms_archive_job.py -q
```

MMS headings and transcript rows use the dedicated `parse_mms.py` module. Ordinary
DR/DN/KKDR tabulation is not used for MMS. Low-level PDF extraction, preprocessing,
speaker recognition and markdown formatting helpers are reused.

Proceedings start at DOA or the timed “Mesyuarat dimulakan pada pukul” opening,
so MMS without DOA or KANDUNGAN can be parsed. Known
ceremony heading openings anchor detection; consecutive uppercase continuation
lines are joined. Uppercase prose such as `KESEDAR.` stays in its speech. The
parser retains section hierarchy, timestamps, physical/printed page ranges and
speaker resumption after annotations. Bracketed stage directions and closing
lines become separate `ANNOTATION` rows, as do oath-taking lists without an
explicit speaker. Colon-ended appointment headings are recognised, wrapped
speaker labels are joined within a physical page, and narrative introductions
are excluded from speaker detection. Standalone `10.07 pg.` / `3.12 ptg.` times
are supported alongside square-marker times. A speaker can continue across a
new speech subheading without repeating their label. The normal draft/final
detector is reused.

Unfamiliar headings and layouts still need review, particularly speaker labels
that cross physical pages or layouts without a recognisable proceedings opening.
Inspect extracted text and headings before bulk ingestion. This parser does not
resolve contradictory source cycle labels.

## Activation

The normal `scrape_website_job` includes the MMS active page alongside DR, DN and
KKDR. No environment toggle is required. Discovered MMS PDFs use the existing
move/queue and sitting pipeline.

For archived MMS, launch the separate Dagster job `scrape_mms_arkib_job` and
select a parliamentary term partition, for example `15`. There is no house
selection: this is an MMS-only job; storage stays under Dewan Negara. After the job succeeds, open the existing
`sittings_job`, select the `MMS-…` partitions listed in the archive asset metadata
and launch them manually. Do not select all DN partitions. No MMS archive sensor
is registered and no sitting runs are launched automatically.

The job scrapes MMS for that term, promotes selected PDFs to their public keys,
and registers the MMS sitting partitions only after promotion completes. All MMS
documents in the selected term are prepared, regardless of year. The ordinary
archive settings `ARKIB_PARTITION_MIN_YEAR` and `ARKIB_PARTITION_MAX_YEAR` do not
apply to MMS. Invalid filenames are skipped with warnings and listed with reasons
in the asset metadata (`skipped_items` and `skipped_count`); valid files continue.
S3 failures and invalid manifest structure still fail the job.
No separate ordinary archive move job is needed.

DN-prefixed files found in the MMS manifest are opened from the isolated raw MMS
storage and checked for `Majlis Mengangkat Sumpah` on PDF page 1. Confirmed files
use MMS partitions/public names while retaining the original raw filename and
scraped Parlimen/Penggal. Saved metadata includes `source_filename` and the PDF
cover verification source. Covers without that title, including unreadable or
empty covers, are skipped with a review warning. S3 read failures fail the job
for retry. This does not reclassify files in the ordinary DN archive flow.

MMS uses isolated storage paths:

- Raw PDFs: dataproc bucket `arkib/majlismengangkatsumpah/pdfs/MMS-DDMMYYYY.pdf`.
- Daily manifests: dataproc bucket `arkib/majlismengangkatsumpah/manifest/YYYY-MM-DD/manifest_term_<term>.json`.
- Current manifests: dataproc bucket `arkib/majlismengangkatsumpah/manifest/latest/manifest_term_<term>.json`.
- Temporary promotion: public bucket `arkib/majlismengangkatsumpah/majlismengangkatsumpah/mms_YYYY-MM-DD.pdf`.
- Final PDFs: public bucket `majlismengangkatsumpah/mms_YYYY-MM-DD.pdf`.

The folder date uses Asia/Kuala_Lumpur; `generated_at` remains a UTC timestamp.
Each scrape writes the dated snapshot first, then the identical `latest` copy.
Same-day reruns replace that day's file for the selected Parlimen; older days
and other Parlimen files are preserved. Archive preparation reads `latest`.
Re-scrape a term to populate the new paths. Legacy raw PDFs and manifests under
`arkib/dewannegara/` are not read or deleted by the new code. Public MMS PDFs/CSVs
use `majlismengangkatsumpah/`; ordinary DN downloads stay under `dewannegara/`.
Intermediate/raw active paths stay unchanged; `get_sitting_object` exposes a
separate `public_house_folder` so parser artifacts do not need relocating.

Raw PDFs remain available for retries. Regular DN archive staging, manifests
and queues are unchanged. The CLI still supports explicit `--category mms`, but the CLI alone
only scrapes; the Dagster job also promotes PDFs and registers partitions.
MMS remains excluded from the default DN/DR/KK archive scrape.

## Cycle seed and document assignment

Both existing `scrape_parliamentary_cycle_active_job` and
`scrape_parliamentary_cycle_arkib_job` now read the MMS hierarchy at
`hansard-majlis.html`. That tree exposes current and historical Parlimen/Penggal;
there is no need to derive membership from a meeting header on the active page.
They insert missing rows directly into the configured database, with this shape:

```json
{"house":3,"term":15,"session":5,"meeting":null,"start_date":null,"end_date":null}
```

The archive cycle job seeds historical MMS rows; both existing weekly cycle
schedules can maintain them. Both jobs use `insert_cycles_to_db` in a transaction
and acquire the same PostgreSQL advisory lock before reading/inserting cycles.
Reruns skip existing `(house, term, session, meeting)` identities, including NULL
meeting for MMS. Existing dates are preserved if portal dates differ. Errors
roll back the batch and fail the job. The MMS partial unique index also protects
against duplicate MMS sessions from other writers. Other writers do not
participate in the jobs' advisory lock unless explicitly implemented.

The MMS document archive scraper includes `term`, `session`, and `source_node`
on every manifest item. Archive preparation persists a per-document assignment
at `metadata/mms/mms_YYYY-MM-DD.json` in the dataproc bucket before registering
partitions. Active PDF discovery uses the hierarchy when the document is listed.
Otherwise it reads PDF pages 1 and 2, preferring the page-1 cover. If the cover
has no complete pair, page 2 can supply it. Disagreements are logged and retained
in `pdf_evidence` with `metadata_conflict=true`; cover values take precedence.
The metadata is saved before queuing, even for already downloaded documents.
The same PDF download is reused for draft/final detection when needed.

`prepare_db_payload` reads that saved metadata and adds `term` and `session` to
the MMS payload. `direct_insert_to_db` resolves exactly one cycle using
`house=3 + term + session`, requiring NULL meeting/dates. Missing assignments,
missing cycles, and duplicate cycle matches fail rather than guessing. Ordinary
DR/DN/KK date lookup is unchanged. Old MMS-as-DN payloads are rejected.

Existing manifests without membership must be re-scraped. Active documents use
the PDF fallback above. Missing, unreadable, or ambiguous within-page PDF labels
fail without inferring a session from dates. Archive hierarchy conflicts still
fail for review.

## Required companion changes: hansard-mod-api (not hansards-back)

See the [MMS backend handoff](mms-backend-handoff.md) for the complete backend
requirements, exact S3 bucket names and paths, migration status, and acceptance
checks.

## Required companion changes: hansards-front

These are instructions only; no frontend files are edited here.

1. In `lib/routes.ts`, add `/katalog/majlis-mengangkat-sumpah` and
   `/hansard/majlis-mengangkat-sumpah` constants and relevant route lists.
   Add the MMS tab in `data-catalogue/layout.tsx`, plus labels in the existing
   locale JSON files under `public/locales`. Update category/search option
   definitions in `lib/options.ts` and consumers where applicable.
2. Add `pages/katalog/majlis-mengangkat-sumpah/index.tsx`, using the existing
   catalogue request pattern with `house=majlis-mengangkat-sumpah`.
3. Update `lib/types.ts`, `data-catalogue/index.tsx`, and
   `data-catalogue/penggal.tsx` for session-level `sitting_list`. The current
   index filters out terms/sessions with no dates, so explicitly support MMS
   NULL dates; do not let its folders disappear. Render date rows immediately
   under Penggal. Keep ordinary Mesyuarat rendering. Support two-level hash
   navigation for MMS; the existing hash handler expects three levels.
4. In `data-catalogue/dates.tsx`, detect `mms_` before the default DN branch and
   link to `/hansard/majlis-mengangkat-sumpah/YYYY-MM-DD`. Update other document
   link generators (search results, shares, citations and sidebar navigation)
   to use the same category resolver.
5. Add `pages/hansard/majlis-mengangkat-sumpah/[...date].tsx` using
   `house=majlis-mengangkat-sumpah` in the API request. Update
   `data-catalogue/hansard/sidebar.tsx` and `data-catalogue/hansard/hansard.tsx`
   to omit the Mesyuarat label for MMS, handle NULL cycle dates, and display its
   category correctly. Existing header logic slicing two filename characters
   needs an explicit MMS case. DN and MMS retain different document URLs.
6. Route every `mms_` PDF/CSV download to `majlismengangkatsumpah/`.
   In `lib/downloads.ts:getHansardPrefix`, add the `mms_` branch and extend its
   return union. In `data-catalogue/hansard/hansard.tsx`, update the inline
   `hansard_url` folder resolver (currently defaults to DN) so embedded viewers
   and download links use the same mapping. No legacy MMS copies/redirects are
   retained under `dewannegara/`; old MMS links will stop working. DN paths do
   not change. If a proxy/CDN has a category allowlist, add the new folder.
7. Verify desktop/mobile tabs, direct links, session folders without dates,
   downloads, shared links, and same-day DN/MMS navigation. Existing DN URLs
   remain DN; they cannot identify a legacy MMS link without a document marker.

## Rollout and backfill

1. Apply `migrations/20261116_support_mms_parliamentary_cycles.sql` to the target
   database first (already applied to dev on 2026-11-16). Backend/frontend rollout
   remains required before exposing MMS; legacy `semua` mappings and NULL response
   fields are not compatible with MMS yet.
2. Deploy dataproc, then run the existing archive cycle job to seed house-3 rows
   directly into DB. Backend cycle endpoint deployment is no longer required.
   Both cycle strategies use the same MMS hierarchy; no additional schedule or
   independent seed list is needed.
3. Re-run `scrape_mms_arkib_job` for terms 12–15 (the MMS portal's currently
   exposed terms, verified during implementation). This refreshes assignments
   and prepares partitions; it does not launch sitting runs automatically.
4. Download the newly generated MMS manifests. Generate a SQL preview with:

   ```sh
   PYTHONPATH=hansards_pipelines env/bin/python scripts/mms/preview_cycle_backfill.py manifest_term_*.json > /tmp/mms-backfill.sql
   ```

   The script never connects to a database. Its SQL defaults to ROLLBACK, checks
   every assignment has exactly one house-3 cycle, and changes only existing
   MMS sittings' cycle_id. IDs, speeches, summaries, DN records, and PDFs are
   preserved. It lists missing/unmapped records for review; source/PDF review
   remains necessary for unresolved assignments. Review before a separately
   approved live run. Do not reingest existing speeches merely to change a link.
5. Run selected new MMS sitting partitions only after their assignments/cycles
   exist. Deploy the frontend once the API response contract is available.
6. Verify live counts and a known same-day DN/MMS pair after the approved rollout.

The dev schema migration was applied on 2026-11-16. Dev has 17 MMS cycles;
three historical sitting links were corrected and both September 2026 active
MMS ingestions were verified. On 2026-11-17, 55 public PDFs and 55 CSVs were moved
from `dewannegara/mms_*` to `majlismengangkatsumpah/`, SHA-256 verified, and their
old public copies deleted. Deploy the updated dataproc code before rerunning
jobs so old workers do not recreate the legacy public paths. BE/FE download
routing must use the new folder. Production changes remain pending.
