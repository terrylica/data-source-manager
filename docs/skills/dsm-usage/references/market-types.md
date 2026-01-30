# Market Types Reference

Detailed documentation for Binance market types supported by DataSourceManager.

## MarketType Enum Values

```python
from data_source_manager import MarketType

# Available market types
MarketType.SPOT           # Spot market trading
MarketType.FUTURES_USDT   # USDT-margined perpetual futures
MarketType.FUTURES_COIN   # Coin-margined perpetual futures
```

## Symbol Format by Market Type

| Market Type  | Symbol Format    | Example     |
| ------------ | ---------------- | ----------- |
| SPOT         | `{BASE}{QUOTE}`  | BTCUSDT     |
| FUTURES_USDT | `{BASE}{QUOTE}`  | BTCUSDT     |
| FUTURES_COIN | `{BASE}USD_PERP` | BTCUSD_PERP |

## API Base URLs

| Market Type  | REST API                 | Vision API                          |
| ------------ | ------------------------ | ----------------------------------- |
| SPOT         | api.binance.com/api/v3   | data.binance.vision/data/spot       |
| FUTURES_USDT | fapi.binance.com/fapi/v1 | data.binance.vision/data/futures/um |
| FUTURES_COIN | dapi.binance.com/dapi/v1 | data.binance.vision/data/futures/cm |

## Data Availability

- **SPOT**: Earliest data varies by symbol (some back to 2017)
- **FUTURES_USDT**: Generally from 2020
- **FUTURES_COIN**: Generally from late 2020

## Common Patterns

```python
# Spot market
manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)
df = manager.get_data("BTCUSDT", start, end, Interval.HOUR_1)

# USDT futures
manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.FUTURES_USDT)
df = manager.get_data("BTCUSDT", start, end, Interval.HOUR_1)

# Coin-margined futures (note different symbol format)
manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.FUTURES_COIN)
df = manager.get_data("BTCUSD_PERP", start, end, Interval.HOUR_1)
```

## Error Handling

```python
from data_source_manager.utils.market_constraints import validate_symbol_for_market_type

# Validate before fetching
is_valid, suggestion = validate_symbol_for_market_type("BTCUSDT", MarketType.FUTURES_COIN)
if not is_valid:
    print(f"Invalid symbol. Suggested: {suggestion}")
    # Output: Invalid symbol. Suggested: BTCUSD_PERP
```
