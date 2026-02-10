# Library Module Examples

## Overview

This directory previously contained a demo module (`ckvd_demo_module.py`) that was removed during the demo layer purge (GitHub #16).

## Current Recommended Usage

Use `fetch_market_data()` for a high-level programmatic interface:

```python
from ckvd import fetch_market_data, DataProvider, MarketType, Interval, ChartType
from datetime import datetime, timezone

df, elapsed_time, records = fetch_market_data(
    provider=DataProvider.BINANCE,
    market_type=MarketType.SPOT,
    chart_type=ChartType.KLINES,
    symbol="BTCUSDT",
    interval=Interval.MINUTE_1,
    end_time=datetime(2025, 5, 15, 13, 45, 30, tzinfo=timezone.utc),
    days=10,
)

print(f"Fetched {records} records in {elapsed_time:.2f}s")
```

Or use `CryptoKlineVisionData` directly for more control:

```python
from ckvd import CryptoKlineVisionData, DataProvider, MarketType, Interval
from datetime import datetime, timedelta, timezone

manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.FUTURES_USDT)
end = datetime.now(timezone.utc)
start = end - timedelta(days=7)

df = manager.get_data("BTCUSDT", start, end, Interval.HOUR_1)
print(f"Fetched {len(df)} bars")
manager.close()
```

## Related

- [quick_start.py](../quick_start.py) - Minimal usage example
- [Cache control example](../ckvd_cache_control_example.py) - Cache toggle mechanisms
- [docs/skills/ckvd-usage/SKILL.md](../../docs/skills/ckvd-usage/SKILL.md) - Full API guide
