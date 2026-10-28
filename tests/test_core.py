import io
from pathlib import Path

import pytest

from variance_analyst import compute_variances, load_csv, rollup, summarize

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_budget_vs_actuals.csv"
HDR = "month,department,account,account_type,budget,actual\n"


def lines(csv_body, **kw):
    return compute_variances(load_csv(HDR + csv_body), **kw)


def test_revenue_over_budget_is_favorable():
    (l,) = lines("2026-01,Sales,Subscription Revenue,revenue,100000,120000\n")
    assert l.variance == 20000 and l.variance_pct == pytest.approx(0.20)
    assert l.favorable and l.material


def test_expense_over_budget_is_unfavorable():
    (l,) = lines("2026-01,Eng,Cloud Hosting,expense,50000,60000\n")
    assert not l.favorable and l.material


def test_expense_under_budget_is_favorable():
    (l,) = lines("2026-01,Eng,Salaries,expense,50000,40000\n")
    assert l.favorable


def test_materiality_requires_both_pct_and_abs():
    # 50% but only $500 -> not material with $5K floor
    (l,) = lines("2026-01,G&A,Postage,expense,1000,1500\n")
    assert not l.material
    (l,) = lines("2026-01,G&A,Postage,expense,1000,1500\n", abs_threshold=100)
    assert l.material


def test_threshold_is_configurable():
    body = "2026-01,Eng,Cloud,expense,100000,108000\n"
    assert not lines(body)[0].material
    assert lines(body, pct_threshold=0.05)[0].material


def test_zero_budget_has_no_pct_but_can_be_material():
    (l,) = lines("2026-01,Eng,New Tool,expense,0,9000\n")
    assert l.variance_pct is None and l.material


def test_missing_columns_raise():
    with pytest.raises(ValueError, match="missing required columns"):
        load_csv("month,department,budget\n2026-01,Sales,1\n")


def test_bad_account_type_raises():
    with pytest.raises(ValueError, match="account_type"):
        load_csv(HDR + "2026-01,Sales,X,asset,1,2\n")


def test_non_numeric_raises():
    with pytest.raises(ValueError, match="numeric"):
        load_csv(HDR + "2026-01,Sales,X,revenue,abc,2\n")


def test_accepts_thousands_separators_and_file_objects():
    rows = load_csv(io.StringIO(HDR + '2026-01,Sales,X,revenue,"1,000",2000\n'))
    assert rows[0]["budget"] == 1000


def test_summary_profit_math():
    ls = lines("2026-01,S,Rev,revenue,1000,1200\n2026-01,S,Cost,expense,600,700\n")
    s = summarize(ls)
    assert s["profit_budget"] == 400 and s["profit_actual"] == 500 and s["profit_variance"] == 100


def test_rollup_net_impact_sorted_worst_first():
    ls = lines("2026-01,A,Rev,revenue,1000,900\n2026-01,B,Cost,expense,1000,800\n")
    r = rollup(ls)
    assert [d["department"] for d in r] == ["A", "B"]
    assert r[0]["net_impact"] == -100 and r[1]["net_impact"] == 200


def test_sample_dataset_loads_and_has_material_items():
    ls = compute_variances(load_csv(SAMPLE))
    assert len(ls) == 90
    assert 3 <= sum(l.material for l in ls) <= 20
