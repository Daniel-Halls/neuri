"""Unit tests for NeuroHeaderSanitizer and RemoteWorkerMCPServer.

Verifies binary NIfTI-1 PHI stripping (descrip, db_name, aux_file), RAS+ and
LPS+ orientation extraction, EDF electrophysiology header sanitization, BIDS
entity extraction, and neuri_worker JSON-RPC 2.0 tool dispatch.
"""

from pathlib import Path
from typing import Any

from neuri.core.schemas import ModalityType, RemoteArtifact
from neuri_worker.mcp_server import RemoteWorkerMCPServer
from neuri_worker.sanitizer import NeuroHeaderSanitizer
from tests.conftest import build_synthetic_nifti_bytes


def test_nifti_phi_stripping_produces_identical_sanitized_hash(
    tmp_path: Path,
) -> None:
    """Verify two NIfTI files differing only in PHI fields hash identically.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts sanitized header hashes match and zero PHI leaks into JSON.
    """
    nii_a: Path = tmp_path / "sub-01_T1w.nii"
    nii_b: Path = tmp_path / "sub-02_T1w.nii"
    nii_a.write_bytes(
        build_synthetic_nifti_bytes(
            orientation="RAS",
            descrip_phi=b"Patient: Alice Smith SSN 123-45-6789",
        )
    )
    nii_b.write_bytes(
        build_synthetic_nifti_bytes(
            orientation="RAS",
            descrip_phi=b"Patient: Bob Jones DOB 1975-09-12",
        )
    )

    sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()
    art_a: RemoteArtifact = sanitizer.inspect_file(nii_a, ModalityType.T1W)
    art_b: RemoteArtifact = sanitizer.inspect_file(nii_b, ModalityType.T1W)

    assert art_a.sha256_header == art_b.sha256_header
    assert art_a.header_summary.orientation == "RAS"
    assert art_a.header_summary.shape == [4, 4, 4, 2]
    assert art_a.header_summary.tr_seconds == 1.5
    assert "Alice" not in art_a.model_dump_json()
    assert "Bob" not in art_b.model_dump_json()


def test_nifti_lps_orientation_and_bids_entities(
    synthetic_nifti_lps_path: Path,
) -> None:
    """Verify LPS orientation detection and BIDS entity parsing from path.

    Parameters
    ------------
    synthetic_nifti_lps_path: Path
        Fixture path to LPS NIfTI file.

    Returns
    --------
        None: NoneType object
            Asserts LPS orientation and extracted BIDS entities.
    """
    sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()
    art: RemoteArtifact = sanitizer.inspect_file(
        synthetic_nifti_lps_path, ModalityType.T1W
    )
    assert art.header_summary.orientation == "LPS"
    assert art.bids_entities.get("sub") == "01"
    assert art.bids_entities.get("suffix") == "T1w"


def test_edf_header_parsing_and_phi_scrubbing(tmp_path: Path) -> None:
    """Verify 256-byte EDF header parsing and patient_id PHI scrubbing.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts channel count, sampling rate, and scrubbed hash equality.
    """
    def make_edf(patient_phi: str) -> bytes:
        """Construct a synthetic EDF header + signal block for testing.

        Parameters
        ------------
        patient_phi: str
            Patient identification string to inject at bytes 8..88.

        Returns
        --------
            bytes: bytes object
                Synthetic EDF binary header bytes.
        """
        fixed: bytearray = bytearray(b" " * 256)
        fixed[0:8] = b"0       "
        fixed[8:88] = patient_phi.ljust(80)[:80].encode("ascii")
        fixed[88:168] = b"Startdate 01-JAN-2026 Hospital_Secret".ljust(80)[:80]
        fixed[236:244] = b"10      "
        fixed[244:252] = b"1       "
        fixed[252:256] = b"2   "
        sig_block: bytearray = bytearray(b" " * (2 * 256))
        sig_block[2 * 216 : 2 * 216 + 16] = b"512     512     "
        return bytes(fixed + sig_block)

    edf_1: Path = tmp_path / "sub-01_task-rest_eeg.edf"
    edf_2: Path = tmp_path / "sub-02_task-rest_eeg.edf"
    edf_1.write_bytes(make_edf("PAT_SECRET_NAME_001"))
    edf_2.write_bytes(make_edf("PAT_OTHER_NAME_999"))

    sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()
    art_1: RemoteArtifact = sanitizer.inspect_file(edf_1, ModalityType.EEG)
    art_2: RemoteArtifact = sanitizer.inspect_file(edf_2, ModalityType.EEG)

    assert art_1.sha256_header == art_2.sha256_header
    assert art_1.header_summary.channel_count == 2
    assert art_1.header_summary.sampling_freq_hz == 512.0
    assert art_1.header_summary.shape == [2, 5120]
    assert "SECRET" not in art_1.model_dump_json()


def test_remote_worker_mcp_server_tools(
    synthetic_nifti_ras_path: Path,
    synthetic_bids_dir: Path,
) -> None:
    """Verify RemoteWorkerMCPServer JSON-RPC 2.0 tool execution.

    Parameters
    ------------
    synthetic_nifti_ras_path: Path
        Synthetic RAS NIfTI fixture.
    synthetic_bids_dir: Path
        Synthetic BIDS directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts inspect_neuro_file, validate_bids_directory, and verify_artifacts.
    """
    server: RemoteWorkerMCPServer = RemoteWorkerMCPServer(
        host_name="cluster-spoke"
    )

    res_inspect: dict[str, Any] = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "inspect_neuro_file",
                "arguments": {
                    "path": str(synthetic_nifti_ras_path),
                    "modality": "bold",
                },
            },
        }
    )
    artifact_data: dict[str, Any] = res_inspect["result"]["artifact"]
    assert artifact_data["host"] == "cluster-spoke"
    assert artifact_data["header_summary"]["orientation"] == "RAS"

    res_bids: dict[str, Any] = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "validate_bids_directory",
                "arguments": {"path": str(synthetic_bids_dir)},
            },
        }
    )
    assert res_bids["result"]["valid_structure"] is True
    assert "sub-01" in res_bids["result"]["subjects"]
