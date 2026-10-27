#!/usr/bin/env python3
"""Fetches an author's publication titles, abstracts, and open-access full texts.

Given a Google Scholar profile URL or author name, queries Scholar, OpenAlex,
and Europe PMC to build a stylistic corpus for the scientific writer skill.
"""

from dataclasses import dataclass
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse
import urllib.request


@dataclass
class ScholarSearchResult:
    """Data container for an author's extracted Google Scholar profile data."""

    author_name: Optional[str]
    titles: List[str]


class ScholarCorpusFetcher:
    """Fetcher for academic publications from Scholar, OpenAlex, and Europe PMC."""

    def __init__(self, user_agent: str) -> None:
        """Initialise the fetcher with a custom User-Agent header.

        Parameters
        ------------
        user_agent: str
            HTTP User-Agent string to identify API queries.

        Returns
        --------
            None: NoneType object
                No return value.
        """
        self._headers: Dict[str, str] = {"User-Agent": user_agent}

    def fetch_json(self, url: str) -> Dict[str, Any]:
        """Fetch and parse JSON from a remote URL.

        Parameters
        ------------
        url: str
            HTTP or HTTPS URL returning JSON.

        Returns
        --------
            dict: dictionary object
                Parsed JSON response as a dictionary.
        """
        req: urllib.request.Request = urllib.request.Request(
            url, headers=self._headers
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data: Dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            return data

    def extract_author_from_scholar(self, url: str) -> ScholarSearchResult:
        """Attempt to read author name and top titles from Google Scholar HTML.

        Parameters
        ------------
        url: str
            Google Scholar profile URL.

        Returns
        --------
            ScholarSearchResult: dataclass object
                Extracted author name and up to 15 paper titles.
        """
        try:
            req: urllib.request.Request = urllib.request.Request(
                url, headers=self._headers
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html: str = resp.read().decode("utf-8", errors="ignore")
            name_match: Optional[re.Match[str]] = re.search(
                r'<div id="gsc_prf_in"[^>]*>([^<]+)</div>', html
            )
            titles: List[str] = re.findall(
                r'class="gsc_a_at"[^>]*>([^<]+)</a>', html
            )
            detected_name: Optional[str] = (
                name_match.group(1).strip() if name_match else None
            )
            return ScholarSearchResult(
                author_name=detected_name, titles=titles[:15]
            )
        except Exception:
            return ScholarSearchResult(author_name=None, titles=[])

    def fetch_fulltext_xml(self, pmcid: str) -> Optional[str]:
        """Fetch full-text XML from Europe PMC and strip tags to prose preview.

        Parameters
        ------------
        pmcid: str
            PubMed Central identifier (e.g., PMC9546313).

        Returns
        --------
            str: string or None
                Extracted clean prose text preview or None on error.
        """
        try:
            ft_url: str = (
                f"https://www.ebi.ac.uk/europepmc/webservices/rest/"
                f"{pmcid}/fullTextXML"
            )
            req: urllib.request.Request = urllib.request.Request(
                ft_url, headers=self._headers
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_text: str = resp.read().decode("utf-8", errors="ignore")
            clean_text: str = re.sub(r"<[^>]+>", " ", xml_text)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()
            return clean_text[:25000]
        except Exception:
            return None

    def build_corpus(self, query_or_url: str) -> Dict[str, Any]:
        """Build the full corpus dictionary for an author or Google Scholar URL.

        Parameters
        ------------
        query_or_url: str
            Author name, query, or Google Scholar profile URL.

        Returns
        --------
            dict: dictionary object
                Dictionary containing detected author, titles, and paper details.
        """
        author_name: Optional[str] = None
        scholar_titles: List[str] = []
        if "scholar.google" in query_or_url:
            scholar_info: ScholarSearchResult = (
                self.extract_author_from_scholar(query_or_url)
            )
            author_name = scholar_info.author_name
            scholar_titles = scholar_info.titles

        search_name: str = author_name or query_or_url
        corpus: Dict[str, Any] = {
            "author_detected": search_name,
            "scholar_titles_found": scholar_titles,
            "papers": [],
        }

        epmc_query: str = f'AUTH:"{search_name}" AND OPEN_ACCESS:y'
        if scholar_titles:
            title_queries: str = " OR ".join(
                [f'TITLE:"{t}"' for t in scholar_titles[:6]]
            )
            epmc_query = f"({title_queries})"

        epmc_url: str = (
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
            f"query={urllib.parse.quote(epmc_query)}&resultType=core"
            f"&pageSize=10&format=json"
        )
        epmc_data: Dict[str, Any] = self.fetch_json(epmc_url)
        epmc_results: List[Dict[str, Any]] = (
            epmc_data.get("resultList", {}).get("result", [])
        )

        for item in epmc_results:
            paper: Dict[str, Any] = {
                "title": item.get("title"),
                "year": item.get("pubYear"),
                "journal": item.get("journalTitle"),
                "doi": item.get("doi"),
                "pmcid": item.get("pmcid"),
                "abstract": item.get("abstractText", ""),
                "fulltext_xml_preview": None,
            }
            pmcid: Optional[str] = item.get("pmcid")
            if pmcid:
                paper["fulltext_xml_preview"] = self.fetch_fulltext_xml(pmcid)
            corpus["papers"].append(paper)

        return corpus


def main() -> None:
    """Run CLI entrypoint for fetching corpus.

    Returns
    --------
        None: NoneType object
            Prints JSON output to standard output.
    """
    target: str = sys.argv[1] if len(sys.argv) > 1 else "Daniel Halls"
    user_agent: str = (
        "Mozilla/5.0 (compatible; ScientificWriterSkill/1.0; "
        "mailto:research@nottingham.ac.uk)"
    )
    fetcher: ScholarCorpusFetcher = ScholarCorpusFetcher(user_agent=user_agent)
    result: Dict[str, Any] = fetcher.build_corpus(target)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
