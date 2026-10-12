-- Empty all business data, keep users + everything the app needs to boot.
--
-- WHY not tools/flush_all.py: it truncates every table except
-- django_migrations, so it also wipes users, auth groups/permissions,
-- content types and shared_documentsequence (rows are not created by any
-- migration -> every new invoice would fail with DoesNotExist).
--
-- No CASCADE on purpose: if a kept table had an FK into an emptied table,
-- CASCADE would silently wipe it. The guard below aborts instead.
--
-- Destructive. Take a DB backup first.
-- Run SECTION 1 alone (read-only preview), then SECTION 2.

-- ===================== SECTION 1: preview (read-only) =====================
SELECT tablename,
       CASE WHEN tablename IN (
            'django_migrations', 'django_content_type', 'django_session',
            'auth_group', 'auth_group_permissions', 'auth_permission',
            'users_user', 'users_user_groups', 'users_user_user_permissions',
            'users_historicaluser', 'shared_documentsequence')
            THEN 'KEEP' ELSE 'EMPTY' END AS action
FROM pg_tables
WHERE schemaname = current_schema()
ORDER BY action, tablename;

SELECT id, phone, first_name, last_name, is_active, is_superuser
FROM users_user ORDER BY id;

SELECT doc_type, next_number FROM shared_documentsequence ORDER BY doc_type;


-- ===================== SECTION 2: reset =====================
BEGIN;

DO $$
DECLARE
    keep text[] := ARRAY[
        'django_migrations', 'django_content_type', 'django_session',
        'auth_group', 'auth_group_permissions', 'auth_permission',
        'users_user', 'users_user_groups', 'users_user_user_permissions',
        'users_historicaluser', 'shared_documentsequence'];
    wipe text[];
    bad  text;
BEGIN
    SELECT array_agg(tablename ORDER BY tablename) INTO wipe
    FROM pg_tables
    WHERE schemaname = current_schema() AND tablename <> ALL (keep);

    IF wipe IS NULL THEN
        RAISE NOTICE 'nothing to empty';
        RETURN;
    END IF;

    SELECT string_agg(format('%s -> %s', src.relname, dst.relname), ', ') INTO bad
    FROM pg_constraint c
    JOIN pg_class src ON src.oid = c.conrelid
    JOIN pg_class dst ON dst.oid = c.confrelid
    WHERE c.contype = 'f'
      AND src.relnamespace = current_schema()::regnamespace
      AND src.relname = ANY (keep)
      AND dst.relname = ANY (wipe);

    IF bad IS NOT NULL THEN
        RAISE EXCEPTION 'aborted, kept table points at an emptied one: %', bad;
    END IF;

    EXECUTE 'TRUNCATE '
        || (SELECT string_agg(format('%I', t), ', ') FROM unnest(wipe) t)
        || ' RESTART IDENTITY';

    RAISE NOTICE 'emptied % tables', array_length(wipe, 1);
END $$;

-- Optional: restart invoice numbering. Uncomment and set the number.
-- UPDATE shared_documentsequence SET next_number = 1 WHERE doc_type IN ('sale', 'purchase');

COMMIT;

-- Verify: users still there, business tables empty.
SELECT (SELECT count(*) FROM users_user)              AS users,
       (SELECT count(*) FROM auth_group)              AS groups,
       (SELECT count(*) FROM shared_documentsequence) AS sequences,
       (SELECT count(*) FROM products_product)        AS products,
       (SELECT count(*) FROM sales_salesinvoice)      AS sales,
       (SELECT count(*) FROM purchasing_purchaseinvoice) AS purchases;
