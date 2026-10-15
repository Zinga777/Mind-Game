from thunder.dashboard import formatters as f


def test_indian_grouping():
    assert f.inr(123456.78) == "₹1,23,456.78"
    assert f.inr(1000) == "₹1,000.00"
    assert f.inr(12345678, 0) == "₹1,23,45,678"
    assert f.inr(-1500.5) == "−₹1,500.50"
    assert f.inr(15, sign=True) == "▲ +₹15.00"
    assert f.inr(-15, sign=True) == "▼ −₹15.00"
    assert f.inr(None) == "—"


def test_signs_and_r():
    assert f.pct(0.0512) == "+5.1%" and f.pct(-0.02) == "−2.0%" and f.pct(0.1, sign=False) == "10.0%"
    assert f.r_mult(0.42) == "+0.42R" and f.r_mult(-1) == "−1.00R"
    assert f.arrow(1) == "▲" and f.arrow(-1) == "▼"


def test_ist():
    assert f.ist(1735689600000) == "01 Jan 2025, 05:30 IST"
    assert f.utc(1735689600000) == "2025-01-01 00:00 UTC"
    assert f.ago(0, 30_000) == "never" and f.ago(1, 61_000) == "60 s ago"
