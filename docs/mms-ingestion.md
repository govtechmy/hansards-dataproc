# MMS as house 3

MMS keeps its existing parser and S3 paths, but database/API identity is
`majlis-mengangkat-sumpah` (`house=3`). Parlimen/Penggal comes from the website
hierarchy, not the document date. The database migration is required before
running cycle jobs. Backend/frontend changes are required to serve MMS, but
cycle seeding writes directly to DB and does not require the cycle API.

| Value | Example |
| --- | --- |
| Original/partition filename | `MMS-29092026` |
| Normalized filename | `mms_2026-09-29` |
| Public PDF key | `dewannegara/mms_2026-09-29.pdf` |
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

- Raw PDFs: dataproc bucket `arkib/dewannegara/mms/MMS-DDMMYYYY.pdf`.
- Manifests: dataproc bucket `arkib/dewannegara/manifest/mms/manifest_term_<term>.json`.
- Temporary promotion: public bucket `arkib/mms/dewannegara/mms_YYYY-MM-DD.pdf`.
- Final PDFs: public bucket `dewannegara/mms_YYYY-MM-DD.pdf`.

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

These are instructions only; this change does not edit the API repository.
Paths below are relative to `hansard-mod-api`.

1. **Stored house identity and all-house filters:** In `src/types/enum.ts`, add
   `majlis-mengangkat-sumpah` to `HOUSE` and map `MAJLIS_MENGANGKAT_SUMPAH=3`.
   IMPORTANT: `SEMUA` currently also equals 3. Remove that collision: treat
   `semua` as a filter sentinel (for example -1), never as a stored house.
   Update `src/controllers/search.controller.ts` to expand `semua`, including
   array inputs, to `[0,1,2,3]`. Update `getSittingList` in
   `src/controllers/sitting.controller.ts` similarly; its current mapping can
   otherwise treat `semua` as MMS. Keep all-house filtering out of single-sitting
   and cycle-create operations. Audit other HOUSE_TO_CODE consumers.

2. **Database migration and model:** In
   `src/models/parliamentary-cycle.model.ts`, permit NULL for `meeting`,
   `start_date`, and `end_date`. Apply corresponding database ALTER statements.
   Add conditional constraints so house 3 requires all three to be NULL and
   houses 0/1/2 still require meeting/dates. Check existing rows before adding
   constraints; do not silently rewrite ordinary cycles. Add a partial unique
   index on `(house,term,session) WHERE house=3` to prevent concurrent duplicates.
   Keep `Sitting.cycle_id` required; MMS references a real house-3 cycle.
   No new table or sitting column is needed. Suggested migration shape:

   ```sql
   ALTER TABLE api_parliamentary_cycle
     ALTER COLUMN meeting DROP NOT NULL,
     ALTER COLUMN start_date DROP NOT NULL,
     ALTER COLUMN end_date DROP NOT NULL;
   ALTER TABLE api_parliamentary_cycle ADD CONSTRAINT cycle_shape CHECK (
     (house=3 AND meeting IS NULL AND start_date IS NULL AND end_date IS NULL)
     OR (house IN (0,1,2) AND meeting IS NOT NULL
         AND start_date IS NOT NULL AND end_date IS NOT NULL)
   );
   CREATE UNIQUE INDEX unique_mms_session
     ON api_parliamentary_cycle (house,term,session) WHERE house=3;
   ```

3. **Validation and response serialization:** Update
   `src/schema/parliamentary/request.schema.ts` to accept house 3, positive MMS
   term/session, and NULL meeting/dates only for MMS. Keep existing ordinary
   meeting validation. Make the corresponding fields nullable in
   `src/schema/parliamentary/response.schema.ts`,
   `src/schema/sitting/response.schema.ts`, `src/types/entities.ts`, and
   `src/types/sql-rows.ts`. Check all nested cycle responses so Fastify/Zod does
   not reject or strip NULL fields. In `getSittingList`, omit empty coverage
   dates or return documented nullable dates and update its response schema.

4. **Optional API cycle creation:** Dataproc cycle jobs no longer call this
   endpoint. If retained for MMS, `src/controllers/parliamentary-cycle.controller.ts`
   currently calls `create` unconditionally. For MMS, find/create by
   `(house,term,session)` under the unique index; return 201 when created and
   200 with the existing cycle when already present. Handle concurrent insert
   conflicts by retrieving the existing row. Add the 200 response schema in
   `src/routes/parliamentary-cycle.route.ts` alongside 201. Do not fabricate
   meeting numbers or date ranges.

5. **Catalogue:** `src/utils/catalogue/cycle-map.util.ts` currently converts
   `meeting` using `Number(...)`, which turns NULL into 0. Branch for house 3:
   attach MMS sittings directly under the session as `sitting_list`; never create
   a `0`, `null`, or other synthetic meeting folder. Adjust
   `src/controllers/catalogue.controller.ts` as needed to pass the category.
   Extend `src/schema/catalogue/response.schema.ts` and utility types to support
   this shape (including `dropdown` mode), preserving the ordinary shape:

   ```json
   {"catalogue_list":{"15":{"start_date":null,"end_date":null,
     "5":{"start_date":null,"end_date":null,"sitting_list":[
       {"sitting_id":123,"date":"2026-09-29","filename":"mms_2026-09-29","is_final":false}
     ]}}},"total_count":1}
   ```

   Dates here represent absent cycle dates, not inferred session boundaries.
   UI may omit the year labels or derive document coverage for display only.

6. **Document retrieval and optional API ingestion:**
   `src/controllers/sitting.controller.ts:getSitting` already filters by the
   mapped house plus date, so mapping MMS to 3 separates it from same-day DN.
   Its current `findOne` can silently select one of multiple same-category
   documents; this design assumes one normalized MMS document per day.
   No filename query parameter is required for the DN/MMS collision.
   `upsertSitting` still resolves every house by date: if that endpoint remains
   supported for MMS, add required MMS `term`/`session` in
   `src/schema/sitting/request.schema.ts` and resolve the house-3 cycle by them,
   with missing/ambiguous assignments rejected. Dataproc's selected sitting job
   writes directly to DB and does not require this endpoint.

7. **Acceptance checks:** Seed the same MMS cycle twice and concurrently; expect
   one DB row. Round-trip NULL fields through cycle, sitting and catalogue
   endpoints. Retrieve DN and MMS on the same date separately. Test MMS-only and
   `semua` search/list filters, including arrays, and existing DR/DN/KK catalogues.

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
6. Keep PDF/CSV download storage under `dewannegara/mms_YYYY-MM-DD.*`.
   `lib/downloads.ts` currently defaults non-DR/KK prefixes to DN, which remains
   compatible; make MMS explicit if consolidating the resolver. Do not change
   bucket folders just because the page route/house changes.
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

The dev schema migration was applied on 2026-11-16. Local pipeline tests use
mocks; the direct cycle writer is additionally checked against temporary dev
PostgreSQL tables. These checks do not seed live MMS cycles or relink sittings.
PDF fallback was verified against the two September 2026 active PDFs. Production
migration, live data backfill, and full Dagster ingestion remain separate steps.
