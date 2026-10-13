"""The default world: four policy domains with deliberately different profiles.

These numbers are assumptions, not measurements. They are chosen so each
domain sits in a different corner of the trade-off space; the phase maps in
the report show how the answer moves when you change them.
"""

from .model import Domain, World

SCHOOLS = Domain(
    "schools",
    heterogeneity=0.20,  # regions disagree a lot about what they want
    within=0.10,
    spillover=0.05,      # benefits mostly stay local
    scale=0.0,
)
ENVIRONMENT = Domain(
    "environment",
    heterogeneity=0.06,  # broad agreement
    within=0.12,
    spillover=0.60,      # most of the benefit leaks to neighbours (air, rivers)
    scale=0.0,
)
TRANSIT = Domain(
    "transit",
    heterogeneity=0.10,
    within=0.10,
    spillover=0.20,
    scale=0.30,          # networks are cheaper to build as one system
)
REDISTRIBUTION = Domain("redistribution", kind="redistribution")
CLIMATE = Domain(
    "climate",
    heterogeneity=0.06,
    within=0.28,
    spillover=0.8,        # most of the benefit of cutting emissions lands elsewhere
    private_costs=True,   # emitters pay, not budgets
    abatement_sd=0.66,    # spread of provincial emissions per person (log sd)
    abatement_taste_corr=0.82,
)

DEFAULT_WORLD = World(domains=(SCHOOLS, ENVIRONMENT, TRANSIT, REDISTRIBUTION, CLIMATE))
