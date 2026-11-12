# Verification log

Every factual claim the project makes outside its own computations, with the
sources it was checked against. "Two sources" means two independent credible
sources (primary documents where possible); where only one primary source or
only secondary sources could be reached, that is stated. Checked October 2026.

## Corrected by this check

| claim as it stood | finding | fix |
|---|---|---|
| "Health transfers" as Canada's example of a matching grant | The Canada Health Transfer is a block transfer with no matching (Library of Parliament publications on the CHST; Department of Finance) | Example changed to the Canada Assistance Plan, which paid 50% of provincial social assistance costs from 1966 to 1996 (Library of Parliament; Fraser Institute history of the 1995 budget) |
| "Canada uses a national carbon-price floor" | The consumer fuel charge was set to zero on April 1, 2025 (SOR/2025-107, reported by EY and Borden Ladner Gervais; Finance Canada backgrounder). Industrial pricing continues under a national benchmark (ECCC industrial carbon pricing page) | Wording updated; the model treats the current regime as industrial pricing with provincial systems |
| Schools: "language and denominational school systems are constitutionally protected" | Section 93 (1867) protects denominational schools in some provinces, not language; Quebec's guarantee was removed in 1997 (s. 93A); minority-language schooling is protected by Charter s. 23 (Justice Laws; Justice Canada; Centre for Constitutional Studies; uOttawa) | Wording made precise |
| README: "Reproduced and distributed on an 'as is' basis" | That notice is for unmodified data. This project transforms the data, so the licence requires "Adapted from Statistics Canada..." and the non-endorsement statement (Statistics Canada Open Licence, s. (b), checked on statcan.gc.ca and two mirrored copies) | README notice changed |

## Confirmed

| claim | sources |
|---|---|
| Federal cannabis minimum age 18; provinces may raise it | Alberta government cannabis page; Miller Thomson summary of Bill C-45 |
| Quebec 21 (since January 1, 2020) | CBC; provincial summary tables |
| Ontario 19 | Global News; CBC; Eastern Ontario Health Unit |
| Criminal law is federal, s. 91(27) Constitution Act, 1867 | Justice Laws; Centre for Constitutional Studies |
| Equalization commitment, s. 36(2) Constitution Act, 1982 | Dahlby (2014), U Calgary School of Public Policy; IRPP |
| Supreme Court upheld federal carbon pricing as minimum national standards, 6-3, March 25, 2021 (2021 SCC 11) | MLT Aikins; WeirFoulds; Gowling WLG; Dickinson Wright |
| Industrial carbon price path: $95/t in 2026, $100 in 2027-2029, $115 in 2030, $130 in 2035, $140 in 2040 | International Carbon Action Partnership; EY Tax News. Not found on a canada.ca page at the time of checking |
| 2024 provincial emissions (Mt CO2 eq) | ECCC Canadian Environmental Sustainability Indicators, 2024 data. Per-person figures computed with Statistics Canada population (17-10-0009); the ten-province total gives 16.6 t per person, matching ECCC's national figure |
| Saskatchewan and Alberta highest, Quebec and PEI lowest per person | The computation above; Nova Scotia Department of Finance release citing Statistics Canada (2023 data) |
| Federal minimum wage covers only federally regulated private sectors ($15 from Dec 29, 2021) | Employment and Social Development Canada; Littler |
| Ontario rent increase guideline (2.5% for 2024-2025, 2.1% for 2026) | City of Toronto; Durham Region directive |
| 71.8% of Canadians lived in a census metropolitan area, July 2021 | Statistics Canada, Annual Demographic Estimates (91-214-X) |
| Municipalities join a CMA when at least 50% of their workers commute to the core (or 25% of their jobs are held by core residents) | Statistics Canada 2011 Census Dictionary and 2010 CMA definitions; 2021 Census Dictionary figure illustrating the 50% rule. The 2021 definition page itself was behind a browser check and was not read |
| Transit share of commuters, May 2023: Vancouver 22.5%, Toronto 20.6%, Montreal 16.4% | Statistics Canada release of August 22, 2023 (as summarised by search; the page was unavailable when fetched); Daily Hive |
| Tiebout (1956), *JPE* 64(5): 416-424 | Paper PDF (UNC, Cornell course copies); Singleton's history of the paper |
| Oates (1972), *Fiscal Federalism*: decentralization theorem, assumes uniform central policy | Koethenbuerger (CESifo WP 2128); Bloch and Zenginobuz |
| Meltzer and Richard (1981), *JPE* 89: 914-927; empirical support mixed | CMU repository; Dao (2001) |
| Layard, Mayraz and Nickell (2008): elasticity of marginal utility of income 1.26 (1.19-1.34) | LSE Research Online (abstract); journal record, *J. Public Econ.* 92(8-9) |
| Dahlby and Ferede: federal PIT MCF 2.86, CIT 2.02 (2021); provincial PIT 1.44 to 3.81 (2006) | Fraser Institute study page (read in a browser); MacEwan University repository abstract of the 2012 *ITPF* article |
| French as first official language spoken, 2021: Quebec 82.2%, Canada 21.4%, New Brunswick 30.0%, Ontario 3.4%; English 13.0% in Quebec | Statistics Canada, The Daily, August 17, 2022 (read verbatim). New Brunswick also from the Government of New Brunswick; Ontario's broader definition gives 4.6% (Ontario government profile), consistent. A CBC figure of "more than 90%" for Quebec does not match this measure and was not used |
| 2016 Census population of all 35 CMAs and of each province (`data/cities/cma_2016.csv`) | Statistics Canada, The Daily, 8 February 2017, Tables 2 and 3 (98-402-X2016001), read directly. The 35 CMAs sum to 24,942,989 (71.0% of 35,151,728); a Durham Region report on the same release gives 24,945,123 (71%), a 0.01% gap consistent with the revised counts footnoted for Québec and Brantford |
| Ottawa-Gatineau 2016 split: Ontario part 991,726, Quebec part 332,057 | City of Ottawa, 2016 Census population and dwelling counts (read directly); the parts sum to Statistics Canada's 1,323,783. Quebec part also matches a second, secondary source |
| 2016 Census transit share of commuters for every CMA (Canada 12.4%; Toronto 24.3%, Montreal 22.3%, Vancouver 20.4%, Ottawa-Gatineau Ontario part 19.6%, ... St. Catharines-Niagara 2.7%) | Statistics Canada, The Daily, 29 November 2017, Table 1, read directly. Ottawa-Gatineau 18.3% and Edmonton 11.3% also match the CFRA and Statistics Canada summaries returned by search |
| Projected emissions per person by province, 2026, 2030 and 2035, with current measures and with additional measures (`data/projections/eccc_2025_per_capita.csv`) | ECCC, *Greenhouse gas and air pollutant emissions projections - 2025*, Table 17, read directly on canada.ca. One primary source; the report says the projections reflect the consumer fuel charge ending on April 1, 2025. The 2023 column reproduces this project's own 2024 calibration of the spread (log sd 0.67 against 0.66) |
| CMA and province growth, 2011 to 2016 (used only for the 2041 trend projection) | Same Statistics Canada tables as the 2016 populations; Ottawa-Gatineau parts (5.9%, 4.4%) from the City of Ottawa page |
| 2019 Canadian Election Study: authors, licence CC BY-NC 4.0 | Harvard Dataverse dataset metadata (doi:10.7910/DVN/DUS88V) |
| Canada Health and Social Transfer took effect April 1, 1996, replacing the Canada Assistance Plan's 50% federal share of provincial social assistance and social services with a block fund; the only social assistance condition kept was no minimum residency period | Department of Finance, *History of Health and Social Transfers*; Bill C-76 (1995) text on parl.ca; Library of Parliament current issue review 95-2 |
| Greater Toronto Transportation Authority Act, 2006: royal assent June 22, 2006; public name Metrolinx from December 4, 2007; legal name from 2009 (Bill 163) | Ontario e-Laws, *Metrolinx Act, 2006*; Legislative Assembly of Ontario, Bill 163 |
| Federal carbon pricing benchmark announced October 3, 2016; provinces may use their own systems; the Greenhouse Gas Pollution Pricing Act backstop applies where they don't (in force June 21, 2018; charge from 2019) | Canada.ca, *Guidance on the pan-Canadian carbon pollution pricing benchmark* and *Greenhouse Gas Pollution Pricing Act: Annual report*; ICAP |
| Alberta equalization referendum, October 18, 2021: 61.7% yes, 38.3% no; not binding on Ottawa | Elections Alberta official results; CBC; Global News |
| Provincial emissions 1990, 2005, 2024 (`data/historical/ghg_by_province_1990_2005_2024.csv`) | ECCC Canadian Environmental Sustainability Indicators, regional table (National Inventory Report 1990-2024), read directly; the 2024 column reproduces the earlier calibration (log sd 0.664 against 0.66). These are today's revised inventory figures, not those published at the time |
| Provincial and local spending by function, FY1988-89 to FY2008-09 (`data/historical/fms_1989_2009.csv`) | Statistics Canada table 10-10-0039 (FMS, archived), via the Web Data Service; each series checked against its own title by `data/scripts/fetch_fms_1989_2009.py` |
| 2025 personal income tax rates: federal 14.5% (blended; 15% to 14% on July 1, 2025), 20.5%, 26%, 29%, 33%, and every province but Quebec | CRA, *Tax rates and income brackets, 2025*, read directly |
| Quebec 2025 rates 14%, 19%, 24%, 25.75% (brackets $53,255, $106,495, $129,590) | Revenu Québec, *Income tax rates*, read directly |
| Quebec abatement: 16.5% of basic federal tax | Department of Finance, *Quebec Abatement*; TaxTips |
| Ontario surtax 2025: 20% of Ontario tax over $5,710, 36% over $7,307 | EY tax alert (Ontario budget 2025); TaxTips; KPMG 2025 table (second threshold) |
| Milligan and Smart: reported-income elasticity of the top 1% to provincial rates, 0.664, including shifting between provinces | IRPP study *Provincial Taxation of High Incomes* (2015); NBER WP 20489 |
| Mildenberger, Lachapelle, Harrison and Stadelmann-Steffen, *Nature Climate Change* 12 (2022): low awareness and substantial underestimation of carbon rebates in Canada | University of Bern repository abstract; phys.org; CTV News |

## Computed from the project's own data (reproducible)

| claim | where |
|---|---|
| Interprovincial migration 0.75% a year; Quebec lowest at 0.35% | `data/raw/17100022.csv`, `17100009.csv` |
| Transit share outside metropolitan areas, 3.0% (2016) | Implied: national 12.4% less the CMAs, weighting by population rather than workers (no published figure found). `tiebout/cities.py` |
| Between/within-province disagreement (schools 0.08, environment 0.20, redistribution 0.21, carbon tax 0.24) | `data/scripts/ces_disagreement.py` |
| Emissions per person vs. carbon-tax support across provinces: r = -0.82, p = 0.003 | 2024 ECCC emissions, Statistics Canada population, CES 2019 |
| Provincial spending spread, income elasticities, market-income spread | `tiebout/canada.py`, `validation/` |

## Not verified

- Elasticity of taxable income for all Canadian taxpayers, sampled 0.1 to 0.4 in `validation/cost_of_funds.py`: an assumption. Sillamaa and Veall (2001) find Canadian responses smaller than the US's, and a summary of Saez, Slemrod and Giertz (2012) gives about 0.25 as a mid-range figure, but no abstract read states a number.
- Share of the carbon rebate voters perceive, sampled 0 to 0.6 in `validation/politics.py`: an assumption informed by Mildenberger et al. (2022), which reports underestimation without a single figure in what was read.

- The May 2023 transit shares for Toronto, Montreal and Vancouver (Labour Force
  Survey) are used only in a sensitivity scenario. The Statistics Canada page
  was unavailable when fetched; the figures come from a search summary of it
  and from Daily Hive. They also come from a different survey than the census,
  so they are not a like-for-like update.

- Commuting between provinces is close to zero outside Ottawa-Gatineau
  (claimed by the automated review; the census commuting-flow tables were not
  downloaded). The model only assumes interprovincial transit spillover is
  small (0 to 10%).
- Research claiming transit economies of scale run out at metropolitan size
  (cited by the automated review). Not used as evidence; the page presents
  scale savings as unmeasured.
- Whether Bill C-4 (2025) has repealed the consumer fuel charge in statute.
  The page says only that the charge was set to zero.
