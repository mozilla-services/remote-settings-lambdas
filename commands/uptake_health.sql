SELECT
    uptake.source,
    
    -- These timestamps help us display a date range when we present the 
    -- data. It helps to "remind" you when something first started appearing.
    MIN(timestamp/1000000000) AS min_timestamp,
    MAX(timestamp/1000000000) AS max_timestamp,
    
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'up_to_date'), 0)) AS up_to_date, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'success'), 0)) AS success, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'backoff'), 0)) AS backoff, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'pref_disabled'), 0)) AS pref_disabled, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'parse_error'), 0)) AS parse_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'content_error'), 0)) AS content_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'sign_error'), 0)) AS sign_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'sign_retry_error'), 0)) AS sign_retry_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'conflict_error'), 0)) AS conflict_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'sync_error'), 0)) AS sync_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'apply_error'), 0)) AS apply_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'server_error'), 0)) AS server_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'certificate_error'), 0)) AS certificate_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'download_error'), 0)) AS download_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'timeout_error'), 0)) AS timeout_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'network_error'), 0)) AS network_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'offline_error'), 0)) AS offline_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'cleanup_error'), 0)) AS cleanup_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'unknown_error'), 0)) AS unknown_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'custom_1_error'), 0)) AS custom_1_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'custom_2_error'), 0)) AS custom_2_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'custom_3_error'), 0)) AS custom_3_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'custom_4_error'), 0)) AS custom_4_error, 
    SUM(COALESCE(ELEMENT_AT(uptake.status, 'custom_5_error'), 0)) AS custom_5_error
FROM main_summary
CROSS JOIN UNNEST(histogram_parent_uptake_remote_content_result_1) AS uptake(source, status)
WHERE
    -- The sample_id *number* isn't important. It's used to partition the datasets 
    -- (based on stable hash of the client_id). Ultimatetly, the sample_id can be any 
    -- number between 1 and 100 and it means that whatever numbers you see below 
    -- corresponds to 1% of the total population.
    sample_id = '42'
    -- It takes about 2 days for *all* data to come in and be available. 
    -- See https://blog.mozilla.org/data/2017/09/19/two-days-or-how-long-until-the-data-is-in/
    -- But! Since we only care about percentages, we can use just today -1 day. 
    -- The total numbers are lower, but proportions still relevant and slightly closer
    -- to recently which can give us an edge in detecting problems sooner. 
    AND submission_date_s3 = DATE_FORMAT(CURRENT_DATE - INTERVAL '1' DAY, '%Y%m%d')
    AND histogram_parent_uptake_remote_content_result_1 IS NOT NULL
GROUP BY 1
ORDER BY 1
