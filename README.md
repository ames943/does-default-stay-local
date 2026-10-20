# Does Default Stay Local?

Code, data and figures for *Does Default Stay Local? City and State Credit in the Wake of America's 1840s No-Bailout Commitment*, by Amey Garg.

Paper: https://doi.org/10.5281/zenodo.23506736

In the early 1840s several US states stopped paying their debts, and the federal government refused to step in. The paper asks two things. Did bond markets treat that refusal as a credible commitment? And when a state defaulted, did the market also punish the state's own cities, which had not defaulted, or did it keep city credit and state credit apart?

I use weekly bond prices from the EH.net Early U.S. Securities Prices database, turn them into yields, and compare state bonds with city bonds before and after February 1843, when the House debate made the no-bailout stance clear.

## Main results

Gap between the state's yield and its city's yield, in percentage points, after the Apr 1843 signal. The unit is a date on which both bonds were quoted. Standard errors are Newey-West (`scripts/hac_standard_errors.py`).

| Pair | Dates | Mean gap | Std. error |
|---|---|---|---|
| Pennsylvania minus Philadelphia | 41 | +2.68 | 0.11 |
| Pennsylvania minus Pittsburgh | 83 | +2.48 | 0.27 |
| Ohio minus Cincinnati | 255 | -0.08 | 0.09 |

Pennsylvania's own yield rises while its cities' yields barely move. Ohio never defaulted, and Cincinnati trades with it.

## Layout

```
data/raw/     EH.net price files and the securities codebook
scripts/      the pipeline, in the order below
output/       yields and comparison tables (CSV)
output/checks/ one-off diagnostic tables (see below)
figures/      the paper's charts, PNG and PDF
LICENSE       MIT (code)
```

## Which script produces what

| Script | Output | Figure in `figures/` | Used for |
|---|---|---|---|
| `parse_securities.py` | `philadelphia_state_debt_prices.csv`, `new_york_state_debt_prices.csv` | | Section 3, price tables |
| `identify_candidates.py` | `candidate_state_codes.csv` | | Section 3, matching codes to states |
| `calculate_yields.py` | `primary_yields.csv` | | Sections 3 and 4, yields for the five states |
| `build_yield_charts.py` | | `chart_panic_window`, `chart_policy_short_medium`, `chart_policy_long_term` | Section 4, state-level yields |
| `compare_city_vs_state.py` | `city_vs_state_yields.csv` | `chart_city_vs_state` | Section 5, Philadelphia and Pennsylvania |
| `compare_city_vs_state_cincinnati_pittsburgh.py` | `city_vs_state_pittsburgh.csv`, `city_vs_state_cincinnati.csv` | `chart_pittsburgh_vs_pa`, `chart_cincinnati_vs_ohio` | Section 5, Pittsburgh and Cincinnati |
| `hac_standard_errors.py` | `hac_standard_errors.csv` | | Section 5, results table |
| `compare_canal_robustness.py` | `canal_robustness_yields.csv` | `chart_canal_robustness` | Section 6, canal bonds and the Indiana preferred/deferred gap |
| `pa_bridge_secondary.py` | `pa_bridge_secondary.csv` | | Pennsylvania past Dec 1844, extended view |
| `make_paper_charts.py` | | all seven figures above | the paper's versions, without titles or footnotes |

The Philadelphia second-bond check (C-1260) is in `output/checks/`; see the notes at the bottom.

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd scripts
python3 parse_securities.py
python3 identify_candidates.py
python3 calculate_yields.py
python3 pa_bridge_secondary.py
python3 build_yield_charts.py
python3 compare_city_vs_state.py
python3 compare_city_vs_state_cincinnati_pittsburgh.py
python3 compare_canal_robustness.py
python3 hac_standard_errors.py
python3 make_paper_charts.py
```

Running `build_yield_charts.py` and the `compare_*.py` scripts also writes captioned versions of the charts to `output/`. Those are not tracked.

## Method in brief

- **Yields.** Yield to maturity, `[C + (100 - P) / n] / [(100 + P) / 2]`, where the codebook gives a maturity year. Current yield, `C / P`, where it does not (Alabama, Indiana, the city bonds). Quotes within a year of maturity or past it are flagged and left out of the trend lines.
- **Default periods.** While a state is in default, current yield replaces yield to maturity, because yield to maturity assumes repayment at par on schedule. Pennsylvania is treated as in default from August 1842 to February 1845, Indiana from January 1841 onward.
- **Groups.** Defaulted (Pennsylvania, Indiana), survived but at risk (Alabama, New York), and never at risk (Ohio). Alabama is treated as not having defaulted, following Wallis and other secondary sources.
- **Bond type.** The main comparison uses general-obligation bonds only. Canal bonds, which have a revenue pledge, are in a separate robustness comparison.
- **Two windows.** The panic window (the 1837 shock and its aftermath) and the policy window (after the February 1843 no-bailout signal) are kept separate.

## Data

- All price data come from the EH.Net *Early U.S. Securities Prices* database: https://eh.net/database/early-u-s-securities-prices/ . The files used are `New-York.xls`, `Philadelphia1.xls` and the codebook `Securities Index.xls`, copied unchanged into `data/raw/`. The data belong to their original compilers; see EH.Net for terms and citation.
- Two things to know about the New York file. Its state debt is split across two sheets ("NY State Debt" and "Other State Debt"), and the second one holds other states' bonds quoted in New York. The parser tags each column with its sheet.

## Notes

- Everything in `output/` other than `checks/` is produced by the scripts and reproduces from the raw files.
- The tables in `output/checks/` come from one-off checks run interactively (trade density, the second Philadelphia bond, the NYC and Brooklyn candidates, the Ohio yield check, the Indiana tranche check, and primary yields before the default override). The code for them is not saved here.
- Dates and the no-bailout anchor rest on secondary sources plus a Congressional Globe page (27th Congress, 3rd session, pp. 283-284) where the exact day could not be read.

## License

The code is released under the MIT license (see `LICENSE`). The raw data in `data/raw/` are not covered by it.
