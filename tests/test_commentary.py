from pathlib import Path

from variance_analyst import compute_variances, generate_commentary, load_csv
from variance_analyst.commentary import explain_line, fmt_money, likely_driver

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_budget_vs_actuals.csv"


def test_fmt_money():
    assert fmt_money(1_250_000) == "$1.25M"
    assert fmt_money(-12_300) == "-$12.3K"
    assert fmt_money(950) == "$950"


def test_driver_lookup_case_insensitive_with_fallback():
    assert "usage" in likely_driver("CLOUD Hosting")
    assert "timing" in likely_driver("Widgets")


def test_explain_line_mentions_direction_and_tone():
    (l,) = compute_variances(load_csv("month,department,account,account_type,budget,actual\n"
                                      "2026-03,Engineering,Cloud Hosting,expense,48000,63360\n"))
    text = explain_line(l)
    assert "over budget" in text and "unfavorable" in text and "+32.0%" in text


def test_commentary_on_sample_is_grounded():
    ls = compute_variances(load_csv(SAMPLE))
    text = generate_commentary(ls)
    assert text.startswith("Operating profit")
    assert "Top material variances" in text
    assert "Subscription Revenue" in text  # biggest miss must be surfaced


def test_llm_flag_without_key_falls_back(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ls = compute_variances(load_csv(SAMPLE))
    assert generate_commentary(ls, use_llm=True) == generate_commentary(ls)


def test_no_material_variances_message():
    ls = compute_variances(load_csv("month,department,account,account_type,budget,actual\n"
                                    "2026-01,S,Rev,revenue,1000,1001\n"))
    assert "No material variances" in generate_commentary(ls)
