"""Neuri Brain Progressive Disclosure Retrieval Engine.

Implements Tier 0 (build_context graph capsules), Tier 1 (read_digest),
and Tier 2 (read_note_slice) progressive disclosure to strictly safeguard
LLM context window budgets while retrieving rich scientific priors.
"""

from pathlib import Path
import re
from typing import Any

from neuri.brain.indexer import BrainIndexer
from neuri.brain.schemas import (
    BrainContextCapsule,
    BrainEntity,
    BrainNote,
    BrainObservation,
    BrainRelation,
    BrainScope,
    BrainSearchResult,
    ObservationCategory,
    RelationType,
)


class BrainRetriever:
    """Progressive disclosure retriever for Brain memory capsules.

    Parameters
    ------------
    indexer: BrainIndexer
        Active SQLite indexer instance.

    Returns
    --------
        BrainRetriever: BrainRetriever instance
            Constructed retriever instance.
    """

    CHARS_PER_TOKEN: int = 4

    def __init__(self, indexer: BrainIndexer) -> None:
        """Initialize retriever with SQLite indexer reference.

        Parameters
        ------------
        indexer: BrainIndexer
            Active SQLite indexer instance.

        Returns
        --------
            None: NoneType object
                Initializes retriever instance.
        """
        self._indexer: BrainIndexer = indexer

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count of a text string using character heuristic.

        Parameters
        ------------
        text: str
            Input text to evaluate.

        Returns
        --------
            int: integer object
                Estimated token consumption.
        """
        if not text:
            return 0
        token_count: int = max(1, len(text) // self.CHARS_PER_TOKEN)
        return token_count

    def search_notes(
        self,
        query: str,
        limit: int = 8,
        scope: BrainScope | None = None,
        category: ObservationCategory | None = None,
    ) -> list[BrainSearchResult]:
        """Perform full-text BM25 search across indexed notes and observations.

        Parameters
        ------------
        query: str
            Search query string.
        limit: int
            Maximum number of results to return. Defaults to 8.
        scope: BrainScope | None
            Optional scope filter. Defaults to None.
        category: ObservationCategory | None
            Optional observation category filter. Defaults to None.

        Returns
        --------
            list[BrainSearchResult]: list object
                Ranked search result models with matching observations.
        """
        results: list[BrainSearchResult] = []
        cleaned_query: str = self._sanitize_fts_query(query)
        if not cleaned_query:
            return results

        scope_filter: str = (
            f"AND e.scope = '{scope.value}'" if scope is not None else ""
        )

        with self._indexer._get_connection() as conn:
            sql: str = f"""
                SELECT brain_fts.entity_id, bm25(brain_fts) AS rank,
                       e.title, e.scope, e.file_path, e.summary_excerpt
                FROM brain_fts
                JOIN brain_entities e ON brain_fts.entity_id = e.entity_id
                WHERE brain_fts MATCH ? {scope_filter}
                ORDER BY rank ASC
                LIMIT ?
            """
            cursor = conn.execute(sql, (cleaned_query, limit))
            for row in cursor.fetchall():
                entity_id: str = row["entity_id"]
                obs_list: list[BrainObservation] = (
                    self._indexer.get_observations_for_entity(entity_id)
                )
                if category is not None:
                    obs_list = [o for o in obs_list if o.category == category]

                res: BrainSearchResult = BrainSearchResult(
                    entity_id=entity_id,
                    title=row["title"],
                    scope=BrainScope(row["scope"]),
                    file_path=row["file_path"],
                    score=float(row["rank"]),
                    summary=row["summary_excerpt"],
                    observations=obs_list,
                )
                results.append(res)

        return results

    def build_context(
        self,
        query: str,
        max_tokens: int = 450,
        depth: int = 1,
        scope: BrainScope | None = None,
    ) -> BrainContextCapsule:
        """Build Tier-0 progressive disclosure context capsule for LLM prompt.

        Parameters
        ------------
        query: str
            Task description, topic, or search query.
        max_tokens: int
            Strict upper token limit for capsule. Defaults to 450.
        depth: int
            Graph traversal hop depth. Defaults to 1.
        scope: BrainScope | None
            Optional scope filter. Defaults to None.

        Returns
        --------
            BrainContextCapsule: BrainContextCapsule object
                Strictly budgeted Markdown memory capsule.
        """
        search_hits: list[BrainSearchResult] = self.search_notes(
            query=query, limit=4, scope=scope
        )

        matched_entity_ids: list[str] = [hit.entity_id for hit in search_hits]
        if depth >= 1:
            for hit in search_hits:
                relations = self._indexer.get_relations_for_entity(
                    hit.entity_id
                )
                for rel in relations:
                    target_id: str = rel.target_permalink.lower()
                    if (
                        target_id not in matched_entity_ids
                        and len(matched_entity_ids) < 8
                    ):
                        matched_entity_ids.append(target_id)

        lines: list[str] = [
            f"### Prior Knowledge Capsule: {query}",
        ]
        entities_included: list[str] = []
        is_truncated: bool = False

        for ent_id in matched_entity_ids:
            entity: BrainEntity | None = self._indexer.get_entity(ent_id)
            if not entity:
                continue

            obs_list: list[BrainObservation] = (
                self._indexer.get_observations_for_entity(ent_id)
            )
            rel_list: list[BrainRelation] = (
                self._indexer.get_relations_for_entity(ent_id)
            )

            header_line: str = f"- **[[{entity.title}]]** (`{entity.entity_id}`):"
            tentative_lines: list[str] = [header_line]

            for obs in obs_list:
                tags_str: str = (
                    " " + " ".join(f"#{t}" for t in obs.tags)
                    if obs.tags
                    else ""
                )
                obs_line: str = (
                    f"  - [{obs.category.value}] {obs.content}{tags_str}"
                )
                tentative_lines.append(obs_line)

            for rel in rel_list:
                rel_line: str = (
                    f"  - [{rel.relation_type.value}] [[{rel.target_permalink}]]"
                )
                tentative_lines.append(rel_line)

            candidate_text: str = "\n".join(lines + tentative_lines)
            if self.estimate_tokens(candidate_text) > max_tokens:
                # Add as many individual observation lines as fit
                for item in tentative_lines:
                    candidate_sub: str = "\n".join(lines + [item])
                    if self.estimate_tokens(candidate_sub) <= max_tokens:
                        lines.append(item)
                    else:
                        is_truncated = True
                        break
                if entity.entity_id not in entities_included:
                    entities_included.append(entity.entity_id)
                break
            else:
                lines.extend(tentative_lines)
                entities_included.append(entity.entity_id)

        md_context: str = "\n".join(lines).strip()
        tokens: int = self.estimate_tokens(md_context)

        capsule: BrainContextCapsule = BrainContextCapsule(
            query=query,
            entities_matched=entities_included,
            token_estimate=tokens,
            markdown_context=md_context,
            truncated=is_truncated,
        )
        return capsule

    def read_digest(self, permalink: str) -> BrainNote | None:
        """Fetch Tier-1 note digest including frontmatter, observations, and links.

        Parameters
        ------------
        permalink: str
            Unique entity permalink identifier.

        Returns
        --------
            BrainNote | None: BrainNote object or None
                Digest representation without full body prose.
        """
        entity: BrainEntity | None = self._indexer.get_entity(permalink)
        if not entity:
            return None

        obs_list: list[BrainObservation] = (
            self._indexer.get_observations_for_entity(permalink)
        )
        rel_list: list[BrainRelation] = (
            self._indexer.get_relations_for_entity(permalink)
        )
        backlinks: list[BrainRelation] = (
            self._indexer.get_backlinks_for_entity(permalink)
        )

        all_relations: list[BrainRelation] = list(rel_list) + list(backlinks)

        note: BrainNote = BrainNote(
            entity=entity,
            observations=obs_list,
            relations=all_relations,
            body_prose="",
            headings=[],
        )
        return note

    def read_note_slice(
        self,
        permalink: str,
        vault_root: Path,
        heading: str | None = None,
        max_tokens: int = 1200,
    ) -> str | None:
        """Fetch Tier-2 targeted Markdown section slice from filesystem.

        Parameters
        ------------
        permalink: str
            Entity permalink identifier.
        vault_root: Path
            Root directory of the Obsidian vault containing the note.
        heading: str | None
            Optional section heading to extract. Defaults to None.
        max_tokens: int
            Token budget cap for returned slice. Defaults to 1200.

        Returns
        --------
            str | None: string object or None
                Extracted Markdown slice or None if not found.
        """
        entity: BrainEntity | None = self._indexer.get_entity(permalink)
        if not entity:
            return None

        file_path: Path = vault_root / entity.file_path
        if not file_path.is_file():
            return None

        raw_content: str = file_path.read_text(encoding="utf-8")
        if heading is None:
            if self.estimate_tokens(raw_content) > max_tokens:
                char_limit: int = max_tokens * self.CHARS_PER_TOKEN
                truncated: str = (
                    f"{raw_content[:char_limit]}\n\n... [Truncated for token budget]"
                )
                return truncated
            return raw_content

        extracted_section: str | None = self._extract_section(
            raw_content=raw_content, target_heading=heading
        )
        if extracted_section is not None:
            if self.estimate_tokens(extracted_section) > max_tokens:
                char_limit = max_tokens * self.CHARS_PER_TOKEN
                section_truncated: str = (
                    f"{extracted_section[:char_limit]}\n\n... [Truncated]"
                )
                return section_truncated
            return extracted_section

        return None

    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize query string for safe SQLite FTS5 matching.

        Parameters
        ------------
        query: str
            Raw user query string.

        Returns
        --------
            str: string object
                Sanitized query formatted with OR terms.
        """
        clean_words: list[str] = re.findall(r"[a-zA-Z0-9_\-]+", query)
        if not clean_words:
            empty_str: str = ""
            return empty_str
        fts_query: str = " OR ".join(f'"{word}"' for word in clean_words)
        return fts_query

    def _extract_section(
        self, raw_content: str, target_heading: str
    ) -> str | None:
        """Extract a single Markdown section delimited by headers.

        Parameters
        ------------
        raw_content: str
            Full Markdown document text.
        target_heading: str
            Heading title to extract.

        Returns
        --------
            str | None: string object or None
                Section content text or None if heading not found.
        """
        lines: list[str] = raw_content.splitlines()
        found: bool = False
        target_level: int = 1
        section_lines: list[str] = []

        for line in lines:
            header_match: re.Match[str] | None = re.match(
                r"^(#{1,6})\s+(.+)$", line
            )
            if header_match:
                level: int = len(header_match.group(1))
                h_text: str = header_match.group(2).strip().lower()
                if not found:
                    if target_heading.lower() in h_text:
                        found = True
                        target_level = level
                        section_lines.append(line)
                else:
                    if level <= target_level:
                        break
                    else:
                        section_lines.append(line)
            elif found:
                section_lines.append(line)

        if not found:
            return None

        result: str = "\n".join(section_lines).strip()
        return result


__all__: list[str] = [
    "BrainRetriever",
]
