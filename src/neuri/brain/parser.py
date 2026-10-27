"""Neuri Brain Semantic Markdown Parser.

Parses Obsidian-compatible Markdown files extracting YAML frontmatter,
structured atomic observations, directed relations, inline WikiLinks,
and document headings for indexing and progressive retrieval.
"""

from collections.abc import Mapping
import hashlib
from pathlib import Path
import re
from typing import Any

import yaml

from neuri.brain.schemas import (
    BrainEntity,
    BrainNote,
    BrainObservation,
    BrainRelation,
    BrainScope,
    ObservationCategory,
    RelationType,
)


class BrainParser:
    """Parser for Obsidian Markdown notes with semantic structures.

    Parameters
    ------------
    None

    Returns
    --------
        BrainParser: BrainParser instance
            Constructed parser utility instance.
    """

    def __init__(self) -> None:
        """Initialize BrainParser with compiled regular expressions.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes regex matchers.
        """
        self._frontmatter_regex: re.Pattern[str] = re.compile(
            r"^---\s*\n(.*?)\n---\s*\n",
            re.DOTALL,
        )
        self._heading_regex: re.Pattern[str] = re.compile(
            r"^(#{1,6})\s+(.+)$",
            re.MULTILINE,
        )
        self._observation_regex: re.Pattern[str] = re.compile(
            r"^\s*-\s*\[([a-zA-Z0-9_\-]+)\]\s+(.+)$"
        )
        self._relation_regex: re.Pattern[str] = re.compile(
            r"^\s*-\s*\[([a-zA-Z0-9_\-]+)\]\s+\[\[(.*?)\]\](?:\s*(.*))?$"
        )
        self._wikilink_regex: re.Pattern[str] = re.compile(
            r"\[\[([^\[\]\|]+)(?:\|([^\[\]]+))?\]\]"
        )
        self._tag_regex: re.Pattern[str] = re.compile(
            r"(?<!\S)#([a-zA-Z0-9_\-]+)"
        )

    def parse_markdown_content(
        self,
        raw_text: str,
        relative_path: str,
        scope: BrainScope,
        mtime_ns: int = 0,
    ) -> BrainNote:
        """Parse raw Markdown string into structured BrainNote representation.

        Parameters
        ------------
        raw_text: str
            Raw content of the Markdown document.
        relative_path: str
            Relative file path of the document within the vault.
        scope: BrainScope
            Knowledge scope classification (global or project).
        mtime_ns: int
            Modification time in nanoseconds. Defaults to 0.

        Returns
        --------
            BrainNote: BrainNote object
                Structured note with frontmatter, observations, and relations.
        """
        frontmatter, body_text = self.extract_frontmatter(raw_text)
        content_hash: str = hashlib.sha256(
            raw_text.encode("utf-8")
        ).hexdigest()

        title: str = self._resolve_title(
            frontmatter=frontmatter,
            body_text=body_text,
            relative_path=relative_path,
        )
        permalink: str = self._resolve_permalink(
            frontmatter=frontmatter,
            relative_path=relative_path,
        )
        entity_type: str = str(frontmatter.get("type", "note"))

        observations: list[BrainObservation] = self.extract_observations(
            raw_text=raw_text
        )
        relations: list[BrainRelation] = self.extract_relations(
            raw_text=raw_text
        )
        headings: list[str] = self.extract_headings(raw_text=raw_text)
        summary: str = self.extract_summary_excerpt(body_text=body_text)

        entity: BrainEntity = BrainEntity(
            entity_id=permalink,
            scope=scope,
            title=title,
            entity_type=entity_type,
            file_path=relative_path,
            content_sha256=content_hash,
            mtime_ns=mtime_ns,
            frontmatter=frontmatter,
            summary_excerpt=summary,
            observations_count=len(observations),
            relations_count=len(relations),
        )

        note: BrainNote = BrainNote(
            entity=entity,
            observations=observations,
            relations=relations,
            body_prose=body_text,
            headings=headings,
        )
        return note

    def extract_frontmatter(
        self, raw_text: str
    ) -> tuple[dict[str, Any], str]:
        """Extract YAML frontmatter dictionary and remaining Markdown body.

        Parameters
        ------------
        raw_text: str
            Full Markdown document text.

        Returns
        --------
            tuple[dict[str, Any], str]: tuple object
                Pair of parsed frontmatter mapping and body content string.
        """
        match: re.Match[str] | None = self._frontmatter_regex.match(raw_text)
        if not match:
            empty_dict: dict[str, Any] = {}
            fallback_result: tuple[dict[str, Any], str] = (
                empty_dict,
                raw_text,
            )
            return fallback_result

        yaml_content: str = match.group(1)
        body: str = raw_text[match.end() :]
        parsed: Any = None
        try:
            parsed = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            parsed = {}

        frontmatter: dict[str, Any] = (
            dict(parsed) if isinstance(parsed, Mapping) else {}
        )
        result: tuple[dict[str, Any], str] = (frontmatter, body)
        return result

    def extract_observations(
        self, raw_text: str
    ) -> list[BrainObservation]:
        """Extract atomic observations matching category bullet patterns.

        Parameters
        ------------
        raw_text: str
            Full Markdown document text.

        Returns
        --------
            list[BrainObservation]: list object
                Extracted atomic observation instances with tags.
        """
        observations: list[BrainObservation] = []
        lines: list[str] = raw_text.splitlines()

        for idx, line in enumerate(lines, start=1):
            match: re.Match[str] | None = self._observation_regex.match(line)
            if not match:
                continue

            raw_cat: str = match.group(1).strip().lower()
            content_with_tags: str = match.group(2).strip()

            # Skip relation matches (e.g., - [extends] [[target]])
            if content_with_tags.startswith("[["):
                continue

            category: ObservationCategory = self._resolve_category(raw_cat)
            tags: list[str] = self.extract_tags(content_with_tags)

            # Strip inline tags from clean observation statement
            clean_content: str = self._tag_regex.sub("", content_with_tags)
            clean_content = " ".join(clean_content.split()).strip()

            if clean_content:
                obs: BrainObservation = BrainObservation(
                    category=category,
                    content=clean_content,
                    tags=tags,
                    line_number=idx,
                )
                observations.append(obs)

        return observations

    def extract_relations(
        self, raw_text: str
    ) -> list[BrainRelation]:
        """Extract semantic directed relationships and inline WikiLinks.

        Parameters
        ------------
        raw_text: str
            Full Markdown document text.

        Returns
        --------
            list[BrainRelation]: list object
                Extracted relation edge instances.
        """
        relations: list[BrainRelation] = []
        seen_targets: set[str] = set()
        lines: list[str] = raw_text.splitlines()

        # Pass 1: Parse explicit - [relation_type] [[target]] lines
        for line in lines:
            match: re.Match[str] | None = self._relation_regex.match(line)
            if not match:
                continue

            raw_type: str = match.group(1).strip().lower()
            target_raw: str = match.group(2).strip()
            snippet: str | None = match.group(3)
            context: str | None = (
                snippet.strip() if snippet and snippet.strip() else None
            )

            rel_type: RelationType = self._resolve_relation_type(raw_type)
            clean_target: str = target_raw.split("|")[0].strip()
            title_alias: str | None = (
                target_raw.split("|")[1].strip()
                if "|" in target_raw
                else None
            )

            if clean_target:
                rel: BrainRelation = BrainRelation(
                    relation_type=rel_type,
                    target_permalink=clean_target,
                    target_title=title_alias,
                    context_snippet=context,
                )
                relations.append(rel)
                seen_targets.add(clean_target.lower())

        # Pass 2: Extract all other inline [[WikiLinks]] as links_to
        for match_link in self._wikilink_regex.finditer(raw_text):
            target: str = match_link.group(1).strip()
            alias: str | None = match_link.group(2)
            if target and target.lower() not in seen_targets:
                inline_rel: BrainRelation = BrainRelation(
                    relation_type=RelationType.LINKS_TO,
                    target_permalink=target,
                    target_title=alias.strip() if alias else None,
                    context_snippet=None,
                )
                relations.append(inline_rel)
                seen_targets.add(target.lower())

        return relations

    def extract_headings(self, raw_text: str) -> list[str]:
        """Extract list of section headings present in Markdown content.

        Parameters
        ------------
        raw_text: str
            Full Markdown document text.

        Returns
        --------
            list[str]: list object
                Extracted heading strings without hash marks.
        """
        headings: list[str] = []
        for match in self._heading_regex.finditer(raw_text):
            heading_text: str = match.group(2).strip()
            if heading_text:
                headings.append(heading_text)
        return headings

    def extract_tags(self, text: str) -> list[str]:
        """Extract inline hashtags from text string.

        Parameters
        ------------
        text: str
            Input text containing hashtags.

        Returns
        --------
            list[str]: list object
                List of unique hashtag label strings without hash symbol.
        """
        tags: list[str] = []
        for match in self._tag_regex.finditer(text):
            tag_name: str = match.group(1).strip()
            if tag_name and tag_name not in tags:
                tags.append(tag_name)
        return tags

    def extract_summary_excerpt(self, body_text: str) -> str:
        """Extract first prose paragraph as an executive summary excerpt.

        Parameters
        ------------
        body_text: str
            Markdown body text without YAML frontmatter.

        Returns
        --------
            str: string object
                First prose paragraph truncated to 250 characters.
        """
        paragraphs: list[str] = body_text.split("\n\n")
        for para in paragraphs:
            stripped: str = para.strip()
            if not stripped:
                continue
            # Skip headings, observation bullets, and relation bullets
            if stripped.startswith("#"):
                continue
            if stripped.startswith("- ["):
                continue
            if stripped.startswith("```"):
                continue
            single_line: str = " ".join(stripped.split())
            if len(single_line) > 250:
                truncated: str = f"{single_line[:247]}..."
                return truncated
            return single_line
        empty_summary: str = ""
        return empty_summary

    def render_markdown_note(
        self,
        title: str,
        observations: list[BrainObservation],
        relations: list[BrainRelation],
        body_prose: str = "",
        frontmatter_extra: dict[str, Any] | None = None,
    ) -> str:
        """Render a structured Brain note to Markdown format.

        Parameters
        ------------
        title: str
            Human-readable note title.
        observations: list[BrainObservation]
            Atomic observations to format.
        relations: list[BrainRelation]
            Directed relations to format.
        body_prose: str
            Freeform prose text. Defaults to ''.
        frontmatter_extra: dict[str, Any] | None
            Optional additional YAML frontmatter keys. Defaults to None.

    Returns
    --------
        str: string object
            Formatted Markdown string ready to write to disk.
        """
        fm_dict: dict[str, Any] = {
            "title": title,
            "type": "note",
        }
        if frontmatter_extra:
            fm_dict.update(frontmatter_extra)

        yaml_dump: str = yaml.safe_dump(
            fm_dict,
            sort_keys=False,
            allow_unicode=True,
        ).strip()
        lines: list[str] = [
            "---",
            yaml_dump,
            "---",
            "",
            f"# {title}",
            "",
        ]

        if observations:
            lines.append("### Observations")
            for obs in observations:
                tags_suffix: str = (
                    " " + " ".join(f"#{t}" for t in obs.tags)
                    if obs.tags
                    else ""
                )
                line_str: str = (
                    f"- [{obs.category.value}] {obs.content}{tags_suffix}"
                )
                lines.append(line_str)
            lines.append("")

        if relations:
            lines.append("### Relations")
            for rel in relations:
                target_str: str = (
                    f"[[{rel.target_permalink}|{rel.target_title}]]"
                    if rel.target_title
                    else f"[[{rel.target_permalink}]]"
                )
                context_str: str = (
                    f" {rel.context_snippet}" if rel.context_snippet else ""
                )
                line_rel: str = (
                    f"- [{rel.relation_type.value}] {target_str}{context_str}"
                )
                lines.append(line_rel)
            lines.append("")

        if body_prose.strip():
            lines.append(body_prose.strip())
            lines.append("")

        rendered: str = "\n".join(lines).strip() + "\n"
        return rendered

    def _resolve_title(
        self,
        frontmatter: dict[str, Any],
        body_text: str,
        relative_path: str,
    ) -> str:
        """Resolve note title from frontmatter, H1 header, or filename.

        Parameters
        ------------
        frontmatter: dict[str, Any]
            Parsed YAML frontmatter dictionary.
        body_text: str
            Markdown body text.
        relative_path: str
            Relative filesystem path.

        Returns
        --------
            str: string object
                Resolved note title string.
        """
        if "title" in frontmatter and str(frontmatter["title"]).strip():
            title_fm: str = str(frontmatter["title"]).strip()
            return title_fm

        match: re.Match[str] | None = re.search(
            r"^#\s+(.+)$", body_text, re.MULTILINE
        )
        if match:
            title_h1: str = match.group(1).strip()
            return title_h1

        file_stem: str = Path(relative_path).stem
        cleaned_stem: str = file_stem.replace("_", " ").replace("-", " ")
        return cleaned_stem

    def _resolve_permalink(
        self, frontmatter: dict[str, Any], relative_path: str
    ) -> str:
        """Resolve entity permalink slug from frontmatter or relative path.

        Parameters
        ------------
        frontmatter: dict[str, Any]
            Parsed YAML frontmatter dictionary.
        relative_path: str
            Relative filesystem path.

        Returns
        --------
            str: string object
                Resolved permalink string.
        """
        if "permalink" in frontmatter and str(frontmatter["permalink"]).strip():
            permalink_fm: str = str(frontmatter["permalink"]).strip()
            return permalink_fm

        path_obj: Path = Path(relative_path)
        parts: list[str] = list(path_obj.parent.parts) + [path_obj.stem]
        slug_parts: list[str] = [
            p.lower().replace(" ", "_") for p in parts if p and p != "."
        ]
        slug: str = "/".join(slug_parts)
        return slug

    def _resolve_category(self, raw_category: str) -> ObservationCategory:
        """Map raw category string to standard ObservationCategory enum.

        Parameters
        ------------
        raw_category: str
            Raw string extracted from square brackets.

        Returns
        --------
            ObservationCategory: ObservationCategory object
                Standardized observation category.
        """
        for cat in ObservationCategory:
            if cat.value == raw_category:
                return cat
        default_cat: ObservationCategory = ObservationCategory.GENERAL
        return default_cat

    def _resolve_relation_type(self, raw_type: str) -> RelationType:
        """Map raw relation string to standard RelationType enum.

        Parameters
        ------------
        raw_type: str
            Raw string extracted from square brackets.

        Returns
        --------
            RelationType: RelationType object
                Standardized relation type.
        """
        for rel in RelationType:
            if rel.value == raw_type:
                return rel
        default_rel: RelationType = RelationType.LINKS_TO
        return default_rel


__all__: list[str] = [
    "BrainParser",
]
