# Migrations

## 20261116_support_mms_parliamentary_cycles.sql

Allows MMS (`house=3`) cycles to store Parlimen/Penggal without meeting or dates.
Other houses still require those fields. A unique index prevents duplicate MMS
Parlimen/Penggal rows. No existing data is changed or seeded.

Apply with the target database configured in `DATABASE_URL`:

```sh
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -f migrations/20261116_support_mms_parliamentary_cycles.sql
```

The migration is transactional and can be rerun. Applied and verified on dev
on 2026-11-16; not applied to production.
Updated cycle jobs write directly to DB; backend/frontend changes are still
needed to display MMS correctly.

Rollback: before seeding MMS, restore NOT NULL on `meeting`, `start_date`, and
`end_date`, then drop `api_parliamentary_cycle_mms_shape_check` and
`api_parliamentary_cycle_mms_session_unique`. After seeding, review dependent
sitting links first; do not delete referenced cycles.
