"""CLI: python -m variance_analyst data/sample_budget_vs_actuals.csv --pct 0.1 --abs 5000"""
import argparse

from .commentary import generate_commentary
from .core import compute_variances, load_csv


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="AI financial variance analyst")
    p.add_argument("csv")
    p.add_argument("--pct", type=float, default=0.10, help="materiality % threshold (0.10 = 10%%)")
    p.add_argument("--abs", type=float, default=5000, help="materiality $ threshold")
    p.add_argument("--llm", action="store_true", help="polish commentary with an LLM (needs OPENAI_API_KEY)")
    a = p.parse_args(argv)
    lines = compute_variances(load_csv(a.csv), a.pct, a.abs)
    print(generate_commentary(lines, use_llm=a.llm))


if __name__ == "__main__":
    main()
