# Income sensitivity

`country_income_fy2015.csv` is the retained author-coded World Bank FY2015 country lookup. `active_outbreak_panel_income_fy2015.csv` joins it to the canonical main panel. The method protocol records the source, category definition, timing and prespecified inference.

Current panel reconstruction: `../build_panels.py` (pure Python; supersedes the former Node builder). Model execution: `run_income_sensitivity.py`. Full execution order is in the [root reproduction guide](../../../docs/REPRODUCTION.md); variable/source details are in the [data dictionary](../../../docs/DATA_DICTIONARY.md).
