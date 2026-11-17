# MMS backend handoff
Updated at: 17 Nov 2026

Repository: **`hansard-mod-api`**. These BE changes are required as of dataproc changes for MMS ticket.
No new endpoint or table is needed.

## 1. Add MMS to the house mapping

Update `src/types/enum.ts` and the existing request schemas:

| Category | API `house` value | Database code |
| --- | --- | ---: |
| Dewan Rakyat | `dewan-rakyat` | 0 |
| Dewan Negara | `dewan-negara` | 1 |
| Kamar Khas | `kamar-khas` | 2 |
| Majlis Mengangkat Sumpah | `majlis-mengangkat-sumpah` | 3 |

`SEMUA` currently uses `3`, which now belongs to MMS.

**Suggestion:** change `SEMUA` to `-1`. FE can keep sending `house=semua`.
BE must query all four houses `[0,1,2,3]` for `semua`, including when it appears
in an array of filters. Never save `-1` in the database.

## 2. Fix BE validation so it can return MMS records

BE currently expects every cycle to have a Mesyuarat number and start/end dates.
MMS has none of these mesyuarat dates, so its database records contain:

```json
{"house": 3, "term": 15, "session": 5, "meeting": null, "start_date": null, "end_date": null}
```

**Change BE validation to accept this MMS record instead of failing because
those three fields are NULL.** Return the NULL values as stored; do not replace
`meeting: null` with `meeting: 0`.

For DR, DN and KK, keep the current behavior: a Mesyuarat number and cycle
start/end dates are still required. Do not clear or change their data.

Update the cycle model, types and response schemas:

- `src/models/parliamentary-cycle.model.ts`
- `src/types/entities.ts`
- `src/types/sql-rows.ts`
- Cycle response schemas under `src/schema/catalogue/`, `src/schema/sitting/`,
  `src/schema/parliamentary/` and `src/schema/search/`.

- The dev database already accepts NULL for MMS `meeting`, `start_date` and
  `end_date`. The remaining change is in BE code.

## 3. Update the existing catalogue endpoint

```http
GET /api/catalogue?house=majlis-mengangkat-sumpah&term=15
```

MMS has **Parlimen → Penggal → documents**, with no Mesyuarat folder.
Return `sitting_list` directly under each Penggal. Support the existing dropdown
mode too. Keep the DR/DN/KK catalogue structure unchanged.

Update:

- `src/controllers/catalogue.controller.ts`
- `src/utils/catalogue/cycle-map.util.ts`
- Catalogue response schemas and types.

## 4. Update the existing document and list endpoints

Accept `house=majlis-mengangkat-sumpah` and map it to `3`:

```http
GET /api/sitting?house=majlis-mengangkat-sumpah&date=2026-09-29
GET /api/sitting/list?house=majlis-mengangkat-sumpah
```

Update `src/controllers/sitting.controller.ts` and the sitting request/response
schemas. For list requests, `semua` must include all four houses.

## 5. Include MMS in search

Update:

- `src/controllers/search.controller.ts`
- `src/services/search.svc.ts`
- `src/schema/search/response.schema.ts`

Required changes:

- MMS searches query house `3`.
- `semua` searches query `[0,1,2,3]`, including array filters.
- Search results return MMS with `meeting: null`.
- Add MMS to `house_counts`. Suggested field name: `majlis_mengangkat_sumpah`;
  use the same name in FE.
- Replace hardcoded three-house lists with all four houses.

## 6. Use the MMS S3 download folder

Region: **`ap-southeast-5`**.

| Environment | Download bucket (`AWS_S3_BUCKET`) |
| --- | --- |
| Dev | `my.gov.parlimen.hsd-download-bucket-dev` |
| Production | `my.gov.parlimen.hsd-download-bucket-prod` |

MMS keys:

```text
majlismengangkatsumpah/mms_YYYY-MM-DD.pdf
majlismengangkatsumpah/mms_YYYY-MM-DD.csv
```

Use the existing download endpoint:

```http
POST /api/file/download
Content-Type: application/json

{"key":"majlismengangkatsumpah/mms_2026-09-29.pdf"}
```

No BE download code change is required. FE must use the MMS keys shown above.

## 7. Database migrations

Both migrations are already applied on dev. **BE does not need to run them
again on dev.** They still need to be applied once when rolling out to production.

- [MMS cycle migration](../migrations/20261116_support_mms_parliamentary_cycles.sql)
- [Sitting timestamp migration](../migrations/20261117_set_sitting_updated_at_on_insert_and_update.sql)

The database handles `updated_at` on insert and update. No BE timestamp code
is required.

## 8. Check before release

- MMS catalogue shows Parlimen/Penggal/documents without a Mesyuarat folder.
- Existing document and list endpoints return MMS.
- DN and MMS on the same date return the correct document for each house.
- NULL cycle fields return without errors.
- MMS and `semua` searches work, and counts include MMS.
- MMS PDF and CSV downloads work from the correct bucket and folder.
- Existing DR/DN/KK requests still work.

Dev reference, verified **17 November 2026**: **57 MMS documents, 505 speech rows**.
This includes the two DN-labelled MMS PDFs, stored as `mms_2017-06-23` and
`mms_2017-11-03`, and the active MMS documents dated `2026-09-02` and `2026-09-29`.
