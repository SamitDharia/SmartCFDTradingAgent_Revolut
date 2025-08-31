import pandas as pd

from SmartCFDTradingAgent.signals import generate_signals


def test_generate_signals_buy_sell_hold():
    idx = pd.date_range("2020-01-01", periods=60)
    step = pd.Series(range(60), index=idx)

    # Upward trending -> Buy
    close_up = pd.Series(range(1, 61), index=idx)
    high_up = close_up + 1 + step * 0.1
    low_up = close_up - 1

    # Downward trending -> Sell
    close_down = pd.Series(range(60, 0, -1), index=idx)
    high_down = 100 + step * 0.2
    low_down = high_down - step * 0.1 - 1

    # Flat -> Hold
    close_flat = pd.Series(10, index=idx)
    high_flat = close_flat + 1
    low_flat = close_flat - 1

    arrays = pd.MultiIndex.from_product([
        ["UP", "DOWN", "FLAT"], ["High", "Low", "Close"]
    ])
    price_df = pd.DataFrame(index=idx, columns=arrays)

    price_df["UP", "High"] = high_up
    price_df["UP", "Low"] = low_up
    price_df["UP", "Close"] = close_up

    price_df["DOWN", "High"] = high_down
    price_df["DOWN", "Low"] = low_down
    price_df["DOWN", "Close"] = close_down

    price_df["FLAT", "High"] = high_flat
    price_df["FLAT", "Low"] = low_flat
    price_df["FLAT", "Close"] = close_flat

    signals = generate_signals(price_df)
    assert signals["UP"] == "Buy"
    assert signals["DOWN"] == "Sell"
    assert signals["FLAT"] == "Hold"
