from pathlib import Path

import pytest

from variance_analyst import compute_variances, detect_run_rate, generate_commentary, load_csv, run_lengths
from variance_analyst.cli import main

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_budget_vs_actuals.csv"
HDR = "month,department,account,account_type,budget,actual\n"


def series(*actuals, budget=50000, account="Cloud Hosting", account_type="expense", start=1):
    """One line item across consecutive months; None skips a month."""
    rows = "".join(f"2026-{start + i:02d},Eng,{account},{account_type},{budget},{a}\n"
                   for i, a in enumerate(actuals) if a is not None)
    return compute_variances(load_csv(HDR + rows))


def pattern(lines, **kw):
    (p,) = detect_run_rate(lines, **kw)
    return p


def test_two_material_months_same_direction_is_run_rate():
    p = pattern(series(50000, 60000, 61000))
    assert p.pattern == "run-rate" and p.streak == 2
    assert p.streak_months == ("2026-02", "2026-03")
    assert p.streak_variance == 21000 and p.favorable is False


def test_streak_counts_every_consecutive_month():
    p = pattern(series(60000, 60000, 60000, 60000))
    assert p.pattern == "run-rate" and p.streak == 4


def test_min_months_is_configurable():
    lines = series(50000, 60000, 60000)
    assert pattern(lines).pattern == "run-rate"
    assert pattern(lines, min_months=3).pattern == "timing"


def test_min_months_below_two_rejected():
    with pytest.raises(ValueError, match="at least 2"):
        detect_run_rate(series(60000), min_months=1)


def test_sign_flip_breaks_streak():
    # over, over, then under: the latest month starts a new streak of 1
    p = pattern(series(60000, 60000, 40000))
    assert p.pattern == "timing" and p.streak == 1 and p.favorable is True


def test_non_material_month_breaks_streak():
    p = pattern(series(60000, 51000, 60000))
    assert p.pattern == "timing" and p.streak == 1


def test_reversed_one_off_is_timing_with_zero_streak():
    p = pattern(series(50000, 65000, 50000))
    assert p.pattern == "timing" and p.streak == 0 and p.favorable is None
    assert p.last_material_month == "2026-02" and p.last_material_variance == 15000


def test_streak_must_reach_latest_month():
    # a run rate that ended earlier is history, not the current run rate
    p = pattern(series(60000, 60000, 60000, 50000))
    assert p.pattern == "timing" and p.streak == 0


def test_missing_month_breaks_streak():
    # Feb exists in the dataset (other account) but this line has no Feb row
    lines = series(60000, None, 60000) + series(1, 1, 1, account="Postage", budget=1)
    p = next(p for p in detect_run_rate(lines) if p.account == "Cloud Hosting")
    assert p.pattern == "timing" and p.streak == 1


def test_line_missing_latest_month_is_not_run_rate():
    lines = series(60000, 60000) + series(1, 1, 1, account="Postage", budget=1)
    p = next(p for p in detect_run_rate(lines) if p.account == "Cloud Hosting")
    assert p.pattern == "timing" and p.streak == 0


def test_single_month_cannot_be_run_rate():
    assert pattern(series(70000)).pattern == "timing"
    text = generate_commentary(series(70000))
    assert "Run-rate vs timing" not in text


def test_never_material_is_none():
    p = pattern(series(50500, 49500, 50200))
    assert p.pattern == "none" and p.streak == 0 and p.last_material_month is None


def test_zero_budget_new_spend_can_be_run_rate():
    p = pattern(series(9000, 9500, budget=0, account="New Tool"))
    assert p.pattern == "run-rate" and p.streak == 2


def test_favorable_revenue_run_rate():
    p = pattern(series(120000, 125000, budget=100000, account="Subscription Revenue", account_type="revenue"))
    assert p.pattern == "run-rate" and p.favorable is True


def test_items_are_tracked_independently_and_sorted():
    lines = (series(60000, 60000)
             + series(200000, 210000, budget=100000, account="Contractors")
             + series(50000, 50000, account="Rent"))
    ps = detect_run_rate(lines)
    assert [(p.account, p.pattern) for p in ps] == [
        ("Contractors", "run-rate"), ("Cloud Hosting", "run-rate"), ("Rent", "none")]


def test_duplicate_line_item_rejected():
    lines = series(60000) + series(60000)
    with pytest.raises(ValueError, match="duplicate line item"):
        detect_run_rate(lines)


def test_empty_input():
    assert detect_run_rate([]) == []


def test_run_lengths_label_each_row_with_its_run():
    lens = run_lengths(series(60000, 60000, 50000, 65000))
    assert lens == {("2026-01", "Eng", "Cloud Hosting"): 2, ("2026-02", "Eng", "Cloud Hosting"): 2,
                    ("2026-04", "Eng", "Cloud Hosting"): 1}


def test_commentary_flags_run_rate_and_timing():
    text = generate_commentary(series(60000, 60000, 60000) + series(50000, 70000, 50000, account="Contractors"))
    assert "Cloud Hosting: unfavorable for 3 months running (2026-01 to 2026-03, $30.0K cumulative)" in text
    assert "likely run-rate, consider re-forecast" in text
    assert "Timing (did not repeat): Eng Contractors (2026-02)" in text


def test_commentary_new_this_month_and_no_run_rate():
    text = generate_commentary(series(50000, 70000))
    assert "No run-rate variances" in text
    assert "New in 2026-02: Eng Cloud Hosting" in text


def test_sample_has_cloud_and_subscription_run_rates():
    ps = {p.account: p for p in detect_run_rate(compute_variances(load_csv(SAMPLE))) if p.department in
          ("Engineering", "Sales")}
    assert ps["Cloud Hosting"].pattern == "run-rate" and ps["Cloud Hosting"].streak == 4
    assert ps["Subscription Revenue"].pattern == "run-rate" and ps["Subscription Revenue"].streak == 2
    assert ps["Contractors"].pattern == "timing"


def test_cli_run_rate_months_flag(capsys):
    main([str(SAMPLE), "--run-rate-months", "3"])
    out = capsys.readouterr().out
    assert "3+ consecutive months" in out and "Cloud Hosting: unfavorable for 4 months running" in out
    assert "Subscription Revenue: unfavorable for 2 months running" not in out


def test_cli_rejects_run_rate_months_below_two():
    with pytest.raises(SystemExit):
        main([str(SAMPLE), "--run-rate-months", "1"])
