"""
=============================================================
  EXCHANGE ENGINE
  Fetches data from Bybit, Binance, MEXC
  Calculates RSI, Volume Trend, Funding Rate
  No TradingView needed — pure Python
=============================================================
"""

import ccxt
import numpy as np
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import config

log = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  TOKEN SIGNAL DATA CLASS
# ─────────────────────────────────────────
@dataclass
class TokenSignal:
    symbol:        str
    exchange:      str
    price:         float
    change_24h:    float
    volume_24h:    float
    rsi:           float
    volume_trend:  str            # INCREASING | DECREASING | FLAT
    funding_rate:  Optional[float]
    score:         int
    signal_type:   str            # DUMP_ALERT | SHORT_SETUP | PUMP_WATCH | MONITOR
    reasons:       list = field(default_factory=list)
    x_mentions:    int = 0
    timestamp:     str = ""

    def __post_init__(self):
        from datetime import datetime
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


# ─────────────────────────────────────────
#  RSI CALCULATOR (pure Python/NumPy)
# ─────────────────────────────────────────
def calculate_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    closes = np.array(closes, dtype=float)
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


# ─────────────────────────────────────────
#  VOLUME TREND ANALYZER
# ─────────────────────────────────────────
def analyze_volume_trend(volumes: list) -> str:
    if len(volumes) < 6:
        return "FLAT"
    recent  = np.mean(volumes[-3:])
    earlier = np.mean(volumes[-6:-3])
    if earlier == 0:
        return "FLAT"
    change = (recent - earlier) / earlier * 100
    if change > 20:
        return "INCREASING"
    elif change < -20:
        return "DECREASING"
    return "FLAT"


# ─────────────────────────────────────────
#  SIGNAL SCORER
# ─────────────────────────────────────────
def score_token(change_24h, rsi, volume_trend, funding_rate, x_mentions=0, is_new_listing=False):
    score = 0
    reasons = []

    # Price change
    if change_24h >= 50:
        score += 25; reasons.append(f"🚀 Massive pump +{change_24h:.1f}%")
    elif change_24h >= 30:
        score += 20; reasons.append(f"🔥 Strong pump +{change_24h:.1f}%")
    elif change_24h >= 15:
        score += 12; reasons.append(f"📈 Pumping +{change_24h:.1f}%")

    # RSI
    if rsi >= 90:
        score += 25; reasons.append(f"⚠️ RSI EXTREME: {rsi} — Dump imminent")
    elif rsi >= 85:
        score += 20; reasons.append(f"🔴 RSI Very High: {rsi} — Strong short signal")
    elif rsi >= 75:
        score += 12; reasons.append(f"🟡 RSI Overbought: {rsi}")
    elif rsi <= 30:
        score += 8;  reasons.append(f"💚 RSI Oversold: {rsi} — Bounce possible")

    # Volume trend
    if volume_trend == "DECREASING" and change_24h > 15:
        score += 20; reasons.append("📉 Volume DROPPING while price high — Dump signal!")
    elif volume_trend == "INCREASING":
        score += 10; reasons.append("📊 Volume INCREASING — Real momentum")
    else:
        score += 3;  reasons.append("➡️ Volume flat")

    # Funding rate
    if funding_rate is not None:
        if funding_rate > 0.002:
            score += 15; reasons.append(f"💸 Funding VERY HIGH: {funding_rate*100:.3f}% — Longs overleveraged")
        elif funding_rate > config.FUNDING_RATE_HIGH:
            score += 10; reasons.append(f"💸 Funding HIGH: {funding_rate*100:.3f}%")
        elif funding_rate < -0.001:
            score += 5;  reasons.append(f"💸 Negative funding: {funding_rate*100:.3f}% — Shorts overleveraged")

    # X mentions
    if x_mentions >= 5:
        score += 15; reasons.append(f"🐦 {x_mentions} influencer mentions — Going viral!")
    elif x_mentions >= 2:
        score += 8;  reasons.append(f"🐦 {x_mentions} influencer mentions")
    elif x_mentions == 1:
        score += 4;  reasons.append("🐦 1 influencer mention")

    # New listing
    if is_new_listing:
        score += 10; reasons.append("🆕 New listing — High volatility expected")

    # Determine signal type
    if rsi >= config.RSI_EXTREME and volume_trend == "DECREASING" and change_24h >= 20:
        signal_type = "DUMP_ALERT"
        score = max(score, 85)
    elif score >= config.SCORE_SHORT and rsi >= config.RSI_OVERBOUGHT:
        signal_type = "SHORT_SETUP"
    elif score >= config.SCORE_WATCH:
        signal_type = "PUMP_WATCH"
    else:
        signal_type = "MONITOR"

    return score, reasons, signal_type


# ─────────────────────────────────────────
#  EXCHANGE CONNECTOR
# ─────────────────────────────────────────
class ExchangeEngine:

    def __init__(self):
        self.exchanges = {}
        self._init_exchanges()

    def _init_exchanges(self):
        configs = {
            "bybit":   ccxt.bybit({"enableRateLimit": True}),
            "binance": ccxt.binance({"enableRateLimit": True}),
            "mexc":    ccxt.mexc({"enableRateLimit": True}),
        }
        for name, ex in configs.items():
            if config.EXCHANGES.get(name):
                self.exchanges[name] = ex
                log.info(f"✅ Connected: {name.upper()}")

    def get_pumping_tokens(self, exchange_name: str, min_change: float = None) -> list[dict]:
        """Fetch all USDT pairs pumping above threshold."""
        min_change = min_change or config.MIN_PRICE_CHANGE_24H
        ex = self.exchanges.get(exchange_name)
        if not ex:
            return []
        try:
            tickers = ex.fetch_tickers()
            pumping = []
            for symbol, t in tickers.items():
                if not symbol.endswith("/USDT"):
                    continue
                change = t.get("percentage") or 0
                volume = t.get("quoteVolume") or 0
                price  = t.get("last") or 0
                if change >= min_change and volume >= config.MIN_VOLUME_USDT and price > 0:
                    pumping.append({
                        "symbol":    symbol,
                        "price":     price,
                        "change_24h": change,
                        "volume_24h": volume,
                    })
            pumping.sort(key=lambda x: x["change_24h"], reverse=True)
            return pumping
        except Exception as e:
            log.error(f"Ticker fetch error [{exchange_name}]: {e}")
            return []

    def get_trending_tokens(self, lookback_days: int = 1, min_gain: float = None, max_gain: float = None, top_n: int = None) -> list[dict]:
        """
        Get top trending tokens across all enabled exchanges.
        Deduplicates by symbol, picks best performer per token.
        """
        min_gain = min_gain or config.TRENDING_MIN_GAIN
        max_gain = max_gain or config.TRENDING_MAX_GAIN
        top_n    = top_n or config.TRENDING_TOP_N

        all_tokens = {}

        for ex_name in self.exchanges:
            tokens = self.get_pumping_tokens(ex_name, min_change=min_gain)
            for t in tokens:
                if t["change_24h"] > max_gain:
                    continue
                sym = t["symbol"]
                # Keep the best performer across exchanges
                if sym not in all_tokens or t["change_24h"] > all_tokens[sym]["change_24h"]:
                    all_tokens[sym] = {**t, "exchange": ex_name}

        sorted_tokens = sorted(all_tokens.values(), key=lambda x: x["change_24h"], reverse=True)
        return sorted_tokens[:top_n]

    def get_ohlcv(self, exchange_name: str, symbol: str) -> tuple[list, list]:
        """Get close prices and volumes for RSI + volume trend."""
        ex = self.exchanges.get(exchange_name)
        if not ex:
            return [], []
        try:
            ohlcv   = ex.fetch_ohlcv(symbol, timeframe="1h", limit=50)
            closes  = [c[4] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            return closes, volumes
        except Exception as e:
            log.warning(f"OHLCV error [{exchange_name}:{symbol}]: {e}")
            return [], []

    def get_funding_rate(self, exchange_name: str, symbol: str) -> Optional[float]:
        """Get perpetual futures funding rate."""
        ex = self.exchanges.get(exchange_name)
        if not ex:
            return None
        try:
            base        = symbol.replace("/USDT", "")
            perp_symbol = f"{base}/USDT:USDT"
            funding     = ex.fetch_funding_rate(perp_symbol)
            return funding.get("fundingRate")
        except Exception:
            return None

    def full_analysis(self, exchange_name: str, token_data: dict, x_mentions: int = 0) -> Optional[TokenSignal]:
        """Full signal analysis on a single token."""
        symbol = token_data["symbol"]
        closes, volumes = self.get_ohlcv(exchange_name, symbol)
        if not closes:
            return None

        rsi          = calculate_rsi(closes)
        volume_trend = analyze_volume_trend(volumes)
        funding_rate = self.get_funding_rate(exchange_name, symbol)

        score, reasons, signal_type = score_token(
            change_24h   = token_data["change_24h"],
            rsi          = rsi,
            volume_trend = volume_trend,
            funding_rate = funding_rate,
            x_mentions   = x_mentions,
        )

        return TokenSignal(
            symbol       = symbol,
            exchange     = exchange_name,
            price        = token_data["price"],
            change_24h   = token_data["change_24h"],
            volume_24h   = token_data["volume_24h"],
            rsi          = rsi,
            volume_trend = volume_trend,
            funding_rate = funding_rate,
            score        = score,
            signal_type  = signal_type,
            reasons      = reasons,
            x_mentions   = x_mentions,
        )

    def active_exchange_names(self):
        return list(self.exchanges.keys())

    def lookup_token(self, token_input: str) -> dict:
        """
        Search for a token across all exchanges.
        Returns price, 24h/7d/30d change on each exchange.
        token_input: e.g. "BLUAI" or "BLUAI/USDT"
        """
        # Normalize symbol
        base = token_input.upper().replace("/USDT", "").strip()
        symbol = f"{base}/USDT"

        results = {}

        for ex_name, ex in self.exchanges.items():
            try:
                # Check if symbol exists on this exchange
                ticker = ex.fetch_ticker(symbol)
                if not ticker or not ticker.get("last"):
                    continue

                price     = ticker.get("last") or 0
                change_24h = ticker.get("percentage") or 0
                volume_24h = ticker.get("quoteVolume") or 0

                # Try to get 7d and 30d data from OHLCV
                change_7d  = None
                change_30d = None

                try:
                    # 7 day: daily candles, 8 candles back
                    ohlcv_7d = ex.fetch_ohlcv(symbol, timeframe="1d", limit=8)
                    if ohlcv_7d and len(ohlcv_7d) >= 7:
                        open_7d   = ohlcv_7d[-7][1]  # Open 7 days ago
                        if open_7d and open_7d > 0:
                            change_7d = ((price - open_7d) / open_7d) * 100
                except Exception:
                    pass

                try:
                    # 30 day: daily candles, 31 candles back
                    ohlcv_30d = ex.fetch_ohlcv(symbol, timeframe="1d", limit=32)
                    if ohlcv_30d and len(ohlcv_30d) >= 30:
                        open_30d  = ohlcv_30d[-30][1]
                        if open_30d and open_30d > 0:
                            change_30d = ((price - open_30d) / open_30d) * 100
                except Exception:
                    pass

                results[ex_name] = {
                    "symbol":     symbol,
                    "exchange":   ex_name,
                    "price":      price,
                    "change_24h": change_24h,
                    "change_7d":  change_7d,
                    "change_30d": change_30d,
                    "volume_24h": volume_24h,
                    "found":      True,
                }

            except Exception:
                # Token not found on this exchange
                results[ex_name] = {"exchange": ex_name, "found": False}

        return {"base": base, "symbol": symbol, "exchanges": results}

    def check_watchlist_token(self, symbol: str) -> dict:
        """
        Full signal analysis on a specific token across all exchanges.
        Used by the watchlist scanner.
        Returns best signal found (highest score).
        """
        base = symbol.replace("/USDT", "").upper()
        sym  = f"{base}/USDT"
        best_signal = None

        for ex_name, ex in self.exchanges.items():
            try:
                ticker = ex.fetch_ticker(sym)
                if not ticker or not ticker.get("last"):
                    continue

                token_data = {
                    "symbol":     sym,
                    "price":      ticker.get("last") or 0,
                    "change_24h": ticker.get("percentage") or 0,
                    "volume_24h": ticker.get("quoteVolume") or 0,
                }

                signal = self.full_analysis(ex_name, token_data)
                if signal and (best_signal is None or signal.score > best_signal.score):
                    best_signal = signal

            except Exception:
                continue

        return best_signal
