# Does Default Stay Local?

Code, data and figures for *Does Default Stay Local? State Default and City Credit in the 1840s*, by Amey Garg.

Paper: https://doi.org/10.5281/zenodo.23506736

In the early 1840s several US states stopped paying their debts, and the federal government refused to step in. The paper asks two things. Did bond markets treat that refusal as a credible commitment? And when a state defaulted, did the market also punish the state's own cities, which had not defaulted, or did it keep city credit and state credit apart?

I use bond prices from the EH.Net Early U.S. Securities Prices database, turn them into yields, and compare state bonds with city bonds before and after the no-bailout signal. The signal is dated February 11, 1843. The after-signal windows start on April 1, 1843, and quotes from February 11 to March 31 are left out of both windows.

## Main results

Gap between the state's yield and its city's yield, in percentage points. The unit is a date on which both bonds were quoted. Standard errors are Newey-West and the intervals are the mean plus or minus 1.96 standard errors (`scripts/hac_standard_errors.py`, saved in `output/hac_standard_errors.csv`).

| Pair and window | Dates | Mean gap | Std. error | 95% interval |
|---|---|---|---|---|
| Pennsylvania minus Philadelphia, before Feb 11 1843 | 328 | 1.49 | 0.404 | [0.70, 2.29] |
| Pennsylvania minus Philadelphia, after (Feb 1844 to Jan 1845) | 41 | 2.68 | 0.112 | [2.46, 2.90] |
| Change, after minus before | | 1.19 | 0.420 | [0.36, 2.01] |
| Pennsylvania minus Pittsburgh, after (from Apr 1 1843) | 83 | 2.48 | 0.269 | [1.95, 3.01] |
| Ohio minus Cincinnati, after (from Apr 1 1843) | 255 | -0.08 | 0.090 | [-0.26, 0.09] |

Pennsylvania's own yield rises while its cities' yields barely move. Ohio never defaulted, and Cincinnati trades with it.

Canal bonds (Section 4.4), from `output/canal_summary.csv`:

| | Value | Quotes |
|---|---|---|
| Indiana bonds paid second, mean yield | 48.38% | 41 |
| Indiana bonds paid first, mean yield | 17.96% | 94 |
| Gap | 30.43 points | |
| Gap with both unusual quotes kept / only the $50 quote dropped | 40.04 / 41.18 points | |
| Months both groups are quoted, and months paid second yields more | 25 of 25 | |
| New York canal bonds, mean yield from Apr 1 1843 | 5.26% | 78 |

Paid first means the preferred tranches (S-0490, S-0500) and paid second means the deferred tranches (S-0480, S-0506) created by Indiana's 1847 restructuring. The headline gap leaves out two unusual quotes: the S-0506 price of $1 (Oct 1851) and the S-0480 price of $50 (Sep 1850). The New York mean leaves out the S-1820 price of 160.00 on Oct 14 1848, a transcription error.

## Layout

```
data/raw/       EH.Net price files and the securities codebook
scripts/        the pipeline, in the order below
output/         yields and comparison tables (CSV)
output/checks/  one-off diagnostic tables (see Notes)
figures/        the paper's figures, PNG and PDF
LICENSE         MIT (code)
```

## Which script produces what

| Script | Output | Figure in `figures/` | Paper section |
|---|---|---|---|
| `parse_securities.py` | `philadelphia_state_debt_prices.csv`, `new_york_state_debt_prices.csv` | | 3, price tables |
| `identify_candidates.py` | `candidate_state_codes.csv` | | 3, matching codes to states |
| `calculate_yields.py` | `primary_yields.csv` | | 3 and 4, yields for the five states |
| `build_yield_charts.py` | | `fig2_states_panic`, `fig3_states_after_signal`, `fig4_ohio_alabama_long_run` | 4, state-level yields |
| `compare_canal_robustness.py` | `canal_robustness_yields.csv`, `canal_summary.csv` | `fig1_canal_bonds` | 4.4, canal bonds, paid first and paid second |
| `compare_city_vs_state.py` | `city_vs_state_yields.csv` | `fig5_philadelphia_vs_pennsylvania` | 5, Philadelphia and Pennsylvania |
| `compare_city_vs_state_cincinnati_pittsburgh.py` | `city_vs_state_pittsburgh.csv`, `city_vs_state_cincinnati.csv` | `fig6_pittsburgh_vs_pennsylvania`, `fig7_cincinnati_vs_ohio` | 5, Pittsburgh and Cincinnati |
| `hac_standard_errors.py` | `hac_standard_errors.csv` | | 5, results table |
| `pa_bridge_secondary.py` | `pa_bridge_secondary.csv` | | Pennsylvania past Dec 1844, extended view |
| `make_paper_charts.py` | | all seven figures | the paper's versions, without titles or footnotes |

The Philadelphia second-bond check (C-1260) is in `output/checks/`; see the Notes.

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

Running `build_yield_charts.py` and the `compare_*.py` scripts also writes captioned versions of the charts to `output/`. Those are not tracked. `figures/` holds the files used in the paper. Running `make_paper_charts.py` again redraws the same figures, but the layout can shift by a pixel or so, so the files are not byte for byte the same.

## Method in brief

- **Yields.** Yield to maturity, `[C + (100 - P) / n] / [(100 + P) / 2]`, where the codebook gives a maturity year. Current yield, `C / P`, where it does not (Alabama, Indiana, the city bonds). Quotes within a year of maturity or past it are flagged and left out of the trend lines.
- **Default periods.** While a state is in default, current yield replaces yield to maturity, because yield to maturity assumes repayment at par on schedule. Pennsylvania is treated as in default from August 1842 to February 1845, Indiana from January 1841 onward.
- **Groups.** Defaulted (Pennsylvania, Indiana), survived but at risk (Alabama, New York), and never at risk (Ohio). Alabama is treated as not having defaulted, following Wallis and other secondary sources.
- **Bond type.** The main comparison uses general-obligation bonds only. Canal bonds, which have a revenue pledge, are compared separately.
- **Two windows.** The panic window (the 1837 shock and its aftermath) and the policy window (after the February 1843 no-bailout signal) are kept separate.

## Data

- All price data come from the EH.Net *Early U.S. Securities Prices* database: https://eh.net/database/early-u-s-securities-prices/ . The files used are `New-York.xls`, `Philadelphia1.xls` and the codebook `Securities Index.xls`, copied unchanged into `data/raw/`. The data belong to their original compilers; see EH.Net for terms and citation.
- Two things to know about the New York file. Its state debt is split across two sheets ("NY State Debt" and "Other State Debt"), and the second one holds other states' bonds quoted in New York. The parser tags each column with its sheet.

## Notes

- Everything in `output/` other than `checks/` is produced by the scripts and reproduces from the raw files.
- The tables in `output/checks/` come from one-off checks run interactively (trade density, the second Philadelphia bond, the NYC and Brooklyn candidates, the Ohio yield check, the Indiana tranche check, and primary yields before the default override). The code for them is not saved here.
- The February 11, 1843 date follows the secondary literature (McGrane 1935, pp. 21-26); the seven-week gap before the after-signal window means a few days either way do not affect the results.

## How to cite

Garg, Amey (2026). "Does Default Stay Local? State Default and City Credit in the 1840s." Preprint, Zenodo. https://doi.org/10.5281/zenodo.23506736

## License

The code is released under the MIT license (see `LICENSE`). The raw data in `data/raw/` are not covered by it.
