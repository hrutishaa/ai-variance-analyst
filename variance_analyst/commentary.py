"""Plain-English variance commentary.

Default: deterministic, rule-based narrative (no API key, reproducible, auditable).
Optional: set OPENAI_API_KEY (any OpenAI-compatible endpoint via OPENAI_BASE_URL) and pass
use_llm=True to have an LLM polish the narrative. The rule-based facts are always passed in
as grounding so the model cannot invent numbers.
"""
from __future__ import annotations

import json
import os
import urllib.request

from .core import VarianceLine, rollup, summarize

DRIVER_HINTS = {
    "salaries": "headcount timing (hires landing earlier/later than plan) or merit/bonus accruals",
    "contractors": "use of contractors to backfill open roles or accelerate projects",
    "cloud": "usage growth, untagged resources, or reserved-instance coverage gaps",
    "software": "new SaaS seats or annual renewals hitting earlier than phased",
    "marketing": "campaign spend timing or a shift between paid channels",
    "travel": "event and customer-visit volume",
    "events": "conference sponsorships or event costs landing in a different month than planned",
    "subscription": "new-logo bookings, expansion, or churn versus plan",
    "services": "implementation project timing and utilization",
    "rent": "facility changes or lease escalations",
    "commission": "bookings mix and accelerators tied to revenue performance",
}


def fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"{sign}${x/1_000:.1f}K"
    return f"{sign}${x:,.0f}"


def likely_driver(account: str) -> str:
    a = account.lower()
    for key, hint in DRIVER_HINTS.items():
        if key in a:
            return hint
    return "volume, price/rate, or timing differences versus the plan phasing"


def explain_line(l: VarianceLine) -> str:
    direction = "over" if l.variance > 0 else "under"
    tone = "favorable" if l.favorable else "unfavorable"
    pct = "n/a" if l.variance_pct is None else f"{l.variance_pct:+.1%}"
    return (f"{l.department} {l.account} ({l.month}) came in {fmt_money(abs(l.variance))} {direction} budget "
            f"({pct}), {tone}. Likely driver: {likely_driver(l.account)}.")


def rule_based_commentary(lines: list[VarianceLine], top_n: int = 5) -> str:
    s = summarize(lines)
    pv = s["profit_variance"]
    head = (f"Operating profit was {fmt_money(s['profit_actual'])} vs budget {fmt_money(s['profit_budget'])}, "
            f"{'a favorable' if pv >= 0 else 'an unfavorable'} variance of {fmt_money(abs(pv))}. "
            f"Revenue landed at {fmt_money(s['revenue_actual'])} ({fmt_money(s['revenue_actual']-s['revenue_budget'])} vs plan) "
            f"and expenses at {fmt_money(s['expense_actual'])} ({fmt_money(s['expense_actual']-s['expense_budget'])} vs plan). "
            f"{s['material_count']} of {s['line_count']} lines breached the materiality threshold.")
    material = sorted((l for l in lines if l.material), key=lambda l: -abs(l.variance))[:top_n]
    bullets = "\n".join(f"- {explain_line(l)}" for l in material) or "- No material variances."
    depts = rollup(lines, "department")
    worst, best = depts[0], depts[-1]
    close = (f"By department, {worst['department']} had the largest net drag on profit ({fmt_money(worst['net_impact'])}) "
             f"and {best['department']} the largest net help ({fmt_money(best['net_impact'])}). "
             "Recommended follow-ups: confirm timing vs permanent items with budget owners, and re-forecast lines "
             "whose variance repeats for 2+ months.")
    return f"{head}\n\nTop material variances:\n{bullets}\n\n{close}"


def llm_commentary(lines: list[VarianceLine], model: str = "gpt-4o-mini") -> str:  # pragma: no cover - network
    key = os.environ["OPENAI_API_KEY"]
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    facts = rule_based_commentary(lines)
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an FP&A analyst. Rewrite the facts into a concise CFO-ready "
             "variance commentary. Use ONLY numbers present in the facts. Never invent drivers as certain; say 'likely'."},
            {"role": "user", "content": facts},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def generate_commentary(lines: list[VarianceLine], use_llm: bool = False) -> str:
    if use_llm and os.environ.get("OPENAI_API_KEY"):
        try:
            return llm_commentary(lines)
        except Exception:  # fall back, never fail the report
            pass
    return rule_based_commentary(lines)
