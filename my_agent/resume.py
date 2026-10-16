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

SYSTEM_PROMPT = """
Convert a résumé into a compact, factual profile.
Rules:
- Only record what the résumé states. Do not infer skills, seniority, or years not written there.
- Every list entry is one short, self-contained line that could be quoted as evidence on its own.
- experience: one line per role, formatted "Title, Company, start–end: 2–4 concrete things done."
  Keep the dates exactly as written.
- skills: concrete technologies, languages, tools. No soft skills.
- education: degree, school, year if given.
- other: certifications, work authorization, languages, publications — only if explicitly stated.
- Leave a list empty rather than guess.
- Report tool failures rather than answering from memory."""

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
    cache_path.write_text(profile.model_dump_json(indent=2))
    return profile


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("resume.pdf")
    profile = load_profile(path)
    text = profile.model_dump_json(indent=2)
    print(text)
    print(f"\n~{len(text) // 4} tokens")  # rough: 4 chars/token. Target is under ~500.
