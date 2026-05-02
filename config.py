"""
=============================================================
  CRYPTO SIGNAL BOT — CONFIGURATION
  On Railway: all secrets come from environment variables
  On local:   just edit the fallback values below
=============================================================
"""

import os

# ─────────────────────────────────────────────────────────────
#  TELEGRAM CREDENTIALS  (set these as Railway env variables)
# ─────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID     = os.environ.get("CHANNEL_ID", "@your_channel_username")

# ─────────────────────────────────────────────────────────────
#  ADMIN IDS  (comma-separated in Railway, e.g. "123456,789012")
# ─────────────────────────────────────────────────────────────
_admin_env = os.environ.get("ADMIN_IDS", "123456789")
ADMIN_IDS = [int(x.strip()) for x in _admin_env.split(",") if x.strip().isdigit()]

# ─────────────────────────────────────────────────────────────
#  EXCHANGES TO MONITOR
# ─────────────────────────────────────────────────────────────
EXCHANGES = {
    "bybit":   True,
    "binance": True,
    "mexc":    True,
}

# ─────────────────────────────────────────────────────────────
#  SIGNAL STRATEGY SETTINGS
# ─────────────────────────────────────────────────────────────
MIN_PRICE_CHANGE_24H = float(os.environ.get("MIN_PRICE_CHANGE_24H", "15.0"))
RSI_OVERBOUGHT       = int(os.environ.get("RSI_OVERBOUGHT", "75"))
RSI_EXTREME          = int(os.environ.get("RSI_EXTREME", "85"))
MIN_VOLUME_USDT      = float(os.environ.get("MIN_VOLUME_USDT", "500000"))
FUNDING_RATE_HIGH    = float(os.environ.get("FUNDING_RATE_HIGH", "0.001"))
SCORE_WATCH          = int(os.environ.get("SCORE_WATCH", "50"))
SCORE_SHORT          = int(os.environ.get("SCORE_SHORT", "70"))
SCAN_INTERVAL        = int(os.environ.get("SCAN_INTERVAL", "300"))

# ─────────────────────────────────────────────────────────────
#  TRENDING TOKEN SETTINGS
# ─────────────────────────────────────────────────────────────
TRENDING_TOP_N   = int(os.environ.get("TRENDING_TOP_N", "10"))
TRENDING_MIN_GAIN = float(os.environ.get("TRENDING_MIN_GAIN", "30.0"))
TRENDING_MAX_GAIN = float(os.environ.get("TRENDING_MAX_GAIN", "300.0"))

# ─────────────────────────────────────────────────────────────
#  USER ALERT SETTINGS
# ─────────────────────────────────────────────────────────────
USER_DEFAULT_MIN_ALERT    = float(os.environ.get("USER_DEFAULT_MIN_ALERT", "30.0"))
USER_DEFAULT_MAX_ALERT    = float(os.environ.get("USER_DEFAULT_MAX_ALERT", "500.0"))
USER_DEFAULT_LOOKBACK_DAYS = int(os.environ.get("USER_DEFAULT_LOOKBACK_DAYS", "1"))
USER_MAX_LOOKBACK_DAYS    = int(os.environ.get("USER_MAX_LOOKBACK_DAYS", "5"))
USER_ALERT_COOLDOWN_HOURS = int(os.environ.get("USER_ALERT_COOLDOWN_HOURS", "6"))

# ─────────────────────────────────────────────────────────────
#  WATCHLIST SETTINGS
# ─────────────────────────────────────────────────────────────
WATCHLIST_DAILY_LIMIT    = int(os.environ.get("WATCHLIST_DAILY_LIMIT", "2"))
WATCHLIST_MAX_TOTAL      = int(os.environ.get("WATCHLIST_MAX_TOTAL", "10"))
WATCHLIST_SCAN_INTERVAL  = int(os.environ.get("WATCHLIST_SCAN_INTERVAL", "600"))
WATCHLIST_ALERT_SCORE    = int(os.environ.get("WATCHLIST_ALERT_SCORE", "60"))
WATCHLIST_COOLDOWN_HOURS = int(os.environ.get("WATCHLIST_COOLDOWN_HOURS", "4"))

# ─────────────────────────────────────────────────────────────
#  DATABASE
#  Railway uses /tmp for writable storage
# ─────────────────────────────────────────────────────────────
DATABASE_FILE = os.environ.get("DATABASE_FILE", "/tmp/cryptobot.db")

# ─────────────────────────────────────────────────────────────
#  OPTIONAL: X (TWITTER) MONITORING
# ─────────────────────────────────────────────────────────────
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

INFLUENCER_ACCOUNTS = [
    "Ansem", "Murad", "Pentoshi", "AltcoinSherpa",
    "CryptoRover", "WhalePanda", "inversebrah",
]

# ─────────────────────────────────────────────────────────────
#  MESSAGES & BRANDING
# ─────────────────────────────────────────────────────────────
BOT_NAME        = os.environ.get("BOT_NAME", "CryptoSignal Pro")
WELCOME_MESSAGE = (
    f"👋 Welcome to *{BOT_NAME}*!\n\n"
    "I monitor Bybit, Binance & MEXC 24/7 and alert you when tokens are pumping or about to dump.\n\n"
    "Use the menu below to get started 👇"
)
CHANNEL_SIGNAL_FOOTER = f"\n\n📊 *{BOT_NAME}* | Real-time Pump & Dump Detection"
