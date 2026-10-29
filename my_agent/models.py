from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Listing(BaseModel):
    """One job posting, normalized across ATS sources. Produced by adapters, never by the model."""

    id: str  # f"{source}:{board}:{job_id}" — stable, unique, cache key
    source: str  # "greenhouse" | "lever" | "ashby" | "smartrecruiters"
    company: str
    title: str
    url: str
    description: str  # plain text, HTML stripped
    location: str | None = None
    fetched_at: datetime


class Requirement(BaseModel):
    """One requirement the model extracted from a Listing.description."""

    text: str  # the requirement in the model's words
    source_span: str  # verbatim from description; Python verifies it's really there
    preferred: bool = False  # True if it came from a "nice to have" / preferred section
    gate: bool = False  # clearance, authorization, degree, min years — fail = blocked


class ResumeProfile(BaseModel):
    """Compact résumé, parsed once. Every entry is a short line the model can quote as evidence."""

    skills: list[str] = []
    experience: list[str] = []  # "Senior Engineer, Acme, 2021–2024: built X, led Y"
    education: list[str] = []
    other: list[str] = []  # certifications, work authorization, languages


class Status(str, Enum):
    met = "met"
    partial = "partial"
    unmet = "unmet"


class RequirementMatch(BaseModel):
    """The model's judgment of one requirement against the profile, plus Python's verification."""

    requirement: Requirement
    status: Status
    evidence: list[str] = []
    evidence_verified: bool = (
        False  # set by Python; False + met → downgraded to partial
    )


class MatchResult(BaseModel):
    """Everything about one listing after scoring. score is computed by Python, never the model."""

    listing_id: str
    matches: list[RequirementMatch]
    score: float | None = None  # 0–100; None until scored
    blocked_by: list[str] = []  # texts of failed gate requirements
