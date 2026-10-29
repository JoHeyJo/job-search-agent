"""list[RequirementMatch] → MatchResult with a score. Pure Python; the model is never involved.

score = Σ weight(req) × credit(status) / Σ weight(req) × 100

Weights, credits, and the gate policy are module constants. Change them and re-run: every match
is cached, so re-scoring costs nothing. That's the point of keeping scoring out of the model.
"""

import re

from models import Listing, MatchResult, RequirementMatch, Status

WEIGHT_REQUIRED = 2.0
WEIGHT_PREFERRED = 1.0

PRIOR = 0.5  # what we assume about a requirement before seeing any evidence
PRIOR_WEIGHT = (
    4.0  # how much evidence it takes to move away from that; 4 = two required items
)

CREDIT = {Status.met: 1.0, Status.partial: 0.5, Status.unmet: 0.0}

# --- Gate policy -------------------------------------------------------------------------------
# A gate blocks a listing (moves it to the blocked bucket) when:
#   - the model marked it unmet, or
#   - it states a minimum number of years above MAX_YEARS and the model didn't find it fully met.
# A gate never blocks when it sits in a preferred section or its own wording softens it
# ("or equivalent experience", "encouraged to apply").

BLOCKING_STATUSES = {Status.unmet}
MAX_YEARS = (
    4  # entry/mid: "5+ years" blocks even at partial; "3+ years" at partial still ranks
)

SOFT_GATE = re.compile(r"or equivalent|encouraged|preferred|a plus|bonus", re.I)
_YEARS = re.compile(r"(\d+)(?:\s*[–-]\s*\d+)?\s*\+?\s*(?:years|yrs)", re.I)


def _blocks(m: RequirementMatch) -> bool:
    r = m.requirement
    if not r.gate or r.preferred or SOFT_GATE.search(r.source_span):
        return False
    if m.status in BLOCKING_STATUSES:
        return True
    yrs = _YEARS.search(r.source_span)
    return bool(yrs) and int(yrs.group(1)) > MAX_YEARS and m.status != Status.met


# --- Scoring -----------------------------------------------------------------------------------


def score(listing_id: str, matches: list[RequirementMatch]) -> MatchResult:
    if not matches:
        return MatchResult(listing_id=listing_id, matches=[], score=None)

    earned = possible = 0.0
    blocked_by = []
    for m in matches:
        w = WEIGHT_PREFERRED if m.requirement.preferred else WEIGHT_REQUIRED
        possible += w
        earned += w * CREDIT[m.status]
        if _blocks(m):
            blocked_by.append(m.requirement.text)

    return MatchResult(
        listing_id=listing_id,
        matches=matches,
        score=round(
            100 * (earned + PRIOR * PRIOR_WEIGHT) / (possible + PRIOR_WEIGHT), 1
        ),
        blocked_by=blocked_by,
    )


def rank(
    results: list[MatchResult],
) -> tuple[list[MatchResult], list[MatchResult], list[MatchResult]]:
    """Split into (ranked, blocked, unscored). ranked and blocked are both sorted by score desc."""
    unscored = [r for r in results if r.score is None]
    blocked = sorted(
        (r for r in results if r.score is not None and r.blocked_by),
        key=lambda r: -r.score,
    )
    ranked = sorted(
        (r for r in results if r.score is not None and not r.blocked_by),
        key=lambda r: -r.score,
    )
    return ranked, blocked, unscored


def explain(result: MatchResult, listing: Listing) -> str:
    """The requirement → status → evidence table. Every number in the score traces to a row here."""
    lines = [f"{listing.title} — {listing.company}  [{result.score}]", listing.url]
    if result.blocked_by:
        lines.append(f"BLOCKED by: {'; '.join(result.blocked_by)}")
    lines.append("")
    for m in result.matches:
        r = m.requirement
        kind = "pref" if r.preferred else "REQ "
        gate = " gate" if r.gate else ""
        lines.append(f"  {m.status.value:7} {kind}{gate:5} {r.text}")
        if m.evidence:
          for e in m.evidence:
              lines.append(f"          ↳ {e}")
          if m.evidence and not m.evidence_verified:
              lines.append("          (one or more evidence lines not found in profile)")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from greenhouse import fetch_board
    from match import match_listing
    from resume import load_profile

    profile = load_profile(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resume.pdf")
    )

    SENIOR = ("senior", "staff", "principal", "lead", "manager", "director")
    listings = [
        l
        for l in fetch_board("cloudflare")
        if "engineer" in l.title.lower()
        and not any(w in l.title.lower() for w in SENIOR)
    ][:10]
    by_id = {l.id: l for l in listings}

    results = [score(l.id, match_listing(profile, l)) for l in listings]
    ranked, blocked, unscored = rank(results)

    def row(r: MatchResult) -> str:
        n = len(r.matches)
        met = sum(m.status == Status.met for m in r.matches)
        part = sum(m.status == Status.partial for m in r.matches)
        return f"  {r.score:5.1f}  {met:2}/{part:2}/{n - met - part:2}  {by_id[r.listing_id].title}"

    print("RANKED         met/part/unmet")
    for r in ranked:
        print(row(r))
    if blocked:
        print("\nBLOCKED")
        for r in blocked:
            print(row(r) + f"\n         ⛔ {'; '.join(r.blocked_by)}")
    if unscored:
        print("\nNO REQUIREMENTS EXTRACTED")
        for r in unscored:
            print(f"         {by_id[r.listing_id].title}")

    if ranked:
        print("\n" + "=" * 70 + "\n" + explain(ranked[0], by_id[ranked[0].listing_id]))
