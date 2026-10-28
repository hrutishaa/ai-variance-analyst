from pathlib import Path

from variance_analyst.cli import main

SAMPLE = str(Path(__file__).resolve().parents[1] / "data" / "sample_budget_vs_actuals.csv")


def test_cli_prints_commentary(capsys):
    main([SAMPLE, "--pct", "0.2", "--abs", "10000"])
    out = capsys.readouterr().out
    assert "Operating profit" in out
