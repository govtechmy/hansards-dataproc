BEGIN;

-- New sittings need a timestamp on first ingestion, not only on re-ingestion.
-- Existing NULL timestamps are left untouched; their ingestion time is unknown.
ALTER TABLE public.api_sitting
    ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;

CREATE OR REPLACE FUNCTION public.api_sitting_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

-- Replace the old UPDATE-only trigger atomically; reruns are safe.
DROP TRIGGER IF EXISTS api_sitting_set_updated_at_trigger ON public.api_sitting;

CREATE TRIGGER api_sitting_set_updated_at_trigger
BEFORE INSERT OR UPDATE ON public.api_sitting
FOR EACH ROW
EXECUTE FUNCTION public.api_sitting_set_updated_at();

COMMENT ON COLUMN public.api_sitting.updated_at IS
    'Timestamp of initial insertion or most recent update, maintained by a database trigger.';

COMMIT;
