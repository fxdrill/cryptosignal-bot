"""
=============================================================
  MESSAGE FORMATTER
  All Telegram message templates in one place
=============================================================
"""

from engine import TokenSignal
import config


def signal_message(signal: TokenSignal) -> str:
    """Format a full signal alert for channel or DM."""

    headers = {
        "DUMP_ALERT":  "🚨 DUMP ALERT 🚨",
        "SHORT_SETUP": "⚡ SHORT SETUP",
        "PUMP_WATCH":  "👀 PUMP WATCH",
        "MONITOR":     "📊 SIGNAL",
    }
    header = headers.get(signal.signal_type, "📊 SIGNAL")

    rsi_label = (
        "🔴 EXTREME"   if signal.rsi >= 90 else
        "🟠 VERY HIGH" if signal.rsi >= 85 else
        "🟡 OVERBOUGHT" if signal.rsi >= 75 else
        "💚 OVERSOLD"  if signal.rsi <= 30 else
        "⚪ NEUTRAL"
    )

    vol_emoji = {"INCREASING": "📈", "DECREASING": "📉", "FLAT": "➡️"}.get(signal.volume_trend, "➡️")

    action = (
        "🔴 *ACTION: Consider SHORT position*\n⚠️ Set Stop Loss above recent high!"
        if signal.signal_type in ("DUMP_ALERT", "SHORT_SETUP")
        else "👀 *ACTION: Watch for reversal signals before shorting*"
    )

    funding_str = f"{signal.funding_rate*100:.4f}%" if signal.funding_rate is not None else "N/A"

    reasons_str = "\n".join(f"  • {r}" for r in signal.reasons)

    msg = (
        f"*{header}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 Exchange: `{signal.exchange.upper()}`\n"
        f"💰 Token: `{signal.symbol}`\n"
        f"💵 Price: `${signal.price:.6f}`\n"
        f"📈 24h Change: `+{signal.change_24h:.1f}%`\n"
        f"📊 Volume 24h: `${signal.volume_24h:,.0f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📉 RSI (14): `{signal.rsi}` {rsi_label}\n"
        f"{vol_emoji} Volume Trend: `{signal.volume_trend}`\n"
        f"💸 Funding Rate: `{funding_str}`\n"
        f"🐦 X Mentions: `{signal.x_mentions}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Signal Score: `{signal.score}/100`\n\n"
        f"📋 *Why:*\n{reasons_str}\n\n"
        f"{action}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ `{signal.timestamp}`"
        f"{config.CHANNEL_SIGNAL_FOOTER}"
    )
    return msg


def trending_message(tokens: list[dict], lookback_days: int = 1, min_gain: float = 30) -> str:
    """Format trending tokens list."""
    if not tokens:
        return "📊 *No trending tokens found right now.*\nMarket may be quiet. Try again soon."

    period = f"Last {lookback_days} day{'s' if lookback_days > 1 else ''}"
    lines = [
        f"🔥 *TOP TRENDING TOKENS*",
        f"📅 Period: {period} | Min Gain: {min_gain:.0f}%",
        f"Exchanges: Bybit • Binance • MEXC",
        f"━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    medals = ["🥇", "🥈", "🥉"] + ["🔥"] * 20

    for i, t in enumerate(tokens):
        medal  = medals[i] if i < len(medals) else "•"
        symbol = t["symbol"].replace("/USDT", "")
        ex     = t.get("exchange", "").upper()
        change = t["change_24h"]
        price  = t["price"]
        vol    = t["volume_24h"]

        bar_len = min(int(change / 10), 20)
        bar = "█" * bar_len

        lines.append(
            f"{medal} *{symbol}* `({ex})`\n"
            f"   📈 `+{change:.1f}%` {bar}\n"
            f"   💵 Price: `${price:.6f}` | Vol: `${vol:,.0f}`\n"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏰ Updated: Live data from exchanges")
    return "\n".join(lines)


def user_prefs_message(prefs: dict) -> str:
    return (
        f"⚙️ *Your Alert Settings*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Alerts: {'✅ ON' if prefs.get('alerts_enabled') else '❌ OFF'}\n"
        f"📈 Min Gain: `{prefs.get('min_gain', 30)}%`\n"
        f"📈 Max Gain: `{prefs.get('max_gain', 500)}%`\n"
        f"📅 Lookback: `{prefs.get('lookback_days', 1)} day(s)`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"You'll only be alerted once per token every {config.USER_ALERT_COOLDOWN_HOURS}h to avoid spam."
    )


def admin_stats_message(user_count: int, users: list[dict]) -> str:
    lines = [
        f"👑 *ADMIN PANEL — User Database*",
        f"━━━━━━━━━━━━━━━━━━━━━",
        f"👥 Total Active Users: `{user_count}`\n",
        f"📋 *Recent Users:*\n",
    ]
    for u in users[:30]:
        name = u.get("first_name") or "Unknown"
        username = f"@{u['username']}" if u.get("username") else "no username"
        uid = u["user_id"]
        joined = u.get("joined_at", "")[:10]
        lines.append(f"• {name} ({username}) | ID: `{uid}` | Joined: {joined}")

    if user_count > 30:
        lines.append(f"\n...and {user_count - 30} more users.")

    return "\n".join(lines)


def token_lookup_message(result: dict) -> str:
    """Format the token lookup result across exchanges."""
    base      = result["base"]
    symbol    = result["symbol"]
    exchanges = result["exchanges"]

    found_on  = [ex for ex, data in exchanges.items() if data.get("found")]
    not_found = [ex for ex, data in exchanges.items() if not data.get("found")]

    if not found_on:
        return (
            f"❌ *Token Not Found*\n\n"
            f"Could not find `{symbol}` on any of the exchanges:\n"
            f"Bybit, Binance, MEXC\n\n"
            f"Check the symbol and try again."
        )

    def change_str(val):
        if val is None:
            return "N/A"
        arrow = "🟢 +" if val >= 0 else "🔴 "
        return f"{arrow}{val:.1f}%"

    lines = [
        f"🔍 *Token Lookup: {base}*",
        f"━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    for ex_name in found_on:
        d = exchanges[ex_name]
        lines.append(
            f"🏦 *{ex_name.upper()}*\n"
            f"  💵 Price:   `${d['price']:.6f}`\n"
            f"  📈 24h:     {change_str(d.get('change_24h'))}\n"
            f"  📈 7 Days:  {change_str(d.get('change_7d'))}\n"
            f"  📈 30 Days: {change_str(d.get('change_30d'))}\n"
            f"  📊 Vol 24h: `${d.get('volume_24h', 0):,.0f}`\n"
        )

    if not_found:
        lines.append(f"⚠️ Not listed on: {', '.join(ex.upper() for ex in not_found)}\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"✅ Added `{symbol}` to your watchlist!")
    lines.append(f"I'll alert you when dump signals appear. 🎯")

    return "\n".join(lines)


def watchlist_message(items: list[dict], daily_adds_left: int) -> str:
    """Show user's current watchlist."""
    import config
    if not items:
        return (
            f"📋 *Your Watchlist is Empty*\n\n"
            f"Type a token symbol like `BLUAI` to add it.\n"
            f"I'll track it and alert you when it's ready to dump.\n\n"
            f"Daily limit: *{config.WATCHLIST_DAILY_LIMIT} tokens/day*"
        )

    lines = [
        f"📋 *Your Watchlist* ({len(items)}/{config.WATCHLIST_MAX_TOTAL})",
        f"━━━━━━━━━━━━━━━━━━━━━\n",
    ]
    for item in items:
        sym    = item["symbol"]
        added  = item.get("added_at", "")[:10]
        lines.append(f"• `{sym}` — Added: {added}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📅 Adds remaining today: *{daily_adds_left}*")
    lines.append(f"⏰ Alerts every {config.WATCHLIST_COOLDOWN_HOURS}h per token (no spam)")
    return "\n".join(lines)


def watchlist_alert_message(signal, user_prefs: dict) -> str:
    """Compact watchlist dump alert for individual user."""
    rsi_label = (
        "🔴 EXTREME"    if signal.rsi >= 90 else
        "🟠 VERY HIGH"  if signal.rsi >= 85 else
        "🟡 OVERBOUGHT" if signal.rsi >= 75 else "⚪"
    )
    vol_emoji = {"INCREASING": "📈", "DECREASING": "📉", "FLAT": "➡️"}.get(signal.volume_trend, "➡️")
    reasons_str = "\n".join(f"  • {r}" for r in signal.reasons[:4])

    return (
        f"🎯 *WATCHLIST ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Token: `{signal.symbol}` ({signal.exchange.upper()})\n"
        f"💵 Price: `${signal.price:.6f}`\n"
        f"📈 24h: `+{signal.change_24h:.1f}%`\n"
        f"📊 Vol: `${signal.volume_24h:,.0f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📉 RSI: `{signal.rsi}` {rsi_label}\n"
        f"{vol_emoji} Volume: `{signal.volume_trend}`\n"
        f"🎯 Score: `{signal.score}/100`\n\n"
        f"📋 *Signals:*\n{reasons_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 *Dump signal detected on your watchlist token!*\n"
        f"⚠️ Set Stop Loss if you're in a position."
        f"{config.CHANNEL_SIGNAL_FOOTER}"
    )
