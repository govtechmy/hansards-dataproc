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
env/bin/python -m pytest tests/test_mms_support.py tests/test_parse_mms.py -q
```

MMS headings and transcript rows use the dedicated `parse_mms.py` module. Ordinary
DR/DN/KKDR tabulation is not used for MMS. Low-level PDF extraction, preprocessing,
speaker recognition and markdown formatting helpers are reused.

Headings are extracted after DOA because these PDFs may have no KANDUNGAN. Known
ceremony heading openings anchor detection; consecutive uppercase continuation
lines are joined. Uppercase prose such as `KESEDAR.` stays in its speech. The
parser retains section hierarchy, timestamps, physical/printed page ranges and
speaker resumption after annotations. Bracketed stage directions and closing
lines become separate `ANNOTATION` rows, as do oath-taking lists without an
explicit speaker. The normal draft/final detector is reused.

Unfamiliar headings and layouts still need review, especially wrapped speaker
labels, headings separated by blank lines/pages, or documents without DOA.
Inspect extracted text and headings before bulk ingestion. This parser does not
resolve contradictory source cycle labels.

## Activation

The normal `scrape_website_job` includes the MMS active page alongside DR, DN and
KKDR. No environment toggle is required. Discovered MMS PDFs use the existing
move/queue and sitting pipeline.

The archive scraper supports explicit `--category mms`. It is excluded from the
default archive run. Its manifests use `arkib/dewannegara/manifest/mms/` to avoid
replacing regular DN manifests. Existing house/term orchestration does not yet
automatically consume these MMS manifests; use explicit reviewed ingestion.
Running the archive scraper uploads to S3.

## Backend/FE handoff (no database migration)

- Dataproc submits `filename: mms_YYYY-MM-DD` and `house: dewan-negara` using
  the existing payload schema.
- Backend derives the MMS type from the `mms_` prefix and exposes it in catalogue
  and sitting responses. Agree on the response field name with FE.
- FE displays “Majlis Mengangkat Sumpah” on the date card in the DN catalogue.
- Retrieval must distinguish regular DN and MMS on the same date by filename or
  sitting ID; the existing house/date-only lookup is ambiguous. Dataproc skips
  that date-only final-status lookup for MMS to avoid using a regular DN result.
- Cycle assignment needs explicit agreement. Current backend ingestion requires
  a cycle containing the document date, but ceremonies can occur outside the
  ordinary meeting date range. Do not invent a cycle from the nearest date.

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
