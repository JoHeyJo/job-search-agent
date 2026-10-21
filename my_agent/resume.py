"""Résumé → ResumeProfile. One public function: load_profile(pdf_path) -> ResumeProfile.

The PDF goes to Bedrock as a document content block; Strands' structured_output() forces the reply
into the ResumeProfile schema. Result is cached on the SHA-256 of the PDF bytes, so the model is
called once per résumé version, ever.
"""

import hashlib
import sys
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from config import settings
from models import ResumeProfile

SYSTEM_PROMPT = """You convert a résumé into a structured profile. Completeness matters more than brevity.

Rules:
- Record everything the résumé states. Do not drop bullets, skills, locations, or dates. Do not
  summarize two bullets into one.
- Do not add anything the résumé does not say. Do not infer skills, seniority, or years.
- Every list entry is one line that could be quoted as evidence on its own.
- skills: every item in every skills category, including methodologies (Agile, CI/CD) and
  categories (Cloud Computing). One item per entry.
- experience: one entry per bullet, prefixed with the role so each line stands alone:
  "Title, Company (employment type if stated), Location, start–end: <bullet text>".
  Keep the bullet's wording; keep dates exactly as written.
- education: degree or program, school, location, dates.
- other: spoken languages, certifications, work authorization, open-source work (one entry per
  bullet, prefixed with the project name), and the candidate's location if stated anywhere.
- Leave a list empty rather than guess."""

agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    structured_output_model=ResumeProfile,
    callback_handler=None,
)


def load_profile(pdf_path: Path) -> ResumeProfile:
    """
    Converts pdf to class instance of ResumeProfile. Returns JSONified version of resume tailed for agent consumption.
    """
    pdf_bytes = pdf_path.read_bytes()
    digest = hashlib.sha256(pdf_bytes).hexdigest()[:16]

    cache_dir = settings.data_dir / "profiles"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{digest}.json"
    if cache_path.exists():
        return ResumeProfile.model_validate_json(cache_path.read_text())

    profile = agent(
        [
            {
                "document": {
                    "format": "pdf",
                    "name": "resume",
                    "source": {"bytes": pdf_bytes},
                }
            },
            {"text": "Convert this résumé into a ResumeProfile."},
        ]
    )
    cache_path.write_text(profile.structured_output.model_dump_json(indent=2))
    return profile


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resume.pdf")
    profile = load_profile(path)
    text = profile.structured_output.model_dump_json(indent=2)
    print(text)
    print(f"\n~{len(text) // 4} tokens")  # rough: 4 chars/token. Target is under ~500.
