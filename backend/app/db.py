"""Tiger Data (Timescale Postgres) logging (Task 9).

If DATABASE_URL is empty or the database is unreachable, logging is skipped quietly
so the demo keeps running.
"""
import logging
from datetime import datetime, timezone

from . import config

log = logging.getLogger("lightsout.db")
_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS window_events (
    time        TIMESTAMPTZ NOT NULL,
    building    TEXT        NOT NULL,
    window_id   INTEGER     NOT NULL,
    risk        DOUBLE PRECISION,
    state       TEXT        NOT NULL,
    event       TEXT        NOT NULL  -- 'decision' or 'confirmed'
);
"""
HYPERTABLE = "SELECT create_hypertable('window_events', 'time', if_not_exists => TRUE);"


def _connect():
    import psycopg
    return psycopg.connect(config.DATABASE_URL, connect_timeout=5, autocommit=True)


def init() -> bool:
    global _ready
    if not config.DATABASE_URL:
        log.info("DATABASE_URL not set: Tiger Data logging off")
        return False
    try:
        with _connect() as conn:
            conn.execute(SCHEMA)
            try:
                conn.execute(HYPERTABLE)
            except Exception:
                pass  # plain Postgres without TimescaleDB still works
        _ready = True
        log.info("Tiger Data logging on")
    except Exception as exc:
        log.warning("Tiger Data unavailable, logging off: %s", exc)
    return _ready


def enabled() -> bool:
    return _ready


def log_rows(building: str, rows: list[tuple[int, float, str]], event: str) -> None:
    """rows = [(window_id, risk, state), ...]"""
    if not _ready or not rows:
        return
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO window_events (time, building, window_id, risk, state, event) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(now, building, wid, r, s, event) for wid, r, s in rows],
            )
    except Exception as exc:
        log.warning("Tiger Data write failed: %s", exc)


def recent(limit: int = 50) -> list[dict]:
    if not _ready:
        return []
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT time, building, window_id, risk, state, event FROM window_events "
                        "ORDER BY time DESC LIMIT %s", (limit,))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) | {"time": row[0].isoformat()} for row in cur.fetchall()]
    except Exception as exc:
        log.warning("Tiger Data read failed: %s", exc)
        return []
