"""AI Variance Analyst: budget-vs-actual variance analysis with plain-English commentary."""
from .core import VarianceLine, load_csv, compute_variances, summarize, rollup
from .commentary import generate_commentary
from .pvm import PVMGroup, ProductPVM, decompose_pvm
from .runrate import VariancePattern, detect_run_rate, run_lengths

__all__ = ["VarianceLine", "load_csv", "compute_variances", "summarize", "rollup", "generate_commentary",
           "VariancePattern", "detect_run_rate", "run_lengths",
           "PVMGroup", "ProductPVM", "decompose_pvm"]
__version__ = "0.3.0"
