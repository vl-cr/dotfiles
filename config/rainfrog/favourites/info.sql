-- PostgreSQL Database Info
SELECT 
    'Database' as info_type,
    current_database() as value
UNION ALL
SELECT 
    'User',
    CASE 
        WHEN current_user = session_user THEN current_user
        ELSE current_user || ' (session user: ' || session_user || ')'
    END
UNION ALL
SELECT 
    'Port',
    inet_server_port()::text
UNION ALL
SELECT 
    'Version',
    version()
UNION ALL
SELECT 
    'Schema',
    current_schema()
ORDER BY info_type;
