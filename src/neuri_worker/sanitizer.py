"""Deterministic PHI Sanitizer and Header Inspector for Neuroimaging Data.

Parses binary NIfTI-1 (.nii, .nii.gz), EDF/BDF, and BIDS JSON sidecars,
stripping Protected Health Information (PHI) and producing compact,
validated SanitizedNeuroHeader and RemoteArtifact models (<150 tokens).
"""

import gzip
import hashlib
import math
from pathlib import Path
import re
import struct
from typing import Any

from neuri.core.schemas import (
    ModalityType,
    RemoteArtifact,
    SanitizedNeuroHeader,
)


class NeuroHeaderSanitizer:
    """Extracts structural metadata and strips identifying subject information.

    Parameters
    ------------
    None

    Returns
    --------
        NeuroHeaderSanitizer: NeuroHeaderSanitizer instance
            Constructed sanitizer utility.
    """

    NIFTI_HDR_SIZE: int = 348
    EDF_FIXED_HDR_SIZE: int = 256

    DATATYPE_MAP: dict[int, str] = {
        2: "uint8",
        4: "int16",
        8: "int32",
        16: "float32",
        32: "complex64",
        64: "float64",
        512: "uint16",
        768: "uint32",
    }

    FORBIDDEN_JSON_KEYS: set[str] = {
        "InstitutionName",
        "InstitutionalDepartmentName",
        "InstitutionAddress",
        "DeviceSerialNumber",
        "PatientName",
        "PatientBirthDate",
        "PatientSex",
        "PatientAge",
        "PatientID",
        "OperatorsName",
    }

    def inspect_file(
        self,
        file_path: Path,
        modality: ModalityType = ModalityType.T1W,
        host: str = "localhost",
        space: str | None = None,
    ) -> RemoteArtifact:
        """Inspect a neuroimaging or electrophysiology file and produce artifact.

        Parameters
        ------------
        file_path: Path
            Path to the local or remote target file.
        modality: ModalityType
            Neuroscience modality enumeration. Defaults to T1W.
        host: str
            Host identifier where the file resides. Defaults to 'localhost'.
        space: str | None
            Spatial stereotaxic space (e.g. 'MNI152NLin2009cAsym'). Defaults to None.

        Returns
        --------
            RemoteArtifact: RemoteArtifact instance
                Constructed remote artifact with sanitized metadata header.
        """
        path_str: str = str(file_path)
        lower_path: str = path_str.lower()
        is_nifti: bool = (
            lower_path.endswith(".nii") or lower_path.endswith(".nii.gz")
        )
        is_edf: bool = (
            lower_path.endswith(".edf") or lower_path.endswith(".bdf")
        )

        header: SanitizedNeuroHeader
        sha_hash: str
        file_size: int = file_path.stat().st_size if file_path.exists() else 0

        if is_nifti and file_path.exists():
            header, sha_hash = self._parse_nifti_header(file_path)
        elif is_edf and file_path.exists():
            header, sha_hash = self._parse_edf_header(file_path)
        else:
            header = SanitizedNeuroHeader(
                shape=[1, 1, 1],
                dtype="float32",
                phi_sanitized=True,
            )
            sha_hash = hashlib.sha256(path_str.encode("utf-8")).hexdigest()

        bids_entities: dict[str, str] = self._extract_bids_entities(file_path)
        inferred_space: str | None = space or bids_entities.get("space")
        art_id: str = f"art_{file_path.stem.split('.')[0]}_{sha_hash[:8]}"
        artifact: RemoteArtifact = RemoteArtifact(
            artifact_id=art_id,
            uri=f"{host}://{file_path.resolve()}",
            host=host,
            posix_path=str(file_path.resolve()),
            modality=modality,
            space=inferred_space,
            bids_entities=bids_entities,
            sha256_header=sha_hash,
            size_bytes=file_size,
            header_summary=header,
        )
        return artifact

    def _extract_bids_entities(self, file_path: Path) -> dict[str, str]:
        """Extract key-value BIDS entities from a file name and parent folder.

        Parameters
        ------------
        file_path: Path
            Target BIDS file path.

        Returns
        --------
            dict[str, str]: dictionary object
                Extracted BIDS entities (e.g. sub, ses, task, run, suffix).
        """
        entities: dict[str, str] = {}
        name: str = file_path.name
        for ext in (".nii.gz", ".nii", ".edf", ".bdf", ".tsv.gz", ".tsv", ".json"):
            if name.endswith(ext):
                name = name[: -len(ext)]
                break

        parts: list[str] = name.split("_")
        for part in parts:
            if "-" in part:
                k, v = part.split("-", 1)
                if k and v:
                    entities[k] = v
            elif part:
                entities["suffix"] = part

        parent_name: str = file_path.parent.name
        if parent_name in ("anat", "func", "dwi", "eeg", "meg", "ieeg", "fmap"):
            entities["datatype"] = parent_name
        return entities

    def _parse_nifti_header(
        self, file_path: Path
    ) -> tuple[SanitizedNeuroHeader, str]:
        """Parse raw 348-byte binary NIfTI-1 header and strip free-text fields.

        Zeroes out db_name (14..32), descrip (148..228), and aux_file (228..252)
        before computing the sanitized header hash.

        Parameters
        ------------
        file_path: Path
            Path to the .nii or .nii.gz file.

        Returns
        --------
            tuple[SanitizedNeuroHeader, str]: tuple object
                Pair containing validated SanitizedNeuroHeader and SHA-256 hash.
        """
        raw_bytes: bytes
        if str(file_path).endswith(".gz"):
            with gzip.open(file_path, "rb") as gz:
                raw_bytes = gz.read(self.NIFTI_HDR_SIZE)
        else:
            with open(file_path, "rb") as fh:
                raw_bytes = fh.read(self.NIFTI_HDR_SIZE)

        if len(raw_bytes) < self.NIFTI_HDR_SIZE:
            fallback_hdr: SanitizedNeuroHeader = SanitizedNeuroHeader(
                shape=[1, 1, 1],
                dtype="unknown",
                phi_sanitized=True,
            )
            return fallback_hdr, hashlib.sha256(raw_bytes).hexdigest()

        # Scrub PHI free-text byte ranges on mutable copy before hashing
        scrubbed_buf: bytearray = bytearray(raw_bytes[: self.NIFTI_HDR_SIZE])
        scrubbed_buf[14:32] = b"\x00" * 18
        scrubbed_buf[148:228] = b"\x00" * 80
        scrubbed_buf[228:252] = b"\x00" * 24
        sanitized_bytes: bytes = bytes(scrubbed_buf)

        sizeof_hdr: int = struct.unpack("<i", sanitized_bytes[0:4])[0]
        endian: str = "<"
        if sizeof_hdr != self.NIFTI_HDR_SIZE:
            sizeof_hdr = struct.unpack(">i", sanitized_bytes[0:4])[0]
            endian = ">"

        dims: tuple[int, ...] = struct.unpack(
            f"{endian}8h", sanitized_bytes[40:56]
        )
        ndim: int = max(1, min(int(dims[0]), 7))
        shape_list: list[int] = [
            max(1, int(dims[i])) for i in range(1, ndim + 1)
        ]

        datatype_code: int = int(
            struct.unpack(f"{endian}h", sanitized_bytes[70:72])[0]
        )
        dtype_str: str = self.DATATYPE_MAP.get(datatype_code, "float32")

        pixdims: tuple[float, ...] = struct.unpack(
            f"{endian}8f", sanitized_bytes[76:108]
        )
        voxel_sizes: list[float] = [
            round(abs(float(pixdims[i])) or 1.0, 4)
            for i in range(1, min(ndim + 1, 4))
        ]

        tr_val: float | None = None
        if ndim >= 4 and pixdims[4] > 0.0:
            tr_val = round(float(pixdims[4]), 4)

        qform_code: int = int(
            struct.unpack(f"{endian}h", sanitized_bytes[252:254])[0]
        )
        sform_code: int = int(
            struct.unpack(f"{endian}h", sanitized_bytes[254:256])[0]
        )

        srow_x: tuple[float, ...] = struct.unpack(
            f"{endian}4f", sanitized_bytes[280:296]
        )
        srow_y: tuple[float, ...] = struct.unpack(
            f"{endian}4f", sanitized_bytes[296:312]
        )
        srow_z: tuple[float, ...] = struct.unpack(
            f"{endian}4f", sanitized_bytes[312:328]
        )
        if sform_code == 0 and qform_code > 0:
            srow_x, srow_y, srow_z = self._qform_to_srows(
                sanitized_bytes, endian, pixdims
            )

        orientation_code: str = self._affine_to_orientation(
            srow_x, srow_y, srow_z
        )

        header_hash: str = hashlib.sha256(sanitized_bytes).hexdigest()
        sanitized: SanitizedNeuroHeader = SanitizedNeuroHeader(
            shape=shape_list,
            voxel_sizes_mm=voxel_sizes,
            orientation=orientation_code,
            tr_seconds=tr_val,
            dtype=dtype_str,
            phi_sanitized=True,
        )
        return sanitized, header_hash

    def _qform_to_srows(
        self,
        hdr_bytes: bytes,
        endian: str,
        pixdims: tuple[float, ...],
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
        """Convert NIfTI-1 quaternion parameters to 3x4 affine rows.

        Parameters
        ------------
        hdr_bytes: bytes
            Sanitized 348-byte NIfTI-1 header.
        endian: str
            Struct endianness prefix ('<' or '>').
        pixdims: tuple[float, ...]
            Unpacked pixdim array.

        Returns
        --------
            tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]: tuple
                Three 4-element affine rows (srow_x, srow_y, srow_z).
        """
        qb, qc, qd, qx, qy, qz = struct.unpack(
            f"{endian}6f", hdr_bytes[256:280]
        )
        a_sq: float = max(0.0, 1.0 - (qb * qb + qc * qc + qd * qd))
        qa: float = math.sqrt(a_sq)
        qfac: float = -1.0 if pixdims[0] < 0.0 else 1.0
        dx: float = abs(pixdims[1]) or 1.0
        dy: float = abs(pixdims[2]) or 1.0
        dz: float = (abs(pixdims[3]) or 1.0) * qfac

        r11: float = (qa * qa + qb * qb - qc * qc - qd * qd) * dx
        r12: float = 2.0 * (qb * qc - qa * qd) * dy
        r13: float = 2.0 * (qb * qd + qa * qc) * dz
        r21: float = 2.0 * (qb * qc + qa * qd) * dx
        r22: float = (qa * qa + qc * qc - qb * qb - qd * qd) * dy
        r23: float = 2.0 * (qc * qd - qa * qb) * dz
        r31: float = 2.0 * (qb * qd - qa * qc) * dx
        r32: float = 2.0 * (qc * qd + qa * qb) * dy
        r33: float = (qa * qa + qd * qd - qb * qb - qc * qc) * dz

        rows: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]] = (
            (r11, r12, r13, qx),
            (r21, r22, r23, qy),
            (r31, r32, r33, qz),
        )
        return rows

    def _parse_edf_header(
        self, file_path: Path
    ) -> tuple[SanitizedNeuroHeader, str]:
        """Parse 256-byte EDF/BDF header and strip patient/recording PHI fields.

        Zeroes out Local Patient Identification (bytes 8..88) and Local
        Recording Identification (bytes 88..168) before hashing.

        Parameters
        ------------
        file_path: Path
            Path to the .edf or .bdf file.

        Returns
        --------
            tuple[SanitizedNeuroHeader, str]: tuple object
                Pair of SanitizedNeuroHeader and SHA-256 sanitized header hash.
        """
        with open(file_path, "rb") as fh:
            fixed_hdr: bytes = fh.read(self.EDF_FIXED_HDR_SIZE)

        if len(fixed_hdr) < self.EDF_FIXED_HDR_SIZE:
            fallback: SanitizedNeuroHeader = SanitizedNeuroHeader(
                shape=[1, 1],
                dtype="int16",
                phi_sanitized=True,
            )
            return fallback, hashlib.sha256(fixed_hdr).hexdigest()

        scrubbed: bytearray = bytearray(fixed_hdr)
        scrubbed[8:88] = b" " * 80
        scrubbed[88:168] = b" " * 80

        num_records_str: str = (
            fixed_hdr[236:244].decode("ascii", errors="ignore").strip()
        )
        record_dur_str: str = (
            fixed_hdr[244:252].decode("ascii", errors="ignore").strip()
        )
        ns_str: str = (
            fixed_hdr[252:256].decode("ascii", errors="ignore").strip()
        )

        num_records: int = (
            max(1, int(num_records_str)) if num_records_str.isdigit() else 1
        )
        try:
            record_dur: float = float(record_dur_str) if record_dur_str else 1.0
        except ValueError:
            record_dur = 1.0
        n_channels: int = max(1, int(ns_str)) if ns_str.isdigit() else 1

        sfreq: float = 256.0
        samples_per_record: int = 256
        with open(file_path, "rb") as fh:
            fh.seek(self.EDF_FIXED_HDR_SIZE + (n_channels * 216))
            spr_bytes: bytes = fh.read(n_channels * 8)
            if len(spr_bytes) >= 8:
                first_spr: str = (
                    spr_bytes[:8].decode("ascii", errors="ignore").strip()
                )
                if first_spr.isdigit():
                    samples_per_record = max(1, int(first_spr))
                    if record_dur > 0.0:
                        sfreq = round(samples_per_record / record_dur, 4)

        total_samples: int = num_records * samples_per_record
        sanitized_bytes: bytes = bytes(scrubbed)
        header_hash: str = hashlib.sha256(sanitized_bytes).hexdigest()
        header: SanitizedNeuroHeader = SanitizedNeuroHeader(
            shape=[n_channels, total_samples],
            sampling_freq_hz=sfreq,
            channel_count=n_channels,
            dtype="int16",
            phi_sanitized=True,
        )
        return header, header_hash

    def _affine_to_orientation(
        self,
        srow_x: tuple[float, ...],
        srow_y: tuple[float, ...],
        srow_z: tuple[float, ...],
    ) -> str:
        """Derive 3-letter anatomical orientation code from 3x4 affine matrix.

        Parameters
        ------------
        srow_x: tuple[float, ...]
            First row of affine matrix.
        srow_y: tuple[float, ...]
            Second row of affine matrix.
        srow_z: tuple[float, ...]
            Third row of affine matrix.

        Returns
        --------
            str: string object
                3-letter anatomical orientation code (e.g. 'RAS', 'LPS').
        """
        matrix: list[list[float]] = [
            [srow_x[0], srow_x[1], srow_x[2]],
            [srow_y[0], srow_y[1], srow_y[2]],
            [srow_z[0], srow_z[1], srow_z[2]],
        ]

        orientation_letters: list[str] = []
        labels: list[tuple[str, str]] = [("R", "L"), ("A", "P"), ("S", "I")]

        for col in range(3):
            col_vals: list[float] = [matrix[row][col] for row in range(3)]
            max_row: int = 0
            max_abs: float = 0.0
            for r_idx, val in enumerate(col_vals):
                if abs(val) > max_abs:
                    max_abs = abs(val)
                    max_row = r_idx

            if max_abs == 0.0:
                orientation_letters.append(labels[col][0])
            else:
                sign: float = matrix[max_row][col]
                letter: str = (
                    labels[max_row][0] if sign > 0 else labels[max_row][1]
                )
                orientation_letters.append(letter)

        res_code: str = "".join(orientation_letters)
        return res_code

    def sanitize_sidecar_json(
        self, sidecar_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Strip forbidden subject or institutional keys from BIDS JSON sidecar.

        Parameters
        ------------
        sidecar_data: dict[str, Any]
            Raw parsed BIDS JSON dictionary.

        Returns
        --------
            dict[str, Any]: dictionary object
                Sanitized dictionary with identifying keys deleted.
        """
        cleaned: dict[str, Any] = {}
        for key, val in sidecar_data.items():
            if key not in self.FORBIDDEN_JSON_KEYS:
                cleaned[key] = val
        return cleaned


__all__: list[str] = [
    "NeuroHeaderSanitizer",
]
