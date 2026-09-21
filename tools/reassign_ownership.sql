-- One-off: make paper_app the owner of every object in paper_plus.
-- The tables were created while Django connected as the postgres superuser.

ALTER DATABASE paper_plus OWNER TO paper_app;
ALTER SCHEMA public OWNER TO paper_app;

DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO paper_app', r.tablename);
    END LOOP;

    FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER SEQUENCE public.%I OWNER TO paper_app', r.sequencename);
    END LOOP;

    FOR r IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER VIEW public.%I OWNER TO paper_app', r.viewname);
    END LOOP;
END $$;

