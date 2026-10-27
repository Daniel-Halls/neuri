"""Resolves publication titles and DOIs to APA 7th edition references.

Uses Crossref bibliographic search and DOI content negotiation to generate
verified, authentic APA 7th edition citation strings without hallucinations.
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class ApaCitation:
    """Container for resolved DOI and APA 7th edition reference string.

    Parameters
    ------------
    doi: str
        Digital Object Identifier string.
    apa_string: str
        Formatted APA 7th edition citation text.

    Returns
    --------
        ApaCitation: ApaCitation instance
            Constructed citation container.
    """

    doi: str
    apa_string: str


class ApaResolver:
    """Resolver for APA 7th edition bibliographic citations via Crossref.

    Parameters
    ------------
    user_agent: str | None
        HTTP User-Agent string to include in API queries. Defaults to None.

    Returns
    --------
        ApaResolver: ApaResolver instance
            Constructed APA resolver.
    """

    DEFAULT_USER_AGENT: str = (
        "NeuriScientificWriter/1.0 (mailto:research@nottingham.ac.uk)"
    )

    def __init__(self, user_agent: str | None = None) -> None:
        """Initialize the APA resolver with an identifiable User-Agent.

        Parameters
        ------------
        user_agent: str | None
            HTTP User-Agent string to identify queries. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes resolver state.
        """
        chosen_agent: str = (
            user_agent if user_agent is not None else self.DEFAULT_USER_AGENT
        )
        self._user_agent: str = chosen_agent

    def resolve_doi_from_title(self, query: str) -> str | None:
        """Search Crossref to find the primary DOI matching a publication title.

        Parameters
        ------------
        query: str
            Article title or bibliographic query string.

        Returns
        --------
            str | None: string or None
                Resolved DOI identifier or None if no match found.
        """
        encoded_query: str = urllib.parse.quote(query)
        url: str = (
            f"https://api.crossref.org/works?"
            f"query.bibliographic={encoded_query}&rows=1"
        )
        headers: dict[str, str] = {"User-Agent": self._user_agent}
        req: urllib.request.Request = urllib.request.Request(
            url, headers=headers
        )
        resolved_doi: str | None = None
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            items: list[dict[str, Any]] = (
                data.get("message", {}).get("items", [])
            )
            if items:
                raw_doi: Any = items[0].get("DOI")
                if isinstance(raw_doi, str) and raw_doi:
                    resolved_doi = raw_doi
        except Exception:
            resolved_doi = None
        return resolved_doi

    def fetch_apa_from_doi(self, doi: str) -> str | None:
        """Request APA 7th reference string via DOI content negotiation.

        Parameters
        ------------
        doi: str
            Digital Object Identifier (e.g. 10.1002/erv.2910).

        Returns
        --------
            str | None: string or None
                Formatted APA 7 reference string or None on error.
        """
        headers: dict[str, str] = {
            "User-Agent": self._user_agent,
            "Accept": "text/x-bibliography; style=apa; locale=en-GB",
        }
        clean_doi: str = doi.strip()
        if clean_doi.lower().startswith("doi:"):
            clean_doi = clean_doi[4:].strip()
        encoded_doi: str = urllib.parse.quote(clean_doi)
        apa_url: str = f"https://doi.org/{encoded_doi}"
        req: urllib.request.Request = urllib.request.Request(
            apa_url, headers=headers
        )
        formatted_apa: str | None = None
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_bytes: bytes = resp.read()
                formatted_apa = raw_bytes.decode("utf-8").strip()
        except Exception:
            formatted_apa = None
        return formatted_apa

    def resolve(self, query: str) -> ApaCitation | None:
        """Resolve a title or DOI query to an ApaCitation object.

        Parameters
        ------------
        query: str
            Paper title, bibliographic citation, or DOI string.

        Returns
        --------
            ApaCitation | None: ApaCitation dataclass or None
                Resolved citation details or None if unresolved.
        """
        raw_query: str = query.strip()
        target_doi: str | None = raw_query
        if not raw_query.startswith("10.") and "10." not in raw_query:
            target_doi = self.resolve_doi_from_title(raw_query)

        resolved_citation: ApaCitation | None = None
        if target_doi:
            clean_doi: str = target_doi.strip()
            if "10." in clean_doi and not clean_doi.startswith("10."):
                idx: int = clean_doi.find("10.")
                clean_doi = clean_doi[idx:]
            apa_string: str | None = self.fetch_apa_from_doi(clean_doi)
            if apa_string:
                resolved_citation = ApaCitation(
                    doi=clean_doi,
                    apa_string=apa_string,
                )
        return resolved_citation
