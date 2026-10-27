"""Neuri literature and scientific writing subsystem.

Provides APA 7th edition bibliographic resolution, Google Scholar corpus
fetching, and 5-pass referee diagnostic auditing.
"""

from neuri.literature.apa7 import ApaCitation, ApaResolver
from neuri.literature.referee import (
    AuditFinding,
    AuditReport,
    RefereeAuditor,
    SeverityLevel,
)
from neuri.literature.scholar_fetcher import (
    ScholarCorpusFetcher,
    ScholarSearchResult,
)

__all__: list[str] = [
    "ApaCitation",
    "ApaResolver",
    "AuditFinding",
    "AuditReport",
    "RefereeAuditor",
    "ScholarCorpusFetcher",
    "ScholarSearchResult",
    "SeverityLevel",
]
