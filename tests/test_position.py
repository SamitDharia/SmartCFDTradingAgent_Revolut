import sys
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from SmartCFDTradingAgent.position import qty_from_atr


@pytest.fixture
def valid_params():
    return {
        "atr_value": 2.0,
        "equity": 10_000.0,
        "risk_frac": 0.02,
    }


def test_qty_from_atr_positive_inputs(valid_params):
    assert qty_from_atr(**valid_params) == 100


@pytest.mark.parametrize(
    "atr_value, equity, risk_frac",
    [
        (0, 10_000.0, 0.02),
        (-1, 10_000.0, 0.02),
        (2.0, 0, 0.02),
        (2.0, -10_000.0, 0.02),
        (2.0, 10_000.0, 0),
        (2.0, 10_000.0, -0.02),
    ],
)

def test_qty_from_atr_invalid_inputs_return_one(atr_value, equity, risk_frac):
    assert qty_from_atr(atr_value=atr_value, equity=equity, risk_frac=risk_frac) == 1
