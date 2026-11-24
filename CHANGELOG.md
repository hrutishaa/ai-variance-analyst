# Changelog

## 0.3.0 (2026-11-23)
### Added
- `decompose_pvm()` (`variance_analyst/pvm.py`): splits each department's revenue variance into **price**, **volume** and **mix** effects using optional `budget_units` / `actual_units` columns (average price = $ / units). The three effects add up exactly to actual − budget, per product and per group. Whole-period by default, or `by_month=True`.
- Edge cases handled: new products (no budget units) land in mix, not price; discontinued products have no price effect; a group with no budget units is all volume; $ with zero units, negative units, half-filled unit pairs and a lone unit column are rejected with a clear error.
- Commentary section "Price / volume / mix" with each group's bridge and its largest effect explained (price per unit, units sold, or unit share). Appears automatically when the CSV has unit columns, so the CLI prints it too.
- Web demo: *Revenue price / volume / mix* card with a budget → price → volume → mix → actual bridge chart and a product table (units, average price, effects), plus a *Load price/volume/mix sample* button. Logic lives in `docs/pvm.js`.
- New synthetic sample `data/sample_revenue_pvm.csv` (3 subscription plans, an implementation service and 2 unit-less expense lines over 6 months).
- 19 tests: textbook price / volume / mix cases, the exact-sum check on the sample (whole period and monthly), edge cases, CSV validation, commentary and CLI, and a parity test that runs `docs/pvm.js` under Node and compares it with the Python results.

### Changed
- CI also checks the PVM sample is the same file in `data/` and `docs/`, and smoke-tests the CLI on it.

## 0.2.0 (2026-11-16)
### Added
- `detect_run_rate()` and `run_lengths()` (`variance_analyst/runrate.py`): classify each line item as `run-rate`, `timing` or `none` from its streak of material, same-direction months ending at the latest month. Non-material months, sign flips and missing months break a streak.
- Commentary section "Run-rate vs timing" with streak length, date range and cumulative variance, plus timing items and new-this-month items to watch.
- CLI flag `--run-rate-months N` (default 2, minimum 2).
- Web demo: *Run-rate months* control, *Run-rate items* KPI and a sortable *Pattern* column (`run-rate ×N` / `timing`), mirroring the Python logic.
- 23 tests covering streaks, sign flips, non-material and missing months, single-month data, zero budget, duplicates and the CLI flag.

### Changed
- Sample data: the March cloud hosting spike now persists through June and the subscription revenue miss repeats in June, so the sample shows both run-rate and timing variances.

## 0.1.0 (2026-10-28)
- MVP: variance math with favorable/unfavorable logic, %+$ materiality, rule-based commentary with optional LLM rewrite, CLI, pytest suite, CI and live demo.
