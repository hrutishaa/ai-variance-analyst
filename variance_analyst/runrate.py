"""Run-rate vs timing detection across months.

A one-off material variance usually reverses (an invoice lands a month early, a hire slips a
month). A variance that stays material *in the same direction* month after month is a new run
rate, and the forecast should change. This module tells the two apart.

Rules, per line item (department + account):

* A month counts toward a streak when the line is material and the variance has the same sign
  as the previous month in the streak.
* A non-material month, a sign flip, or a month missing from the data breaks the streak.
* ``run-rate``: the streak that ends at the latest month in the data is >= ``min_months`` long.
* ``timing``: the item was material at least once, but not for ``min_months`` consecutive months
  through the latest month (it reversed, did not repeat, or is new this month).
* ``none``: never material in the window.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .core import VarianceLine

RUN_RATE = "run-rate"
TIMING = "timing"
NONE = "none"
DEFAULT_MIN_MONTHS = 2

ItemKey = tuple[str, str]  # (department, account)


@dataclass(frozen=True)
class VariancePattern:
    department: str
    account: str
    account_type: str
    pattern: str                    # "run-rate" | "timing" | "none"
    streak: int                     # material same-direction months ending at the latest month
    streak_months: tuple[str, ...]  # the months in that streak, oldest first
    streak_variance: float          # cumulative variance over the streak
    favorable: bool | None          # direction of the streak, None when streak == 0
    last_material_month: str | None
    last_material_variance: float

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_min_months(min_months: int) -> None:
    if min_months < 2:
        raise ValueError("min_months must be at least 2 (one month cannot be a run rate)")


def _direction(line: VarianceLine | None) -> int:
    """+1 / -1 for a material variance, 0 for anything that breaks a streak."""
    if line is None or not line.material or line.variance == 0:
        return 0
    return 1 if line.variance > 0 else -1


def _group(lines: Iterable[VarianceLine]) -> tuple[list[str], dict[ItemKey, dict[str, VarianceLine]]]:
    months: set[str] = set()
    items: dict[ItemKey, dict[str, VarianceLine]] = {}
    for ln in lines:
        months.add(ln.month)
        by_month = items.setdefault((ln.department, ln.account), {})
        if ln.month in by_month:
            raise ValueError(f"duplicate line item {ln.department} / {ln.account} in {ln.month}; "
                             "aggregate rows before run-rate detection")
        by_month[ln.month] = ln
    return sorted(months), items


def _runs(months: list[str], by_month: dict[str, VarianceLine]) -> list[list[VarianceLine]]:
    """Split one item's timeline into runs of consecutive material, same-sign months."""
    runs: list[list[VarianceLine]] = []
    current: list[VarianceLine] = []
    current_sign = 0
    for m in months:
        ln = by_month.get(m)
        sign = _direction(ln)
        if sign and sign == current_sign:
            current.append(ln)
            continue
        if current:
            runs.append(current)
        current, current_sign = ([ln], sign) if sign else ([], 0)
    if current:
        runs.append(current)
    return runs


def run_lengths(lines: Iterable[VarianceLine]) -> dict[tuple[str, str, str], int]:
    """Length of the run each material row belongs to, keyed by (month, department, account).

    Useful for row-level badges: a row is part of a run rate when its run length >= min_months.
    Non-material rows are not in the result.
    """
    months, items = _group(lines)
    out: dict[tuple[str, str, str], int] = {}
    for (dept, acct), by_month in items.items():
        for run in _runs(months, by_month):
            for ln in run:
                out[(ln.month, dept, acct)] = len(run)
    return out


def detect_run_rate(lines: Iterable[VarianceLine], min_months: int = DEFAULT_MIN_MONTHS) -> list[VariancePattern]:
    """Classify every line item as run-rate, timing, or none as of the latest month in the data.

    Sorted run-rate first (largest cumulative variance first), then timing, then none.
    """
    _validate_min_months(min_months)
    months, items = _group(lines)
    if not months:
        return []
    latest = months[-1]
    out = []
    for (dept, acct), by_month in items.items():
        runs = _runs(months, by_month)
        trailing = runs[-1] if runs and runs[-1][-1].month == latest else []
        last_material = runs[-1][-1] if runs else None
        if len(trailing) >= min_months:
            pattern = RUN_RATE
        elif runs:
            pattern = TIMING
        else:
            pattern = NONE
        out.append(VariancePattern(
            department=dept,
            account=acct,
            account_type=next(iter(by_month.values())).account_type,
            pattern=pattern,
            streak=len(trailing),
            streak_months=tuple(ln.month for ln in trailing),
            streak_variance=sum(ln.variance for ln in trailing),
            favorable=trailing[0].favorable if trailing else None,
            last_material_month=last_material.month if last_material else None,
            last_material_variance=last_material.variance if last_material else 0.0,
        ))
    order = {RUN_RATE: 0, TIMING: 1, NONE: 2}
    return sorted(out, key=lambda p: (order[p.pattern],
                                      -abs(p.streak_variance if p.pattern == RUN_RATE else p.last_material_variance),
                                      p.department, p.account))
