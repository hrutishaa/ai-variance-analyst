import json
import shutil
import subprocess
from pathlib import Path

import pytest

from variance_analyst import compute_variances, decompose_pvm, generate_commentary, load_csv
from variance_analyst.cli import main

ROOT = Path(__file__).resolve().parents[1]
PVM_SAMPLE = ROOT / "data" / "sample_revenue_pvm.csv"
MAIN_SAMPLE = ROOT / "data" / "sample_budget_vs_actuals.csv"
HDR = "month,department,account,account_type,budget,actual,budget_units,actual_units\n"


def pvm(body, **kw):
    return decompose_pvm(compute_variances(load_csv(HDR + body)), **kw)


def effects(g):
    return g.price_effect, g.volume_effect, g.mix_effect


def test_effects_always_sum_to_variance_on_sample():
    groups = decompose_pvm(compute_variances(load_csv(PVM_SAMPLE)))
    assert {g.department for g in groups} == {"Subscriptions", "Services"}
    for g in groups:
        assert sum(effects(g)) == pytest.approx(g.variance, abs=1e-6)
        for p in g.products:
            assert p.price_effect + p.volume_effect + p.mix_effect == pytest.approx(p.variance, abs=1e-6)


def test_monthly_mode_sums_to_each_month():
    ls = compute_variances(load_csv(PVM_SAMPLE))
    groups = decompose_pvm(ls, by_month=True)
    assert len({g.period for g in groups}) == 6
    for g in groups:
        assert sum(effects(g)) == pytest.approx(g.variance, abs=1e-6)


def test_pure_price_change():
    (g,) = pvm("2026-01,Subs,Pro,revenue,1000,900,10,10\n")
    assert effects(g) == pytest.approx((-100, 0, 0))


def test_pure_volume_change_keeps_mix_zero():
    # both products grow 50%, mix unchanged
    (g,) = pvm("2026-01,Subs,A,revenue,1000,1500,10,15\n2026-01,Subs,B,revenue,2000,3000,10,15\n")
    assert effects(g) == pytest.approx((0, 1500, 0))


def test_pure_mix_shift_toward_cheaper_product():
    # same 20 units in total, 5 move from the $200 product to the $100 product
    (g,) = pvm("2026-01,Subs,Cheap,revenue,1000,1500,10,15\n2026-01,Subs,Premium,revenue,2000,1000,10,5\n")
    assert effects(g) == pytest.approx((0, 0, -500))


def test_textbook_example_all_three_effects():
    # A: 100u @ $10 -> 120u @ $9 ; B: 100u @ $20 -> 60u @ $22
    (g,) = pvm("2026-01,Subs,A,revenue,1000,1080,100,120\n2026-01,Subs,B,revenue,2000,1320,100,60\n")
    # price: (9-10)*120 + (22-20)*60 = 0 ; volume: (180-200)*15 = -300 ; mix: (120-90)*10 + (60-90)*20 = -300
    assert effects(g) == pytest.approx((0, -300, -300))
    assert g.variance == pytest.approx(-600)


def test_new_product_lands_in_mix_not_price():
    (g,) = pvm("2026-01,Subs,Old,revenue,1000,1000,10,10\n2026-01,Subs,New,revenue,0,500,0,5\n")
    new = next(p for p in g.products if p.account == "New")
    assert new.price_effect == 0 and new.budget_price == 100
    assert sum(effects(g)) == pytest.approx(500)


def test_discontinued_product_has_no_price_effect():
    (g,) = pvm("2026-01,Subs,Old,revenue,1000,0,10,0\n2026-01,Subs,Core,revenue,1000,1000,10,10\n")
    old = next(p for p in g.products if p.account == "Old")
    assert old.price_effect == 0
    assert sum(effects(g)) == pytest.approx(-1000)


def test_group_with_no_budget_units_is_all_volume():
    (g,) = pvm("2026-01,Subs,New,revenue,0,800,0,8\n")
    assert effects(g) == pytest.approx((0, 800, 0))


def test_dollars_without_units_is_rejected():
    with pytest.raises(ValueError, match="price is undefined"):
        pvm("2026-01,Subs,Pro,revenue,1000,900,0,10\n")


def test_expense_and_unitless_lines_are_ignored():
    groups = pvm("2026-01,Subs,Pro,revenue,1000,900,10,10\n2026-01,Ops,Hosting,expense,500,600,,\n"
                 "2026-01,Subs,Other,revenue,100,100,,\n")
    assert [p.account for g in groups for p in g.products] == ["Pro"]


def test_products_group_by_department_and_aggregate_across_months():
    groups = pvm("2026-01,Subs,Pro,revenue,1000,1000,10,10\n2026-02,Subs,Pro,revenue,1000,1200,10,12\n"
                 "2026-01,Services,Impl,revenue,500,400,5,4\n")
    by = {g.department: g for g in groups}
    assert by["Subs"].period == "2026-01 to 2026-02"
    assert (by["Subs"].budget_units, by["Subs"].actual_units) == (20, 22)
    assert effects(by["Services"]) == pytest.approx((0, -100, 0))


def test_no_units_means_no_pvm():
    assert decompose_pvm(compute_variances(load_csv(MAIN_SAMPLE))) == []
    assert "Price / volume / mix" not in generate_commentary(compute_variances(load_csv(MAIN_SAMPLE)))


@pytest.mark.parametrize("body,msg", [
    ("2026-01,Subs,Pro,revenue,1000,900,10,\n", "fill both"),
    ("2026-01,Subs,Pro,revenue,1000,900,10,x\n", "numeric"),
    ("2026-01,Subs,Pro,revenue,1000,900,-1,10\n", "negative"),
])
def test_bad_units_raise(body, msg):
    with pytest.raises(ValueError, match=msg):
        load_csv(HDR + body)


def test_unit_columns_must_come_in_pairs():
    with pytest.raises(ValueError, match="pair"):
        load_csv("month,department,account,account_type,budget,actual,budget_units\n2026-01,S,P,revenue,1,1,1\n")


def test_commentary_and_cli_include_pvm_section(capsys):
    text = generate_commentary(compute_variances(load_csv(PVM_SAMPLE)))
    assert "Price / volume / mix (revenue lines with units, 2026-01 to 2026-06):" in text
    assert "- Subscriptions:" in text and "Largest effect:" in text
    main([str(PVM_SAMPLE)])
    assert "Price / volume / mix" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_web_demo_js_matches_python(tmp_path):
    ls = compute_variances(load_csv(PVM_SAMPLE))
    data = tmp_path / "lines.json"
    data.write_text(json.dumps([l.to_dict() for l in ls]))
    out = subprocess.run(["node", str(ROOT / "tests" / "pvm_parity.js"), str(data)],
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    for mode, by_month in (("total", False), ("monthly", True)):
        py = [g.to_dict() for g in decompose_pvm(ls, by_month=by_month)]
        assert len(js[mode]) == len(py)
        for a, b in zip(js[mode], py):
            assert (a["period"], a["department"]) == (b["period"], b["department"])
            for k in ("budget", "actual", "price_effect", "volume_effect", "mix_effect"):
                assert a[k] == pytest.approx(b[k], abs=1e-6)
            for pa, pb in zip(a["products"], b["products"]):
                assert pa["account"] == pb["account"]
                assert pa["price_effect"] == pytest.approx(pb["price_effect"], abs=1e-6)
                assert pa["mix_effect"] == pytest.approx(pb["mix_effect"], abs=1e-6)
