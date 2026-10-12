"""ai-auditor plugin: turn the critique of the federalism model into model changes.

The built-in stages judge whether the claims hold up. This stage asks a narrower
question for each policy area: which mechanisms missing from the simulation
does real evidence say matter, would any of them flip the verdict, and how
would we add them as a parameter? The answers feed the next uncertainty run.

    ai-auditor ... --plugin audit/structural_gaps.py
"""

from typing import Literal

from pydantic import BaseModel

from ai_auditor import Auditor, stage

AREAS = ("transit", "environment", "redistribution", "schools", "general")


class Gap(BaseModel):
    area: Literal["transit", "environment", "redistribution", "schools", "general"]
    mechanism: str
    pushes_toward: Literal["regions", "national", "ambiguous"]
    could_flip_verdict: bool
    evidence_strength: Literal["strong", "moderate", "weak"]
    evidence: str
    how_to_model: str


class GapList(BaseModel):
    gaps: list[Gap]


def _render(r: GapList) -> str:
    if not r.gaps:
        return "  (no structural gaps identified)"
    lines = []
    for g in sorted(r.gaps, key=lambda g: (AREAS.index(g.area), not g.could_flip_verdict)):
        flip = "COULD FLIP" if g.could_flip_verdict else "refines"
        lines.append(f"  [{g.area} | {flip} | {g.evidence_strength}] {g.mechanism} (pushes toward {g.pushes_toward})")
        lines.append(f"      evidence: {g.evidence}")
        lines.append(f"      to model: {g.how_to_model}")
    return "\n".join(lines)


def _summarize(r: GapList) -> str:
    flips = [g for g in r.gaps if g.could_flip_verdict and g.evidence_strength != "weak"]
    if not flips:
        return f"{len(r.gaps)} missing mechanisms found; none with moderate or strong evidence would flip a verdict"
    named = "; ".join(f"{g.area}: {g.mechanism} ({g.evidence_strength})" for g in flips)
    return f"{len(flips)} missing mechanism(s) with real evidence could flip a verdict: {named}"


@stage(
    requires=("solution", "evidence"), evidence=True, title="STRUCTURAL GAPS IN THE MODEL", order=55,
    render=_render, summarize=_summarize,
)
def structural_gaps(ctx) -> GapList:
    """Missing mechanisms that real evidence says matter, and how to add them."""
    return ctx.llm.parse(
        "The solution below reports conclusions from a simulation of fiscal federalism. "
        "Uncertainty about its parameter values has already been handled by sampling wide "
        "ranges. What sampling cannot fix is missing structure: mechanisms the model does not "
        "contain at all.\n\n"
        "For each of the four policy areas (transit, environment, redistribution, schools), "
        "and for the general lesson, list the mechanisms absent from the model that the "
        "empirical or theoretical literature says materially affect which level of government "
        "should decide. Include mechanisms the solution already acknowledges if the evidence "
        "says they matter. For each one:\n"
        "- which way it pushes authority (toward regions, toward the national level, or ambiguous)\n"
        "- whether it could plausibly flip that area's verdict, not merely change its magnitude\n"
        "- how strong the evidence is, naming specific studies, natural experiments or "
        "well-documented cases (use the gathered evidence where it applies)\n"
        "- a concrete way to add it to this simulation as a mechanism with a parameter whose "
        "range could be sampled\n\n"
        "Prefer a few well-evidenced mechanisms over a long speculative list. Do not use em "
        "dashes.\n\n"
        f"Problem:\n{ctx.problem}\n\nSolution:\n{ctx.solution}\n\n"
        f"Gathered evidence:\n{ctx['evidence'] or '(none gathered)'}",
        GapList, effort="high", max_tokens=6000,
    )


def register(auditor: Auditor) -> None:
    auditor.add(structural_gaps)
