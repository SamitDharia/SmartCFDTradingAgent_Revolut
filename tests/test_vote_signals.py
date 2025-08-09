from SmartCFDTradingAgent.pipeline import vote_signals


def test_weighted_vote_prefers_heavier_interval():
    maps = {
        "1h": {"BTC": "Buy"},
        "15m": {"BTC": "Sell"},
    }
    weights = {"1h": 2, "15m": 1}
    result = vote_signals(maps, weights)
    assert result["BTC"] == "Buy"


def test_unweighted_defaults_to_majority():
    maps = {
        "1h": {"ETH": "Sell"},
        "15m": {"ETH": "Sell"},
        "4h": {"ETH": "Buy"},
    }
    # weights omitted -> defaults to 1 each
    result = vote_signals(maps, {})
    assert result["ETH"] == "Sell"
