"""Listing → list[Requirement]. One public function: extract_requirements(listing).

The model proposes requirements, each with a verbatim source_span. Python keeps only the ones whose
span is actually in the description. Anything else is dropped and reported — that drop is the
fabrication check this whole project exists for.
"""

import json
import re

from pydantic import BaseModel
from strands import Agent

from config import settings
from models import Listing, Requirement

SYSTEM_PROMPT = """You extract hiring requirements from a job posting.

Rules:
- One Requirement per distinct qualification. Split combined bullets ("Python and Go") only if the
  posting treats them as separate items.
- source_span: copy a contiguous substring of the posting EXACTLY as written, character for
  character. Never paraphrase, trim words from the middle, or fix typos. The span is how your work
  gets verified; a span that is not in the posting will be discarded.
- text: the requirement in plain words. May shorten the span; may not add to it.
- preferred: true only if the item sits under a heading like "Preferred", "Nice to have","Nice-to-Have Skills","Good-to-Haves", "Bonus", "Strongly Preferred Qualifications".
- gate: true only for hard eligibility: security clearance, work authorization or sponsorship,
  a required degree, a required location, or a stated minimum years of experience.
- Only extract from requirement/qualification sections. Skip responsibilities, company blurbs,
  and benefits.
- Skip personality and soft-skill items (curiosity, communication, team player, collaboration, passion, ownership, or mindset) — they cannot be verified against a résumé.
- If the posting has no requirements, return an empty list. Never invent.
"""

# Python's own view of what a gate is, independent of the model's flag.
GATE_PATTERNS = [
    r"\bclearance\b",
    r"\bauthoriz(ed|ation) to work\b",
    r"\bsponsorship\b",
    r"\bvisa\b",
    r"\b(bachelor|master|phd|degree)\b",
    r"\b\d+\+?\s*(years|yrs)\b",
    r"\bmust (be|reside|live|relocate)\b",
]
_GATE_RE = re.compile("|".join(GATE_PATTERNS), re.IGNORECASE)

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


class _Extraction(BaseModel):
    requirements: list[Requirement]


def _agent() -> Agent:
    return Agent(system_prompt=SYSTEM_PROMPT, callback_handler=None)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_TYPO)).strip()


def span_in_text(span: str, text: str) -> bool:
    """Exact match first; then tolerate whitespace differences only."""
    return bool(span) and (span in text or _norm(span) in _norm(text))


def extract_requirements(
    listing: Listing,
) -> tuple[list[Requirement], list[Requirement]]:
    """Returns (kept, dropped). Cached per listing id."""
    cache_dir = settings.data_dir / "requirements"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (listing.id.replace(":", "_") + ".json")
    if cache_path.exists():
        data = json.loads(cache_path.read_text())
        return (
            [Requirement(**r) for r in data["kept"]],
            [Requirement(**r) for r in data["dropped"]],
        )

    result = _agent().structured_output(
        _Extraction, f"Job title: {listing.title}\n\n{listing.description}"
    )

    kept, dropped = [], []
    for req in result.requirements:
        if span_in_text(req.source_span, listing.description):
            req.gate = req.gate or bool(_GATE_RE.search(req.source_span))
            kept.append(req)
        else:
            dropped.append(req)

    cache_path.write_text(
        json.dumps(
            {
                "kept": [r.model_dump() for r in kept],
                "dropped": [r.model_dump() for r in dropped],
            },
            indent=2,
        )
    )
    return kept, dropped


if __name__ == "__main__":
    from greenhouse import fetch_board
    import re
    from extract import extract_requirements

    SENIOR = ("senior", "staff", "principal", "lead", "manager", "director")
    listings = [
        l
        for l in fetch_board("cloudflare")
        if "engineer" in l.title.lower()
        and not any(w in l.title.lower() for w in SENIOR)
    ][:10]

    total_kept = total_dropped = 0
    years = re.compile(r"\b\d+\+?\s*(years|yrs)\b", re.I)
    for l in listings:
        kept, dropped = extract_requirements(l)
        total_kept += len(kept)
        total_dropped += len(dropped)

        in_posting = bool(years.search(l.description))
        in_gates = any(r.gate and years.search(r.source_span) for r in kept)
        if in_posting != in_gates:
            print(f"MISMATCH  posting={in_posting} gate={in_gates}  {l.title}")

        print(
            f"\n=== {l.title}  ({len(kept)} kept, {len(dropped)} dropped)\n    {l.url}"
        )
        for r in kept:
            tag = "P" if r.preferred else "R"
            gate = " GATE" if r.gate else ""
            print(f"  [{tag}]{gate} {r.text}")
            print(f'        ↳ "{r.source_span}"')
        for r in dropped:
            print(f'  [DROPPED] {r.text}\n        ↳ "{r.source_span}"')

    print(
        f"\n{len(listings)} listings · {total_kept} requirements kept · {total_dropped} dropped"
    )
