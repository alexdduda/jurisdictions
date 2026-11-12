# How these findings compare with published work

Each finding of this project next to the closest published evidence. "Agrees"
means the published work reaches the same conclusion by a different method;
"differs" says where and why. Sources were read at least as abstracts on two
independent sites (publisher or repository, plus an index or mirror) unless
noted. Checked November 2026. None of these authors has reviewed this project.

| this project finds | closest published evidence | relation |
|---|---|---|
| Canadians disagree far more within provinces than provinces disagree with each other (between-province spread is 8% to 24% of within-province spread, 2019 Canadian Election Study) | Environics Institute, *Confederation of Tomorrow 2020*: on the economy versus the environment, no option had a majority and "this division exists within each province", not between regions (report; Maclean's piece by the authors) | Agrees, different survey and question. The same survey series (2019) found provincial differences larger than urban-rural ones on lists of concerns, which this project does not test |
| Where provinces differ, costs explain it: emissions per person vs. carbon-tax support, r = -0.82 | No published Canadian estimate of this exact correlation was found | New; reproducible from public data (VERIFICATION.md) |
| Canadians move for income, not services | Day and Winer, *Interregional Migration and Public Policy in Canada* (McGill-Queen's, 2012) and *International Tax and Public Finance* 13(5), 2006: policy-induced migration, 1974-1996 tax-file data, is real but small next to wages and employment; political and economic shocks (Quebec in the 1970s, the 1992 cod moratorium) matter more | Agrees, with far better data than this project's provincial panel |
| For climate, a carbon price keeps 99% of the attainable gain; one uniform national quantity standard keeps 44% | Canada's Ecofiscal Commission, *Bridging the Gap* (2019): carbon pricing is the lowest-cost way to meet the targets; a well-designed set of *flexible* regulations performs almost as well; regulation- and subsidy-heavy paths cost more (Commission's annual report; CBC and Globe and Mail coverage) | Agrees on the ranking. The project's standard is uniform and inflexible, which is why it does worse than Ecofiscal's flexible regulations |
| Redistribution belongs at the national level (98% of sampled worlds, even with nobody moving) | Feldstein and Wrobel, "Can state taxes redistribute income?", *J. Public Econ.* 68(3), 1998: US states cannot redistribute because gross wages adjust within a few years. The textbook assignment (Musgrave; Oates 1972) says the same | Agrees on the answer by a different route: Feldstein and Wrobel rely on mobility; this project finds it even without mobility, because a province's own redistribution is limited by its narrower tax base and cost of funds |
| Equalization beats centralizing where provinces raise money cheaply | Smart, *Canadian J. Econ.* 31(1), 1998, and "Raising taxes through equalization", 40(4), 2007: capacity equalization changes provincial tax incentives and can offset deadweight loss | Related, not the same question: Smart studies the incentive effects of Canada's actual formula, which this project does not model |
| Schools: provincial control (with equalization) beats one national standard | Oates (1972) decentralization theorem; Besley and Coate, *J. Public Econ.* 87(12), 2003: with benevolent government the case for decentralization weakens, and it rests on political economy (conflict over shared costs) and on spillovers versus taste differences | Consistent with Oates. Besley and Coate is the main challenge: this project's central rule is uniform, as Oates assumed, and its governments are median-voter, not legislatures bargaining over shared costs |
| Transit: cities, unless a national network would save 5% to 10% | Horak, *Governing Public Transit in Canada: A Primer* (Western University, 2025): transit is a municipal responsibility in most provinces, with many governance models. Eidelman, Forman and Slack, IMFG *Who Does What* No. 6 (2023), on the municipal role in transportation | Agrees with how Canada actually assigns it; those works are descriptive and don't estimate the welfare trade-off |
| Many cities (this update): see "Many cities per province" below | Ahrend, Farchy, Kaplanis and Lembcke, "What makes cities more productive?" (OECD Regional Development WP 2014/05; LSE SERC DP 178): twice as many municipalities in a metropolitan area goes with about 6% lower productivity, an effect almost halved where a metropolitan governance body exists. Germany, Mexico, Spain, UK, US | Complementary: this project's "city" is already the whole metropolitan area (the OECD's governance body), so it models the decision that body makes, not the fragmentation it fixes |
| Backtest: with 1986-1995 data the model still says redistribution belongs nationally; Canada moved the other way in 1996 (CHST) | Provincial social-services spending afterwards fell from 4.4% to 3.4% of GDP and spread out (this project's FMS series); the 1995 budget cuts and the late-1990s recovery also explain part of it | Consistent with the model's prediction for provincial choice, not proof of it |
| A carbon price passes on real welfare but not as voters see it; the best passable rule is a quantity floor | Mildenberger, Lachapelle, Harrison and Stadelmann-Steffen, *Nature Climate Change* 12 (2022): low awareness and underestimation of Canada's rebates, and rebate information did not raise support. The consumer charge was set to zero on April 1, 2025, while industrial pricing stayed | Agrees; the textbook argument that hidden costs (regulation) pass more easily than visible ones (taxes) |
| Equalization is the rule with concentrated losers | Alberta's 2021 referendum: 61.7% voted to remove equalization from the Constitution (Elections Alberta) | Agrees on where opposition comes from |
| Utilitarian totals can't see concentrated minorities | Charter s. 23 and the constitutional history of s. 93 (VERIFICATION.md) | A limit acknowledged, not a finding to compare |

## Directly comparable studies that do not exist (as far as found)

No published study was found that scores Canada's division of powers across
several policy areas with one calibrated model and a regret-based robustness
criterion. The closest in spirit:

- Alesina and Spolaore, *The Size of Nations* (MIT Press, 2003): the same
  trade-off between scale economies and heterogeneity of preferences, applied
  to country borders rather than to policy assignment.
- Hooghe, Marks and Schakel, Regional Authority Index (96 countries,
  1950-2018): measures how much authority regions *have*, not how much they
  *should* have. A natural benchmark for a cross-country version.

## What would make a fair comparison

The two pieces of published evidence this project most needs, and does not
have, are the ones flagged on the page as deciding verdicts: the marginal cost
of public funds at each level of government (Dahlby and Ferede give provincial
and federal estimates in different years; no matched pair), and transit network
scale economies in Canada.
