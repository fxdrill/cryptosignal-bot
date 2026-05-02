"""
=============================================================
  DATABASE MANAGER
  Handles: Users, Alert Preferences, Signal Cooldowns
  Uses SQLite — data persists permanently
=============================================================
"""

import sqlite3
import logging
from datetime import datetime, timedelta
import config

log = logging.getLogger(__name__)


def get_conn():
    conn = sqlite3.connect(config.DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    # ── Users table ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            last_name     TEXT,
            joined_at     TEXT,
            is_active     INTEGER DEFAULT 1
        )
    """)

    # ── User alert preferences ────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id           INTEGER PRIMARY KEY,
            alerts_enabled    INTEGER DEFAULT 1,
            min_gain          REAL    DEFAULT 30.0,
            max_gain          REAL    DEFAULT 500.0,
            lookback_days     INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    # ── Alert cooldowns (prevents spamming same token to same user) ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_cooldowns (
            user_id    INTEGER,
            symbol     TEXT,
            exchange   TEXT,
            alerted_at TEXT,
            PRIMARY KEY (user_id, symbol, exchange)
        )
    """)

    # ── Channel signal log ────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT,
            exchange    TEXT,
            signal_type TEXT,
            score       INTEGER,
            sent_at     TEXT
        )
    """)

    # ── Channel signal cooldowns (don't re-post same token) ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_cooldowns (
            symbol     TEXT,
            exchange   TEXT,
            sent_at    TEXT,
            PRIMARY KEY (symbol, exchange)
        )
    """)

    # ── User Watchlist ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            symbol    TEXT,
            added_at  TEXT,
            is_active INTEGER DEFAULT 1,
            UNIQUE(user_id, symbol)
        )
    """)

    # ── Watchlist alert cooldowns (no spam per token per user) ─
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_cooldowns (
            user_id    INTEGER,
            symbol     TEXT,
            alerted_at TEXT,
            PRIMARY KEY (user_id, symbol)
        )
    """)

    # ── Daily watchlist add counter ───────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_daily_adds (
            user_id INTEGER,
            date    TEXT,
            count   INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    """)

    conn.commit()
    conn.close()
    log.info("✅ Database initialized")


# ─────────────────────────────────────────
#  USER MANAGEMENT
# ─────────────────────────────────────────

def upsert_user(user_id: int, username: str, first_name: str, last_name: str):
    """Add new user or update existing one."""
    conn = get_conn()
    conn.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, joined_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name,
            last_name  = excluded.last_name,
            is_active  = 1
    """, (user_id, username, first_name, last_name, datetime.utcnow().isoformat()))

    # Create default prefs if not exists
    conn.execute("""
        INSERT OR IGNORE INTO user_prefs (user_id, alerts_enabled, min_gain, max_gain, lookback_days)
        VALUES (?, 1, ?, ?, ?)
    """, (user_id, config.USER_DEFAULT_MIN_ALERT, config.USER_DEFAULT_MAX_ALERT, config.USER_DEFAULT_LOOKBACK_DAYS))

    conn.commit()
    conn.close()


def get_all_users(active_only=True):
    """Get all users (for broadcast or admin view)."""
    conn = get_conn()
    query = "SELECT * FROM users"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY joined_at DESC"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
    conn.close()
    return count


def get_user_prefs(user_id: int) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM user_prefs WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "alerts_enabled": 1,
        "min_gain": config.USER_DEFAULT_MIN_GAIN,
        "max_gain": config.USER_DEFAULT_MAX_ALERT,
        "lookback_days": config.USER_DEFAULT_LOOKBACK_DAYS,
    }


def update_user_prefs(user_id: int, **kwargs):
    """Update one or more user preference fields."""
    conn = get_conn()
    for key, value in kwargs.items():
        conn.execute(f"UPDATE user_prefs SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()


def get_users_to_alert(symbol: str, exchange: str, gain_pct: float) -> list:
    """
    Get users who should receive an alert for this token.
    Filters by: alerts enabled, gain within their range, not on cooldown.
    """
    conn = get_conn()
    cooldown_cutoff = (datetime.utcnow() - timedelta(hours=config.USER_ALERT_COOLDOWN_HOURS)).isoformat()

    rows = conn.execute("""
        SELECT u.user_id
        FROM users u
        JOIN user_prefs p ON u.user_id = p.user_id
        WHERE u.is_active = 1
          AND p.alerts_enabled = 1
          AND p.min_gain <= ?
          AND p.max_gain >= ?
          AND u.user_id NOT IN (
              SELECT user_id FROM alert_cooldowns
              WHERE symbol = ? AND exchange = ? AND alerted_at > ?
          )
    """, (gain_pct, gain_pct, symbol, exchange, cooldown_cutoff)).fetchall()

    conn.close()
    return [r["user_id"] for r in rows]


def set_user_alert_cooldown(user_id: int, symbol: str, exchange: str):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO alert_cooldowns (user_id, symbol, exchange, alerted_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, symbol, exchange, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
#  CHANNEL COOLDOWN (avoid reposting same signal)
# ─────────────────────────────────────────

def can_post_to_channel(symbol: str, exchange: str, cooldown_hours: int = 4) -> bool:
    conn = get_conn()
    cutoff = (datetime.utcnow() - timedelta(hours=cooldown_hours)).isoformat()
    row = conn.execute("""
        SELECT sent_at FROM channel_cooldowns
        WHERE symbol = ? AND exchange = ? AND sent_at > ?
    """, (symbol, exchange, cutoff)).fetchone()
    conn.close()
    return row is None


def mark_channel_posted(symbol: str, exchange: str):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO channel_cooldowns (symbol, exchange, sent_at)
        VALUES (?, ?, ?)
    """, (symbol, exchange, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def log_channel_signal(symbol: str, exchange: str, signal_type: str, score: int):
    conn = get_conn()
    conn.execute("""
        INSERT INTO channel_signals (symbol, exchange, signal_type, score, sent_at)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, exchange, signal_type, score, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
#  WATCHLIST MANAGEMENT
# ─────────────────────────────────────────

def get_daily_add_count(user_id: int) -> int:
    """How many tokens has this user added today."""
    conn = get_conn()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT count FROM watchlist_daily_adds WHERE user_id = ? AND date = ?",
        (user_id, today)
    ).fetchone()
    conn.close()
    return row["count"] if row else 0


def increment_daily_add_count(user_id: int):
    """Increment today's add count for user."""
    conn = get_conn()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    conn.execute("""
        INSERT INTO watchlist_daily_adds (user_id, date, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
    """, (user_id, today))
    conn.commit()
    conn.close()


def add_to_watchlist(user_id: int, symbol: str) -> tuple[bool, str]:
    """
    Add a token to user's watchlist.
    Returns (success, message).
    """
    # Check daily limit
    daily_count = get_daily_add_count(user_id)
    if daily_count >= config.WATCHLIST_DAILY_LIMIT:
        return False, f"daily_limit"

    # Check total watchlist size
    conn = get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = ? AND is_active = 1",
        (user_id,)
    ).fetchone()[0]

    if total >= config.WATCHLIST_MAX_TOTAL:
        conn.close()
        return False, "max_total"

    # Check if already on watchlist
    existing = conn.execute(
        "SELECT id, is_active FROM watchlist WHERE user_id = ? AND symbol = ?",
        (user_id, symbol)
    ).fetchone()

    if existing and existing["is_active"] == 1:
        conn.close()
        return False, "already_exists"

    # Add or reactivate
    conn.execute("""
        INSERT INTO watchlist (user_id, symbol, added_at, is_active)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id, symbol) DO UPDATE SET
            is_active = 1,
            added_at  = excluded.added_at
    """, (user_id, symbol, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    increment_daily_add_count(user_id)
    return True, "added"


def remove_from_watchlist(user_id: int, symbol: str) -> bool:
    """Remove (deactivate) a token from user watchlist."""
    conn = get_conn()
    conn.execute(
        "UPDATE watchlist SET is_active = 0 WHERE user_id = ? AND symbol = ?",
        (user_id, symbol)
    )
    conn.commit()
    conn.close()
    return True


def get_user_watchlist(user_id: int) -> list[dict]:
    """Get all active watchlist tokens for a user."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT symbol, added_at FROM watchlist
        WHERE user_id = ? AND is_active = 1
        ORDER BY added_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_watchlist_entries() -> list[dict]:
    """
    Get all active watchlist entries across all users.
    Used by background scanner to check all watched tokens.
    Returns list of {user_id, symbol} dicts.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT w.user_id, w.symbol
        FROM watchlist w
        JOIN users u ON w.user_id = u.user_id
        WHERE w.is_active = 1 AND u.is_active = 1
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def can_watchlist_alert(user_id: int, symbol: str) -> bool:
    """Check if we can alert this user about this watchlist token (cooldown)."""
    conn = get_conn()
    cutoff = (datetime.utcnow() - timedelta(hours=config.WATCHLIST_COOLDOWN_HOURS)).isoformat()
    row = conn.execute("""
        SELECT alerted_at FROM watchlist_cooldowns
        WHERE user_id = ? AND symbol = ? AND alerted_at > ?
    """, (user_id, symbol, cutoff)).fetchone()
    conn.close()
    return row is None


def set_watchlist_alert_cooldown(user_id: int, symbol: str):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO watchlist_cooldowns (user_id, symbol, alerted_at)
        VALUES (?, ?, ?)
    """, (user_id, symbol, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

