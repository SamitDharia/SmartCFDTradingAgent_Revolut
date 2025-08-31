from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from SmartCFDTradingAgent import revolut_recon as rr


def test_recon_creates_output(tmp_path, monkeypatch):
    decisions = tmp_path / "decision_log.csv"
    decisions.write_text("ts,ticker,side,price\n2023-01-01T10:00:00,ABC,Buy,100\n")
    trades = tmp_path / "trades.csv"
    trades.write_text("timestamp,symbol,quantity,price\n2023-01-01T10:30:00,ABC,1,101\n")
    monkeypatch.setattr(rr, "DECISIONS", decisions)
    monkeypatch.setattr(rr, "STORE", tmp_path)
    out = rr.recon(str(trades), "2023-01-01", window_min=90, to_telegram=False)
    assert out.exists()
    df = pd.read_csv(out)
    assert df.loc[0, "match"] == "YES"
    assert df.loc[0, "ex_price"] == 101.0
