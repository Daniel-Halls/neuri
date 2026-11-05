"""One-time build utility to extract FSL atlases into a standalone SQLite database.

Parses XML definitions and NIfTI volumes from FSL data directory and compiles
a compact, zero-dependency sparse database (fsl_atlases.db) for Neuri.
"""

import argparse
import gzip
import os
from pathlib import Path
import sqlite3
import struct
import sys
from typing import Any
import xml.etree.ElementTree as ET


class FSLAtlasDatabaseBuilder:
    """Builder class extracting FSL atlas volumes into a sparse SQLite database.

    Parameters
    ------------
    fsl_atlases_dir: Path
        Path to FSL data/atlases directory.
    output_db_path: Path
        Destination path for generated SQLite database.

    Returns
    --------
        FSLAtlasDatabaseBuilder: FSLAtlasDatabaseBuilder instance
            Constructed builder instance.
    """

    MNI_DIM1: int = 91
    MNI_DIM2: int = 109
    MNI_DIM3: int = 91

    EXCLUDED_ATLAS_PREFIXES: tuple[str, ...] = (
        "XTRACT_MAC",
        "XTRACT_NEO",
    )

    def __init__(
        self,
        fsl_atlases_dir: Path,
        output_db_path: Path,
    ) -> None:
        """Initialize builder paths and storage structures.

        Parameters
        ------------
        fsl_atlases_dir: Path
            Directory containing FSL atlas XML files and NIfTI folders.
        output_db_path: Path
            Filepath for output SQLite database.

        Returns
        --------
            None: NoneType object
                Initializes builder state.
        """
        self._fsl_dir: Path = fsl_atlases_dir.resolve()
        self._output_db_path: Path = output_db_path.resolve()
        self._voxel_hits: dict[int, list[tuple[int, int, int]]] = {}

    def _voxel_coords_to_id(self, i: int, j: int, k: int) -> int:
        """Convert 2mm grid coordinates (i, j, k) to a single integer row ID.

        Parameters
        ------------
        i: int
            Grid X index (0..90).
        j: int
            Grid Y index (0..108).
        k: int
            Grid Z index (0..90).

        Returns
        --------
            int: integer object
                Linear 1D voxel index.
        """
        voxel_id: int = i + self.MNI_DIM1 * j + (self.MNI_DIM1 * self.MNI_DIM2) * k
        return voxel_id

    def _convert_label_voxel_to_mni(
        self,
        vx: float,
        vy: float,
        vz: float,
        scale: float = 2.0,
    ) -> tuple[float, float, float]:
        """Convert native XML label voxel center of gravity to MNI millimeters.

        Parameters
        ------------
        vx: float
            Voxel X coordinate from XML attribute.
        vy: float
            Voxel Y coordinate from XML attribute.
        vz: float
            Voxel Z coordinate from XML attribute.
        scale: float
            Voxel resolution in millimeters. Defaults to 2.0.

        Returns
        --------
            tuple[float, float, float]: tuple of 3 floats
                MNI (x, y, z) coordinates in millimeters.
        """
        mni_x: float = round(90.0 - scale * vx, 1)
        mni_y: float = round(-126.0 + scale * vy, 1)
        mni_z: float = round(-72.0 + scale * vz, 1)
        coords: tuple[float, float, float] = (mni_x, mni_y, mni_z)
        return coords

    def _parse_xml_metadata(
        self, xml_path: Path
    ) -> dict[str, Any]:
        """Extract atlas metadata, image paths, and label dictionary from XML.

        Parameters
        ------------
        xml_path: Path
            Path to atlas XML file.

        Returns
        --------
            dict[str, Any]: dictionary object
                Extracted metadata dictionary.
        """
        tree: ET.ElementTree = ET.parse(xml_path)
        root: ET.Element = tree.getroot()
        header: ET.Element | None = root.find("header")

        raw_name: str = (
            header.findtext("name")
            if header is not None and header.findtext("name")
            else xml_path.stem
        )
        short_name: str = (
            header.findtext("shortname")
            if header is not None and header.findtext("shortname")
            else xml_path.stem
        )
        atlas_type: str = (
            header.findtext("type")
            if header is not None and header.findtext("type")
            else "Probabilistic"
        )

        chosen_img_rel: str = ""
        if header is not None:
            images = header.findall("images")
            for img in images:
                f = img.findtext("imagefile")
                if f and "2mm" in f:
                    chosen_img_rel = f
                    break
            if not chosen_img_rel and images:
                first_f = images[0].findtext("imagefile")
                if first_f:
                    chosen_img_rel = first_f

        # Determine scale based on chosen image path
        scale_mm: float = 2.0
        if "0.5mm" in chosen_img_rel or "p5mm" in chosen_img_rel:
            scale_mm = 0.5
        elif "1mm" in chosen_img_rel:
            scale_mm = 1.0

        labels_data: list[tuple[int, str, float, float, float]] = []
        data_elem: ET.Element | None = root.find("data")
        if data_elem is not None:
            for lbl in data_elem.findall("label"):
                idx_str: str = lbl.get("index", "-1")
                try:
                    idx_val: int = int(idx_str)
                except ValueError:
                    continue
                label_text: str = (lbl.text or "").strip()
                vx = float(lbl.get("x", "0"))
                vy = float(lbl.get("y", "0"))
                vz = float(lbl.get("z", "0"))
                mni_x, mni_y, mni_z = self._convert_label_voxel_to_mni(
                    vx, vy, vz, scale=scale_mm
                )
                labels_data.append((idx_val, label_text, mni_x, mni_y, mni_z))

        meta: dict[str, Any] = {
            "key": xml_path.stem,
            "short_name": short_name,
            "name": raw_name,
            "atlas_type": atlas_type,
            "image_rel": chosen_img_rel,
            "labels": labels_data,
        }
        return meta

    def _ingest_2mm_probabilistic(
        self, atlas_id: int, raw_bytes: bytes, num_vols: int
    ) -> int:
        """Ingest standard 2mm probabilistic atlas (uint8 or float32).

        Parameters
        ------------
        atlas_id: int
            Integer ID of the atlas.
        raw_bytes: bytes
            Raw uncompressed NIfTI image bytes.
        num_vols: int
            Number of probability volumes (regions).

        Returns
        --------
            int: integer object
                Total number of recorded voxel hits.
        """
        vol_size: int = self.MNI_DIM1 * self.MNI_DIM2 * self.MNI_DIM3
        is_float: bool = len(raw_bytes) >= vol_size * num_vols * 4
        recorded: int = 0

        for t in range(num_vols):
            if is_float:
                v_slice = raw_bytes[t * vol_size * 4 : (t + 1) * vol_size * 4]
            else:
                v_slice = raw_bytes[t * vol_size : (t + 1) * vol_size]

            for k in range(self.MNI_DIM3):
                for j in range(self.MNI_DIM2):
                    for i in range(self.MNI_DIM1):
                        v_idx: int = i + self.MNI_DIM1 * j + (
                            self.MNI_DIM1 * self.MNI_DIM2
                        ) * k
                        if is_float:
                            val_f = struct.unpack_from("<f", v_slice, v_idx * 4)[0]
                            prob: int = int(round(val_f))
                        else:
                            prob = v_slice[v_idx]

                        if prob >= 5:
                            prob_clamped: int = min(100, max(1, prob))
                            voxel_id: int = self._voxel_coords_to_id(i, j, k)
                            if voxel_id not in self._voxel_hits:
                                self._voxel_hits[voxel_id] = []
                            self._voxel_hits[voxel_id].append(
                                (atlas_id, prob_clamped, t)
                            )
                            recorded += 1
        return recorded

    def _ingest_2mm_discrete_labels(
        self, atlas_id: int, raw_bytes: bytes, dt: int
    ) -> int:
        """Ingest 2mm discrete label atlas (uint8, int16, or float32).

        Parameters
        ------------
        atlas_id: int
            Integer ID of the atlas.
        raw_bytes: bytes
            Raw uncompressed NIfTI image bytes.
        dt: int
            NIfTI datatype code (2=uint8, 4=int16, 16=float32).

        Returns
        --------
            int: integer object
                Total number of recorded voxel hits.
        """
        recorded: int = 0
        for k in range(self.MNI_DIM3):
            for j in range(self.MNI_DIM2):
                for i in range(self.MNI_DIM1):
                    v_idx: int = i + self.MNI_DIM1 * j + (
                        self.MNI_DIM1 * self.MNI_DIM2
                    ) * k
                    label_idx: int = 0
                    if dt == 2:
                        label_idx = raw_bytes[v_idx]
                    elif dt == 4:
                        label_idx = struct.unpack_from(
                            "<h", raw_bytes, v_idx * 2
                        )[0]
                    elif dt == 16:
                        lbl_f = struct.unpack_from("<f", raw_bytes, v_idx * 4)[0]
                        label_idx = int(round(lbl_f))

                    if label_idx > 0:
                        voxel_id: int = self._voxel_coords_to_id(i, j, k)
                        if voxel_id not in self._voxel_hits:
                            self._voxel_hits[voxel_id] = []
                        self._voxel_hits[voxel_id].append(
                            (atlas_id, 100, label_idx)
                        )
                        recorded += 1
        return recorded

    def _ingest_1mm_discrete_labels(
        self, atlas_id: int, raw_bytes: bytes
    ) -> int:
        """Ingest 1mm discrete label atlas (e.g. SMATT) sampled at 2mm grid points.

        Parameters
        ------------
        atlas_id: int
            Integer ID of the atlas.
        raw_bytes: bytes
            Raw uncompressed NIfTI image bytes.

        Returns
        --------
            int: integer object
                Total number of recorded voxel hits.
        """
        dim1_1mm: int = 182
        dim2_1mm: int = 218
        recorded: int = 0

        for k in range(self.MNI_DIM3):
            for j in range(self.MNI_DIM2):
                for i in range(self.MNI_DIM1):
                    # Sample at center of 2mm voxel (2i, 2j, 2k)
                    v_idx_1mm: int = (2 * i) + dim1_1mm * (2 * j) + (
                        dim1_1mm * dim2_1mm
                    ) * (2 * k)
                    lbl = struct.unpack_from("<i", raw_bytes, v_idx_1mm * 4)[0]
                    if lbl > 0:
                        voxel_id: int = self._voxel_coords_to_id(i, j, k)
                        if voxel_id not in self._voxel_hits:
                            self._voxel_hits[voxel_id] = []
                        self._voxel_hits[voxel_id].append(
                            (atlas_id, 100, lbl)
                        )
                        recorded += 1
        return recorded

    def _ingest_1mm_probabilistic(
        self, atlas_id: int, raw_bytes: bytes, num_vols: int
    ) -> int:
        """Ingest 1mm probabilistic atlas (e.g. XTRACT) by sampling 2mm grid centers.

        Parameters
        ------------
        atlas_id: int
            Integer ID of the atlas.
        raw_bytes: bytes
            Raw uncompressed NIfTI image bytes.
        num_vols: int
            Number of probability tract volumes.

        Returns
        --------
            int: integer object
                Total number of recorded voxel hits.
        """
        dim1_1mm: int = 182
        dim2_1mm: int = 218
        dim3_1mm: int = 182
        vol_size_1mm: int = dim1_1mm * dim2_1mm * dim3_1mm
        recorded: int = 0

        for t in range(num_vols):
            v_slice = raw_bytes[
                t * vol_size_1mm * 4 : (t + 1) * vol_size_1mm * 4
            ]
            for k in range(self.MNI_DIM3):
                for j in range(self.MNI_DIM2):
                    for i in range(self.MNI_DIM1):
                        # Sample center of 2mm voxel
                        v_idx_1mm: int = (2 * i) + dim1_1mm * (2 * j) + (
                            dim1_1mm * dim2_1mm
                        ) * (2 * k)
                        val_f = struct.unpack_from(
                            "<f", v_slice, v_idx_1mm * 4
                        )[0]
                        prob: int = int(round(val_f))
                        if prob >= 5:
                            prob_clamped: int = min(100, max(1, prob))
                            voxel_id: int = self._voxel_coords_to_id(i, j, k)
                            if voxel_id not in self._voxel_hits:
                                self._voxel_hits[voxel_id] = []
                            self._voxel_hits[voxel_id].append(
                                (atlas_id, prob_clamped, t)
                            )
                            recorded += 1
        return recorded

    def _ingest_05mm_probabilistic(
        self, atlas_id: int, raw_bytes: bytes, num_vols: int
    ) -> int:
        """Ingest 0.5mm probabilistic atlas (e.g. STN) by block maximum search.

        Parameters
        ------------
        atlas_id: int
            Integer ID of the atlas.
        raw_bytes: bytes
            Raw uncompressed NIfTI image bytes.
        num_vols: int
            Number of subthalamic volumes.

        Returns
        --------
            int: integer object
                Total number of recorded voxel hits.
        """
        dim1_05: int = 364
        dim2_05: int = 436
        dim3_05: int = 364
        vol_bytes: int = dim1_05 * dim2_05 * dim3_05 * 4
        recorded: int = 0

        for t in range(num_vols):
            v_slice = raw_bytes[t * vol_bytes : (t + 1) * vol_bytes]
            for k in range(self.MNI_DIM3):
                for j in range(self.MNI_DIM2):
                    for i in range(self.MNI_DIM1):
                        max_v: float = 0.0
                        for dk in (1, 2):
                            for dj in (1, 2):
                                for di in (1, 2):
                                    idx_05: int = (
                                        (i * 4 + di)
                                        + dim1_05 * (j * 4 + dj)
                                        + (dim1_05 * dim2_05) * (k * 4 + dk)
                                    )
                                    val_f = struct.unpack_from(
                                        "<f", v_slice, idx_05 * 4
                                    )[0]
                                    if val_f > max_v:
                                        max_v = val_f
                        prob: int = int(round(max_v))
                        if prob >= 5:
                            prob_clamped: int = min(100, max(1, prob))
                            voxel_id: int = self._voxel_coords_to_id(i, j, k)
                            if voxel_id not in self._voxel_hits:
                                self._voxel_hits[voxel_id] = []
                            self._voxel_hits[voxel_id].append(
                                (atlas_id, prob_clamped, t)
                            )
                            recorded += 1
        return recorded

    def build(self) -> int:
        """Execute full extraction of 20 human FSL atlases into SQLite database.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Total count of unique populated voxels.
        """
        self._output_db_path.parent.mkdir(parents=True, exist_ok=True)
        if self._output_db_path.exists():
            self._output_db_path.unlink()

        conn: sqlite3.Connection = sqlite3.connect(str(self._output_db_path))
        cursor: sqlite3.Cursor = conn.cursor()

        cursor.executescript(
            """
            PRAGMA page_size = 4096;
            PRAGMA journal_mode = DELETE;
            PRAGMA synchronous = NORMAL;

            CREATE TABLE atlases (
                atlas_id INTEGER PRIMARY KEY,
                atlas_key TEXT UNIQUE NOT NULL,
                short_name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                atlas_type TEXT NOT NULL,
                num_labels INTEGER NOT NULL
            );

            CREATE TABLE atlas_labels (
                atlas_id INTEGER NOT NULL,
                label_index INTEGER NOT NULL,
                label_name TEXT NOT NULL,
                cog_mni_x REAL NOT NULL,
                cog_mni_y REAL NOT NULL,
                cog_mni_z REAL NOT NULL,
                PRIMARY KEY (atlas_id, label_index)
            );

            CREATE TABLE voxel_lookup (
                voxel_id INTEGER PRIMARY KEY,
                packed_hits BLOB NOT NULL
            );

            CREATE INDEX idx_labels_name ON atlas_labels(label_name);
            """
        )

        xml_files: list[Path] = sorted(self._fsl_dir.glob("*.xml"))
        human_xmls: list[Path] = [
            x for x in xml_files
            if not any(x.name.startswith(p) for p in self.EXCLUDED_ATLAS_PREFIXES)
        ]

        sys.stdout.write(f"Extracting {len(human_xmls)} human FSL atlases...\n")

        for atlas_id, xml_path in enumerate(human_xmls, start=1):
            meta = self._parse_xml_metadata(xml_path)
            labels = meta["labels"]
            sys.stdout.write(
                f"[{atlas_id:2d}/{len(human_xmls)}] {meta['key']:35s} "
                f"({len(labels)} labels)... "
            )
            sys.stdout.flush()

            cursor.execute(
                """
                INSERT INTO atlases (atlas_id, atlas_key, short_name, full_name, atlas_type, num_labels)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    atlas_id,
                    meta["key"],
                    meta["short_name"],
                    meta["name"],
                    meta["atlas_type"],
                    len(labels),
                ),
            )

            for l_idx, l_name, mni_x, mni_y, mni_z in labels:
                cursor.execute(
                    """
                    INSERT INTO atlas_labels (atlas_id, label_index, label_name, cog_mni_x, cog_mni_y, cog_mni_z)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (atlas_id, l_idx, l_name, mni_x, mni_y, mni_z),
                )

            # Read NIfTI file
            img_rel: str = meta["image_rel"]
            nii_path: Path = self._fsl_dir / (img_rel.lstrip("/") + ".nii.gz")
            if not nii_path.exists():
                sys.stdout.write(f"WARNING: NIfTI file not found at {nii_path}\n")
                continue

            with gzip.open(nii_path, "rb") as f:
                hdr = f.read(352)
                dims = struct.unpack("<8h", hdr[40:56])
                dt = struct.unpack("<h", hdr[70:72])[0]
                raw_data = f.read()

            num_vols: int = dims[4] if dims[0] >= 4 else 1

            if "0.5mm" in str(nii_path):
                hits = self._ingest_05mm_probabilistic(atlas_id, raw_data, num_vols)
            elif "1mm" in str(nii_path) and meta["atlas_type"] == "Label":
                hits = self._ingest_1mm_discrete_labels(atlas_id, raw_data)
            elif "1mm" in str(nii_path):
                hits = self._ingest_1mm_probabilistic(atlas_id, raw_data, num_vols)
            elif meta["atlas_type"] == "Label":
                hits = self._ingest_2mm_discrete_labels(atlas_id, raw_data, dt)
            else:
                hits = self._ingest_2mm_probabilistic(atlas_id, raw_data, num_vols)

            sys.stdout.write(f"-> {hits:,} hits\n")

        # Insert all packed voxel hits
        sys.stdout.write(
            f"Packing {len(self._voxel_hits):,} active voxels into database...\n"
        )
        batch: list[tuple[int, bytes]] = []
        for voxel_id, hits in self._voxel_hits.items():
            # Sort hits by probability descending
            hits.sort(key=lambda h: h[1], reverse=True)
            blob_parts: list[bytes] = []
            for a_id, prob, l_idx in hits:
                blob_parts.append(struct.pack("<BBH", a_id, prob, l_idx))
            batch.append((voxel_id, b"".join(blob_parts)))
            if len(batch) >= 10000:
                cursor.executemany(
                    "INSERT INTO voxel_lookup (voxel_id, packed_hits) VALUES (?, ?)",
                    batch,
                )
                batch.clear()

        if batch:
            cursor.executemany(
                "INSERT INTO voxel_lookup (voxel_id, packed_hits) VALUES (?, ?)",
                batch,
            )

        conn.commit()
        cursor.execute("VACUUM;")
        conn.close()

        db_size_mb: float = self._output_db_path.stat().st_size / (1024 * 1024)
        sys.stdout.write(
            f"Build complete! Saved to {self._output_db_path} ({db_size_mb:.2f} MB, "
            f"{len(self._voxel_hits):,} voxels).\n"
        )
        return len(self._voxel_hits)


def main() -> None:
    """Parse command line arguments and execute database build.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Builds database and exits.
    """
    default_fsl: Path = Path("/Users/mszdjh3/fsl/data/atlases")
    if not default_fsl.exists() and "FSLDIR" in os.environ:
        default_fsl = Path(os.environ["FSLDIR"]) / "data" / "atlases"

    repo_root: Path = Path(__file__).resolve().parent.parent
    default_output: Path = repo_root / "neuri" / "brain" / "fsl_atlases.db"

    parser = argparse.ArgumentParser(
        description="Compile FSL atlases into a standalone Neuri SQLite database"
    )
    parser.add_argument(
        "--fsl-dir",
        type=Path,
        default=default_fsl,
        help="Path to FSL data/atlases directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help="Target SQLite database file path",
    )

    args = parser.parse_args()
    if not args.fsl_dir.exists():
        sys.stderr.write(f"Error: FSL directory not found: {args.fsl_dir}\n")
        sys.exit(1)

    builder = FSLAtlasDatabaseBuilder(
        fsl_atlases_dir=args.fsl_dir,
        output_db_path=args.output,
    )
    builder.build()


if __name__ == "__main__":
    main()
