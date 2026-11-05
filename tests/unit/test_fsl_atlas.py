"""Unit tests for offline FSL MNI152 brain atlas lookup and MCP server.

Tests coordinate decoding, region search, standalone CLI functions, MCP tools,
and NiiVue bridge HTTP endpoints across 20 human FSL atlases.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from neuri.mcp_servers.mcp_fsl_atlas import FSLAtlasMCPServer
from neuri.viewer.fsl_atlas import (
    FSLAtlasClient,
    FSLAtlasHit,
    FSLCoordinateResult,
    FSLRegionSearchResult,
    query_fsl_coordinates,
    search_fsl_regions,
)
from neuri.viewer.niivue_bridge import NiiVueBridgeHandler


class TestFSLAtlasDataStructures:
    """Tests for FSL atlas dataclasses and formatting methods."""

    def test_atlas_hit_serialization(self) -> None:
        """Verify serialization of a single FSLAtlasHit object.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts hit attributes match serialized dictionary.
        """
        hit: FSLAtlasHit = FSLAtlasHit(
            atlas_key="HarvardOxford-Subcortical",
            atlas_name="Harvard-Oxford Subcortical Structural Atlas",
            atlas_type="Probabilistic",
            label_index=9,
            region_name="Left Amygdala",
            probability=92.0,
            cog_mni=(-23.0, -3.0, -19.0),
        )
        data: dict[str, Any] = hit.to_dict()
        assert data["atlas_key"] == "HarvardOxford-Subcortical"
        assert data["region_name"] == "Left Amygdala"
        assert data["probability"] == 92.0

    def test_coordinate_result_markdown_and_summary(self) -> None:
        """Verify Markdown table generation and single-line prompt summary.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts Markdown table structure and summary formatting.
        """
        hit1: FSLAtlasHit = FSLAtlasHit(
            atlas_key="HOSPA",
            atlas_name="Harvard-Oxford Subcortical",
            atlas_type="Probabilistic",
            label_index=9,
            region_name="Left Amygdala",
            probability=92.0,
            cog_mni=(-23.0, -3.0, -19.0),
        )
        hit2: FSLAtlasHit = FSLAtlasHit(
            atlas_key="Talairach",
            atlas_name="Talairach Daemon Labels",
            atlas_type="Label",
            label_index=15,
            region_name="Amygdala",
            probability=100.0,
            cog_mni=(-22.0, -4.0, -18.0),
        )
        res: FSLCoordinateResult = FSLCoordinateResult(
            x=-24.0,
            y=-2.0,
            z=-20.0,
            voxel_id=263593,
            hits=(hit1, hit2),
        )

        md: str = res.format_markdown()
        assert "### FSL Anatomy" in md
        assert "Left Amygdala" in md
        assert "92%" in md
        assert "Discrete" in md

        summary: str = res.to_summary_text()
        assert "MNI [-24.0, -2.0, -20.0]" in summary
        assert "Left Amygdala [92% HOSPA]" in summary
        assert "Amygdala (Talairach)" in summary


class TestFSLAtlasClient:
    """Tests for FSLAtlasClient queries and coordinate math."""

    def test_coordinate_conversion_math(self) -> None:
        """Verify MNI millimeter to 2mm grid conversion.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts exact voxel indices and bounds checking.
        """
        client: FSLAtlasClient = FSLAtlasClient()

        # Origin (0, 0, 0)
        # i = round((90 - 0)/2) = 45
        # j = round((0 + 126)/2) = 63
        # k = round((0 + 72)/2) = 36
        coords_origin = client.mni_to_voxel_coords(0.0, 0.0, 0.0)
        assert coords_origin == (45, 63, 36)

        # Left Amygdala [-24.0, -2.0, -20.0]
        # i = round((90 - (-24))/2) = 57
        # j = round((-2 + 126)/2) = 62
        # k = round((-20 + 72)/2) = 26
        coords_amygdala = client.mni_to_voxel_coords(-24.0, -2.0, -20.0)
        assert coords_amygdala == (57, 62, 26)

        # Out-of-bounds coordinates
        oob = client.mni_to_voxel_coords(300.0, 400.0, 500.0)
        assert oob is None

    def test_query_coordinate_known_landmarks(self) -> None:
        """Verify anatomical decoding at Left Amygdala and Visual Cortex.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts expected atlas regions are retrieved with high probability.
        """
        client: FSLAtlasClient = FSLAtlasClient()
        if not client.is_available():
            pytest.skip("FSL atlas database not found on this machine")

        # 1. Left Amygdala
        res_amyg: FSLCoordinateResult = client.query_coordinate(
            x=-24.0, y=-2.0, z=-20.0, min_prob=5.0
        )
        assert res_amyg.voxel_id > 0
        assert len(res_amyg.hits) > 0
        amyg_names: list[str] = [h.region_name.lower() for h in res_amyg.hits]
        assert any("amygdala" in name for name in amyg_names)

        # Verify Harvard-Oxford Subcortical identifies Left Amygdala
        hos_hits = [
            h for h in res_amyg.hits if h.atlas_key == "HarvardOxford-Subcortical"
        ]
        assert len(hos_hits) > 0
        assert hos_hits[0].region_name == "Left Amygdala"
        assert hos_hits[0].probability >= 50.0

        # 2. Primary Visual Cortex / Occipital Lobe [0.0, -85.0, 0.0]
        res_v1: FSLCoordinateResult = client.query_coordinate(
            x=0.0, y=-85.0, z=0.0, min_prob=5.0
        )
        v1_names: list[str] = [h.region_name.lower() for h in res_v1.hits]
        assert any(
            "occipital" in name or "cuneus" in name or "calcarine" in name
            for name in v1_names
        )

    def test_search_regions_by_name(self) -> None:
        """Verify region substring search across atlases.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts matching regions and center-of-gravity coordinates.
        """
        client: FSLAtlasClient = FSLAtlasClient()
        if not client.is_available():
            pytest.skip("FSL atlas database not found on this machine")

        matches: list[FSLRegionSearchResult] = client.search_regions(
            query="Insular Cortex"
        )
        assert len(matches) > 0
        match_keys: list[str] = [m.atlas_key for m in matches]
        assert "HarvardOxford-Cortical" in match_keys
        hoc_match = [
            m for m in matches if m.atlas_key == "HarvardOxford-Cortical"
        ][0]
        assert hoc_match.region_name == "Insular Cortex"
        # Center of gravity should be within expected anatomical range
        assert 30.0 <= hoc_match.cog_mni[0] <= 50.0

    def test_list_bundled_human_atlases(self) -> None:
        """Verify all 20 human FSL atlases are present in the catalog.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts atlas count and key presence.
        """
        client: FSLAtlasClient = FSLAtlasClient()
        if not client.is_available():
            pytest.skip("FSL atlas database not found on this machine")

        atlases = client.list_atlases()
        assert len(atlases) == 20
        keys: set[str] = {a["atlas_key"] for a in atlases}
        assert "HarvardOxford-Cortical" in keys
        assert "HarvardOxford-Subcortical" in keys
        assert "Juelich" in keys
        assert "JHU-tracts" in keys
        assert "Talairach" in keys
        assert "XTRACT" in keys
        assert "STN" in keys


class TestFSLAtlasMCPServer:
    """Tests for the stdio FSL atlas MCP server tools."""

    def test_mcp_tool_definitions(self) -> None:
        """Verify MCP server advertises declared tool schemas.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts tool names and required schema properties.
        """
        server: FSLAtlasMCPServer = FSLAtlasMCPServer()
        assert server.server_name == "fsl_atlas"
        tools = server.get_tool_definitions()
        tool_names: list[str] = [t["name"] for t in tools]
        assert "query_mni_coordinate" in tool_names
        assert "search_fsl_brain_region" in tool_names
        assert "list_fsl_atlases" in tool_names

    def test_mcp_call_tool_query_mni_coordinate(self) -> None:
        """Verify execution of query_mni_coordinate MCP tool.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts tool execution returns FSL anatomy and Neurosynth data.
        """
        server: FSLAtlasMCPServer = FSLAtlasMCPServer()
        result: dict[str, Any] = server.call_tool(
            "query_mni_coordinate",
            {"x": -24.0, "y": -2.0, "z": -20.0, "include_neurosynth": True},
        )
        assert result["x"] == -24.0
        assert "fsl_anatomy" in result
        assert "summary" in result
        assert "neurosynth" in result
        assert len(result["fsl_anatomy"]["hits"]) > 0

    def test_mcp_call_tool_search_region(self) -> None:
        """Verify execution of search_fsl_brain_region MCP tool.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts matching region list is returned.
        """
        server: FSLAtlasMCPServer = FSLAtlasMCPServer()
        matches = server.call_tool(
            "search_fsl_brain_region",
            {"query": "Putamen"},
        )
        assert isinstance(matches, list)
        assert len(matches) > 0
        assert any("putamen" in m["region_name"].lower() for m in matches)


class TestNiiVueBridgeFSLAtlasEndpoint:
    """Tests for HTTP serving of FSL atlas data on NiiVueBridgeHandler."""

    def test_serve_fsl_atlas_handler(self) -> None:
        """Verify _serve_fsl_atlas sends 200 and serialized atlas hits.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts handler sends 200 response with JSON hits.
        """
        handler: MagicMock = MagicMock()
        handler._get_cors_origin.return_value = "*"

        NiiVueBridgeHandler._serve_fsl_atlas(
            handler,
            x_str="-24",
            y_str="-2",
            z_str="-20",
            min_prob_str="5.0",
        )

        handler.send_response.assert_called_with(200)
        assert handler.wfile.write.called
        written_bytes: bytes = handler.wfile.write.call_args[0][0]
        data: dict[str, Any] = json.loads(written_bytes.decode("utf-8"))
        assert data["x"] == -24.0
        assert "hits" in data
        assert len(data["hits"]) > 0

    def test_serve_neurosynth_includes_fsl_anatomy(self) -> None:
        """Verify _serve_neurosynth response bundles fsl_anatomy payload.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts combined response payload contains fsl_anatomy and associations.
        """
        handler: MagicMock = MagicMock()
        handler._get_cors_origin.return_value = "*"

        NiiVueBridgeHandler._serve_neurosynth(
            handler,
            x_str="-24",
            y_str="-2",
            z_str="-20",
            radius_str="6",
            top_str="5",
        )

        handler.send_response.assert_called_with(200)
        assert handler.wfile.write.called
        written_bytes: bytes = handler.wfile.write.call_args[0][0]
        data: dict[str, Any] = json.loads(written_bytes.decode("utf-8"))
        assert "associations" in data
        assert "fsl_anatomy" in data
        assert len(data["fsl_anatomy"]["hits"]) > 0
