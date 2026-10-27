#!/usr/bin/env python3
"""Resolves a paper title or DOI to an official APA 7th edition reference.

Uses Crossref bibliographic search and DOI content negotiation to generate
verified, authentic APA 7th edition citation strings.
"""

from dataclasses import dataclass
import json
import sys
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request


@dataclass
class ApaCitation:
    """Container for resolved DOI and APA 7th edition reference string."""

    doi: str
    apa_string: str


class ApaResolver:
    """Resolver for APA 7th edition bibliographic citations via Crossref."""

    def __init__(self, user_agent: str) -> None:
        """Initialise the APA resolver with an identifiable User-Agent.

        Parameters
        ------------
        user_agent: str
            HTTP User-Agent string to include in API queries.

        Returns
        --------
            None: NoneType object
                No return value.
        """
        self._user_agent: str = user_agent

    def resolve_doi_from_title(self, query: str) -> Optional[str]:
        """Search Crossref to find the primary DOI matching a publication title.

        Parameters
        ------------
        query: str
            Article title or bibliographic query string.

        Returns
        --------
            str: string or None
                Resolved DOI identifier or None if no match found.
        """
        url: str = (
            f"https://api.crossref.org/works?"
            f"query.bibliographic={urllib.parse.quote(query)}&rows=1"
        )
        headers: Dict[str, str] = {"User-Agent": self._user_agent}
        req: urllib.request.Request = urllib.request.Request(
            url, headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data: Dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            items: List[Dict[str, Any]] = (
                data.get("message", {}).get("items", [])
            )
            if not items:
                return None
            doi_val: Optional[str] = items[0].get("DOI")
            return doi_val
        except Exception:
            return None

    def fetch_apa_from_doi(self, doi: str) -> Optional[str]:
        """Request APA 7th reference string via DOI content negotiation.

        Parameters
        ------------
        doi: str
            Digital Object Identifier (e.g. 10.1002/erv.2910).

        Returns
        --------
            str: string or None
                Formatted APA 7 reference string or None on error.
        """
        headers: Dict[str, str] = {
            "User-Agent": self._user_agent,
            "Accept": "text/x-bibliography; style=apa; locale=en-GB",
        }
        apa_url: str = f"https://doi.org/{urllib.parse.quote(doi)}"
        req: urllib.request.Request = urllib.request.Request(
            apa_url, headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                apa_text: str = resp.read().decode("utf-8").strip()
            return apa_text
        except Exception:
            return None

    def resolve(self, query: str) -> Optional[ApaCitation]:
        """Resolve a title or DOI query to an ApaCitation object.

        Parameters
        ------------
        query: str
            Paper title, bibliographic citation, or DOI.

        Returns
        --------
            ApaCitation: dataclass or None
                Resolved citation details or None if unresolved.
        """
        raw_query: str = query.strip()
        doi: Optional[str] = raw_query
        if not raw_query.startswith("10."):
            doi = self.resolve_doi_from_title(raw_query)

        if not doi:
            return None

        apa_string: Optional[str] = self.fetch_apa_from_doi(doi)
        if not apa_string:
            return None

        return ApaCitation(doi=doi, apa_string=apa_string)


def main() -> None:
    """Execute CLI citation resolution.

    Returns
    --------
        None: NoneType object
            Prints formatted citations to standard output.
    """
    user_agent: str = (
        "ScientificWriterAPA/1.0 (mailto:research@nottingham.ac.uk)"
    )
    resolver: ApaResolver = ApaResolver(user_agent=user_agent)
    for arg in sys.argv[1:]:
        citation: Optional[ApaCitation] = resolver.resolve(arg)
        if citation:
            print(f"DOI: https://doi.org/{citation.doi}\nAPA: {citation.apa_string}")
        else:
            print(f"No match found for: {arg}")


if __name__ == "__main__":
    main()
