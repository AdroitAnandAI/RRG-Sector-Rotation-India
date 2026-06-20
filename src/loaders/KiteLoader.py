"""
Zerodha Kite Connect Data Loader for RRG Charts

Mirrors the interface of AngelOneLoader so the rest of the app does not need to
know which broker is supplying the data:

    loader = KiteLoader(config, tf="weekly", period=200)
    df = loader.get(symbol, token)   # returns OHLC DataFrame (token is ignored)
    loader.close()

The AngelOne `token` argument is accepted for signature compatibility but is NOT
used -- Kite has its own `instrument_token` namespace, so this loader resolves
the symbol to a Kite instrument token internally using the Kite instrument dump.

Requires a Kite Connect app with the historical-data add-on and a valid
(daily) access token. See `kite_login.py` to generate one.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .ohlc_utils import resample_ohlc

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    """Normalise an index name for matching: uppercase, alphanumerics only."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


# Maps an AngelOne-style index name (normalised) to the Kite index tradingsymbol
# (normalised). Only entries that genuinely differ between the two providers
# need to be listed here; everything else matches after normalisation.
INDEX_ALIASES = {
    _norm("Nifty Financial Services"): _norm("NIFTY FIN SERVICE"),
    _norm("Nifty Fin Service"): _norm("NIFTY FIN SERVICE"),
    _norm("Nifty Infrastructure"): _norm("NIFTY INFRA"),
    _norm("Nifty Midcap 50"): _norm("NIFTY MIDCAP 50"),
    _norm("Nifty Next 50"): _norm("NIFTY NEXT 50"),
}


class KiteLoader:
    """Load Daily/Weekly/Monthly OHLC data from Zerodha Kite Connect."""

    # Kite only exposes a "day" historical interval; weekly/monthly are resampled.
    KITE_INTERVAL = "day"
    # Kite caps a single "day" request at ~2000 candles.
    MAX_DAYS_PER_REQUEST = 2000

    def __init__(
        self,
        config: dict,
        tf: Optional[str] = "daily",
        end_date: Optional[datetime] = None,
        period: int = 160,
    ):
        self.closed = False
        self.tf = tf if tf else "daily"
        self.end_date = end_date if end_date else datetime.now()
        self.period = period

        self.api_key = config.get("KITE_API_KEY") or config.get("API_KEY")
        self.access_token = config.get("KITE_ACCESS_TOKEN") or config.get("ACCESS_TOKEN")
        self.exchange = config.get("EXCHANGE", "NSE")

        if not self.api_key or not self.access_token:
            raise ValueError(
                "Missing Kite credentials: KITE_API_KEY and KITE_ACCESS_TOKEN are required"
            )

        # Imported lazily so AngelOne-only users don't need kiteconnect installed.
        try:
            from kiteconnect import KiteConnect
        except ImportError as e:
            raise ImportError(
                "The 'kiteconnect' package is required to use the Kite data provider. "
                "Install it with: pip install kiteconnect"
            ) from e

        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)

        # symbol/name -> Kite instrument_token
        self._eq_map = {}
        self._idx_map = {}
        self._token_cache = {}
        self._load_instruments()

    def _load_instruments(self):
        """Build equity and index lookup tables from the Kite instrument dump."""
        try:
            instruments = self.kite.instruments(self.exchange)
        except Exception as e:
            logger.error(f"Failed to fetch Kite instruments for {self.exchange}: {e}")
            raise

        for inst in instruments:
            seg = inst.get("segment", "")
            tsym = inst.get("tradingsymbol", "")
            name = inst.get("name", "")
            token = inst.get("instrument_token")
            itype = inst.get("instrument_type", "")

            if seg == "INDICES":
                self._idx_map[_norm(tsym)] = token
                if name:
                    self._idx_map[_norm(name)] = token
            elif itype == "EQ":
                # ETFs are also instrument_type "EQ" on Kite, which is what we want.
                self._eq_map[tsym.upper()] = token

        logger.info(
            f"Kite instruments loaded: {len(self._eq_map)} equities, "
            f"{len(self._idx_map)} index keys ({self.exchange})"
        )

    def _resolve_token(self, symbol: str) -> Optional[int]:
        """Resolve an AngelOne-style symbol to a Kite instrument_token."""
        if symbol in self._token_cache:
            return self._token_cache[symbol]

        token = None
        s = (symbol or "").strip()

        if s.upper().endswith("-EQ"):
            # Equity / ETF: "RELIANCE-EQ" -> Kite tradingsymbol "RELIANCE"
            base = s[:-3].upper()
            token = self._eq_map.get(base)
        else:
            # Treat as an index name.
            key = _norm(s)
            key = INDEX_ALIASES.get(key, key)
            token = self._idx_map.get(key)
            if token is None:
                # Fall back to a contains match (shortest candidate wins).
                candidates = [
                    (k, v) for k, v in self._idx_map.items()
                    if key and (key in k or k in key)
                ]
                if candidates:
                    candidates.sort(key=lambda kv: len(kv[0]))
                    token = candidates[0][1]

        if token is None:
            # Last resort: maybe it is an equity passed without the -EQ suffix.
            token = self._eq_map.get(s.upper())

        if token is None:
            logger.warning(f"Could not resolve Kite instrument token for '{symbol}'")
        else:
            self._token_cache[symbol] = token
        return token

    def get(self, symbol: str, token: str = None) -> Optional[pd.DataFrame]:
        """
        Returns OHLC data for `symbol` as a DataFrame.

        The `token` argument is the AngelOne token and is ignored; the Kite
        instrument token is resolved from `symbol` internally.
        """
        instrument_token = self._resolve_token(symbol)
        if instrument_token is None:
            return None

        try:
            if self.tf == "daily":
                days_back = self.period + 50
            elif self.tf == "weekly":
                days_back = (self.period + 10) * 7
            else:  # monthly
                days_back = (self.period + 10) * 30

            # Kite caps a single daily request, so clamp the lookback window.
            days_back = min(days_back, self.MAX_DAYS_PER_REQUEST)
            start_date = self.end_date - timedelta(days=days_back)

            candles = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=start_date,
                to_date=self.end_date,
                interval=self.KITE_INTERVAL,
            )

            if not candles:
                logger.warning(f"No data returned for {symbol}")
                return None

            df_data = []
            for c in candles:
                df_data.append({
                    'Date': pd.to_datetime(c['date']),
                    'Open': float(c['open']),
                    'High': float(c['high']),
                    'Low': float(c['low']),
                    'Close': float(c['close']),
                    'Volume': float(c.get('volume', 0) or 0),
                })

            df = pd.DataFrame(df_data)
            df.set_index('Date', inplace=True)
            # Kite returns tz-aware timestamps; drop tz to match AngelOne output.
            try:
                df.index = df.index.tz_localize(None)
            except (TypeError, AttributeError):
                pass
            df.sort_index(inplace=True)

            return resample_ohlc(df, self.tf, self.period, symbol)

        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def close(self):
        """No persistent session to tear down for Kite; kept for interface parity."""
        self.closed = True
