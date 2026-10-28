# Roadmap

## v0.1: MVP ✅
- [x] Variance math with favorable/unfavorable sign logic and a %+$ materiality rule
- [x] Rule-based commentary with likely-driver hints
- [x] Optional LLM rewrite grounded on the computed facts
- [x] CLI, pytest suite, CI on Python 3.10–3.12
- [x] Live in-browser demo on GitHub Pages (upload CSV, thresholds, charts, sortable table)

## Next
- [ ] Price / volume / mix decomposition for revenue lines (needs units + price columns)
- [ ] Run-rate detection: flag variances that repeat for 2+ months as "permanent" vs "timing"
- [ ] Rolling forecast suggestion: re-forecast remaining months from the YTD trend
- [ ] Export commentary + table to Excel / PowerPoint for the monthly business review
- [ ] Bring-your-own-key LLM mode in the web demo (key kept only in browser memory)
- [ ] LLM eval set: check the generated commentary never states a number that isn't in the facts
- [ ] Pyodide build so the browser runs the exact Python package instead of the JS mirror
- [ ] Variance waterfall chart (budget profit → actual profit)
