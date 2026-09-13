"""ETF valuation and blocked-account interest helpers for the dashboard."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.request import Request

import pandas as pd

ALPHA_VANTAGE_API_KEY_ENV = "ALPHA_VANTAGE_API_KEY"
ALPHA_VANTAGE_DAILY_URL = "https://www.alphavantage.co/query"
YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart"
BOERSE_FRANKFURT_QUOTE_URL = "https://api.boerse-frankfurt.de/v1/data/quote_box/single"
HTTP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
INVESTMENT_ORDER_FEE = 0.85
KLARNA_BLOCKED_PRINCIPAL = 6000.0
KLARNA_ANNUAL_INTEREST_RATE = 0.0279
KLARNA_INTEREST_START_DATE = pd.Timestamp("2026-03-11")
KLARNA_INTEREST_END_DATE = pd.Timestamp("2029-03-11")

HOLDING_COLUMNS = [
    "isin",
    "symbol",
    "name",
    "units",
    "cost_basis",
    "transactions",
    "latest_purchase_date",
]
PRICE_COLUMNS = ["symbol", "date", "close", "fetched_at"]
VALUATION_COLUMNS = [
    *HOLDING_COLUMNS,
    "market_price",
    "market_price_date",
    "market_value",
    "gain_loss",
    "valuation_source",
]


@dataclass(frozen=True)
class EtfInstrument:
    """ETF identity needed to map Santander PDF rows to market prices."""

    isin: str
    symbol: str
    name: str


@dataclass(frozen=True)
class InvestmentOrder:
    """One parsed ETF order from a Santander statement transaction."""

    isin: str
    side: str
    units: float


class MarketPriceError(RuntimeError):
    """Raised when a market price provider response cannot be used."""


ETF_INSTRUMENTS: dict[str, EtfInstrument] = {
    "IE00B5BMR087": EtfInstrument(
        isin="IE00B5BMR087",
        symbol="SXR8.DEX",
        name="iShares Core S&P 500 UCITS ETF",
    ),
    "IE00BK5BQT80": EtfInstrument(
        isin="IE00BK5BQT80",
        symbol="VWCE.DEX",
        name="Vanguard FTSE All-World UCITS ETF",
    ),
    "IE00BK5BQZ41": EtfInstrument(
        isin="IE00BK5BQZ41",
        symbol="VGEK.DEX",
        name="Vanguard FTSE Developed Asia Pacific ex Japan UCITS ETF",
    ),
    "LU0274209237": EtfInstrument(
        isin="LU0274209237",
        symbol="XMEU.DEX",
        name="Xtrackers MSCI Europe UCITS ETF",
    ),
}
ETF_INSTRUMENTS_BY_SYMBOL = {
    instrument.symbol: instrument for instrument in ETF_INSTRUMENTS.values()
}
YAHOO_SYMBOL_OVERRIDES = {
    "SXR8.DEX": "SXR8.DE",
    "VWCE.DEX": "VWCE.DE",
    "VGEK.DEX": "VGEK.DE",
    "XMEU.DEX": "XMEU.DE",
}

PriceFetcher = Callable[[str, str], pd.DataFrame]
_ORDER_PATTERN = re.compile(
    r"\bISIN\s+(?P<isin>[A-Z0-9]{12})\b.*?"
    r"\b(?P<side>KAUF|VERKAUF)\s+(?P<units>[0-9][0-9\s.,]*)",
    re.IGNORECASE | re.DOTALL,
)


def _empty_holdings_frame() -> pd.DataFrame:
    """Return an empty ETF holdings frame with the dashboard schema."""
    return pd.DataFrame(columns=HOLDING_COLUMNS)


def _empty_price_frame() -> pd.DataFrame:
    """Return an empty market-price frame with the dashboard schema."""
    return pd.DataFrame(columns=PRICE_COLUMNS)


def _empty_valuation_frame() -> pd.DataFrame:
    """Return an empty ETF valuation frame with the dashboard schema."""
    return pd.DataFrame(columns=VALUATION_COLUMNS)


def _parse_decimal(value: str) -> float:
    """Parse Santander's German-style decimal values."""
    compact_value = re.sub(r"\s+", "", str(value))
    if "," in compact_value and "." in compact_value:
        compact_value = compact_value.replace(".", "")
    compact_value = compact_value.replace(",", ".")
    return float(compact_value)


def parse_investment_order(description: str) -> InvestmentOrder | None:
    """Parse the ISIN and units from a Santander ETF order description."""
    match = _ORDER_PATTERN.search(str(description))
    if not match:
        return None

    return InvestmentOrder(
        isin=match.group("isin").upper(),
        side=match.group("side").upper(),
        units=_parse_decimal(match.group("units")),
    )


def build_etf_holdings(
    transactions: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    currency: str = "EUR",
) -> pd.DataFrame:
    """Build PDF-derived ETF holdings and cost basis through one date.

    The source of truth is the extracted Santander statement transactions. The
    embedded Santander order fee is excluded from cost basis because it is
    reported separately as spending in the dashboard.
    """
    if transactions.empty:
        return _empty_holdings_frame()

    bank_mask = transactions["bank"].fillna("").astype(str).str.lower().eq("santander")
    pdf_source_mask = (
        transactions["source_file"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.endswith(".pdf")
    )
    rows = transactions.loc[
        transactions["category"].eq("Investments")
        & transactions["currency"].eq(currency)
        & transactions["date"].le(pd.Timestamp(as_of_date))
        & transactions["amount"].lt(0)
        & bank_mask
        & pdf_source_mask
    ].copy()
    if rows.empty:
        return _empty_holdings_frame()

    holdings: list[dict[str, object]] = []
    for row in rows.itertuples(index=False):
        order = parse_investment_order(str(row.description))
        if order is None:
            continue

        signed_units = order.units if order.side == "KAUF" else -order.units
        gross_amount = abs(float(row.amount))
        cost_basis = max(0.0, gross_amount - INVESTMENT_ORDER_FEE)
        if order.side == "VERKAUF":
            cost_basis *= -1

        instrument = ETF_INSTRUMENTS.get(order.isin)
        holdings.append(
            {
                "isin": order.isin,
                "symbol": instrument.symbol if instrument else "",
                "name": instrument.name if instrument else order.isin,
                "units": signed_units,
                "cost_basis": cost_basis,
                "transactions": 1,
                "latest_purchase_date": pd.Timestamp(row.date),
            }
        )

    if not holdings:
        return _empty_holdings_frame()

    holding_frame = pd.DataFrame(holdings)
    grouped = (
        holding_frame.groupby(["isin", "symbol", "name"], dropna=False)
        .agg(
            units=("units", "sum"),
            cost_basis=("cost_basis", "sum"),
            transactions=("transactions", "sum"),
            latest_purchase_date=("latest_purchase_date", "max"),
        )
        .reset_index()
        .sort_values("isin")
    )
    return grouped.loc[:, HOLDING_COLUMNS].reset_index(drop=True)


def market_price_cache_dir(output_root: str | Path) -> Path:
    """Return the cache directory for market-price CSV files."""
    return Path(output_root) / "market_prices"


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    """Return the cache path for one market symbol."""
    safe_symbol = re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_")
    return cache_dir / f"{safe_symbol}.csv"


def _read_symbol_cache(cache_dir: Path, symbol: str) -> pd.DataFrame:
    """Read cached prices for one symbol."""
    path = _cache_path(cache_dir, symbol)
    if not path.exists():
        return _empty_price_frame()

    prices = pd.read_csv(path)
    if prices.empty:
        return _empty_price_frame()

    prices["symbol"] = prices.get("symbol", symbol)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices["fetched_at"] = pd.to_datetime(prices.get("fetched_at"), errors="coerce")
    return prices.dropna(subset=["date", "close"]).loc[:, PRICE_COLUMNS]


def read_cached_market_prices(
    cache_dir: str | Path,
    symbols: tuple[str, ...],
) -> pd.DataFrame:
    """Read all available cached market prices for the requested symbols."""
    resolved_cache = Path(cache_dir)
    frames = [
        _read_symbol_cache(resolved_cache, symbol)
        for symbol in sorted(set(symbols))
        if symbol
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_price_frame()
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])


def _write_symbol_cache(cache_dir: Path, symbol: str, prices: pd.DataFrame) -> None:
    """Persist fetched prices for one market symbol."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    prices.loc[:, PRICE_COLUMNS].to_csv(_cache_path(cache_dir, symbol), index=False)


def _is_cache_fresh(prices: pd.DataFrame, *, cache_ttl_hours: int) -> bool:
    """Return whether cached market prices are fresh enough for dashboard use."""
    if prices.empty or "fetched_at" not in prices.columns:
        return False

    latest_fetch = pd.to_datetime(prices["fetched_at"], errors="coerce").max()
    if pd.isna(latest_fetch):
        return False

    age = pd.Timestamp.utcnow().tz_localize(None) - pd.Timestamp(
        latest_fetch
    ).tz_localize(None)
    return age <= pd.Timedelta(hours=cache_ttl_hours)


def fetch_alpha_vantage_daily_prices(symbol: str, api_key: str) -> pd.DataFrame:
    """Fetch daily closing prices from Alpha Vantage's stock time-series API."""
    query = urlencode(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": api_key,
        }
    )
    url = f"{ALPHA_VANTAGE_DAILY_URL}?{query}"
    try:
        with urlopen(url, timeout=15) as response:  # noqa: S310 - trusted API URL
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MarketPriceError(f"Could not fetch {symbol}: {exc}") from exc

    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict):
        message = (
            payload.get("Error Message")
            or payload.get("Note")
            or payload.get("Information")
            or "unexpected Alpha Vantage response"
        )
        raise MarketPriceError(f"Could not fetch {symbol}: {message}")

    fetched_at = pd.Timestamp.utcnow().tz_localize(None).isoformat()
    rows = []
    for date_label, values in series.items():
        try:
            close_value = float(values["4. close"])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": pd.Timestamp(date_label),
                "close": close_value,
                "fetched_at": fetched_at,
            }
        )

    if not rows:
        raise MarketPriceError(f"Could not fetch {symbol}: no close prices returned")
    return pd.DataFrame(rows, columns=PRICE_COLUMNS).sort_values("date")


def _read_json_url(url: str) -> dict[str, object]:
    """Read JSON from a market-data endpoint using a browser-like user-agent."""
    request = Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS URLs
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MarketPriceError(f"Could not read market endpoint: {exc}") from exc


def fetch_yahoo_chart_prices(symbol: str, _api_key: str = "") -> pd.DataFrame:
    """Fetch recent daily closes from Yahoo Finance's chart endpoint.

    Yahoo uses `.DE` XETRA tickers where Alpha Vantage uses `.DEX`, so prices
    are normalized back to the canonical dashboard symbol before caching.
    """
    yahoo_symbol = YAHOO_SYMBOL_OVERRIDES.get(symbol, symbol)
    query = urlencode({"range": "1y", "interval": "1d"})
    url = f"{YAHOO_CHART_URL}/{yahoo_symbol}?{query}"
    payload = _read_json_url(url)
    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise MarketPriceError(f"Yahoo Finance returned no chart for {symbol}")

    result = chart.get("result")
    if not isinstance(result, list) or not result:
        error = chart.get("error")
        raise MarketPriceError(f"Yahoo Finance returned no result for {symbol}: {error}")

    data = result[0]
    timestamps = data.get("timestamp")
    indicators = data.get("indicators", {})
    quotes = indicators.get("quote", []) if isinstance(indicators, dict) else []
    if not isinstance(timestamps, list) or not quotes:
        raise MarketPriceError(f"Yahoo Finance returned no daily closes for {symbol}")

    closes = quotes[0].get("close") if isinstance(quotes[0], dict) else None
    if not isinstance(closes, list):
        raise MarketPriceError(f"Yahoo Finance returned malformed closes for {symbol}")

    fetched_at = pd.Timestamp.utcnow().tz_localize(None).isoformat()
    rows = []
    for timestamp, close_value in zip(timestamps, closes, strict=False):
        if close_value is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "date": pd.to_datetime(timestamp, unit="s")
                .tz_localize(None)
                .normalize(),
                "close": float(close_value),
                "fetched_at": fetched_at,
            }
        )

    if not rows:
        raise MarketPriceError(f"Yahoo Finance returned no usable closes for {symbol}")
    return pd.DataFrame(rows, columns=PRICE_COLUMNS).sort_values("date")


def fetch_boerse_frankfurt_quote(symbol: str, _api_key: str = "") -> pd.DataFrame:
    """Fetch the latest XETRA quote from Boerse Frankfurt by ISIN."""
    instrument = ETF_INSTRUMENTS_BY_SYMBOL.get(symbol)
    if instrument is None:
        raise MarketPriceError(f"Boerse Frankfurt has no ISIN mapping for {symbol}")

    query = urlencode({"isin": instrument.isin, "mic": "XETR"})
    payload = _read_json_url(f"{BOERSE_FRANKFURT_QUOTE_URL}?{query}")
    last_price = payload.get("lastPrice")
    price_timestamp = payload.get("timestampLastPrice") or payload.get("timestamp")
    if last_price is None or price_timestamp is None:
        raise MarketPriceError(
            f"Boerse Frankfurt returned no latest price for {symbol}"
        )

    return pd.DataFrame(
        [
            {
                "symbol": symbol,
                "date": pd.Timestamp(price_timestamp).tz_localize(None).normalize(),
                "close": float(last_price),
                "fetched_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
            }
        ],
        columns=PRICE_COLUMNS,
    )


def load_or_fetch_market_prices(
    symbols: tuple[str, ...],
    *,
    cache_dir: str | Path,
    api_key: str | None = None,
    fetcher: PriceFetcher = fetch_alpha_vantage_daily_prices,
    fallback_fetchers: tuple[PriceFetcher, ...] = (
        fetch_yahoo_chart_prices,
        fetch_boerse_frankfurt_quote,
    ),
    cache_ttl_hours: int = 12,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Load ETF prices from cache and refresh them from available providers.

    Alpha Vantage remains the keyed provider. When no key is configured, the
    dashboard tries no-key public endpoints before falling back to stale cache or
    PDF-derived cost basis.
    """
    clean_symbols = tuple(sorted(symbol for symbol in set(symbols) if symbol))
    if not clean_symbols:
        return _empty_price_frame(), tuple()

    resolved_cache = Path(cache_dir)
    selected_api_key = api_key or os.environ.get(ALPHA_VANTAGE_API_KEY_ENV)
    price_frames: list[pd.DataFrame] = []
    warnings: list[str] = []

    for symbol in clean_symbols:
        cached_prices = _read_symbol_cache(resolved_cache, symbol)
        should_use_cache = _is_cache_fresh(
            cached_prices,
            cache_ttl_hours=cache_ttl_hours,
        )
        if should_use_cache:
            price_frames.append(cached_prices)
            continue

        fetch_errors: list[str] = []
        fetched_prices = _empty_price_frame()
        if selected_api_key:
            try:
                fetched_prices = fetcher(symbol, selected_api_key)
            except MarketPriceError as exc:
                fetch_errors.append(str(exc))

        if fetched_prices.empty:
            for fallback_fetcher in fallback_fetchers:
                try:
                    fetched_prices = fallback_fetcher(symbol, selected_api_key or "")
                except MarketPriceError as exc:
                    fetch_errors.append(str(exc))
                    continue
                if not fetched_prices.empty:
                    break

        if fetched_prices.empty:
            if cached_prices.empty:
                if not selected_api_key:
                    fetch_errors.insert(
                        0,
                        f"{ALPHA_VANTAGE_API_KEY_ENV} is not set",
                    )
                warnings.append(f"{symbol}: {'; '.join(fetch_errors)}")
            else:
                warnings.append(
                    f"{symbol}: {'; '.join(fetch_errors)}; using stale cached prices"
                )
                price_frames.append(cached_prices)
            continue

        _write_symbol_cache(resolved_cache, symbol, fetched_prices)
        price_frames.append(fetched_prices)

    if not price_frames:
        return _empty_price_frame(), tuple(warnings)
    prices = pd.concat(price_frames, ignore_index=True).sort_values(["symbol", "date"])
    return prices.loc[:, PRICE_COLUMNS], tuple(warnings)


def value_etf_holdings(
    holdings: pd.DataFrame,
    market_prices: pd.DataFrame | None,
    *,
    as_of_date: pd.Timestamp,
) -> pd.DataFrame:
    """Value PDF-derived ETF holdings using latest available market prices."""
    if holdings.empty:
        return _empty_valuation_frame()

    prices = market_prices.copy() if market_prices is not None else _empty_price_frame()
    if prices.empty or not {"symbol", "date", "close"}.issubset(prices.columns):
        prices = _empty_price_frame()
    else:
        prices = prices.copy()
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")

    valuation_rows: list[dict[str, object]] = []
    for holding in holdings.itertuples(index=False):
        symbol_prices = prices.loc[prices["symbol"].eq(holding.symbol)].sort_values(
            "date"
        )
        historical_price_rows = symbol_prices.loc[
            symbol_prices["date"].le(pd.Timestamp(as_of_date))
        ]
        if not historical_price_rows.empty:
            latest_price = historical_price_rows.iloc[-1]
            valuation_source = "market_price"
        elif not symbol_prices.empty:
            # A live quote is still useful for the current wealth view when
            # historical month-end prices are unavailable from the provider.
            latest_price = symbol_prices.iloc[-1]
            valuation_source = "latest_market_price"
        else:
            latest_price = None
            valuation_source = "cost_basis_fallback"

        if latest_price is None:
            market_price = pd.NA
            market_price_date = pd.NaT
            market_value = float(holding.cost_basis)
            gain_loss = 0.0
        else:
            market_price = float(latest_price["close"])
            market_price_date = pd.Timestamp(latest_price["date"])
            market_value = float(holding.units) * market_price
            gain_loss = market_value - float(holding.cost_basis)

        valuation_rows.append(
            {
                "isin": holding.isin,
                "symbol": holding.symbol,
                "name": holding.name,
                "units": float(holding.units),
                "cost_basis": float(holding.cost_basis),
                "transactions": int(holding.transactions),
                "latest_purchase_date": pd.Timestamp(holding.latest_purchase_date),
                "market_price": market_price,
                "market_price_date": market_price_date,
                "market_value": market_value,
                "gain_loss": gain_loss,
                "valuation_source": valuation_source,
            }
        )

    return pd.DataFrame(valuation_rows, columns=VALUATION_COLUMNS)


def calculate_klarna_accrued_interest(
    as_of_date: pd.Timestamp,
    *,
    principal: float = KLARNA_BLOCKED_PRINCIPAL,
    annual_rate: float = KLARNA_ANNUAL_INTEREST_RATE,
    start_date: pd.Timestamp = KLARNA_INTEREST_START_DATE,
    end_date: pd.Timestamp = KLARNA_INTEREST_END_DATE,
) -> float:
    """Return simple daily accrued Klarna blocked-account interest."""
    normalized_date = pd.Timestamp(as_of_date).normalize()
    normalized_start = pd.Timestamp(start_date).normalize()
    normalized_end = pd.Timestamp(end_date).normalize()
    if normalized_date < normalized_start:
        return 0.0

    capped_date = min(normalized_date, normalized_end)
    accrued_days = (capped_date - normalized_start).days + 1
    return principal * annual_rate * accrued_days / 365.0
