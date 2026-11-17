BEGIN;

-- MMS uses house=3 and is grouped by Parlimen (term) and Penggal (session).
-- It has no Mesyuarat or meeting date range. Existing sitting.cycle_id links
-- remain required; no cycle rows or sitting assignments are changed here.
ALTER TABLE public.api_parliamentary_cycle
    ALTER COLUMN meeting DROP NOT NULL,
    ALTER COLUMN start_date DROP NOT NULL,
    ALTER COLUMN end_date DROP NOT NULL;

-- Preserve the former NOT NULL requirements for every non-MMS house.
-- Validate existing rows too: incompatible data aborts the whole migration.
-- Guard constraint creation so the migration can be run more than once.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'api_parliamentary_cycle_mms_shape_check'
          AND conrelid = 'public.api_parliamentary_cycle'::regclass
    ) THEN
        ALTER TABLE public.api_parliamentary_cycle
            ADD CONSTRAINT api_parliamentary_cycle_mms_shape_check
            CHECK (
                (
                    house = 3
                    AND meeting IS NULL
                    AND start_date IS NULL
                    AND end_date IS NULL
                )
                OR
                (
                    house <> 3
                    AND meeting IS NOT NULL
                    AND start_date IS NOT NULL
                    AND end_date IS NOT NULL
                )
            );
    END IF;
END;
$$;

-- Unlike a unique key containing nullable meeting, this prevents duplicate MMS
-- sessions even when meeting is NULL. Duplicate existing rows abort migration.
CREATE UNIQUE INDEX IF NOT EXISTS api_parliamentary_cycle_mms_session_unique
    ON public.api_parliamentary_cycle (house, term, session)
    WHERE house = 3;

COMMIT;
