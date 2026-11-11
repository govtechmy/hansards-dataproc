# MMS under Dewan Negara

MMS is identified by its filename, with no new database field or ingestion payload
field. The pipeline retains `MMS` as its internal parsing identity, while public
storage and backend house assignment belong to Dewan Negara.

| Value | Example |
| --- | --- |
| Original/partition filename | `MMS-29092026` |
| Normalized filename | `mms_2026-09-29` |
| Public PDF key | `dewannegara/mms_2026-09-29.pdf` |
| API house | `dewan-negara` |
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
selection: MMS belongs to Dewan Negara. After the job succeeds, open the existing
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

MMS uses isolated storage paths:

- Raw PDFs: dataproc bucket `arkib/dewannegara/mms/MMS-DDMMYYYY.pdf`.
- Manifests: dataproc bucket `arkib/dewannegara/manifest/mms/manifest_term_<term>.json`.
- Temporary promotion: public bucket `arkib/mms/dewannegara/mms_YYYY-MM-DD.pdf`.
- Final PDFs: public bucket `dewannegara/mms_YYYY-MM-DD.pdf`.

Raw PDFs remain available for retries. Regular DN archive staging, manifests
and queues are unchanged. The CLI still supports explicit `--category mms`, but the CLI alone
only scrapes; the Dagster job also promotes PDFs and registers partitions.
MMS remains excluded from the default DN/DR/KK archive scrape.

Ingestion uses the filename date and the same containing-cycle rule as DN/DR.
A date outside every Dewan Negara cycle fails ingestion; neither PDF content
nor the nearest cycle overrides this rule.

## Backend/FE handoff (no database migration)

- Dataproc submits `filename: mms_YYYY-MM-DD` and `house: dewan-negara` using
  the existing payload schema.
- Backend derives the MMS type from the `mms_` prefix and exposes it in catalogue
  and sitting responses. Agree on the response field name with FE.
- FE displays “Majlis Mengangkat Sumpah” on the date card in the DN catalogue.
- Retrieval must distinguish regular DN and MMS on the same date by filename or
  sitting ID; the existing house/date-only lookup is ambiguous. Dataproc skips
  that date-only final-status lookup for MMS to avoid using a regular DN result.
- Cycle assignment requires a Dewan Negara cycle containing the filename date,
  just as for ordinary DN documents.

## Pilot observations

Local parsing succeeded for MMS dated 23 July 2025, 2 September 2026 and
29 September 2026, producing respectively 9, 13 and 14 transcript rows including
annotations. Closing annotations are separate in all three samples; printed
speaker labels, timestamps and page references were checked. These are layout
smoke checks, not verified author matching
or full archive coverage. The 29 September 2026 sample has conflicting penggal
labels on its cover and proceedings page. The archive places 23 July 2025 under
a meeting whose displayed date range starts in August. Preserve these findings
for cycle review before ingestion.
