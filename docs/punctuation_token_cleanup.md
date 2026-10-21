# Punctuation token cleanup

Set `HANSARD_DB_URL` in `.env.prod`, then run:

```bash
env/bin/python data_migrations/20261015_punctuation_cleanup/run_punctuation_cleanup.py --env-file .env.prod --apply
```

Removes punctuation-only tokens such as `’`, `“`, and `—`. Keeps words and leaves `length` unchanged. Creates no reports or backups.

Remove `--apply` to preview counts only. Safe to rerun if interrupted; completed batches are skipped automatically.

Deploy the ingestion filter change so new records stay clean.
