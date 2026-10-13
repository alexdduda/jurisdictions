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
| 2019 Canadian Election Study: authors, licence CC BY-NC 4.0 | Harvard Dataverse dataset metadata (doi:10.7910/DVN/DUS88V) |

## Computed from the project's own data (reproducible)

| claim | where |
|---|---|
| Interprovincial migration 0.75% a year; Quebec lowest at 0.35% | `data/raw/17100022.csv`, `17100009.csv` |
| Between/within-province disagreement (schools 0.08, environment 0.20, redistribution 0.21, carbon tax 0.24) | `data/scripts/ces_disagreement.py` |
| Emissions per person vs. carbon-tax support across provinces: r = -0.82, p = 0.003 | 2024 ECCC emissions, Statistics Canada population, CES 2019 |
| Provincial spending spread, income elasticities, market-income spread | `tiebout/canada.py`, `validation/` |

## Not verified

- Commuting between provinces is close to zero outside Ottawa-Gatineau
  (claimed by the automated review; the census commuting-flow tables were not
  downloaded). The model only assumes interprovincial transit spillover is
  small (0 to 10%).
- Research claiming transit economies of scale run out at metropolitan size
  (cited by the automated review). Not used as evidence; the page presents
  scale savings as unmeasured.
- Whether Bill C-4 (2025) has repealed the consumer fuel charge in statute.
  The page says only that the charge was set to zero.
