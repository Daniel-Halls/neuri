"""Unit tests for Neuri documentation database, chunker, and MCP server.

Verifies deterministic full-text search across commands.md, functions.md,
and documentation.md, schema isolation, and JSON-RPC 2.0 dispatching.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from neuri.docs.db.repository import DocsRepository
from neuri.docs.grounding import PipelinePreGrounder
from neuri.docs.ingest.cli import get_docs_cli_app
from neuri.docs.ingest.indexer import DocsIndexer
from neuri.docs.ingest.markdown_chunker import MarkdownDocChunker
from neuri.docs.models import DocChunkRecord, DocSearchResult
from neuri.docs.server import DocsMCPServer


@pytest.fixture
def temp_docs_env(tmp_path: Path) -> tuple[Path, Path]:
    """Create a temporary docs directory tree and temporary sqlite db path.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        tuple[Path, Path]: tuple object
            Tuple containing (docs_dir, db_path).
    """
    docs_dir: Path = tmp_path / "brain_docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pipeline with commands.md and documentation.md (e.g. sample_pipeline)
    pipe_a: Path = docs_dir / "sample_pipe"
    pipe_a.mkdir()

    cmd_text: str = (
        "### Command Line Syntax\n\n"
        "```bash\npipe_cmd [options] input output\n```\n\n"
        "### 1. Filtering Flags\n\n"
        "* **`--output-spaces [SPACES ...]`**: Spatial normalization targets.\n"
        "* **`-t, --task-id TASK_ID`**: Selects specific task to process.\n"
        "* **`--anat-only`**: Run anatomical workflow only.\n"
    )
    (pipe_a / "commands.md").write_text(cmd_text, encoding="utf-8")

    doc_text: str = (
        "### 1. Overview\n\n"
        "Sample pipeline performs minimal preprocessing for functional MRI.\n\n"
        "### 2. Anatomical Workflow\n\n"
        "The anatomical stage performs skull-stripping and normalisation.\n"
    )
    (pipe_a / "documentation.md").write_text(doc_text, encoding="utf-8")

    # 2. Package with functions.md and documentation.md (e.g. sample_lib)
    lib_b: Path = docs_dir / "sample_lib"
    lib_b.mkdir()

    fn_text: str = (
        "## 1. Datasets Module\n\n"
        "* **`fetch_data(data_dir=None, subjects=[1])`**:\n"
        "  * **What it does**: Downloads sample datasets from public repos.\n"
        "  * **Arguments**: `subjects` (list of integers).\n\n"
        "* **`Masker(mask_img=None, standardize=True)`**:\n"
        "  * **What it does**: Extracts time series signals from regions.\n"
    )
    (lib_b / "functions.md").write_text(fn_text, encoding="utf-8")

    doc_lib_text: str = (
        "### Overview\n\n"
        "Sample library is a Python package for statistical analysis.\n"
    )
    (lib_b / "documentation.md").write_text(doc_lib_text, encoding="utf-8")

    db_path: Path = tmp_path / "test_docs.db"
    return docs_dir, db_path


class TestMarkdownDocChunker:
    """Test suite for MarkdownDocChunker parsing."""

    def test_chunk_commands_extracts_flags(self, tmp_path: Path) -> None:
        """Verify command flags and options are chunked as atomic items.

        Parameters
        ------------
        tmp_path: Path
            Temporary directory fixture.

        Returns
        --------
            None: NoneType object
                Asserts extracted items match expectations.
        """
        chunker: MarkdownDocChunker = MarkdownDocChunker()
        cmd_file: Path = tmp_path / "commands.md"
        cmd_file.write_text(
            "### Options\n\n"
            "* **`--output-spaces [SPACES ...]`**: Target spaces.\n"
            "* **`--low-mem`**: Reduce memory footprint.\n",
            encoding="utf-8",
        )
        chunks: list[DocChunkRecord] = chunker.chunk_file(
            file_path=cmd_file,
            pipeline_name="sample",
            doc_type="commands",
        )
        assert len(chunks) >= 2
        items = [c.item_name for c in chunks]
        assert any("--output-spaces" in it for it in items)
        assert any("--low-mem" in it for it in items)
        assert all(c.doc_type == "commands" for c in chunks)

    def test_chunk_functions_extracts_apis(self, tmp_path: Path) -> None:
        """Verify Python functions and classes are chunked as atomic items.

        Parameters
        ------------
        tmp_path: Path
            Temporary directory fixture.

        Returns
        --------
            None: NoneType object
                Asserts function names and doc_type are preserved.
        """
        chunker: MarkdownDocChunker = MarkdownDocChunker()
        fn_file: Path = tmp_path / "functions.md"
        fn_file.write_text(
            "## Nilearn Maskers\n\n"
            "* **`NiftiMasker(mask_img=None)`**:\n"
            "  * **What it does**: Computes masks from 3D/4D images.\n",
            encoding="utf-8",
        )
        chunks: list[DocChunkRecord] = chunker.chunk_file(
            file_path=fn_file,
            pipeline_name="nilearn",
            doc_type="functions",
        )
        assert len(chunks) >= 1
        assert any("NiftiMasker" in c.item_name for c in chunks)
        assert all(c.doc_type == "functions" for c in chunks)


class TestDocsRepository:
    """Test suite for DocsRepository SQLite FTS5 operations."""

    def test_pipeline_upsert_and_type_isolation(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify strict isolation when searching by doc_type.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts command searches do not return functions and vice-versa.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        idx_res = indexer.index_all()
        assert idx_res["status"] == "success"
        assert idx_res["pipelines_indexed"] == 2

        # 1. Search commands for sample_pipe -> should find --output-spaces
        cmd_hits: list[DocSearchResult] = repo.search(
            pipeline="sample_pipe",
            query="--output-spaces",
            doc_type="commands",
        )
        assert len(cmd_hits) > 0
        assert cmd_hits[0].doc_type == "commands"
        assert "--output-spaces" in cmd_hits[0].item_name

        # 2. Searching functions for sample_pipe -> must be empty
        empty_fn: list[DocSearchResult] = repo.search(
            pipeline="sample_pipe",
            query="--output-spaces",
            doc_type="functions",
        )
        assert len(empty_fn) == 0

        # 3. Search functions for sample_lib -> should find fetch_data
        fn_hits: list[DocSearchResult] = repo.search(
            pipeline="sample_lib",
            query="fetch_data",
            doc_type="functions",
        )
        assert len(fn_hits) > 0
        assert fn_hits[0].doc_type == "functions"
        assert "fetch_data" in fn_hits[0].item_name

        # 4. Searching commands for sample_lib -> must be empty
        empty_cmd: list[DocSearchResult] = repo.search(
            pipeline="sample_lib",
            query="fetch_data",
            doc_type="commands",
        )
        assert len(empty_cmd) == 0

        # 5. Search documentation for workflow rationale
        doc_hits: list[DocSearchResult] = repo.search(
            pipeline="sample_pipe",
            query="anatomical",
            doc_type="documentation",
        )
        assert len(doc_hits) > 0
        assert doc_hits[0].doc_type == "documentation"

    def test_alias_resolution(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify pipeline names and aliases resolve flexibly.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts case-insensitive and alias resolution.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        indexer.index_all()

        assert repo.resolve_pipeline_name("SAMPLE_PIPE") == "sample_pipe"
        assert repo.resolve_pipeline_name("sample-pipe") == "sample_pipe"
        assert repo.resolve_pipeline_name("sample_lib") == "sample_lib"
        assert repo.resolve_pipeline_name("non_existent") is None


class TestDocsMCPServer:
    """Test suite for DocsMCPServer tool dispatch and JSON-RPC protocol."""

    def test_mcp_tools_and_type_enforcement(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify MCP tools dispatch to correct type-restricted search.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts search_commands, search_functions, search_docs.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        indexer.index_all()

        server: DocsMCPServer = DocsMCPServer(repository=repo)

        # 1. search_commands tool
        res_cmd = server.search_commands(
            pipeline="sample_pipe", query="output-spaces"
        )
        assert res_cmd["doc_type"] == "commands"
        assert res_cmd["match_count"] > 0
        assert "--output-spaces" in res_cmd["results"][0]["item"]

        # 2. search_functions tool
        res_fn = server.search_functions(
            pipeline="sample_lib", query="fetch_data"
        )
        assert res_fn["doc_type"] == "functions"
        assert res_fn["match_count"] > 0
        assert "fetch_data" in res_fn["results"][0]["item"]

        # 3. search_documentation tool
        res_doc = server.search_documentation(
            pipeline="sample_pipe", query="preprocessing"
        )
        assert res_doc["doc_type"] == "documentation"
        assert res_doc["match_count"] > 0

        # 4. list_supported_pipelines tool
        res_list = server.list_supported_pipelines()
        assert res_list["total_pipelines"] == 2

    def test_mcp_jsonrpc_protocol(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify JSON-RPC 2.0 initialize, tools/list, and tools/call handling.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts JSON-RPC 2.0 compliance.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        indexer.index_all()

        server: DocsMCPServer = DocsMCPServer(repository=repo)

        # 1. initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        init_resp = server.handle_request(init_req)
        assert init_resp["id"] == 1
        assert "serverInfo" in init_resp["result"]

        # 2. tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        list_resp = server.handle_request(list_req)
        assert list_resp["id"] == 2
        tools = list_resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "search_pipeline_commands" in tool_names
        assert "search_pipeline_functions" in tool_names
        assert "search_pipeline_docs" in tool_names
        assert "list_supported_pipelines" in tool_names

        # 3. tools/call
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_pipeline_commands",
                "arguments": {
                    "pipeline": "sample_pipe",
                    "query": "output-spaces",
                },
            },
        }
        call_resp = server.handle_request(call_req)
        assert call_resp["id"] == 3
        content = call_resp["result"]["content"][0]["text"]
        parsed = json.loads(content)
        assert parsed["doc_type"] == "commands"
        assert parsed["match_count"] > 0


class TestDocsCLI:
    """Test suite for Typer CLI commands."""

    def test_cli_index_and_search(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify CLI index, search, and list subcommands.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts zero exit codes and console outputs.
        """
        docs_dir, db_path = temp_docs_env
        runner: CliRunner = CliRunner()
        cli_app = get_docs_cli_app()

        # 1. index
        res_idx = runner.invoke(
            cli_app,
            ["index", "-d", str(docs_dir), "-b", str(db_path)],
        )
        assert res_idx.exit_code == 0
        assert "Successfully indexed 2 pipelines" in res_idx.output

        # 2. list
        res_list = runner.invoke(cli_app, ["list", "-b", str(db_path)])
        assert res_list.exit_code == 0
        assert "sample_pipe" in res_list.output
        assert "sample_lib" in res_list.output

        # 3. search
        res_search = runner.invoke(
            cli_app,
            [
                "search",
                "sample_pipe",
                "output-spaces",
                "-t",
                "commands",
                "-b",
                str(db_path),
            ],
        )
        assert res_search.exit_code == 0
        assert "Found" in res_search.output
        assert "--output-spaces" in res_search.output


class TestPipelinePreGrounder:
    """Test suite for in-process PipelinePreGrounder query analysis and grounding."""

    def test_detect_pipelines(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify pipeline names and aliases are accurately detected from prompts.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts canonical pipeline names are returned.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        indexer.index_all()

        grounder: PipelinePreGrounder = PipelinePreGrounder(repository=repo)
        detected_a: list[str] = grounder.detect_pipelines(
            "are there any sample_pipe commands for skull stripping?"
        )
        assert "sample_pipe" in detected_a

        detected_b: list[str] = grounder.detect_pipelines(
            "how to load data using sample_lib in python?"
        )
        assert "sample_lib" in detected_b

        detected_none: list[str] = grounder.detect_pipelines(
            "write a python script to calculate mean squared error"
        )
        assert len(detected_none) == 0

    def test_infer_doc_type(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify doc type inference based on prompt keywords and pipeline metadata.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts accurate classification to commands, functions, or docs.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        indexer.index_all()

        grounder: PipelinePreGrounder = PipelinePreGrounder(repository=repo)
        pipes = repo.list_pipelines()
        pipe_a = next(p for p in pipes if p.name == "sample_pipe")
        pipe_b = next(p for p in pipes if p.name == "sample_lib")

        # sample_pipe only has commands & doc
        assert (
            grounder.infer_doc_type("what are the flags for run", pipe_a)
            == "commands"
        )

        # sample_lib only has functions & doc
        assert (
            grounder.infer_doc_type("how do I call the api", pipe_b)
            == "functions"
        )

    def test_extract_search_terms(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify domain search terms are extracted while stopwords are filtered.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts stopwords and command keywords are excluded.
        """
        _, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        repo.init_db()
        grounder: PipelinePreGrounder = PipelinePreGrounder(repository=repo)

        terms: list[str] = grounder.extract_search_terms(
            "are there any sample_pipe commands for output-spaces?",
            pipeline_name="sample_pipe",
        )
        assert "output-spaces" in terms
        assert "commands" not in terms
        assert "are" not in terms
        assert "sample_pipe" not in terms

    def test_ground_prompt_matches(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify ground_prompt injects verified documentation blocks into prompt.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts markdown grounding block formatting and content.
        """
        docs_dir, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        indexer: DocsIndexer = DocsIndexer(repository=repo, docs_dir=docs_dir)
        indexer.index_all()

        grounder: PipelinePreGrounder = PipelinePreGrounder(repository=repo)
        grounded_text: str = grounder.ground_prompt(
            "are there any sample_pipe options for output-spaces?"
        )
        assert (
            "## Neuri Verified Brain Documentation (In-Process Grounding)"
            in grounded_text
        )
        assert "sample_pipe" in grounded_text
        assert "--output-spaces" in grounded_text

    def test_ground_prompt_no_pipeline(
        self, temp_docs_env: tuple[Path, Path]
    ) -> None:
        """Verify ground_prompt returns empty string when no pipeline is mentioned.

        Parameters
        ------------
        temp_docs_env: tuple[Path, Path]
            Temporary environment fixture.

        Returns
        --------
            None: NoneType object
                Asserts empty string return value.
        """
        _, db_path = temp_docs_env
        repo: DocsRepository = DocsRepository(db_path=db_path)
        repo.init_db()
        grounder: PipelinePreGrounder = PipelinePreGrounder(repository=repo)

        grounded_text: str = grounder.ground_prompt("generate a synthetic matrix")
        assert grounded_text == ""

