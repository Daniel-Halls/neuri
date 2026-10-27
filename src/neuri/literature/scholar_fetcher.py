"""Fetches an author's publication titles, abstracts, and open-access full texts.

Given a Google Scholar profile URL or author name, queries Scholar, OpenAlex,
and Europe PMC to build a stylistic corpus for the scientific writer.
"""

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class ScholarSearchResult:
    """Data container for an author's extracted Google Scholar profile data.

    Parameters
    ------------
    author_name: str | None
        Extracted author name if detected.
    titles: list[str]
        List of extracted publication titles.

    Returns
    --------
        ScholarSearchResult: ScholarSearchResult instance
            Constructed search result container.
    """

    author_name: str | None
    titles: list[str]


class ScholarCorpusFetcher:
    """Fetcher for academic publications from Scholar, OpenAlex, and Europe PMC.

    Parameters
    ------------
    user_agent: str | None
        HTTP User-Agent string to identify API queries. Defaults to None.

    Returns
    --------
        ScholarCorpusFetcher: ScholarCorpusFetcher instance
            Constructed corpus fetcher.
    """

    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; NeuriScholarFetcher/1.0; "
        "mailto:research@nottingham.ac.uk)"
    )

    def __init__(self, user_agent: str | None = None) -> None:
        """Initialize the fetcher with a custom User-Agent header.

        Parameters
        ------------
        user_agent: str | None
            HTTP User-Agent string to identify API queries. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes fetcher state.
        """
        agent: str = (
            user_agent if user_agent is not None else self.DEFAULT_USER_AGENT
        )
        self._headers: dict[str, str] = {"User-Agent": agent}

    def fetch_json(self, url: str) -> dict[str, Any]:
        """Fetch and parse JSON from a remote URL.

        Parameters
        ------------
        url: str
            HTTP or HTTPS URL returning JSON.

        Returns
        --------
            dict[str, Any]: dictionary object
                Parsed JSON response as a dictionary.
        """
        req: urllib.request.Request = urllib.request.Request(
            url, headers=self._headers
        )
        parsed_payload: dict[str, Any] = {}
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                parsed_payload = data
        except Exception:
            parsed_payload = {}
        return parsed_payload

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
        extracted_result: ScholarSearchResult = ScholarSearchResult(
            author_name=None, titles=[]
        )
        try:
            req: urllib.request.Request = urllib.request.Request(
                url, headers=self._headers
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html: str = resp.read().decode("utf-8", errors="ignore")
            name_match: re.Match[str] | None = re.search(
                r'<div id="gsc_prf_in"[^>]*>([^<]+)</div>', html
            )
            titles: list[str] = re.findall(
                r'class="gsc_a_at"[^>]*>([^<]+)</a>', html
            )
            detected_name: str | None = (
                name_match.group(1).strip() if name_match else None
            )
            extracted_result = ScholarSearchResult(
                author_name=detected_name, titles=titles[:15]
            )
        except Exception:
            extracted_result = ScholarSearchResult(author_name=None, titles=[])
        return extracted_result

    def fetch_fulltext_xml(self, pmcid: str) -> str | None:
        """Fetch full-text XML from Europe PMC and strip tags to prose preview.

        Parameters
        ------------
        pmcid: str
            PubMed Central identifier (e.g., PMC9546313).

        Returns
        --------
            str | None: string or None
                Extracted clean prose text preview or None on error.
        """
        clean_text_preview: str | None = None
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
            clean_text_preview = clean_text[:25000]
        except Exception:
            clean_text_preview = None
        return clean_text_preview

    def build_corpus(self, query_or_url: str) -> dict[str, Any]:
        """Build the full corpus dictionary for an author or Google Scholar URL.

        Parameters
        ------------
        query_or_url: str
            Author name, query, or Google Scholar profile URL.

        Returns
        --------
            dict[str, Any]: dictionary object
                Dictionary containing detected author, titles, and paper details.
        """
        author_name: str | None = None
        scholar_titles: list[str] = []
        if "scholar.google" in query_or_url:
            scholar_info: ScholarSearchResult = (
                self.extract_author_from_scholar(query_or_url)
            )
            author_name = scholar_info.author_name
            scholar_titles = scholar_info.titles

        search_name: str = author_name or query_or_url
        corpus: dict[str, Any] = {
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
        epmc_data: dict[str, Any] = self.fetch_json(epmc_url)
        epmc_results: list[dict[str, Any]] = (
            epmc_data.get("resultList", {}).get("result", [])
        )

        for item in epmc_results:
            paper: dict[str, Any] = {
                "title": item.get("title"),
                "year": item.get("pubYear"),
                "journal": item.get("journalTitle"),
                "doi": item.get("doi"),
                "pmcid": item.get("pmcid"),
                "abstract": item.get("abstractText", ""),
                "fulltext_xml_preview": None,
            }
            pmcid: str | None = item.get("pmcid")
            if pmcid:
                paper["fulltext_xml_preview"] = self.fetch_fulltext_xml(pmcid)
            corpus["papers"].append(paper)

        return corpus
