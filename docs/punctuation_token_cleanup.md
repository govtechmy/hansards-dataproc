# Punctuation token cleanup

Set `HANSARD_DB_URL` in `.env.prod`, then run:

```bash
env/bin/python data_migrations/20261015_punctuation_cleanup/run_punctuation_cleanup.py --env-file .env.prod --apply
```

Removes punctuation-only tokens such as `’`, `“`, and `—`. Keeps words and leaves `length` unchanged. Creates no reports or backups.

Remove `--apply` to preview counts only. Safe to rerun if interrupted; completed batches are skipped automatically.

Deploy the ingestion filter change so new records stay clean.

## Symbol cleanup (2026-10-21)

The original migration excludes Unicode symbols such as `$`, `£`, `+` and `=`.
Use the additional migration to remove punctuation/symbol-only tokens:

```bash
env/bin/python data_migrations/20261021_remove_symbol_only_speech_tokens.py --env-file .env.prod --apply
```

Use `.env` for dev, or omit `--apply` to preview. Keeps tokens containing letters
or digits (such as `$100`, `RM50`, `COVID-19` and `don't`). Changes only
`api_speech.speech_tokens`; original speech text, `length` and speaker links stay
unchanged. No reports or backups are created. Deploy the shared ingestion filter
before rerunning sittings so the symbols are not reintroduced.
