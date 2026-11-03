"""Indexer for scanning and persisting neuroimaging documentation vaults.

Discovers package directories, parses markdown documentation files into
structured chunks, and writes them to SQLite FTS5.
"""

import os
import re
from pathlib import Path
from typing import Any

from neuri.core.paths import PathResolver
from neuri.docs.db.repository import DocsRepository
from neuri.docs.ingest.markdown_chunker import MarkdownDocChunker
from neuri.docs.models import DocChunkRecord, PipelineMetadata


class DocsIndexer:
    """Orchestrates filesystem scanning and database ingestion of pipeline docs.

    Parameters
    ------------
    repository: DocsRepository | None
        Target DocsRepository instance. Defaults to None (resolves default).
    docs_dir: Path | None
        Directory containing pipeline subfolders. Defaults to None.

    Returns
    --------
        DocsIndexer: DocsIndexer instance
            Constructed indexer instance.
    """

    KNOWN_ALIASES: dict[str, list[str]] = {
        "fmriprep": ["fmriprep", "smriprep", "bold_preproc"],
        "fsl": ["fsl", "feat", "melodic", "flirt", "fnirt", "bet", "topup", "eddy"],
        "afni": ["afni", "3dcalc", "3dtshift", "3dvolreg"],
        "spm": ["spm", "spm12"],
        "nilearn": ["nilearn"],
        "nipype": ["nipype"],
        "nibabel": ["nibabel"],
        "qsiprep": ["qsiprep", "dwi_preproc"],
        "qsirecon": ["qsirecon"],
        "xcp-d": ["xcp_d", "xcpd", "xcp-d", "postprocessing"],
        "fastsurfer": ["fastsurfer"],
        "freesurfer": ["freesurfer", "recon-all"],
        "tedana": ["tedana", "me-fmri", "multiecho"],
        "hcp-pipelines": ["hcp", "hcp-pipelines", "hcppipelines"],
        "qunex": ["qunex"],
        "workbench": ["workbench", "wb_command", "connectome-workbench"],
        "dcm2niix": ["dcm2niix", "dcm2nii"],
        "pydeface": ["pydeface", "pyedface"],
        "bctnet": ["bctnet", "bct", "brain-connectivity-toolbox"],
        "hoi": ["hoi", "higher-order-interactions"],
    }

    def __init__(
        self,
        repository: DocsRepository | None = None,
        docs_dir: Path | None = None,
    ) -> None:
        """Initialize DocsIndexer with repository and docs source directory.

        Parameters
        ------------
        repository: DocsRepository | None
            DocsRepository reference. Defaults to None.
        docs_dir: Path | None
            Root documentation directory. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes repository, chunker, and docs directory paths.
        """
        self.repository: DocsRepository = repository or DocsRepository()
        self.chunker: MarkdownDocChunker = MarkdownDocChunker()
        self.docs_dir: Path = self._resolve_docs_dir(docs_dir)

    def _resolve_docs_dir(self, explicit_dir: Path | None) -> Path:
        """Resolve documentation root directory path.

        Parameters
        ------------
        explicit_dir: Path | None
            Explicit directory or None.

        Returns
        --------
            Path: Path object
                Canonical directory path to documentation files.
        """
        if explicit_dir is not None:
            return explicit_dir

        env_dir: str = os.environ.get("NEURI_BRAIN_DOCS", "").strip()
        if env_dir:
            return Path(env_dir).expanduser().resolve()

        repo_root: Path = PathResolver.get_repo_root()
        candidate: Path = repo_root / "neuri" / "brain" / "doc"
        if candidate.is_dir():
            return candidate

        home_candidate: Path = Path.home() / ".neuri" / "brain" / "doc"
        return home_candidate

    def _extract_summary(self, doc_path: Path) -> str:
        """Extract a one-sentence summary from the documentation markdown.

        Parameters
        ------------
        doc_path: Path
            Path to documentation.md.

        Returns
        --------
            str: string object
                Extracted summary string.
        """
        if not doc_path.is_file():
            return ""

        text: str = doc_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line_str: str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            # Remove markdown citations like [1, 2] and links
            cleaned: str = re.sub(r"\[\d+[^\]]*\]", "", line_str)
            cleaned = re.sub(r"[\*\`]", "", cleaned).strip()
            if len(cleaned) > 20:
                summary: str = cleaned[:240] + ("..." if len(cleaned) > 240 else "")
                return summary

        return ""

    def index_all(self) -> dict[str, Any]:
        """Index all pipeline documentation markdown files into SQLite database.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Summary of indexed pipelines and total documentation chunks.
        """
        self.repository.init_db()

        if not self.docs_dir.is_dir():
            return {
                "status": "error",
                "message": f"Documentation directory not found: {self.docs_dir}",
                "pipelines_indexed": 0,
                "total_chunks": 0,
            }

        packages_indexed: int = 0
        total_chunks: int = 0
        details: list[dict[str, Any]] = []

        subdirs: list[Path] = sorted(
            [
                p
                for p in self.docs_dir.iterdir()
                if p.is_dir() and not p.is_symlink()
            ]
        )

        for pkg_dir in subdirs:
            raw_name: str = pkg_dir.name.lower()
            pkg_name: str = "pydeface" if raw_name == "pyedface" else raw_name
            cmd_file: Path = pkg_dir / "commands.md"
            fn_file: Path = pkg_dir / "functions.md"
            doc_file: Path = pkg_dir / "documentation.md"

            has_cmd: bool = cmd_file.is_file()
            has_fn: bool = fn_file.is_file()
            has_doc: bool = doc_file.is_file()

            if not (has_cmd or has_fn or has_doc):
                continue

            summary: str = self._extract_summary(doc_file)
            aliases: list[str] = self.KNOWN_ALIASES.get(
                pkg_name, [pkg_name, pkg_dir.name]
            )

            meta: PipelineMetadata = PipelineMetadata(
                name=pkg_name,
                display_name=pkg_dir.name,
                aliases=aliases,
                has_commands=has_cmd,
                has_functions=has_fn,
                has_documentation=has_doc,
                description=summary,
            )

            pipe_id: int = self.repository.upsert_pipeline(meta)
            pkg_chunks: int = 0

            # Ingest commands.md
            if has_cmd:
                cmd_chunks: list[DocChunkRecord] = self.chunker.chunk_file(
                    file_path=cmd_file,
                    pipeline_name=pkg_name,
                    doc_type="commands",
                )
                self.repository.insert_doc_chunks(
                    pipeline_id=pipe_id,
                    pipeline_name=pkg_name,
                    doc_type="commands",
                    chunks=cmd_chunks,
                )
                pkg_chunks += len(cmd_chunks)

            # Ingest functions.md
            if has_fn:
                fn_chunks: list[DocChunkRecord] = self.chunker.chunk_file(
                    file_path=fn_file,
                    pipeline_name=pkg_name,
                    doc_type="functions",
                )
                self.repository.insert_doc_chunks(
                    pipeline_id=pipe_id,
                    pipeline_name=pkg_name,
                    doc_type="functions",
                    chunks=fn_chunks,
                )
                pkg_chunks += len(fn_chunks)

            # Ingest documentation.md
            if has_doc:
                doc_chunks: list[DocChunkRecord] = self.chunker.chunk_file(
                    file_path=doc_file,
                    pipeline_name=pkg_name,
                    doc_type="documentation",
                )
                self.repository.insert_doc_chunks(
                    pipeline_id=pipe_id,
                    pipeline_name=pkg_name,
                    doc_type="documentation",
                    chunks=doc_chunks,
                )
                pkg_chunks += len(doc_chunks)

            packages_indexed += 1
            total_chunks += pkg_chunks
            details.append(
                {
                    "name": pkg_name,
                    "display_name": pkg_dir.name,
                    "chunks": pkg_chunks,
                    "has_commands": has_cmd,
                    "has_functions": has_fn,
                    "has_documentation": has_doc,
                }
            )

        return {
            "status": "success",
            "docs_dir": str(self.docs_dir),
            "db_path": str(self.repository.db_path),
            "pipelines_indexed": packages_indexed,
            "total_chunks": total_chunks,
            "details": details,
        }


__all__: list[str] = [
    "DocsIndexer",
]
