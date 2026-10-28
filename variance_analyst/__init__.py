"""AI Variance Analyst: budget-vs-actual variance analysis with plain-English commentary."""
from .core import VarianceLine, load_csv, compute_variances, summarize, rollup
from .commentary import generate_commentary

__all__ = ["VarianceLine", "load_csv", "compute_variances", "summarize", "rollup", "generate_commentary"]
__version__ = "0.1.0"
