"""Unit tests for Neurosynth coordinate decoding and 'What's this?' lookup.

Tests association data structures, API client responses, caching mechanisms,
landmark fallbacks, and the NiiVue bridge endpoint.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from neuri.viewer.neurosynth import (
    NeurosynthAssociation,
    NeurosynthClient,
    NeurosynthResult,
    query_neurosynth_coordinates,
)
from neuri.viewer.niivue_bridge import NiiVueBridgeHandler


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Provide a temporary cache directory for Neurosynth testing.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary path fixture.

    Returns
    --------
        Path: Path object
            Dedicated temporary cache folder.
    """
    cache_path: Path = tmp_path / "neurosynth_cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


class TestNeurosynthDataStructures:
    """Tests for NeurosynthAssociation and NeurosynthResult dataclasses."""

    def test_association_to_dict(self) -> None:
        """Verify serialization of a single association item.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts fields match serialized dictionary.
        """
        assoc: NeurosynthAssociation = NeurosynthAssociation(
            term="amygdala",
            z_score=15.4,
            posterior_prob=0.88,
            functional_conn=0.45,
            meta_analytic=12.2,
        )
        data: dict[str, Any] = assoc.to_dict()
        assert data["term"] == "amygdala"
        assert data["z_score"] == 15.4
        assert data["posterior_prob"] == 0.88

    def test_result_markdown_formatting(self) -> None:
        """Verify Markdown table generation from query result.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts Markdown headers and rows are present.
        """
        assoc: NeurosynthAssociation = NeurosynthAssociation(
            term="visual cortex",
            z_score=9.8,
            posterior_prob=0.75,
            functional_conn=0.2,
            meta_analytic=8.1,
        )
        res: NeurosynthResult = NeurosynthResult(
            x=0.0,
            y=-85.0,
            z=0.0,
            radius_mm=6,
            associations=(assoc,),
            source="live_api",
        )
        md: str = res.format_markdown()
        assert "What's This?" in md
        assert "visual cortex" in md
        assert "9.80" in md
        assert "live_api" in md


class TestNeurosynthClient:
    """Tests for NeurosynthClient querying, caching, and fallback logic."""

    def test_query_parses_neurosynth_api_format(
        self, temp_cache_dir: Path
    ) -> None:
        """Verify parsing of Neurosynth compare table JSON data format.

        Parameters
        ------------
        temp_cache_dir: Path
            Isolated cache directory fixture.

        Returns
        --------
            None: NoneType object
                Asserts parsed associations are properly sorted by z-score.
        """
        mock_payload: dict[str, Any] = {
            "data": [
                ["fusiform", "7.12", "0.65", "0.1", "5.2"],
                ["face", "12.45", "0.82", "0.3", "10.1"],
                ["invalid_entry", "-", "0.0", "0.0", "0.0"],
            ]
        }
        mock_response: MagicMock = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            client: NeurosynthClient = NeurosynthClient(
                cache_dir=temp_cache_dir, timeout_seconds=1.0
            )
            res: NeurosynthResult = client.query(
                x=40.0, y=-50.0, z=-18.0, radius=6, top_n=5
            )

        assert res.x == 40.0
        assert res.y == -50.0
        assert res.z == -18.0
        assert res.source == "live_api"
        # Non-numeric "-" row is skipped, leaving 2 valid associations
        assert len(res.associations) == 2
        # First association should be highest z-score (face: 12.45)
        assert res.associations[0].term == "face"
        assert res.associations[0].z_score == 12.45
        assert res.associations[1].term == "fusiform"

    def test_disk_caching_avoids_repeated_network(
        self, temp_cache_dir: Path
    ) -> None:
        """Verify responses are written to disk and reused without network calls.

        Parameters
        ------------
        temp_cache_dir: Path
            Isolated cache directory fixture.

        Returns
        --------
            None: NoneType object
                Asserts second query retrieves from disk cache.
        """
        mock_payload: dict[str, Any] = {
            "data": [["motor", "8.5", "0.7", "0.2", "6.1"]]
        }
        mock_response: MagicMock = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_url:
            client: NeurosynthClient = NeurosynthClient(
                cache_dir=temp_cache_dir, timeout_seconds=1.0
            )
            res1: NeurosynthResult = client.query(
                x=0.0, y=-20.0, z=55.0, radius=6, top_n=5
            )
            assert res1.source == "live_api"
            assert mock_url.call_count == 1

            # Second call with same coordinates should hit disk cache
            res2: NeurosynthResult = client.query(
                x=0.0, y=-20.0, z=55.0, radius=6, top_n=5
            )
            assert res2.source == "cached"
            assert mock_url.call_count == 1
            assert len(res2.associations) == 1
            assert res2.associations[0].term == "motor"

    def test_offline_fallback_on_network_error(
        self, temp_cache_dir: Path
    ) -> None:
        """Verify fallback to canonical landmark when network is unavailable.

        Parameters
        ------------
        temp_cache_dir: Path
            Isolated cache directory fixture.

        Returns
        --------
            None: NoneType object
                Asserts landmark fallback is used with distance calculation.
        """
        err: urllib.error.URLError = urllib.error.URLError("Network unreachable")
        with patch("urllib.request.urlopen", side_effect=err):
            client: NeurosynthClient = NeurosynthClient(
                cache_dir=temp_cache_dir, timeout_seconds=0.1
            )
            # Coordinates near Left Amygdala (-24, -2, -20)
            res: NeurosynthResult = client.query(
                x=-23.0, y=-3.0, z=-19.0, radius=6, top_n=5
            )

        assert "offline" in res.source or "landmark" in res.source
        assert len(res.associations) > 0
        assert any("amygdala" in a.term.lower() for a in res.associations)

    def test_query_neurosynth_coordinates_helper(
        self, temp_cache_dir: Path
    ) -> None:
        """Verify top-level module function query_neurosynth_coordinates.

        Parameters
        ------------
        temp_cache_dir: Path
            Isolated cache directory fixture.

        Returns
        --------
            None: NoneType object
                Asserts result is returned with expected attributes.
        """
        mock_payload: dict[str, Any] = {
            "data": [["language", "6.2", "0.6", "0.1", "4.0"]]
        }
        mock_response: MagicMock = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            res: NeurosynthResult = query_neurosynth_coordinates(
                x=-50.0, y=20.0, z=15.0, radius=6, top_n=5
            )

        assert isinstance(res, NeurosynthResult)
        assert res.x == -50.0
        assert len(res.associations) == 1
        assert res.associations[0].term == "language"


class TestNiiVueBridgeNeurosynthEndpoint:
    """Tests for the HTTP endpoint on NiiVueBridgeHandler."""

    def test_serve_neurosynth_success(self) -> None:
        """Verify NiiVueBridgeHandler._serve_neurosynth sends JSON response.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts handler sends 200 and serialized Neurosynth payload.
        """
        handler: MagicMock = MagicMock()
        handler._get_cors_origin.return_value = "*"

        fake_result: NeurosynthResult = NeurosynthResult(
            x=-24.0,
            y=-2.0,
            z=-20.0,
            radius_mm=6,
            associations=(
                NeurosynthAssociation(
                    term="amygdala",
                    z_score=14.2,
                    posterior_prob=0.85,
                    functional_conn=0.4,
                    meta_analytic=11.0,
                ),
            ),
            source="cached",
        )

        with patch(
            "neuri.viewer.neurosynth.query_neurosynth_coordinates",
            return_value=fake_result,
        ):
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
        assert data["x"] == -24.0
        assert data["y"] == -2.0
        assert data["z"] == -20.0
        assert len(data["associations"]) == 1
        assert data["associations"][0]["term"] == "amygdala"

    def test_serve_neurosynth_invalid_parameters_error(self) -> None:
        """Verify NiiVueBridgeHandler._serve_neurosynth returns 400 on bad input.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts handler calls send_error with 400 status.
        """
        handler: MagicMock = MagicMock()
        NiiVueBridgeHandler._serve_neurosynth(
            handler,
            x_str="not_a_float",
            y_str="-2",
            z_str="-20",
        )
        handler.send_error.assert_called_with(
            400, "Invalid coordinate, radius, or top parameter."
        )
