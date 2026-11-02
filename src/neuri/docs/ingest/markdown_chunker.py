"""Markdown chunker for neuroimaging pipeline documentation.

Parses markdown files into discrete, semantically rich documentation chunks
classified by doc_type ('commands', 'functions', 'documentation').
"""

import re
from pathlib import Path

from neuri.docs.models import DocChunkRecord, DocType


class MarkdownDocChunker:
    """Parser that converts documentation markdown files into chunk records.

    Parameters
    ------------
    None

    Returns
    --------
        MarkdownDocChunker: MarkdownDocChunker instance
            Constructed chunker instance.
    """

    def __init__(self) -> None:
        """Initialize regex matchers for markdown headings and bullet items.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes internal compiled regular expressions.
        """
        self._heading_pattern: re.Pattern[str] = re.compile(
            r"^(#{1,6})\s+(.+)$", re.MULTILINE
        )
        self._item_pattern: re.Pattern[str] = re.compile(
            r"^\s*[\*\-]\s+\*\*(.+?)\*\*(.*)$"
        )
        self._code_item_pattern: re.Pattern[str] = re.compile(
            r"[`\*]+([a-zA-Z0-9_\-\.\:\(\)\{\}\= ]+)[`\*]+"
        )

    def chunk_file(
        self,
        file_path: Path,
        pipeline_name: str,
        doc_type: DocType,
    ) -> list[DocChunkRecord]:
        """Read and parse a markdown documentation file into atomic chunks.

        Parameters
        ------------
        file_path: Path
            Path to the source markdown file on disk.
        pipeline_name: str
            Canonical pipeline or package identifier.
        doc_type: DocType
            Documentation category ('commands', 'functions', 'documentation').

        Returns
        --------
            list[DocChunkRecord]: list object
                Extracted documentation chunk models.
        """
        if not file_path.is_file():
            return []

        text: str = file_path.read_text(encoding="utf-8")
        rel_path: str = str(file_path)

        if doc_type == "commands":
            return self._chunk_commands(text, pipeline_name, rel_path)
        if doc_type == "functions":
            return self._chunk_functions(text, pipeline_name, rel_path)
        return self._chunk_documentation(text, pipeline_name, rel_path)

    def _clean_title(self, raw_title: str) -> str:
        """Strip markdown formatting, bold markers, and numbering from titles.

        Parameters
        ------------
        raw_title: str
            Raw markdown heading text.

        Returns
        --------
            str: string object
                Sanitized title text.
        """
        cleaned: str = re.sub(r"[\*\`\#]", "", raw_title).strip()
        return cleaned

    def _extract_item_name(self, raw_header: str) -> str:
        """Extract primary flag, executable, or function name from markdown.

        Parameters
        ------------
        raw_header: str
            Bold or backtick-enclosed header text.

        Returns
        --------
            str: string object
                Cleaned identifier string.
        """
        cleaned: str = re.sub(r"[\*`]", "", raw_header).strip()
        if ":" in cleaned:
            cleaned = cleaned.split(":", 1)[0].strip()
        return cleaned

    def _split_into_sections(
        self, text: str
    ) -> list[tuple[str, str]]:
        """Split text by markdown headings into (heading, body) pairs.

        Parameters
        ------------
        text: str
            Full raw markdown content.

        Returns
        --------
            list[tuple[str, str]]: list object
                Pairs of section titles and section body texts.
        """
        matches: list[re.Match[str]] = list(
            self._heading_pattern.finditer(text)
        )
        if not matches:
            return [("General Overview", text.strip())]

        sections: list[tuple[str, str]] = []
        # Check text before first heading
        first_start: int = matches[0].start()
        if first_start > 0:
            preamble: str = text[:first_start].strip()
            if preamble:
                sections.append(("General Overview", preamble))

        for idx, match in enumerate(matches):
            raw_title: str = match.group(2).strip()
            title: str = self._clean_title(raw_title)
            body_start: int = match.end()
            body_end: int = (
                matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            )
            body: str = text[body_start:body_end].strip()
            if body or title:
                sections.append((title, body))

        return sections

    def _chunk_commands(
        self,
        text: str,
        pipeline_name: str,
        source_file: str,
    ) -> list[DocChunkRecord]:
        """Chunk command-line reference documentation.

        Parameters
        ------------
        text: str
            Raw commands.md text.
        pipeline_name: str
            Target pipeline name.
        source_file: str
            Source file path.

        Returns
        --------
            list[DocChunkRecord]: list object
                Parsed CLI flag and command chunks.
        """
        chunks: list[DocChunkRecord] = []
        sections: list[tuple[str, str]] = self._split_into_sections(text)

        for sec_title, body in sections:
            if not body:
                continue

            lines: list[str] = body.splitlines()
            current_item_name: str = ""
            current_lines: list[str] = []
            intro_lines: list[str] = []

            for line in lines:
                item_match = self._item_pattern.match(line)
                if item_match:
                    if current_item_name and current_lines:
                        chunk_content: str = "\n".join(current_lines).strip()
                        chunks.append(
                            DocChunkRecord(
                                pipeline_name=pipeline_name,
                                doc_type="commands",
                                section_title=sec_title,
                                item_name=current_item_name,
                                content=chunk_content,
                                source_file=source_file,
                            )
                        )
                        current_lines = []

                    raw_item: str = item_match.group(1)
                    current_item_name = self._extract_item_name(raw_item)
                    current_lines.append(line.strip())
                elif current_item_name:
                    current_lines.append(line)
                else:
                    intro_lines.append(line)

            if current_item_name and current_lines:
                chunk_content = "\n".join(current_lines).strip()
                chunks.append(
                    DocChunkRecord(
                        pipeline_name=pipeline_name,
                        doc_type="commands",
                        section_title=sec_title,
                        item_name=current_item_name,
                        content=chunk_content,
                        source_file=source_file,
                    )
                )

            if intro_lines:
                intro_text: str = "\n".join(intro_lines).strip()
                if len(intro_text) > 30:
                    chunks.append(
                        DocChunkRecord(
                            pipeline_name=pipeline_name,
                            doc_type="commands",
                            section_title=sec_title,
                            item_name=sec_title,
                            content=intro_text,
                            source_file=source_file,
                        )
                    )

        return chunks

    def _chunk_functions(
        self,
        text: str,
        pipeline_name: str,
        source_file: str,
    ) -> list[DocChunkRecord]:
        """Chunk Python functions and API reference documentation.

        Parameters
        ------------
        text: str
            Raw functions.md text.
        pipeline_name: str
            Target pipeline name.
        source_file: str
            Source file path.

        Returns
        --------
            list[DocChunkRecord]: list object
                Parsed function and class chunks.
        """
        chunks: list[DocChunkRecord] = []
        sections: list[tuple[str, str]] = self._split_into_sections(text)

        for sec_title, body in sections:
            if not body:
                continue

            lines: list[str] = body.splitlines()
            current_fn_name: str = ""
            current_lines: list[str] = []
            intro_lines: list[str] = []

            for line in lines:
                item_match = self._item_pattern.match(line)
                if item_match:
                    if current_fn_name and current_lines:
                        chunk_content: str = "\n".join(current_lines).strip()
                        chunks.append(
                            DocChunkRecord(
                                pipeline_name=pipeline_name,
                                doc_type="functions",
                                section_title=sec_title,
                                item_name=current_fn_name,
                                content=chunk_content,
                                source_file=source_file,
                            )
                        )
                        current_lines = []

                    raw_item: str = item_match.group(1)
                    current_fn_name = self._extract_item_name(raw_item)
                    current_lines.append(line.strip())
                elif current_fn_name:
                    current_lines.append(line)
                else:
                    intro_lines.append(line)

            if current_fn_name and current_lines:
                chunk_content = "\n".join(current_lines).strip()
                chunks.append(
                    DocChunkRecord(
                        pipeline_name=pipeline_name,
                        doc_type="functions",
                        section_title=sec_title,
                        item_name=current_fn_name,
                        content=chunk_content,
                        source_file=source_file,
                    )
                )

            # If section has no individual bullet items, treat section as whole
            if not current_fn_name and body.strip():
                chunks.append(
                    DocChunkRecord(
                        pipeline_name=pipeline_name,
                        doc_type="functions",
                        section_title=sec_title,
                        item_name=sec_title,
                        content=body.strip(),
                        source_file=source_file,
                    )
                )
            elif intro_lines:
                intro_text: str = "\n".join(intro_lines).strip()
                if len(intro_text) > 40:
                    chunks.append(
                        DocChunkRecord(
                            pipeline_name=pipeline_name,
                            doc_type="functions",
                            section_title=sec_title,
                            item_name=sec_title,
                            content=intro_text,
                            source_file=source_file,
                        )
                    )

        return chunks

    def _chunk_documentation(
        self,
        text: str,
        pipeline_name: str,
        source_file: str,
    ) -> list[DocChunkRecord]:
        """Chunk general pipeline and workflow documentation.

        Parameters
        ------------
        text: str
            Raw documentation.md text.
        pipeline_name: str
            Target pipeline name.
        source_file: str
            Source file path.

        Returns
        --------
            list[DocChunkRecord]: list object
                Parsed workflow, concept, and architecture chunks.
        """
        chunks: list[DocChunkRecord] = []
        sections: list[tuple[str, str]] = self._split_into_sections(text)

        for sec_title, body in sections:
            if not body:
                continue

            # Split paragraphs cleanly if section is long (> 1200 chars)
            paragraphs: list[str] = [
                p.strip() for p in body.split("\n\n") if p.strip()
            ]
            if len(body) <= 1200 or len(paragraphs) <= 1:
                chunks.append(
                    DocChunkRecord(
                        pipeline_name=pipeline_name,
                        doc_type="documentation",
                        section_title=sec_title,
                        item_name=sec_title,
                        content=body,
                        source_file=source_file,
                    )
                )
            else:
                # Group paragraphs into readable chunks
                buffer: list[str] = []
                buffer_len: int = 0
                part_idx: int = 1

                for p in paragraphs:
                    buffer.append(p)
                    buffer_len += len(p)
                    if buffer_len >= 800:
                        sub_content: str = "\n\n".join(buffer)
                        sub_item: str = (
                            f"{sec_title} (Part {part_idx})"
                            if part_idx > 1
                            else sec_title
                        )
                        chunks.append(
                            DocChunkRecord(
                                pipeline_name=pipeline_name,
                                doc_type="documentation",
                                section_title=sec_title,
                                item_name=sub_item,
                                content=sub_content,
                                source_file=source_file,
                            )
                        )
                        buffer = []
                        buffer_len = 0
                        part_idx += 1

                if buffer:
                    sub_content = "\n\n".join(buffer)
                    sub_item = (
                        f"{sec_title} (Part {part_idx})"
                        if part_idx > 1
                        else sec_title
                    )
                    chunks.append(
                        DocChunkRecord(
                            pipeline_name=pipeline_name,
                            doc_type="documentation",
                            section_title=sec_title,
                            item_name=sub_item,
                            content=sub_content,
                            source_file=source_file,
                        )
                    )

        return chunks


__all__: list[str] = [
    "MarkdownDocChunker",
]
