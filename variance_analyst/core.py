"""Core variance math. Pure standard library so it runs anywhere (incl. Pyodide)."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = {"month", "department", "account", "account_type", "budget", "actual"}
VALID_TYPES = {"revenue", "expense"}


@dataclass(frozen=True)
class VarianceLine:
    month: str
    department: str
    account: str
    account_type: str
    budget: float
    actual: float
    variance: float          # actual - budget
    variance_pct: float | None  # variance / |budget|, None when budget == 0
    favorable: bool
    material: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_rows(reader: csv.DictReader) -> list[dict]:
    cols = {c.strip().lower() for c in (reader.fieldnames or [])}
    missing = REQUIRED_COLUMNS - cols
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
    rows = []
    for i, raw in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        atype = row["account_type"].lower()
        if atype not in VALID_TYPES:
            raise ValueError(f"line {i}: account_type must be revenue or expense, got {row['account_type']!r}")
        try:
            budget = float(row["budget"].replace(",", ""))
            actual = float(row["actual"].replace(",", ""))
        except ValueError as exc:
            raise ValueError(f"line {i}: budget/actual must be numeric") from exc
        rows.append({**row, "account_type": atype, "budget": budget, "actual": actual})
    return rows


def load_csv(source: str | Path | io.TextIOBase) -> list[dict]:
    """Load budget-vs-actuals rows from a path, a file object, or raw CSV text."""
    if isinstance(source, io.TextIOBase):
        return _parse_rows(csv.DictReader(source))
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source):
        with open(source, newline="", encoding="utf-8") as fh:
            return _parse_rows(csv.DictReader(fh))
    return _parse_rows(csv.DictReader(io.StringIO(source)))


def compute_variances(
    rows: Iterable[dict], pct_threshold: float = 0.10, abs_threshold: float = 5_000.0
) -> list[VarianceLine]:
    """Compute $ and % variance per row.

    A line is *material* when |variance %| >= pct_threshold AND |variance $| >= abs_threshold
    (the usual FP&A "both" rule, so tiny accounts don't flood the report).
    Revenue over budget is favorable; expense under budget is favorable.
    """
    out = []
    for r in rows:
        var = r["actual"] - r["budget"]
        pct = None if r["budget"] == 0 else var / abs(r["budget"])
        favorable = var >= 0 if r["account_type"] == "revenue" else var <= 0
        pct_hit = pct is None and var != 0 or (pct is not None and abs(pct) >= pct_threshold)
        material = bool(pct_hit and abs(var) >= abs_threshold)
        out.append(VarianceLine(r["month"], r["department"], r["account"], r["account_type"],
                                r["budget"], r["actual"], var, pct, favorable, material))
    return out


def rollup(lines: Iterable[VarianceLine], by: str = "department") -> list[dict]:
    """Aggregate budget/actual/variance by a dimension (department, account, month)."""
    agg: dict[str, dict] = {}
    for ln in lines:
        key = getattr(ln, by)
        a = agg.setdefault(key, {by: key, "budget": 0.0, "actual": 0.0, "net_impact": 0.0})
        a["budget"] += ln.budget
        a["actual"] += ln.actual
        # net impact on profit: favorable variances help, unfavorable hurt
        a["net_impact"] += abs(ln.variance) if ln.favorable else -abs(ln.variance)
    return sorted(agg.values(), key=lambda d: d["net_impact"])


def summarize(lines: list[VarianceLine]) -> dict:
    rev_b = sum(l.budget for l in lines if l.account_type == "revenue")
    rev_a = sum(l.actual for l in lines if l.account_type == "revenue")
    exp_b = sum(l.budget for l in lines if l.account_type == "expense")
    exp_a = sum(l.actual for l in lines if l.account_type == "expense")
    return {
        "revenue_budget": rev_b, "revenue_actual": rev_a,
        "expense_budget": exp_b, "expense_actual": exp_a,
        "profit_budget": rev_b - exp_b, "profit_actual": rev_a - exp_a,
        "profit_variance": (rev_a - exp_a) - (rev_b - exp_b),
        "material_count": sum(l.material for l in lines),
        "line_count": len(lines),
    }
