TOUCH_VERSION = """
INSERT INTO app_versions (package, version_code, first_seen_at, last_seen_at)
VALUES (?, ?, ?, ?)
ON CONFLICT (package, version_code) DO UPDATE SET
    last_seen_at = MAX(last_seen_at, excluded.last_seen_at)
"""

UPSERT_STATE = """
INSERT INTO states (state_id, package, version_code, activity, coarse_key, skeleton,
                    static_tokens, is_opaque, dhash, sample_session_id, sample_step_id,
                    sample_image_sha, first_seen_at, last_seen_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (state_id) DO UPDATE SET last_seen_at = MAX(last_seen_at, excluded.last_seen_at)
"""

INSERT_OUTSIDE = """
INSERT INTO states (state_id, package, version_code, coarse_key, skeleton, static_tokens,
                    is_virtual, first_seen_at, last_seen_at)
VALUES (?, ?, ?, '@outside', '[]', '[]', 1, ?, ?)
ON CONFLICT (state_id) DO NOTHING
"""

SELECT_STATES = """
SELECT state_id, activity, coarse_key, skeleton, static_tokens, is_opaque, dhash
FROM states WHERE package = ? AND version_code = ? AND is_virtual = 0
ORDER BY state_id
"""

UPSERT_EDGE = """
INSERT INTO edges (edge_id, package, version_code, src_state_id, dst_state_id,
                   action_signature, actions, last_seen_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (edge_id) DO UPDATE SET last_seen_at = MAX(last_seen_at, excluded.last_seen_at)
"""

SELECT_OBSERVED_EDGE = "SELECT edge_id FROM observations WHERE session_id = ? AND step_id = ?"

UPSERT_OBSERVATION = """
INSERT INTO observations (session_id, step_id, edge_id, src_state_id, action_signature,
                          status, recorded_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (session_id, step_id) DO UPDATE SET
    edge_id = excluded.edge_id,
    src_state_id = excluded.src_state_id,
    action_signature = excluded.action_signature,
    status = excluded.status,
    recorded_at = excluded.recorded_at
"""

SELECT_COUNTS = "SELECT confirmed_n, discounted_n, provisional_n FROM edges WHERE edge_id = ?"

INSERT_MODEL = """
INSERT INTO embedding_models (model_id, provider, model, dim) VALUES (?, ?, ?, ?)
ON CONFLICT (model_id) DO NOTHING
"""

SELECT_OBSERVED_STEPS = "SELECT step_id FROM observations WHERE session_id = ?"

INSERT_LIVE_SESSION = """
INSERT INTO harvested_sessions (session_id, status) VALUES (?, 'live')
ON CONFLICT (session_id) DO NOTHING
"""

SETTLE_OBSERVATIONS = """
UPDATE observations SET status = ? WHERE session_id = ? AND status = 'provisional'
"""

SELECT_SESSION_EDGES = """
SELECT DISTINCT edge_id FROM observations WHERE session_id = ? AND edge_id IS NOT NULL
"""

FINALIZE_SESSION = """
INSERT INTO harvested_sessions (session_id, status, outcome, finalized_at)
VALUES (?, 'finalized', ?, ?)
ON CONFLICT (session_id) DO UPDATE SET
    status = 'finalized',
    outcome = COALESCE(outcome, excluded.outcome),
    finalized_at = COALESCE(finalized_at, excluded.finalized_at)
"""

SELECT_LIVE_SESSIONS = """
SELECT session_id FROM harvested_sessions WHERE status = 'live' ORDER BY session_id
"""

SELECT_LAST_ACTIVITY = "SELECT MAX(recorded_at) FROM observations WHERE session_id = ?"

SELECT_MAP_STATS = """
SELECT v.package, v.version_code,
       (SELECT COUNT(*) FROM states x WHERE x.package = v.package
            AND x.version_code = v.version_code AND x.is_virtual = 0),
       (SELECT COUNT(*) FROM edges e WHERE e.package = v.package
            AND e.version_code = v.version_code),
       COALESCE(SUM(o.status = 'confirmed'), 0),
       COALESCE(SUM(o.status = 'discounted'), 0),
       COALESCE(SUM(o.status = 'provisional'), 0)
FROM app_versions v
LEFT JOIN states s ON s.package = v.package AND s.version_code = v.version_code
LEFT JOIN observations o ON o.src_state_id = s.state_id
GROUP BY v.package, v.version_code
ORDER BY v.package, v.version_code
"""
