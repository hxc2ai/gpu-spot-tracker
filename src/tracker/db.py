from __future__ import annotations
import sqlite3, time
from .models import Offer

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers(
  key TEXT PRIMARY KEY, source TEXT, provider TEXT, gpu TEXT, region TEXT, gpu_count INT,
  price REAL, p_int REAL, reliability REAL, note TEXT,
  first_prun INT, last_prun INT, seen INT, last_ts INT);
CREATE TABLE IF NOT EXISTS history(key TEXT, ts INT, price REAL);
CREATE INDEX IF NOT EXISTS h_key ON history(key, ts);
CREATE TABLE IF NOT EXISTS provider_state(provider TEXT PRIMARY KEY, n INT, last_ts INT, last_ok INT, last_error TEXT);
"""


def connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=DELETE")  # single file, safe to upload
    db.executescript(SCHEMA)
    return db


def due(db, provider: str, every_min: int, now: int) -> bool:
    r = db.execute("SELECT last_ts FROM provider_state WHERE provider=?", (provider,)).fetchone()
    return r is None or now - r[0] >= (every_min - 2) * 60


def record_failure(db, provider: str, err: str, now: int):
    db.execute("INSERT INTO provider_state(provider,n,last_ts,last_ok,last_error) VALUES(?,0,?,0,?) "
               "ON CONFLICT(provider) DO UPDATE SET last_ts=?, last_ok=0, last_error=?",
               (provider, now, err[:300], now, err[:300]))


def record_success(db, provider: str, offers: list[Offer], now: int):
    """Store offers; history rows are written only when a price changes."""
    row = db.execute("SELECT n FROM provider_state WHERE provider=?", (provider,)).fetchone()
    n = (row[0] if row else 0) + 1
    db.execute("INSERT INTO provider_state(provider,n,last_ts,last_ok,last_error) VALUES(?,?,?,1,NULL) "
               "ON CONFLICT(provider) DO UPDATE SET n=?, last_ts=?, last_ok=1, last_error=NULL",
               (provider, n, now, n, now))
    for o in offers:
        old = db.execute("SELECT price FROM offers WHERE key=?", (o.key,)).fetchone()
        if old is None:
            db.execute("INSERT INTO offers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (o.key, provider, o.provider, o.gpu, o.region, o.gpu_count, o.price, o.p_int,
                        o.reliability, o.note, n, n, 1, now))
        else:
            db.execute("UPDATE offers SET gpu_count=?,price=?,p_int=?,reliability=?,note=?,"
                       "last_prun=?,seen=seen+1,last_ts=? WHERE key=?",
                       (o.gpu_count, o.price, o.p_int, o.reliability, o.note, n, now, o.key))
        last = db.execute("SELECT price FROM history WHERE key=? ORDER BY ts DESC LIMIT 1", (o.key,)).fetchone()
        if last is None or abs(last[0] - o.price) > 1e-9:
            db.execute("INSERT INTO history VALUES(?,?,?)", (o.key, now, o.price))
    db.execute("DELETE FROM offers WHERE last_ts < ?", (now - 30 * 86400,))  # prune dead keys
    db.commit()
