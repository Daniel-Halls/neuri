"""Unit tests for NeuroHeaderSanitizer and PHI stripping subsystem.

Tests binary NIfTI header parsing, spatial orientation calculation, zero-token
PHI stripping of descrip/aux_file fields, and artifact model construction.
"""

import gzip
from pathlib import Path
import struct
from typing import Any

import pytest

from neuri.core.schemas import ModalityType, RemoteArtifact, SanitizedNeuroHeader
from neuri_worker.sanitizer import NeuroHeaderSanitizer


def create_synthetic_nifti_bytes(
    dim_x: int = 10,
    dim_y: int = 10,
    dim_z: int = 10,
    phi_descrip: str = "Patient=JaneDoe;MRN=12345;DOB=1980-01-01",
) -> bytes:
    """Create a synthetic 348-byte binary NIfTI header followed by voxels.

    Parameters
    ------------
    dim_x: int
        X dimension size. Defaults to 10.
    dim_y: int
        Y dimension size. Defaults to 10.
    dim_z: int
        Z dimension size. Defaults to 10.
    phi_descrip: str
        Injected PHI string in descrip field. Defaults to patient metadata.

    Returns
    --------
        bytes: bytes object
            Raw binary NIfTI file content.
    """
    buf: bytearray = bytearray(352)

    # sizeof_hdr = 348
    struct.pack_into("<i", buf, 0, 348)

    # dim: [3, dim_x, dim_y, dim_z, 1, 1, 1, 1]
    struct.pack_into(
        "<8h", buf, 40, 3, dim_x, dim_y, dim_z, 1, 1, 1, 1
    )

    # datatype = 4 (int16), bitpix = 16
    struct.pack_into("<h", buf, 70, 4)
    struct.pack_into("<h", buf, 72, 16)

    # pixdim: [1.0, 2.0, 2.0, 2.5, 0.0, 0.0, 0.0, 0.0]
    struct.pack_into(
        "<8f", buf, 76, 1.0, 2.0, 2.0, 2.5, 0.0, 0.0, 0.0, 0.0
    )

    # vox_offset = 352.0
    struct.pack_into("<f", buf, 108, 352.0)

    # descrip: up to 80 bytes with PHI
    descrip_bytes: bytes = phi_descrip.encode("utf-8")[:80].ljust(80, b"\x00")
    buf[148:228] = descrip_bytes

    # sform affine (RAS orientation)
    struct.pack_into("<4f", buf, 280, 2.0, 0.0, 0.0, -90.0)
    struct.pack_into("<4f", buf, 296, 0.0, 2.0, 0.0, -126.0)
    struct.pack_into("<4f", buf, 312, 0.0, 0.0, 2.5, -72.0)

    # magic = b'n+1\0'
    buf[344:348] = b"n+1\x00"

    # Append voxel payload (int16 zeroes)
    voxels: bytes = bytes(dim_x * dim_y * dim_z * 2)
    return bytes(buf) + voxels


def test_sanitizer_parses_nifti_and_strips_phi(tmp_path: Path) -> None:
    """Test that binary NIfTI headers are parsed while PHI is strictly stripped.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts dimensions, zooms, orientation, and PHI stripping.
    """
    raw_data: bytes = create_synthetic_nifti_bytes(
        dim_x=16,
        dim_y=16,
        dim_z=12,
        phi_descrip="PatientName=Smith^John;ScannerSerial=998877",
    )
    nii_file: Path = tmp_path / "sub-01_T1w.nii"
    nii_file.write_bytes(raw_data)

    sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()
    artifact: RemoteArtifact = sanitizer.inspect_file(
        file_path=nii_file,
        modality=ModalityType.T1W,
        host="test-node",
    )

    assert artifact.modality == ModalityType.T1W
    assert artifact.header_summary is not None
    hdr: SanitizedNeuroHeader = artifact.header_summary

    assert hdr.shape == [16, 16, 12]
    assert hdr.voxel_sizes_mm == [2.0, 2.0, 2.5]
    assert hdr.orientation == "RAS"
    assert hdr.phi_sanitized is True

    # Verify that patient name/serial nowhere exists in the model serialization
    serialized_json: str = artifact.model_dump_json()
    assert "Smith" not in serialized_json
    assert "998877" not in serialized_json
    assert "John" not in serialized_json


def test_sanitizer_handles_gzipped_nifti(tmp_path: Path) -> None:
    """Test that compressed .nii.gz files are transparently read and sanitized.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts successful decompression and header extraction.
    """
    raw_data: bytes = create_synthetic_nifti_bytes(dim_x=8, dim_y=8, dim_z=8)
    gz_file: Path = tmp_path / "sub-02_bold.nii.gz"
    with gzip.open(gz_file, "wb") as gz:
        gz.write(raw_data)

    sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()
    artifact: RemoteArtifact = sanitizer.inspect_file(
        file_path=gz_file,
        modality=ModalityType.BOLD,
        host="ada-cluster",
    )

    assert artifact.header_summary is not None
    assert artifact.header_summary.shape == [8, 8, 8]
    assert artifact.header_summary.phi_sanitized is True


def test_sanitized_header_is_under_150_tokens() -> None:
    """Verify that SanitizedNeuroHeader representation is concise (< 150 tokens).

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts word/token count bound.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        voxel_sizes_mm=[1.0, 1.0, 1.0],
        orientation="RAS",
        tr_seconds=None,
        dtype="float32",
        phi_sanitized=True,
    )
    raw_json: str = header.model_dump_json()
    # Approximate tokens as whitespace / punctuation tokens: len(raw_json) / 4
    estimated_tokens: int = len(raw_json) // 4
    assert estimated_tokens < 150, (
        f"Header exceeds token budget: {estimated_tokens} tokens"
    )
