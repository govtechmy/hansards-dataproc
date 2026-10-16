# Stopword cleanup

Set `HANSARD_DB_URL` in `.env.prod`, then run from the project root:

```bash
env/bin/python data_migrations/20261015_stopword_cleanup/run_stopword_cleanup.py --env-file .env.prod --apply
```

Removes exact matches from the 35-word `ADDITIONAL_STOPWORDS` list in
`hansards_pipelines/utils/additional_stopwords.py`. Ingestion uses that same list.
Existing base and custom stopword lists stay separate.
Preserves other tokens, their order, speech text, and `length`.
Creates no reports or backups. Remove `--apply` to preview counts only.
Safe to rerun after interruption; completed batches stay committed.

Deploy the ingestion code changes so new records use the updated list too.
