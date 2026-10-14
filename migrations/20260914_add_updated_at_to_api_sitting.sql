BEGIN;

-- Historical rows remain NULL. The trigger only records a timestamp when an
-- existing sitting is actually updated.
ALTER TABLE public.api_sitting
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

ALTER TABLE public.api_sitting
    ALTER COLUMN updated_at DROP DEFAULT,
    ALTER COLUMN updated_at DROP NOT NULL;

CREATE OR REPLACE FUNCTION public.api_sitting_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

-- PostgreSQL has no CREATE TRIGGER IF NOT EXISTS, so guard creation through
-- the system catalogue to make this migration safe to run more than once.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'api_sitting_set_updated_at_trigger'
          AND tgrelid = 'public.api_sitting'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER api_sitting_set_updated_at_trigger
        BEFORE UPDATE ON public.api_sitting
        FOR EACH ROW
        EXECUTE FUNCTION public.api_sitting_set_updated_at();
    END IF;
END;
$$;

COMMENT ON COLUMN public.api_sitting.updated_at IS
    'Timestamp of the most recent update, maintained by a database trigger.';

COMMIT;
