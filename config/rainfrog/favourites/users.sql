-- PostgreSQL Users Info
SELECT 
    rolname as info_type,
    CASE 
        WHEN rolsuper THEN 'Superuser'
        WHEN rolcreatedb THEN 'Can Create DB'
        WHEN rolcreaterole THEN 'Can Create Roles'
        WHEN rolcanlogin THEN 'Can Login'
        ELSE 'Regular User'
    END as value
FROM pg_roles
WHERE rolcanlogin = true
ORDER BY rolname;
