"""
=============================================================
  CRYPTO SIGNAL BOT — MAIN BOT
  Handles all Telegram interactions:
    • User menu with buttons
    • Trending tokens
    • Per-user alert preferences
    • Admin panel (users, broadcast, channel post)
    • Background scanner
=============================================================
"""

import logging
import asyncio
import time
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler,
    filters,
)
from telegram.constants import ParseMode

import config
import database as db
from engine import ExchangeEngine, TokenSignal
import formatter

# ─────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────
import sys
import os

# UTF-8 stdout for Railway (Linux) and Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Log to file (utf-8) + stdout
_handlers = [logging.StreamHandler(sys.stdout)]
try:
    _handlers.append(logging.FileHandler("bot.log", encoding="utf-8"))
except Exception:
    pass  # /tmp or read-only fs — stdout only is fine on Railway

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_handlers,
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  CONVERSATION STATES
# ─────────────────────────────────────────
(
    ADMIN_BROADCAST_INPUT,
    ADMIN_CHANNEL_POST_INPUT,
    SET_MIN_GAIN,
    SET_MAX_GAIN,
    SET_LOOKBACK,
    WATCHLIST_ADD_INPUT,
) = range(6)

# ─────────────────────────────────────────
#  EXCHANGE ENGINE (shared)
# ─────────────────────────────────────────
engine = ExchangeEngine()


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Main menu keyboard. Admins see extra button."""
    buttons = [
        [InlineKeyboardButton("🔥 Trending Tokens",   callback_data="trending")],
        [InlineKeyboardButton("📋 My Watchlist",       callback_data="my_watchlist")],
        [InlineKeyboardButton("➕ Track a Token",      callback_data="watchlist_add")],
        [InlineKeyboardButton("⚙️ My Alert Settings", callback_data="my_settings")],
        [InlineKeyboardButton("🔔 Toggle My Alerts",  callback_data="toggle_alerts")],
        [InlineKeyboardButton("📊 Set Alert Range",   callback_data="set_range")],
        [InlineKeyboardButton("📅 Set Lookback Days", callback_data="set_lookback")],
    ]
    if is_admin(user_id):
        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)
    return InlineKeyboardMarkup(buttons)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("📢 Broadcast to All Users", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📡 Post Signal to Channel", callback_data="admin_channel_post")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ])


def trending_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Today", callback_data="trending_1"),
            InlineKeyboardButton("📅 2 Days", callback_data="trending_2"),
            InlineKeyboardButton("📅 3 Days", callback_data="trending_3"),
            InlineKeyboardButton("📅 5 Days", callback_data="trending_5"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]])


async def send_to_channel(app, message: str, signal: TokenSignal = None):
    """Send signal to Telegram channel with Check Trending button."""
    channel_buttons = [[InlineKeyboardButton("🔥 Check Trending", url=f"https://t.me/{app.bot.username}")]]
    markup = InlineKeyboardMarkup(channel_buttons)

    await app.bot.send_message(
        chat_id    = config.CHANNEL_ID,
        text       = message,
        parse_mode = ParseMode.MARKDOWN,
        reply_markup = markup,
    )


# ─────────────────────────────────────────
#  /START COMMAND
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Save user to database
    db.upsert_user(
        user_id    = user.id,
        username   = user.username or "",
        first_name = user.first_name or "",
        last_name  = user.last_name or "",
    )

    log.info(f"New user: {user.id} @{user.username}")

    await update.message.reply_text(
        config.WELCOME_MESSAGE,
        parse_mode   = ParseMode.MARKDOWN,
        reply_markup = main_menu_keyboard(user.id),
    )


# ─────────────────────────────────────────
#  /MENU COMMAND
# ─────────────────────────────────────────
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *{config.BOT_NAME} Menu*\nWhat would you like to do?",
        parse_mode   = ParseMode.MARKDOWN,
        reply_markup = main_menu_keyboard(user.id),
    )


# ─────────────────────────────────────────
#  CALLBACK QUERY HANDLER (buttons)
# ─────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user    = query.from_user
    data    = query.data
    user_id = user.id

    await query.answer()

    # ── MAIN MENU ─────────────────────────────────────────────
    if data == "main_menu":
        await query.edit_message_text(
            f"👋 *{config.BOT_NAME} Menu*\nWhat would you like to do?",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = main_menu_keyboard(user_id),
        )

    # ── TRENDING ──────────────────────────────────────────────
    elif data == "trending":
        await query.edit_message_text(
            "🔥 *Trending Tokens*\nSelect time period:",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = trending_keyboard(),
        )

    elif data.startswith("trending_"):
        days    = int(data.split("_")[1])
        prefs   = db.get_user_prefs(user_id)
        min_g   = prefs.get("min_gain", config.TRENDING_MIN_GAIN)
        max_g   = prefs.get("max_gain", config.TRENDING_MAX_GAIN)

        await query.edit_message_text(
            f"⏳ Fetching trending tokens (last {days} day{'s' if days > 1 else ''})...",
            parse_mode = ParseMode.MARKDOWN,
        )

        tokens  = engine.get_trending_tokens(
            lookback_days = days,
            min_gain      = min_g,
            max_gain      = max_g,
            top_n         = config.TRENDING_TOP_N,
        )
        msg     = formatter.trending_message(tokens, lookback_days=days, min_gain=min_g)

        await query.edit_message_text(
            msg,
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data=data)],
                [InlineKeyboardButton("🔙 Back", callback_data="trending")],
            ]),
        )

    # ── MY WATCHLIST ──────────────────────────────────────────
    elif data == "my_watchlist":
        items      = db.get_user_watchlist(user_id)
        daily_used = db.get_daily_add_count(user_id)
        daily_left = max(0, config.WATCHLIST_DAILY_LIMIT - daily_used)
        msg        = formatter.watchlist_message(items, daily_left)

        # Build remove buttons for each watchlisted token
        buttons = []
        for item in items:
            sym = item["symbol"]
            buttons.append([InlineKeyboardButton(f"❌ Remove {sym}", callback_data=f"wl_remove_{sym}")])
        buttons.append([InlineKeyboardButton("➕ Add Token", callback_data="watchlist_add")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])

        await query.edit_message_text(
            msg,
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = InlineKeyboardMarkup(buttons),
        )

    elif data == "watchlist_add":
        daily_used = db.get_daily_add_count(user_id)
        daily_left = max(0, config.WATCHLIST_DAILY_LIMIT - daily_used)

        if daily_left <= 0:
            await query.edit_message_text(
                f"⛔ *Daily Limit Reached*\n\n"
                f"You can add up to *{config.WATCHLIST_DAILY_LIMIT} tokens per day*.\n"
                f"Your limit resets at midnight UTC.\n\n"
                f"Come back tomorrow!",
                parse_mode   = ParseMode.MARKDOWN,
                reply_markup = back_keyboard(),
            )
            return

        await query.edit_message_text(
            f"➕ *Track a Token*\n\n"
            f"Type the token symbol below.\n"
            f"Example: `BLUAI` or `CSPR` or `DOGE`\n\n"
            f"I'll search all 3 exchanges, show you the price & % gains,\n"
            f"then start watching it for dump signals 24/7.\n\n"
            f"📅 Adds remaining today: *{daily_left}/{config.WATCHLIST_DAILY_LIMIT}*\n\n"
            f"Type /cancel to go back.",
            parse_mode = ParseMode.MARKDOWN,
        )
        return WATCHLIST_ADD_INPUT

    elif data.startswith("wl_remove_"):
        sym = data.replace("wl_remove_", "")
        db.remove_from_watchlist(user_id, sym)
        await query.answer(f"✅ {sym} removed from watchlist", show_alert=True)

        # Refresh watchlist view
        items      = db.get_user_watchlist(user_id)
        daily_used = db.get_daily_add_count(user_id)
        daily_left = max(0, config.WATCHLIST_DAILY_LIMIT - daily_used)
        msg        = formatter.watchlist_message(items, daily_left)
        buttons    = []
        for item in items:
            s = item["symbol"]
            buttons.append([InlineKeyboardButton(f"❌ Remove {s}", callback_data=f"wl_remove_{s}")])
        buttons.append([InlineKeyboardButton("➕ Add Token", callback_data="watchlist_add")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(buttons))

    # ── MY SETTINGS ───────────────────────────────────────────
    elif data == "my_settings":
        prefs = db.get_user_prefs(user_id)
        await query.edit_message_text(
            formatter.user_prefs_message(prefs),
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = back_keyboard(),
        )

    # ── TOGGLE ALERTS ─────────────────────────────────────────
    elif data == "toggle_alerts":
        prefs   = db.get_user_prefs(user_id)
        current = prefs.get("alerts_enabled", 1)
        new_val = 0 if current else 1
        db.update_user_prefs(user_id, alerts_enabled=new_val)
        status = "✅ ON" if new_val else "❌ OFF"
        await query.edit_message_text(
            f"🔔 Alerts turned *{status}*\n\nYou can change this anytime from the menu.",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = back_keyboard(),
        )

    # ── SET ALERT RANGE ───────────────────────────────────────
    elif data == "set_range":
        prefs = db.get_user_prefs(user_id)
        await query.edit_message_text(
            f"📊 *Set Your Alert Range*\n\n"
            f"Current: Min `{prefs.get('min_gain',30)}%` → Max `{prefs.get('max_gain',500)}%`\n\n"
            f"Choose a preset or type custom below:",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("30–100%",  callback_data="range_30_100"),
                    InlineKeyboardButton("30–200%",  callback_data="range_30_200"),
                    InlineKeyboardButton("30–500%",  callback_data="range_30_500"),
                ],
                [
                    InlineKeyboardButton("50–300%",  callback_data="range_50_300"),
                    InlineKeyboardButton("100–600%", callback_data="range_100_600"),
                    InlineKeyboardButton("20–600%",  callback_data="range_20_600"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
            ]),
        )

    elif data.startswith("range_"):
        parts   = data.split("_")
        min_g   = float(parts[1])
        max_g   = float(parts[2])
        db.update_user_prefs(user_id, min_gain=min_g, max_gain=max_g)
        await query.edit_message_text(
            f"✅ Alert range set to *{min_g:.0f}% – {max_g:.0f}%*\n\n"
            f"You'll be alerted when trending tokens gain between {min_g:.0f}% and {max_g:.0f}%.",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = back_keyboard(),
        )

    # ── SET LOOKBACK ──────────────────────────────────────────
    elif data == "set_lookback":
        prefs = db.get_user_prefs(user_id)
        await query.edit_message_text(
            f"📅 *Set Lookback Window*\n\n"
            f"Current: `{prefs.get('lookback_days', 1)} day(s)`\n\n"
            f"How many days back should I check for trending tokens?",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("1 Day",  callback_data="lookback_1"),
                    InlineKeyboardButton("2 Days", callback_data="lookback_2"),
                    InlineKeyboardButton("3 Days", callback_data="lookback_3"),
                    InlineKeyboardButton("5 Days", callback_data="lookback_5"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
            ]),
        )

    elif data.startswith("lookback_"):
        days = int(data.split("_")[1])
        db.update_user_prefs(user_id, lookback_days=days)
        await query.edit_message_text(
            f"✅ Lookback window set to *{days} day{'s' if days > 1 else ''}*",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = back_keyboard(),
        )

    # ── ADMIN PANEL ───────────────────────────────────────────
    elif data == "admin_panel":
        if not is_admin(user_id):
            await query.answer("⛔ Access denied.", show_alert=True)
            return
        await query.edit_message_text(
            "👑 *Admin Panel*\nSelect an action:",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = admin_panel_keyboard(),
        )

    elif data == "admin_users":
        if not is_admin(user_id):
            await query.answer("⛔ Access denied.", show_alert=True)
            return
        users = db.get_all_users()
        count = db.get_user_count()
        msg   = formatter.admin_stats_message(count, users)
        await query.edit_message_text(
            msg,
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]),
        )

    elif data == "admin_broadcast":
        if not is_admin(user_id):
            await query.answer("⛔ Access denied.", show_alert=True)
            return
        context.user_data["admin_action"] = "broadcast"
        await query.edit_message_text(
            "📢 *Broadcast to All Users*\n\nType your message below.\n"
            "It will be sent to ALL active users.\n\n"
            "Type /cancel to abort.",
            parse_mode = ParseMode.MARKDOWN,
        )
        return ADMIN_BROADCAST_INPUT

    elif data == "admin_channel_post":
        if not is_admin(user_id):
            await query.answer("⛔ Access denied.", show_alert=True)
            return
        context.user_data["admin_action"] = "channel_post"
        await query.edit_message_text(
            "📡 *Post to Channel*\n\nType your signal message.\n"
            "I'll format it and post it to the channel with a *Check Trending* button.\n\n"
            "Type /cancel to abort.",
            parse_mode = ParseMode.MARKDOWN,
        )
        return ADMIN_CHANNEL_POST_INPUT


# ─────────────────────────────────────────
#  WATCHLIST TOKEN INPUT HANDLER
# ─────────────────────────────────────────
async def watchlist_add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User types a token symbol — look it up and add to watchlist."""
    user_id = update.effective_user.id
    raw     = update.message.text.strip().upper().replace("/USDT", "")

    # Validate input
    if len(raw) < 2 or len(raw) > 15 or not raw.isalnum():
        await update.message.reply_text(
            "❌ Invalid symbol. Please type just the token name, e.g. `BLUAI` or `CSPR`",
            parse_mode = ParseMode.MARKDOWN,
        )
        return WATCHLIST_ADD_INPUT

    searching_msg = await update.message.reply_text(
        f"🔍 Searching for `{raw}` across Bybit, Binance & MEXC...",
        parse_mode = ParseMode.MARKDOWN,
    )

    # Look up token across all exchanges
    result = engine.lookup_token(raw)
    found_on = [ex for ex, data in result["exchanges"].items() if data.get("found")]

    if not found_on:
        await searching_msg.edit_text(
            f"❌ *`{raw}` not found* on any exchange.\n\n"
            f"Check the symbol spelling and try again.\n"
            f"Type another symbol or /cancel to go back.",
            parse_mode = ParseMode.MARKDOWN,
        )
        return WATCHLIST_ADD_INPUT

    # Try to add to watchlist
    symbol = result["symbol"]
    success, reason = db.add_to_watchlist(user_id, symbol)

    msg = formatter.token_lookup_message(result)

    if not success:
        if reason == "daily_limit":
            msg += f"\n\n⛔ *Daily limit reached* ({config.WATCHLIST_DAILY_LIMIT}/day). Try again tomorrow."
        elif reason == "max_total":
            msg += f"\n\n⛔ *Watchlist full* ({config.WATCHLIST_MAX_TOTAL} max). Remove a token first."
        elif reason == "already_exists":
            msg += f"\n\n⚠️ `{symbol}` is already on your watchlist!"
    else:
        msg = msg  # Already includes "Added to watchlist!" in formatter

    await searching_msg.edit_text(
        msg,
        parse_mode   = ParseMode.MARKDOWN,
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 View My Watchlist", callback_data="my_watchlist")],
            [InlineKeyboardButton("➕ Add Another",       callback_data="watchlist_add")],
            [InlineKeyboardButton("🔙 Main Menu",         callback_data="main_menu")],
        ]),
    )
    return ConversationHandler.END


# ─────────────────────────────────────────
#  ADMIN CONVERSATION HANDLERS
# ─────────────────────────────────────────
async def admin_broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin types broadcast message."""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    raw_msg = update.message.text
    users   = db.get_all_users(active_only=True)
    count   = 0
    failed  = 0

    status_msg = await update.message.reply_text(f"📢 Sending to {len(users)} users...")

    for u in users:
        try:
            await context.bot.send_message(
                chat_id    = u["user_id"],
                text       = f"📢 *Message from Admin:*\n\n{raw_msg}",
                parse_mode = ParseMode.MARKDOWN,
            )
            count += 1
            await asyncio.sleep(0.05)  # Avoid rate limits
        except Exception as e:
            log.warning(f"Broadcast failed for {u['user_id']}: {e}")
            failed += 1

    await status_msg.edit_text(
        f"✅ Broadcast complete!\n"
        f"Sent: {count} | Failed: {failed}",
        reply_markup = back_keyboard(),
    )
    return ConversationHandler.END


async def admin_channel_post_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin types channel message — bot formats and posts."""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    raw_msg = update.message.text
    formatted = (
        f"📡 *SIGNAL ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{raw_msg}\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
        f"{config.CHANNEL_SIGNAL_FOOTER}"
    )

    try:
        await send_to_channel(context.application, formatted)
        await update.message.reply_text(
            "✅ Message posted to channel with *Check Trending* button!",
            parse_mode   = ParseMode.MARKDOWN,
            reply_markup = back_keyboard(),
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error posting to channel:\n`{e}`", parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END


# ─────────────────────────────────────────
#  BACKGROUND SCANNER
# ─────────────────────────────────────────
async def scanner_loop(app):
    """
    Runs in background. Every SCAN_INTERVAL seconds:
    1. Scans all exchanges for pumping tokens
    2. Runs full signal analysis
    3. Posts strong signals to channel
    4. DMs individual users based on their preferences
    """
    log.info("🔍 Background scanner started")

    while True:
        try:
            log.info(f"⏰ Running scan — {datetime.utcnow().strftime('%H:%M UTC')}")

            for ex_name in engine.active_exchange_names():
                pumping = engine.get_pumping_tokens(ex_name)
                log.info(f"  {ex_name.upper()}: {len(pumping)} tokens pumping")

                for token_data in pumping[:20]:  # Top 20 per exchange
                    symbol = token_data["symbol"]
                    change = token_data["change_24h"]

                    # Full analysis
                    signal = engine.full_analysis(ex_name, token_data)
                    if not signal:
                        continue

                    # ── Post to channel (if strong signal, not spamming) ──
                    if (signal.score >= config.SCORE_SHORT and
                            db.can_post_to_channel(symbol, ex_name)):
                        try:
                            msg = formatter.signal_message(signal)
                            await send_to_channel(app, msg, signal)
                            db.mark_channel_posted(symbol, ex_name)
                            db.log_channel_signal(symbol, ex_name, signal.signal_type, signal.score)
                            log.info(f"  📡 Posted to channel: {symbol} score={signal.score}")
                        except Exception as e:
                            log.error(f"  Channel post error: {e}")

                    # ── Alert individual users based on their preferences ──
                    users_to_alert = db.get_users_to_alert(symbol, ex_name, change)
                    for uid in users_to_alert:
                        try:
                            prefs = db.get_user_prefs(uid)
                            lookback = prefs.get("lookback_days", 1)

                            # Build compact user alert
                            user_msg = (
                                f"🔔 *Personal Alert*\n"
                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💰 `{symbol}` on *{ex_name.upper()}*\n"
                                f"📈 Gain: `+{change:.1f}%`\n"
                                f"💵 Price: `${signal.price:.6f}`\n"
                                f"📉 RSI: `{signal.rsi}` | Vol: `{signal.volume_trend}`\n"
                                f"🎯 Score: `{signal.score}/100`\n"
                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                f"Your alert range: {prefs.get('min_gain',30):.0f}% – {prefs.get('max_gain',500):.0f}%"
                            )

                            check_btn = InlineKeyboardMarkup([[
                                InlineKeyboardButton("🔥 Check Trending", callback_data="trending")
                            ]])

                            await app.bot.send_message(
                                chat_id      = uid,
                                text         = user_msg,
                                parse_mode   = ParseMode.MARKDOWN,
                                reply_markup = check_btn,
                            )
                            db.set_user_alert_cooldown(uid, symbol, ex_name)
                            await asyncio.sleep(0.05)
                        except Exception as e:
                            log.warning(f"  User alert error ({uid}): {e}")

                    await asyncio.sleep(0.3)  # Rate limit between tokens

        except Exception as e:
            log.error(f"Scanner error: {e}")

        log.info(f"💤 Next scan in {config.SCAN_INTERVAL}s")
        await asyncio.sleep(config.SCAN_INTERVAL)


# ─────────────────────────────────────────
#  WATCHLIST BACKGROUND SCANNER
# ─────────────────────────────────────────
async def watchlist_scanner_loop(app):
    """
    Separate loop that scans user watchlist tokens every WATCHLIST_SCAN_INTERVAL seconds.
    Alerts individual users when their watched token shows dump signals.
    """
    log.info("📋 Watchlist scanner started")

    while True:
        try:
            entries = db.get_all_watchlist_entries()

            if entries:
                log.info(f"📋 Checking {len(entries)} watchlist entries...")

                # Deduplicate symbols — only check each symbol once
                unique_symbols = list({e["symbol"] for e in entries})

                for symbol in unique_symbols:
                    try:
                        signal = engine.check_watchlist_token(symbol)

                        if not signal:
                            continue

                        # Only alert if score meets threshold
                        if signal.score < config.WATCHLIST_ALERT_SCORE:
                            continue

                        # Find all users watching this token
                        watchers = [e["user_id"] for e in entries if e["symbol"] == symbol]

                        for uid in watchers:
                            if not db.can_watchlist_alert(uid, symbol):
                                continue  # On cooldown

                            try:
                                prefs = db.get_user_prefs(uid)
                                msg   = formatter.watchlist_alert_message(signal, prefs)

                                await app.bot.send_message(
                                    chat_id    = uid,
                                    text       = msg,
                                    parse_mode = ParseMode.MARKDOWN,
                                    reply_markup = InlineKeyboardMarkup([
                                        [InlineKeyboardButton("📋 My Watchlist", callback_data="my_watchlist")],
                                        [InlineKeyboardButton("🔥 Trending",     callback_data="trending")],
                                    ]),
                                )
                                db.set_watchlist_alert_cooldown(uid, symbol)
                                log.info(f"  📋 Watchlist alert → user {uid}: {symbol} score={signal.score}")
                                await asyncio.sleep(0.05)

                            except Exception as e:
                                log.warning(f"  Watchlist alert error (uid={uid}): {e}")

                        await asyncio.sleep(0.5)  # Between symbols

                    except Exception as e:
                        log.error(f"  Watchlist check error [{symbol}]: {e}")

        except Exception as e:
            log.error(f"Watchlist scanner error: {e}")

        await asyncio.sleep(config.WATCHLIST_SCAN_INTERVAL)


# ─────────────────────────────────────────
#  MAIN — BUILD AND RUN BOT
# ─────────────────────────────────────────
def main():
    # Initialize database
    db.init_db()

    # Build app
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Watchlist conversation handler
    watchlist_conv = ConversationHandler(
        entry_points = [CallbackQueryHandler(button_handler, pattern="^watchlist_add$")],
        states = {
            WATCHLIST_ADD_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, watchlist_add_receive)],
        },
        fallbacks = [CommandHandler("cancel", cancel_conversation)],
    )

    # Admin conversation handler (broadcast + channel post)
    admin_conv = ConversationHandler(
        entry_points = [CallbackQueryHandler(button_handler, pattern="^admin_(broadcast|channel_post)$")],
        states = {
            ADMIN_BROADCAST_INPUT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_receive)],
            ADMIN_CHANNEL_POST_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_channel_post_receive)],
        },
        fallbacks = [CommandHandler("cancel", cancel_conversation)],
    )

    # Register handlers (order matters — conversations first)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu",  menu))
    app.add_handler(watchlist_conv)
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    # Set bot commands (shows in Telegram menu)
    async def post_init(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("menu",  "Open main menu"),
            BotCommand("cancel", "Cancel current action"),
        ])
        # Start both background scanners
        asyncio.create_task(scanner_loop(app))
        asyncio.create_task(watchlist_scanner_loop(app))

    app.post_init = post_init

    # Run
    log.info(f"🤖 {config.BOT_NAME} starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
