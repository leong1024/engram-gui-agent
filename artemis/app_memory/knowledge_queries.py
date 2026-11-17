from artemis.app_memory.graph_queries import IN_MAP, select_cards

SELECT_MAP_COUNTS = """
WITH pages AS (
    SELECT package, version_code, COUNT(*) AS states,
           SUM(description_status = 'ready') AS described, MAX(last_seen_at) AS last_seen_at
    FROM states WHERE is_virtual = 0
    GROUP BY package, version_code),
routes AS (
    SELECT package, version_code, COUNT(*) AS routes
    FROM edges WHERE confirmed_n > 0
    GROUP BY package, version_code),
sessions AS (
    SELECT s.package, s.version_code, COUNT(DISTINCT o.session_id) AS sessions
    FROM observations o JOIN states s ON s.state_id = o.src_state_id
    GROUP BY s.package, s.version_code),
vectored AS (
    SELECT s.package, s.version_code
    FROM embeddings m JOIN states s ON m.owner_kind = 'state' AND s.state_id = m.owner_id
    WHERE m.model_id = :model_id
    UNION
    SELECT e.package, e.version_code
    FROM embeddings m JOIN edges e ON m.owner_kind = 'edge' AND e.edge_id = m.owner_id
    WHERE m.model_id = :model_id)
SELECT v.package, v.version_code, v.version_name,
       COALESCE(p.states, 0), COALESCE(p.described, 0), COALESCE(r.routes, 0),
       COALESCE(x.sessions, 0), COALESCE(p.last_seen_at, v.last_seen_at),
       w.package IS NOT NULL
FROM app_versions v
LEFT JOIN pages p USING (package, version_code)
LEFT JOIN routes r USING (package, version_code)
LEFT JOIN sessions x USING (package, version_code)
LEFT JOIN vectored w USING (package, version_code)
ORDER BY v.package, v.version_code
"""

SELECT_PAGES = select_cards(f"{IN_MAP} AND s.is_virtual = 0 AND s.description_status = 'ready'")

SELECT_COMPLETED_SESSIONS = f"""
SELECT h.session_id FROM harvested_sessions h
WHERE h.outcome = 'completed' AND h.session_id IN (
    SELECT o.session_id FROM observations o JOIN states s ON s.state_id = o.src_state_id
    WHERE {IN_MAP})
ORDER BY h.finalized_at DESC, h.session_id
LIMIT :limit
"""
