"""CLI: python -m variance_analyst data/sample_budget_vs_actuals.csv --pct 0.1 --abs 5000 --run-rate-months 2"""
import argparse

from .commentary import generate_commentary
from .core import compute_variances, load_csv


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="AI financial variance analyst")
    p.add_argument("csv")
    p.add_argument("--pct", type=float, default=0.10, help="materiality % threshold (0.10 = 10%%)")
    p.add_argument("--abs", type=float, default=5000, help="materiality $ threshold")
    p.add_argument("--run-rate-months", type=int, default=2, metavar="N",
                   help="flag a variance as run-rate when material in the same direction for N+ consecutive "
                        "months (default 2)")
    p.add_argument("--llm", action="store_true", help="polish commentary with an LLM (needs OPENAI_API_KEY)")
    a = p.parse_args(argv)
    if a.run_rate_months < 2:
        p.error("--run-rate-months must be at least 2")
    lines = compute_variances(load_csv(a.csv), a.pct, a.abs)
    print(generate_commentary(lines, use_llm=a.llm, run_rate_months=a.run_rate_months))


if __name__ == "__main__":
    main()
