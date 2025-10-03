import json
import SmartCFDTradingAgent.reporting as reporting


def test_digest_handles_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "aggregate_trade_stats", lambda: {"wins": 1, "losses": 0, "open": 0})
    monkeypatch.setattr(reporting, "read_last_decisions", lambda count: [])

    d = reporting.Digest()
    plain, html, chart = d.build_email_content(decisions=3)
    assert "Daily Trading Digest" in plain
    assert "Glossary" in plain
    assert "fresh trade ideas".split()[-1] in plain.lower()

    out_txt = tmp_path / "digest.txt"
    out_json = tmp_path / "digest.json"
    d.save_digest(plain, out_txt)
    d.dump_json([], out_json)
    assert out_txt.read_text(encoding="utf-8") == plain
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "generated_at" in payload
    assert payload["decisions"] == []
