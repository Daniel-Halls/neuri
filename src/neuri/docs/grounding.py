"""In-process pipeline documentation pre-grounder for Neuri.

Analyzes natural language prompts in Python, queries the local SQLite FTS5
documentation database in ~1ms, and pre-injects authoritative syntax, flags,
and APIs directly into task envelopes across any agent harness.
"""

import re

from neuri.docs.db.repository import DocsRepository
from neuri.docs.models import DocSearchResult, DocType, PipelineMetadata


class PipelinePreGrounder:
    """Pre-execution grounding engine injecting verified pipeline docs into tasks.

    Parameters
    ------------
    repository: DocsRepository | None
        Underlying SQLite documentation repository. Defaults to None.

    Returns
    --------
        PipelinePreGrounder: PipelinePreGrounder instance
            Constructed pre-grounder engine.
    """

    STOPWORDS: set[str] = {
        "a", "an", "the", "in", "on", "of", "to", "for", "with", "is", "are",
        "there", "any", "how", "what", "can", "i", "do", "we", "you", "use",
        "and", "or", "from", "at", "by", "this", "that", "it", "run", "using",
    }

    COMMAND_KEYWORDS: set[str] = {
        "command", "commands", "flag", "flags", "option", "options", "syntax",
        "slurm", "sbatch", "script", "bash", "cli", "run", "args", "arguments",
        "parameter", "parameters", "execute", "executing",
    }

    FUNCTION_KEYWORDS: set[str] = {
        "python", "function", "functions", "class", "classes", "method",
        "methods", "api", "apis", "import", "module", "code", "call", "script",
    }

    def __init__(self, repository: DocsRepository | None = None) -> None:
        """Initialize pre-grounder with repository reference and pipeline catalog.

        Parameters
        ------------
        repository: DocsRepository | None
            Database repository instance. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes repository and cached pipeline metadata.
        """
        self.repository: DocsRepository = repository or DocsRepository()
        self._cached_pipelines: list[PipelineMetadata] = []
        self._refresh_pipelines()

    def _refresh_pipelines(self) -> None:
        """Refresh and cache available pipeline models from database.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Caches pipeline models in memory.
        """
        try:
            self._cached_pipelines = self.repository.list_pipelines()
        except Exception:
            self._cached_pipelines = []

    def detect_pipelines(self, text: str) -> list[str]:
        """Detect any neuroimaging pipeline or package names mentioned in text.

        Parameters
        ------------
        text: str
            Raw natural language prompt string.

        Returns
        --------
            list[str]: list object
                Canonical pipeline names found in the text.
        """
        if not self._cached_pipelines:
            self._refresh_pipelines()

        text_lower: str = text.lower()
        # Clean punctuation except hyphens and underscores
        cleaned_tokens: list[str] = re.findall(r'[a-zA-Z0-9_\-]+', text_lower)
        cleaned_str: str = " " + " ".join(cleaned_tokens) + " "

        detected: list[str] = []
        for p in self._cached_pipelines:
            # Check canonical name
            p_name: str = p.name.lower()
            if f" {p_name} " in cleaned_str:
                detected.append(p.name)
                continue

            # Check aliases
            for alias in p.aliases:
                a_name: str = alias.lower()
                if f" {a_name} " in cleaned_str:
                    detected.append(p.name)
                    break

        return detected

    def infer_doc_type(
        self, text: str, pipeline_meta: PipelineMetadata
    ) -> DocType:
        """Infer target doc category ('commands', 'functions', 'documentation').

        Parameters
        ------------
        text: str
            User prompt text.
        pipeline_meta: PipelineMetadata
            Metadata of the target pipeline.

        Returns
        --------
            DocType: string object
                Inferred documentation type ('commands', 'functions', etc.).
        """
        text_lower: str = text.lower()
        tokens: set[str] = set(re.findall(r'[a-zA-Z0-9_\-]+', text_lower))

        has_cmd_clues: bool = bool(tokens & self.COMMAND_KEYWORDS)
        has_fn_clues: bool = bool(tokens & self.FUNCTION_KEYWORDS)

        # If pipeline only has functions (e.g. Nilearn, Nibabel, BCTnet)
        if pipeline_meta.has_functions and not pipeline_meta.has_commands:
            return "functions"

        # If pipeline only has commands (e.g. fMRIPrep, QSIPrep, FSL, AFNI)
        if pipeline_meta.has_commands and not pipeline_meta.has_functions:
            if has_fn_clues and not has_cmd_clues:
                return "documentation"
            return "commands"

        # If pipeline has both (e.g. Tedana, Pydeface)
        if has_fn_clues and not has_cmd_clues:
            return "functions"
        if has_cmd_clues and not has_fn_clues:
            return "commands"

        return "commands" if pipeline_meta.has_commands else "documentation"

    def extract_search_terms(
        self, text: str, pipeline_name: str
    ) -> list[str]:
        """Extract domain-specific search query keywords from prompt text.

        Parameters
        ------------
        text: str
            Raw user prompt text.
        pipeline_name: str
            Name of identified pipeline to exclude from terms.

        Returns
        --------
            list[str]: list object
                Filtered salient keyword terms.
        """
        tokens: list[str] = re.findall(r'[a-zA-Z0-9_\-\.]+', text.lower())
        filtered: list[str] = []
        p_lower: str = pipeline_name.lower()

        for t in tokens:
            if t in self.STOPWORDS:
                continue
            if t == p_lower or t in self.COMMAND_KEYWORDS:
                continue
            if len(t) <= 2 and not t.startswith("-"):
                continue
            filtered.append(t)

        return filtered

    def ground_prompt(
        self, prompt: str, max_chunks_per_pipe: int = 4
    ) -> str:
        """Generate verified documentation context for any pipelines in prompt.

        Parameters
        ------------
        prompt: str
            Natural language prompt text.
        max_chunks_per_pipe: int
            Maximum chunks to retrieve per pipeline. Defaults to 4.

        Returns
        --------
            str: string object
                Formatted markdown reference block or empty string if none.
        """
        pipelines: list[str] = self.detect_pipelines(prompt)
        if not pipelines:
            return ""

        context_blocks: list[str] = []
        for pipe_name in pipelines:
            meta = next(
                (p for p in self._cached_pipelines if p.name == pipe_name), None
            )
            if meta is None:
                continue

            doc_type: DocType = self.infer_doc_type(prompt, meta)
            terms: list[str] = self.extract_search_terms(prompt, pipe_name)

            hits: list[DocSearchResult] = []
            if terms:
                query_str: str = " ".join(terms)
                hits = self.repository.search(
                    pipeline=pipe_name,
                    query=query_str,
                    doc_type=doc_type,
                    limit=max_chunks_per_pipe,
                )

            # If no hits from combined query, search individual salient terms
            if not hits and terms:
                for term in terms:
                    sub_hits: list[DocSearchResult] = self.repository.search(
                        pipeline=pipe_name,
                        query=term,
                        doc_type=doc_type,
                        limit=2,
                    )
                    for h in sub_hits:
                        if not any(x.item_name == h.item_name for x in hits):
                            hits.append(h)
                    if len(hits) >= max_chunks_per_pipe:
                        break

            # If still no hits or no specific terms, fetch general syntax/overview
            if not hits:
                fallback_hits: list[DocSearchResult] = self.repository.search(
                    pipeline=pipe_name,
                    query="syntax overview",
                    doc_type=doc_type,
                    limit=2,
                )
                hits = fallback_hits

            # Format block
            block: str = self._format_grounding_block(
                pipeline_meta=meta,
                doc_type=doc_type,
                search_terms=terms,
                results=hits,
            )
            context_blocks.append(block)

        if not context_blocks:
            return ""

        grounding_header: str = (
            "## Neuri Verified Brain Documentation (In-Process Grounding)\n"
            "Authoritative syntax, parameters, and flags retrieved from "
            "Neuri's local database. Use these exact specifications.\n\n"
        )
        full_grounding: str = grounding_header + "\n\n".join(context_blocks)
        return full_grounding

    def _format_grounding_block(
        self,
        pipeline_meta: PipelineMetadata,
        doc_type: DocType,
        search_terms: list[str],
        results: list[DocSearchResult],
    ) -> str:
        """Format retrieved search results into concise markdown block.

        Parameters
        ------------
        pipeline_meta: PipelineMetadata
            Target pipeline metadata model.
        doc_type: DocType
            Documentation type queried.
        search_terms: list[str]
            Salient query terms extracted.
        results: list[DocSearchResult]
            Retrieved search hits.

        Returns
        --------
            str: string object
                Formatted markdown text for injection.
        """
        lines: list[str] = [
            f"### [{pipeline_meta.display_name}] ({doc_type.upper()})"
        ]

        if not results:
            terms_str: str = ", ".join(search_terms) if search_terms else "query"
            lines.append(
                f"- No exact {doc_type} entries matching '{terms_str}' found in "
                f"official {pipeline_meta.display_name} documentation."
            )
            return "\n".join(lines)

        for r in results:
            lines.append(f"#### {r.item_name} ({r.section_title})")
            cleaned_content: str = r.content.strip()
            # Truncate content to max 600 characters per item to preserve tokens
            if len(cleaned_content) > 600:
                cleaned_content = cleaned_content[:600] + "..."
            lines.append(cleaned_content)

        return "\n\n".join(lines)


__all__: list[str] = [
    "PipelinePreGrounder",
]
