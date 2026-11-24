"""Price / volume / mix decomposition for revenue lines.

A revenue miss can come from selling fewer units (volume), selling them cheaper (price), or
selling more of the cheaper products (mix). This module splits each group's revenue variance into
those three effects so that, for every group, ``price + volume + mix == actual - budget`` exactly
(up to float rounding).

Inputs: revenue lines that carry ``budget_units`` and ``actual_units`` (optional CSV columns).
Each line item (department + account) is a *product*; products in the same department form a
*group*, so put comparable products (e.g. subscription plans counted in seats) in one department.
Average price is amount / units.

Formulas, per product i in a group (B = budget, A = actual, Q = units, P = price, t = group total):

* price effect  = (AP_i - BP_i) * AQ_i
* volume effect = (AQ_t - BQ_t) * BMix_i * BP_i      where BMix_i = BQ_i / BQ_t
* mix effect    = (AQ_i - AQ_t * BMix_i) * BP_i

Edge cases: a product with no budget units (new product) is priced at its actual price, so its
revenue shows up as mix, not price. A product with no actual units (discontinued) has no price
effect. A group with no budget units at all puts everything in volume. A line with $ but zero
units is rejected because its price is undefined.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .core import VarianceLine


@dataclass(frozen=True)
class ProductPVM:
    department: str
    account: str
    budget_units: float
    actual_units: float
    budget_price: float
    actual_price: float
    budget: float
    actual: float
    variance: float
    price_effect: float
    volume_effect: float
    mix_effect: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PVMGroup:
    period: str        # a month, or "first to last" for the whole file
    department: str
    budget: float
    actual: float
    variance: float
    budget_units: float
    actual_units: float
    price_effect: float
    volume_effect: float
    mix_effect: float
    products: tuple[ProductPVM, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def pvm_lines(lines: Iterable[VarianceLine]) -> list[VarianceLine]:
    """Revenue lines that carry units (the only lines PVM can decompose)."""
    return [l for l in lines if l.account_type == "revenue"
            and l.budget_units is not None and l.actual_units is not None]


def _price(amount: float, units: float, what: str, dept: str, acct: str) -> float | None:
    if units == 0:
        if amount != 0:
            raise ValueError(f"{dept} / {acct}: {what} is {amount:,.2f} but {what} units are 0, "
                             "so the average price is undefined")
        return None
    return amount / units


def _decompose(period: str, dept: str, items: dict[str, list[float]]) -> PVMGroup:
    bqt = sum(v[0] for v in items.values())
    aqt = sum(v[1] for v in items.values())
    products = []
    for acct, (bq, aq, b, a) in sorted(items.items()):
        bp = _price(b, bq, "budget", dept, acct)
        ap = _price(a, aq, "actual", dept, acct)
        if bp is None:
            bp = ap if ap is not None else 0.0   # new product: no price effect
        if ap is None:
            ap = bp                              # discontinued: no price effect
        price = (ap - bp) * aq
        if bqt > 0:
            bmix = bq / bqt
            volume = (aqt - bqt) * bmix * bp
            mix = (aq - aqt * bmix) * bp
        else:
            volume, mix = (aq - bq) * bp, 0.0
        products.append(ProductPVM(dept, acct, bq, aq, bp, ap, b, a, a - b, price, volume, mix))
    b_tot = sum(p.budget for p in products)
    a_tot = sum(p.actual for p in products)
    return PVMGroup(period, dept, b_tot, a_tot, a_tot - b_tot, bqt, aqt,
                    sum(p.price_effect for p in products), sum(p.volume_effect for p in products),
                    sum(p.mix_effect for p in products), tuple(products))


def decompose_pvm(lines: Iterable[VarianceLine], by_month: bool = False) -> list[PVMGroup]:
    """Price / volume / mix per department for revenue lines with units.

    ``by_month=False`` (default) sums units and $ per product across all months in the data and
    decomposes once per department; ``by_month=True`` decomposes each month separately.
    Returns [] when no revenue line has units. Sorted by period, then largest |variance| first.
    """
    eligible = pvm_lines(lines)
    if not eligible:
        return []
    months = sorted({l.month for l in eligible})
    whole = months[0] if len(months) == 1 else f"{months[0]} to {months[-1]}"
    groups: dict[tuple[str, str], dict[str, list[float]]] = {}
    for l in eligible:
        period = l.month if by_month else whole
        acc = groups.setdefault((period, l.department), {}).setdefault(l.account, [0.0, 0.0, 0.0, 0.0])
        acc[0] += l.budget_units
        acc[1] += l.actual_units
        acc[2] += l.budget
        acc[3] += l.actual
    out = [_decompose(period, dept, items) for (period, dept), items in groups.items()]
    return sorted(out, key=lambda g: (g.period, -abs(g.variance), g.department))
