# Changelog

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
