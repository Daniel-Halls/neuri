"""Unit tests for Neuri Brain semantic memory subsystem.

Verifies schema validation, Obsidian Markdown parsing, SQLite FTS5 incremental
indexing, progressive disclosure retrieval budgets, and /brain slash commands.
"""

from pathlib import Path
import tempfile
from typing import Any

import pytest

from neuri.brain import (
    BrainContextCapsule,
    BrainEntity,
    BrainIndexer,
    BrainManager,
    BrainNote,
    BrainObservation,
    BrainParser,
    BrainRelation,
    BrainRetriever,
    BrainScope,
    BrainSearchResult,
    BrainStats,
    ObservationCategory,
    RelationType,
)
from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter


class TestBrainParser:
    """Test suite for Obsidian Markdown parsing and rendering."""

    def test_parse_structured_markdown(self) -> None:
        """Verify parsing of frontmatter, observations, relations, and wikilinks.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts parsed note structure matches expectations.
        """
        parser: BrainParser = BrainParser()
        raw_md: str = (
            "---\n"
            "title: 'fMRIPrep Pipeline'\n"
            "type: 'method'\n"
            "permalink: 'methods/fmriprep'\n"
            "tags:\n"
            "  - bold\n"
            "  - fmri\n"
            "---\n\n"
            "# fMRIPrep Pipeline\n\n"
            "Standardized preprocessing for task and resting BOLD.\n\n"
            "### Observations\n"
            "- [parameter] Smoothing kernel set to 6.0 mm #fwhm #smoothing\n"
            "- [finding] Sub-04 showed framewise displacement > 0.5 mm #motion\n\n"
            "### Relations\n"
            "- [extends] [[00_Index/Lab Standards|Lab Standards]]\n"
            "- [applies_to] [[Study_Overview]]\n\n"
            "See also inline [[Schaefer2018_Atlas]] for parcellation."
        )

        note: BrainNote = parser.parse_markdown_content(
            raw_text=raw_md,
            relative_path="methods/fmriprep.md",
            scope=BrainScope.GLOBAL,
            mtime_ns=1000,
        )

        assert note.entity.title == "fMRIPrep Pipeline"
        assert note.entity.entity_id == "methods/fmriprep"
        assert note.entity.scope == BrainScope.GLOBAL
        assert "Standardized preprocessing" in note.entity.summary_excerpt

        assert len(note.observations) == 2
        assert note.observations[0].category == ObservationCategory.PARAMETER
        assert "Smoothing kernel set to 6.0 mm" in note.observations[0].content
        assert "fwhm" in note.observations[0].tags
        assert note.observations[1].category == ObservationCategory.FINDING

        assert len(note.relations) >= 3
        rel_targets: list[str] = [r.target_permalink for r in note.relations]
        assert "00_Index/Lab Standards" in rel_targets
        assert "Study_Overview" in rel_targets
        assert "Schaefer2018_Atlas" in rel_targets

    def test_render_and_roundtrip(self) -> None:
        """Verify note rendering generates valid parseable Markdown.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts rendered note parses identically.
        """
        parser: BrainParser = BrainParser()
        obs = [
            BrainObservation(
                category=ObservationCategory.DECISION,
                content="Use FreeSurfer 7.4 recon-all",
                tags=["freesurfer"],
            )
        ]
        rels = [
            BrainRelation(
                relation_type=RelationType.USES_METHOD,
                target_permalink="methods/freesurfer",
                target_title="FreeSurfer",
            )
        ]
        rendered: str = parser.render_markdown_note(
            title="Structural Processing",
            observations=obs,
            relations=rels,
            body_prose="Prose section describing T1w pipeline.",
        )
        assert "# Structural Processing" in rendered
        assert "- [decision] Use FreeSurfer 7.4 recon-all #freesurfer" in rendered
        assert (
            "- [uses_method] [[methods/freesurfer|FreeSurfer]]" in rendered
        )

        re_parsed: BrainNote = parser.parse_markdown_content(
            raw_text=rendered,
            relative_path="methods/structural.md",
            scope=BrainScope.PROJECT,
        )
        assert re_parsed.entity.title == "Structural Processing"
        assert len(re_parsed.observations) == 1
        assert re_parsed.observations[0].category == ObservationCategory.DECISION


class TestBrainIndexer:
    """Test suite for SQLite WAL and FTS5 incremental indexing."""

    def test_incremental_sync_and_dirty_check(self) -> None:
        """Verify file mtime and hash dirty check prevents redundant parsing.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts added, unchanged, updated, and deleted counts.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_dir: Path = Path(tmp_dir) / "vault"
            vault_dir.mkdir()
            db_path: Path = Path(tmp_dir) / "brain.db"
            indexer: BrainIndexer = BrainIndexer(db_path=db_path)

            note1: Path = vault_dir / "Note1.md"
            note1.write_text(
                "# Note 1\n\n### Observations\n- [finding] Finding A #tag\n",
                encoding="utf-8",
            )

            metrics1: dict[str, int] = indexer.sync_vault(
                vault_dir=vault_dir, scope=BrainScope.GLOBAL
            )
            assert metrics1["added"] == 1
            assert metrics1["unchanged"] == 0

            # Second sync without touching file -> unchanged
            metrics2: dict[str, int] = indexer.sync_vault(
                vault_dir=vault_dir, scope=BrainScope.GLOBAL
            )
            assert metrics2["added"] == 0
            assert metrics2["unchanged"] == 1

            # Update file content -> updated
            note1.write_text(
                "# Note 1 Updated\n\n### Observations\n- [finding] Finding B\n",
                encoding="utf-8",
            )
            metrics3: dict[str, int] = indexer.sync_vault(
                vault_dir=vault_dir, scope=BrainScope.GLOBAL
            )
            assert metrics3["updated"] == 1

            # Delete file -> deleted
            note1.unlink()
            metrics4: dict[str, int] = indexer.sync_vault(
                vault_dir=vault_dir, scope=BrainScope.GLOBAL
            )
            assert metrics4["deleted"] == 1

            counts: dict[str, int] = indexer.get_counts()
            assert counts["global_notes"] == 0


class TestBrainRetriever:
    """Test suite for progressive disclosure token budgeting."""

    def test_build_context_token_capping(self) -> None:
        """Verify Tier-0 build_context strictly adheres to token ceiling.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts token ceiling constraint is respected.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_dir: Path = Path(tmp_dir) / "vault"
            vault_dir.mkdir()
            db_path: Path = Path(tmp_dir) / "brain.db"
            indexer: BrainIndexer = BrainIndexer(db_path=db_path)

            # Create a note with many observation lines
            obs_lines: list[str] = [
                f"- [parameter] Hyperparameter alpha_{i} set to {i * 0.1:.2f} #param"
                for i in range(50)
            ]
            content: str = (
                "# Hyperparameters\n\n### Observations\n"
                + "\n".join(obs_lines)
                + "\n"
            )
            (vault_dir / "Hyperparameters.md").write_text(
                content, encoding="utf-8"
            )
            indexer.sync_vault(vault_dir=vault_dir, scope=BrainScope.GLOBAL)

            retriever: BrainRetriever = BrainRetriever(indexer=indexer)

            # Test tight token budget
            capsule: BrainContextCapsule = retriever.build_context(
                query="hyperparameters", max_tokens=100
            )
            assert capsule.token_estimate <= 100
            assert capsule.truncated is True
            assert "Hyperparameters" in capsule.markdown_context


class TestBrainManagerAndSlashCommands:
    """Test suite for BrainManager coordination and /brain slash commands."""

    def test_manager_scaffolding_and_observation_recording(self) -> None:
        """Verify vault initialization and remember_observation ledger.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts notes exist and observations append cleanly.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            g_vault: Path = Path(tmp_dir) / "global_brain"
            p_vault: Path = Path(tmp_dir) / "project_brain"
            mgr: BrainManager = BrainManager(
                global_vault_dir=g_vault, project_vault_dir=p_vault
            )

            g_files = mgr.init_global_vault()
            p_files = mgr.init_project_vault()
            assert len(g_files) >= 2
            assert len(p_files) >= 1

            stats: BrainStats = mgr.get_stats()
            assert stats.global_notes_count >= 2
            assert stats.project_notes_count >= 1
            assert stats.total_observations_count >= 3

            # Append a quick observation
            obs = BrainObservation(
                category=ObservationCategory.DECISION,
                content="Switched from 32-channel to 64-channel head coil",
                tags=["hardware"],
            )
            ok: bool = mgr.remember_observation(observation=obs)
            assert ok is True

            search_hits = mgr.search("head coil")
            assert len(search_hits) >= 1
            assert "Quick Notes" in search_hits[0].title

    def test_slash_command_brain(self) -> None:
        """Verify /brain slash command routing and execution.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts all /brain subcommands return success.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir: Path = Path(tmp_dir)
            cfg: NeuriConfig = NeuriConfig()
            cfg.brain.global_vault_path = str(ws_dir / "global_vault")
            cfg.brain.project_vault_subdir = "project_vault"

            bb: Blackboard = Blackboard(ws_dir / "blackboard.db")
            orch: DAGOrchestrator = DAGOrchestrator(
                blackboard=bb,
                config=cfg,
            )
            router: SlashCommandRouter = SlashCommandRouter(
                workspace_dir=ws_dir,
                config=cfg,
                blackboard=bb,
                orchestrator=orch,
            )

            # 1. /brain init
            res_init: SlashCommandResult = router.execute("/brain init")
            assert res_init.success is True
            assert "Neuri Brain Initialized" in res_init.markdown_output

            # 2. /brain status
            res_status: SlashCommandResult = router.execute("/brain status")
            assert res_status.success is True
            assert "Neuri Brain Status" in res_status.markdown_output

            # 3. /brain remember
            res_rem: SlashCommandResult = router.execute(
                "/brain remember High pass filter set to 0.01 Hz"
            )
            assert res_rem.success is True
            assert "Observation Recorded" in res_rem.markdown_output

            # 4. /brain search
            res_search: SlashCommandResult = router.execute(
                "/brain search filter"
            )
            assert res_search.success is True
            assert "Brain Search Results" in res_search.markdown_output

            # 5. /brain context
            res_ctx: SlashCommandResult = router.execute(
                "/brain context standards"
            )
            assert res_ctx.success is True
            assert "Prior Knowledge Capsule" in res_ctx.markdown_output

            # 6. /brain sync
            res_sync: SlashCommandResult = router.execute("/brain sync")
            assert res_sync.success is True
            assert "Brain Vaults Synchronized" in res_sync.markdown_output
