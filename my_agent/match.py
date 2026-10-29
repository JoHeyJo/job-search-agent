"""Requirements × ResumeProfile → list[RequirementMatch]. One public function: match_listing(profile, listing).

The model judges each requirement: met / partial / unmet and quotes the profile line that proves it.
Python verifies the quote is really in the profile. A "met" with no verifiable evidence is downgraded
to "partial" — the model doesn't get credit for a match it can't point to.
"""

import hashlib
import json
import re

from pydantic import BaseModel
from datetime import date
from strands import Agent
from strands.models import BedrockModel

from config import settings
from extract import extract_requirements
from models import Listing, Requirement, RequirementMatch, ResumeProfile, Status

SYSTEM_PROMPT = """You compare job requirements against a candidate profile.

For each requirement, decide:
- met: a profile line explicitly demonstrates the whole requirement.
- partial: a profile line demonstrates the requirement with one clear, nameable gap —
  fewer years than asked, a sibling technology in the same family, the same task at
  smaller scale, or one half of an "A and B" requirement explicitly satisfied.
- unmet: nothing in the profile addresses it. If you would need to explain why the
  evidence is related, it is unmet. When torn between partial and unmet, choose unmet.

evidence: one to three profile lines, each copied exactly (or a contiguous substring of one).
Use more than one line when the requirement needs it: for "N years of X", cite every role line
whose dates should count; for compound requirements, cite the line for each part. For unmet,
evidence is an empty list. Do not include the leading ‘- ‘ bullet.

- A requirement listing alternatives ("X, Y, or Z"; "such as A or B") is met if any one alternative
  is met. The named tools are examples, not a checklist.
- A requirement offering "or equivalent experience" is judged on the experience branch.

Be strict:
- A skill merely listed does not satisfy a stated minimum of years. Use partial unless the
  experience lines clearly cover the duration.
- Do not assume unstated skills from job titles or company names.
- Judge every requirement by its index. Do not skip any."""

_TYPO = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",  # curly single quotes
        "\u201c": '"',
        "\u201d": '"',  # curly double quotes
        "\u2013": "-",
        "\u2014": "-",  # en and em dashes
        "\u00a0": " ",  # non-breaking space
    }
)

_BULLET = re.compile(r"^\s*[-*•]\s+")


class _Judgment(BaseModel):
    requirement_index: int
    status: Status
    evidence: list[str] = []


class _Matching(BaseModel):
    judgments: list[_Judgment]


def _agent() -> Agent:
    return Agent(system_prompt=SYSTEM_PROMPT, callback_handler=None)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_TYPO)).strip()


def _strip_bullet(s: str | None) -> str | None:
    """Remove a leading list marker the model may copy from profile_text."""
    return _BULLET.sub("", s) if s else s


def profile_lines(profile: ResumeProfile) -> list[str]:
    return profile.skills + profile.experience + profile.education + profile.other


def profile_text(profile: ResumeProfile) -> str:
    out = []
    for section in ("skills", "experience", "education", "other"):
        items = getattr(profile, section)
        if items:
            out.append(f"## {section}")
            out.extend(f"- {line}" for line in items)
    return "\n".join(out)


def evidence_in_profile(evidence: str | None, lines: list[str]) -> bool:
    """Evidence must sit inside a single profile line (whitespace-tolerant)."""
    if not evidence:
        return False
    e = _norm(evidence)
    return any(e in _norm(line) for line in lines)


def verify(
    judgments: list[_Judgment], reqs: list[Requirement], lines: list[str]
) -> list[RequirementMatch]:
    """Pure Python: zip judgments back to requirements, check every evidence line, apply the downgrade rule."""
    by_index = {
        j.requirement_index: j
        for j in judgments
        if 0 <= j.requirement_index < len(reqs)
    }
    matches = []
    for i, req in enumerate(reqs):
        j = by_index.get(i)
        if j is None:  # model skipped it → unmet, no credit
            matches.append(RequirementMatch(requirement=req, status=Status.unmet))
            continue
        evidence = [
            e for e in j.evidence if e
        ]  # drop empty strings the model sometimes emits
        ok = bool(evidence) and all(evidence_in_profile(e, lines) for e in evidence)
        status = j.status
        if status == Status.met and not ok:
            status = Status.partial
        matches.append(
            RequirementMatch(
                requirement=req, status=status, evidence=evidence, evidence_verified=ok
            )
        )
    return matches


def match_listing(profile: ResumeProfile, listing: Listing) -> list[RequirementMatch]:
    reqs, _ = extract_requirements(listing)
    if not reqs:
        return []

    pkey = hashlib.sha256(profile.model_dump_json().encode()).hexdigest()[:8]
    cache_dir = settings.data_dir / "matches"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{pkey}__{listing.id.replace(':', '_')}.json"
    if cache_path.exists():
        return [
            RequirementMatch.model_validate(m)
            for m in json.loads(cache_path.read_text())
        ]

    req_block = "\n".join(
        f"{i}. [{'preferred' if r.preferred else 'required'}] {r.text}"
        for i, r in enumerate(reqs)
    )
    today = date.today().strftime("%B %Y")

    prompt = (
        f"Today is {today}. Treat 'Present' in the profile as {today}.\n\n"
        f"# Candidate profile\n{profile_text(profile)}\n\n# Requirements\n{req_block}"
    )

    result = _agent().structured_output(_Matching, prompt)

    matches = verify(result.judgments, reqs, profile_lines(profile))
    cache_path.write_text(
        json.dumps([m.model_dump(mode="json") for m in matches], indent=2)
    )
    return matches


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from greenhouse import fetch_board
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

    downgraded = skipped = 0
    for l in listings:
        matches = match_listing(profile, l)
        print(f"\n=== {l.title}")
        for m in matches:
            r = m.requirement
            tag = ("P" if r.preferred else "R") + (" GATE" if r.gate else "")
            flag = ""
            if m.status == Status.partial and m.evidence and not m.evidence_verified:
                flag = "  ← DOWNGRADED (evidence not in profile)"
                downgraded += 1
            print(f"  {m.status.value:7} [{tag}] {r.text}{flag}")
            if m.evidence:
                print(f'          ↳ "{m.evidence}"')

    print(f"\n{len(listings)} listings · {downgraded} met→partial downgrades")

"""
            (Shouldn't this be unmet?)
            partial [R] Fluency in English and Turkish (written and spoken)
          ↳ "Spoken language: Spanish"

            (Here is correct but the proof of "Spoken language: Spanish" doesn't make sense.)
            met     [R GATE] Fluency in English is required.
          ↳ "Spoken language: Spanish"

            (Does the supporting quote actually translate to a partial? These are soft skills that could actually require its own section in the future. But this could be ok as a partial for now.)
            partial [R] Curiosity, initiative, and a demonstrated ability to learn new technologies quickly
          ↳ "Open Source Contributor — Open Disclosure (Ruby, JavaScript, Jekyll): optimized campaign-contribution calculation algorithm; used Slack and code reviews to align on technical strategy."

          (Does the supporting quote actually translate toa partial. Seems like a stretch.)
          partial [P] Experience creating reusable technical assets such as demonstrations, code samples, technical documentation, reference architectures, or customer workshops
          ↳ "upheld coding standards via code reviews"

            (These don't seem to support a partial rating)
            partial [P] Experience working with SMB or Digital Native Business customers
          ↳ "Built and shipped full stack app (React/TypeScript front end, Python/PostgreSQL back end) now live in beta with local businesses"
"""
