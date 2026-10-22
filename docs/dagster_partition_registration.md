# One-time production Dagster partition registration

Script: `data_migrations/20261021_register_missing_dagster_partitions.py`.

This transfers only missing `house_sittings` and `house_sittings_legacy`
partition keys from the dev Dagster DB to production. It requires the matching
PDF to exist in production S3, including `kamarkhas/` for Kamar Khas keys.
Invalid keys and missing PDFs are reported and skipped.

It preserves production-only partitions, run history, schedules and sensor state.
It does not restore a backup, connect to the Hansard DB, launch ingestion jobs,
or synchronize materialization/run statuses. Registered partitions may show as
unmaterialized until jobs run in production; that is expected.

From the repository root, preview when authorized:

```bash
env/bin/python data_migrations/20261021_register_missing_dagster_partitions.py \
  --source-env-file .env \
  --target-env-file .env.prod \
  --target-bucket my.gov.parlimen.hsd-download-bucket-prod \
  --profile shared-services \
  --report /private/tmp/prod-partition-registration-plan.json
```

Both env files must provide their respective `DAGSTER_DB_URL`; the target file
must also provide the matching `S3_PUBLIC_BUCKET`. Credentials are not printed.

Review the plan, then add `--apply` only when registration is authorized.
The script uses Dagster's API, verifies additions, and can be rerun after a
partial failure. Existing partitions are never deleted. Counts can differ from
dev because production-only keys are retained and invalid/unavailable inputs
are skipped. It does not enable stopped sensors; existing running sensors retain
their normal behavior.

After registration, refresh Dagster, select partitions in the appropriate job,
and launch the desired runs manually.
