"""Headless QA snapshot and registration overlay generator for Neuri.

Generates deterministic orthographic slice PNG snapshots and registration
contour overlays directly on headless compute nodes with zero external GUI
dependencies, maintaining file sizes under 200 KB for rapid hub-spoke sync.
"""

import gzip
from pathlib import Path
import struct
from typing import Any
import zlib

from neuri_worker.sanitizer import NeuroHeaderSanitizer, SanitizedNeuroHeader


class PurePNGWriter:
    """Zero-dependency pure-Python PNG encoder for headless diagnostic renders.

    Parameters
    ------------
    None

    Returns
    --------
        PurePNGWriter: PurePNGWriter instance
            Constructed PNG writer.
    """

    @staticmethod
    def _create_chunk(tag: bytes, data: bytes) -> bytes:
        """Construct a single PNG chunk with length, tag, data, and CRC32.

        Parameters
        ------------
        tag: bytes
            4-byte chunk type tag (e.g. b'IHDR', b'IDAT', b'IEND').
        data: bytes
            Chunk payload bytes.

        Returns
        --------
            bytes: bytes object
                Formatted PNG chunk block.
        """
        length: bytes = struct.pack(">I", len(data))
        crc: int = zlib.crc32(tag + data) & 0xFFFFFFFF
        crc_bytes: bytes = struct.pack(">I", crc)
        return length + tag + data + crc_bytes

    def write_grayscale_png(
        self, width: int, height: int, pixels: bytes, output_path: Path
    ) -> Path:
        """Encode 8-bit grayscale pixel stream into a valid PNG file.

        Parameters
        ------------
        width: int
            Image width in pixels.
        height: int
            Image height in pixels.
        pixels: bytes
            Raw byte sequence of length (width * height), values 0-255.
        output_path: Path
            Target destination path for PNG file.

        Returns
        --------
            Path: Path object
                Path to the written PNG file.
        """
        signature: bytes = b"\x89PNG\r\n\x1a\n"

        # IHDR: width, height, bit depth 8, color type 0 (grayscale)
        ihdr_data: bytes = struct.pack(
            ">IIBBBBB", width, height, 8, 0, 0, 0, 0
        )
        ihdr_chunk: bytes = self._create_chunk(b"IHDR", ihdr_data)

        # IDAT: Scanlines prepended with filter type 0 (None)
        raw_scanlines: bytearray = bytearray()
        for y in range(height):
            raw_scanlines.append(0)
            start_idx: int = y * width
            raw_scanlines.extend(pixels[start_idx : start_idx + width])

        compressed_data: bytes = zlib.compress(bytes(raw_scanlines), level=6)
        idat_chunk: bytes = self._create_chunk(b"IDAT", compressed_data)
        iend_chunk: bytes = self._create_chunk(b"IEND", b"")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            f.write(signature + ihdr_chunk + idat_chunk + iend_chunk)

        return output_path

    def write_rgb_png(
        self, width: int, height: int, rgb_pixels: bytes, output_path: Path
    ) -> Path:
        """Encode 24-bit RGB pixel stream into a valid PNG file.

        Parameters
        ------------
        width: int
            Image width in pixels.
        height: int
            Image height in pixels.
        pixels: bytes
            Raw byte sequence of length (width * height * 3).
        output_path: Path
            Target destination path for PNG file.

        Returns
        --------
            Path: Path object
                Path to the written PNG file.
        """
        signature: bytes = b"\x89PNG\r\n\x1a\n"

        # IHDR: width, height, bit depth 8, color type 2 (RGB)
        ihdr_data: bytes = struct.pack(
            ">IIBBBBB", width, height, 8, 2, 0, 0, 0
        )
        ihdr_chunk: bytes = self._create_chunk(b"IHDR", ihdr_data)

        raw_scanlines: bytearray = bytearray()
        row_stride: int = width * 3
        for y in range(height):
            raw_scanlines.append(0)
            start_idx: int = y * row_stride
            raw_scanlines.extend(rgb_pixels[start_idx : start_idx + row_stride])

        compressed_data: bytes = zlib.compress(bytes(raw_scanlines), level=6)
        idat_chunk: bytes = self._create_chunk(b"IDAT", compressed_data)
        iend_chunk: bytes = self._create_chunk(b"IEND", b"")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            f.write(signature + ihdr_chunk + idat_chunk + iend_chunk)

        return output_path


class HeadlessQAGenerator:
    """Generates deterministic QA slice montages and registration overlays.

    Parameters
    ------------
    output_dir: Path | str | None
        Directory where generated QA snapshots will be saved. Defaults to
        current working directory.

    Returns
    --------
        HeadlessQAGenerator: HeadlessQAGenerator instance
            Constructed QA generator instance.
    """

    def __init__(self, output_dir: Path | str | None = None) -> None:
        """Initialize generator with destination output directory.

        Parameters
        ------------
        output_dir: Path | str | None
            Output directory path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes generator state.
        """
        self._output_dir: Path = (
            Path(output_dir) if output_dir is not None else Path.cwd()
        )
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._png_writer: PurePNGWriter = PurePNGWriter()
        self._sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()

    def _read_raw_voxels(
        self, nifti_path: Path
    ) -> tuple[tuple[int, int, int], list[int]]:
        """Read 3D volume dimensions and raw scalar voxel array.

        Parameters
        ------------
        nifti_path: Path
            Path to .nii or .nii.gz file.

        Returns
        --------
            tuple[tuple[int, int, int], list[int]]: tuple object
                Tuple of ((dim_x, dim_y, dim_z), voxel_intensities).
        """
        artifact: RemoteArtifact = self._sanitizer.inspect_file(nifti_path)
        meta: SanitizedNeuroHeader | None = artifact.header_summary
        shape: list[int] = (
            meta.shape if meta and meta.shape else [10, 10, 10]
        )
        dim_x: int = max(1, shape[0])
        dim_y: int = max(1, shape[1] if len(shape) > 1 else 1)
        dim_z: int = max(1, shape[2] if len(shape) > 2 else 1)
        total_voxels: int = dim_x * dim_y * dim_z

        is_gzipped: bool = nifti_path.name.lower().endswith(".gz")
        if is_gzipped:
            with gzip.open(nifti_path, "rb") as gz_f:
                raw_bytes: bytes = gz_f.read()
        else:
            with nifti_path.open("rb") as raw_f:
                raw_bytes = raw_f.read()

        # NIfTI-1 header is 348 bytes; data offset typically 352
        vox_offset: int = 352
        if len(raw_bytes) > 108:
            custom_offset: int = int(
                struct.unpack("<f", raw_bytes[108:112])[0]
            )
            if custom_offset >= 348 and custom_offset < len(raw_bytes):
                vox_offset = custom_offset

        data_payload: bytes = raw_bytes[vox_offset:]

        # Unpack as signed 16-bit integers or 8-bit unsigned
        bytes_needed_short: int = total_voxels * 2
        if len(data_payload) >= bytes_needed_short:
            fmt: str = f"<{total_voxels}h"
            voxels: list[int] = list(
                struct.unpack(fmt, data_payload[:bytes_needed_short])
            )
        else:
            voxels = [int(b) for b in data_payload[:total_voxels]]
            if len(voxels) < total_voxels:
                voxels.extend([0] * (total_voxels - len(voxels)))

        return ((dim_x, dim_y, dim_z), voxels)

    def _normalize_slice(
        self, slice_data: list[int], width: int, height: int
    ) -> bytes:
        """Scale slice intensities to 0-255 uint8 range.

        Parameters
        ------------
        slice_data: list[int]
            Raw integer slice intensities.
        width: int
            Slice width in pixels.
        height: int
            Slice height in pixels.

        Returns
        --------
            bytes: bytes object
                Normalized uint8 byte stream.
        """
        if not slice_data:
            return bytes([0] * (width * height))

        min_val: int = min(slice_data)
        max_val: int = max(slice_data)
        span: int = max_val - min_val

        out: bytearray = bytearray()
        if span == 0:
            out.extend([0] * len(slice_data))
        else:
            for val in slice_data:
                normalized: int = int(((val - min_val) / span) * 255.0)
                clamped: int = max(0, min(255, normalized))
                out.append(clamped)

        return bytes(out)

    def generate_orthographic_snapshot(
        self,
        nifti_path: Path | str,
        output_name: str | None = None,
    ) -> dict[str, Any]:
        """Generate a 3-panel orthographic snapshot (axial, coronal, sagittal).

        Parameters
        ------------
        nifti_path: Path | str
            Target NIfTI volume path.
        output_name: str | None
            Output PNG filename override. Defaults to auto-generated name.

        Returns
        --------
            dict[str, Any]: dictionary object
                Snapshot result dictionary with file path, dimensions, and size.
        """
        src_path: Path = Path(nifti_path)
        (dim_x, dim_y, dim_z), voxels = self._read_raw_voxels(src_path)

        mid_x: int = dim_x // 2
        mid_y: int = dim_y // 2
        mid_z: int = dim_z // 2

        # 1. Axial slice (dim_x * dim_y at mid_z)
        axial_slice: list[int] = []
        for y in range(dim_y):
            for x in range(dim_x):
                idx = x + y * dim_x + mid_z * (dim_x * dim_y)
                axial_slice.append(voxels[idx] if idx < len(voxels) else 0)

        # 2. Coronal slice (dim_x * dim_z at mid_y)
        coronal_slice: list[int] = []
        for z in range(dim_z):
            for x in range(dim_x):
                idx = x + mid_y * dim_x + z * (dim_x * dim_y)
                coronal_slice.append(voxels[idx] if idx < len(voxels) else 0)

        # 3. Sagittal slice (dim_y * dim_z at mid_x)
        sagittal_slice: list[int] = []
        for z in range(dim_z):
            for y in range(dim_y):
                idx = mid_x + y * dim_x + z * (dim_x * dim_y)
                sagittal_slice.append(voxels[idx] if idx < len(voxels) else 0)

        # Combine into mosaic: max height across panels
        panel_h: int = max(dim_y, dim_z)
        mosaic_w: int = dim_x + dim_x + dim_y
        mosaic_h: int = panel_h

        mosaic_pixels: bytearray = bytearray(mosaic_w * mosaic_h)

        norm_axial = self._normalize_slice(axial_slice, dim_x, dim_y)
        norm_coronal = self._normalize_slice(coronal_slice, dim_x, dim_z)
        norm_sagittal = self._normalize_slice(sagittal_slice, dim_y, dim_z)

        # Blit axial into mosaic at x=0
        for y in range(dim_y):
            row_start = y * mosaic_w
            mosaic_pixels[row_start : row_start + dim_x] = norm_axial[
                y * dim_x : (y + 1) * dim_x
            ]

        # Blit coronal into mosaic at x=dim_x
        for z in range(dim_z):
            row_start = z * mosaic_w + dim_x
            mosaic_pixels[row_start : row_start + dim_x] = norm_coronal[
                z * dim_x : (z + 1) * dim_x
            ]

        # Blit sagittal into mosaic at x=(dim_x + dim_x)
        for z in range(dim_z):
            row_start = z * mosaic_w + (dim_x * 2)
            mosaic_pixels[row_start : row_start + dim_y] = norm_sagittal[
                z * dim_y : (z + 1) * dim_y
            ]

        # Save output PNG
        out_filename: str = (
            output_name
            if output_name is not None
            else f"{src_path.stem}_qa_ortho.png"
        )
        out_dest: Path = self._output_dir / out_filename
        self._png_writer.write_grayscale_png(
            mosaic_w, mosaic_h, bytes(mosaic_pixels), out_dest
        )

        file_size: int = out_dest.stat().st_size
        return {
            "snapshot_path": str(out_dest),
            "width": mosaic_w,
            "height": mosaic_h,
            "file_size_bytes": file_size,
            "dimensions": (dim_x, dim_y, dim_z),
            "slice_indices": (mid_x, mid_y, mid_z),
            "quality_status": "OK" if file_size < 200000 else "WARNING",
        }

    def generate_registration_overlay(
        self,
        fixed_path: Path | str,
        moving_path: Path | str,
        output_name: str | None = None,
    ) -> dict[str, Any]:
        """Generate contour overlay of fixed brain edges over moving volume.

        Parameters
        ------------
        fixed_path: Path | str
            Path to reference/target NIfTI volume.
        moving_path: Path | str
            Path to moving/registered source NIfTI volume.
        output_name: str | None
            Output PNG filename override. Defaults to auto-generated name.

        Returns
        --------
            dict[str, Any]: dictionary object
                Overlay result dictionary with output path and file size.
        """
        ref_path: Path = Path(fixed_path)
        mov_path: Path = Path(moving_path)

        (fx_x, fx_y, fx_z), fx_voxels = self._read_raw_voxels(ref_path)
        (mv_x, mv_y, mv_z), mv_voxels = self._read_raw_voxels(mov_path)

        w: int = min(fx_x, mv_x)
        h: int = min(fx_y, mv_y)
        mid_z: int = min(fx_z, mv_z) // 2

        # Extract axial slices
        fx_slice: list[int] = []
        mv_slice: list[int] = []
        for y in range(h):
            for x in range(w):
                f_idx = x + y * fx_x + mid_z * (fx_x * fx_y)
                m_idx = x + y * mv_x + mid_z * (mv_x * mv_y)
                fx_slice.append(fx_voxels[f_idx] if f_idx < len(fx_voxels) else 0)
                mv_slice.append(mv_voxels[m_idx] if m_idx < len(mv_voxels) else 0)

        norm_mv: bytes = self._normalize_slice(mv_slice, w, h)
        norm_fx: bytes = self._normalize_slice(fx_slice, w, h)

        # Simple edge detection on fixed slice (gradient magnitude threshold)
        rgb_pixels: bytearray = bytearray()
        for y in range(h):
            for x in range(w):
                idx = y * w + x
                base_lum: int = norm_mv[idx]

                # Check gradient
                is_edge: bool = False
                if x > 0 and y > 0 and x < w - 1 and y < h - 1:
                    gx: int = abs(norm_fx[idx + 1] - norm_fx[idx - 1])
                    gy: int = abs(norm_fx[idx + w] - norm_fx[idx - w])
                    if gx + gy > 80:
                        is_edge = True

                if is_edge:
                    rgb_pixels.extend([255, 30, 30])  # Bright red contour
                else:
                    rgb_pixels.extend([base_lum, base_lum, base_lum])

        out_filename: str = (
            output_name
            if output_name is not None
            else f"{mov_path.stem}_reg_overlay.png"
        )
        out_dest: Path = self._output_dir / out_filename
        self._png_writer.write_rgb_png(w, h, bytes(rgb_pixels), out_dest)

        file_size: int = out_dest.stat().st_size
        return {
            "snapshot_path": str(out_dest),
            "width": w,
            "height": h,
            "file_size_bytes": file_size,
            "fixed_volume": str(ref_path),
            "moving_volume": str(mov_path),
            "quality_status": "OK" if file_size < 200000 else "WARNING",
        }
