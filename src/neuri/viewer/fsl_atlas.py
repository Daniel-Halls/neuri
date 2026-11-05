"""Deterministic FSL MNI152 brain atlas lookup and region search for Neuri.

Provides offline coordinate decoding across 20 human FSL atlases (including
Harvard-Oxford Cortical/Subcortical, Juelich Histological, Cerebellar, and
JHU/XTRACT white-matter tracts) using a self-contained sparse SQLite database
without requiring FSL, Nibabel, or internet access.
"""

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import sqlite3
import struct
from typing import Any


@dataclass(frozen=True)
class FSLAtlasHit:
    """Represents a single anatomical region hit from an FSL atlas.

    Parameters
    ------------
    atlas_key: str
        Unique identifier of the FSL atlas.
    atlas_name: str
        Full human-readable name of the atlas.
    atlas_type: str
        Type of atlas ('Probabilistic' or 'Label').
    label_index: int
        Internal region index in the atlas.
    region_name: str
        Anatomical region or tract label.
    probability: float
        Probability percentage (0.0 to 100.0).
    cog_mni: tuple[float, float, float]
        Center-of-gravity (x, y, z) coordinates in MNI152 millimeters.
    """

    atlas_key: str
    atlas_name: str
    atlas_type: str
    label_index: int
    region_name: str
    probability: float
    cog_mni: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert hit into a JSON-serializable dictionary.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Serialized atlas hit dictionary.
        """
        payload: dict[str, Any] = asdict(self)
        return payload


@dataclass(frozen=True)
class FSLCoordinateResult:
    """Encapsulates all FSL atlas hits for a given 3D MNI coordinate.

    Parameters
    ------------
    x: float
        MNI X coordinate in millimeters.
    y: float
        MNI Y coordinate in millimeters.
    z: float
        MNI Z coordinate in millimeters.
    voxel_id: int
        Mapped 2mm linear voxel index (or -1 if out-of-bounds).
    hits: tuple[FSLAtlasHit, ...]
        Tuple of matching region hits sorted by probability.
    error_message: str | None
        Optional error string. Defaults to None.
    """

    x: float
    y: float
    z: float
    voxel_id: int
    hits: tuple[FSLAtlasHit, ...]
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete lookup result to dictionary.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Serialized dictionary representation.
        """
        payload: dict[str, Any] = {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "voxel_id": self.voxel_id,
            "hits": [h.to_dict() for h in self.hits],
            "error_message": self.error_message,
        }
        return payload

    def to_summary_text(self, max_items: int = 4) -> str:
        """Construct a concise single-line text summary for AI prompt context.

        Parameters
        ------------
        max_items: int
            Maximum number of top hits to include. Defaults to 4.

        Returns
        --------
            str: string object
                Single-line summary string.
        """
        if not self.hits:
            empty_summary: str = (
                f"MNI [{self.x:.1f}, {self.y:.1f}, {self.z:.1f}] (No atlas label)"
            )
            return empty_summary

        items: list[str] = []
        for h in self.hits[:max_items]:
            if h.atlas_type == "Label":
                items.append(f"{h.region_name} ({h.atlas_key})")
            else:
                items.append(f"{h.region_name} [{h.probability:.0f}% {h.atlas_key}]")

        summary_str: str = (
            f"MNI [{self.x:.1f}, {self.y:.1f}, {self.z:.1f}] "
            f"(FSL Anatomy: {', '.join(items)})"
        )
        return summary_str

    def format_markdown(self) -> str:
        """Format association results as a readable Markdown table.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Markdown formatted summary table.
        """
        lines: list[str] = [
            f"### FSL Anatomy (MNI: [{self.x:.1f}, {self.y:.1f}, {self.z:.1f}])",
            "*Source: Offline FSL Atlases (20 Human MNI152 parcellations)*\n",
            "| Atlas | Anatomical Region / Tract | Probability | Type |",
            "| :--- | :--- | :---: | :---: |",
        ]
        for hit in self.hits:
            prob_str: str = (
                f"`{hit.probability:.0f}%`"
                if hit.atlas_type == "Probabilistic"
                else "Discrete"
            )
            lines.append(
                f"| **{hit.atlas_name}** | {hit.region_name} | "
                f"{prob_str} | {hit.atlas_type} |"
            )
        if not self.hits:
            lines.append("| *(No matching FSL atlas region found)* | -- | -- | -- |")

        md_text: str = "\n".join(lines)
        return md_text


@dataclass(frozen=True)
class FSLRegionSearchResult:
    """Represents a search match for an anatomical structure across atlases.

    Parameters
    ------------
    atlas_key: str
        Identifier of the parent atlas.
    atlas_name: str
        Full human-readable atlas name.
    label_index: int
        Internal label index.
    region_name: str
        Full region name string.
    cog_mni: tuple[float, float, float]
        Center-of-gravity (x, y, z) coordinates in MNI152 millimeters.
    """

    atlas_key: str
    atlas_name: str
    label_index: int
    region_name: str
    cog_mni: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        """Serialize search result to dictionary.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Serialized result dictionary.
        """
        payload: dict[str, Any] = asdict(self)
        return payload


class FSLAtlasClient:
    """Client querying standalone SQLite FSL atlas database.

    Parameters
    ------------
    db_path: Path | None
        Path to fsl_atlases.db file. Defaults to auto-discovery.

    Returns
    --------
        FSLAtlasClient: FSLAtlasClient instance
            Constructed client instance.
    """

    MNI_DIM1: int = 91
    MNI_DIM2: int = 109
    MNI_DIM3: int = 91

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize client and resolve database location.

        Parameters
        ------------
        db_path: Path | None
            Optional explicit path to SQLite database. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes database connection resolver.
        """
        if db_path is not None:
            self._db_path: Path = db_path.resolve()
        else:
            self._db_path = self._discover_database_path()

    def _discover_database_path(self) -> Path:
        """Search standard workspace and user home directories for fsl_atlases.db.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Resolved database path.
        """
        candidates: list[Path] = [
            Path(__file__).resolve().parent.parent.parent.parent
            / "neuri"
            / "brain"
            / "fsl_atlases.db",
            Path.home() / ".neuri" / "brain" / "fsl_atlases.db",
            Path.cwd() / "neuri" / "brain" / "fsl_atlases.db",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        default_fallback: Path = candidates[0]
        return default_fallback

    def is_available(self) -> bool:
        """Check whether the FSL atlas SQLite database exists on disk.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if database file exists and is accessible.
        """
        available: bool = self._db_path.is_file()
        return available

    def mni_to_voxel_coords(
        self, x: float, y: float, z: float
    ) -> tuple[int, int, int] | None:
        """Convert continuous MNI152 millimeters to 2mm grid coordinates (i, j, k).

        Parameters
        ------------
        x: float
            MNI X coordinate in millimeters.
        y: float
            MNI Y coordinate in millimeters.
        z: float
            MNI Z coordinate in millimeters.

        Returns
        --------
            tuple[int, int, int] | None: tuple or None
                Grid index tuple (i, j, k) or None if coordinate is out-of-bounds.
        """
        i: int = int(round((90.0 - x) / 2.0))
        j: int = int(round((y + 126.0) / 2.0))
        k: int = int(round((z + 72.0) / 2.0))

        if 0 <= i < self.MNI_DIM1 and 0 <= j < self.MNI_DIM2 and 0 <= k < self.MNI_DIM3:
            coords: tuple[int, int, int] = (i, j, k)
            return coords
        return None

    def voxel_coords_to_id(self, i: int, j: int, k: int) -> int:
        """Compute unique linear voxel row ID from 2mm indices.

        Parameters
        ------------
        i: int
            Grid X index.
        j: int
            Grid Y index.
        k: int
            Grid Z index.

        Returns
        --------
            int: integer object
                Linear integer voxel identifier.
        """
        voxel_id: int = i + self.MNI_DIM1 * j + (self.MNI_DIM1 * self.MNI_DIM2) * k
        return voxel_id

    def query_coordinate(
        self,
        x: float,
        y: float,
        z: float,
        atlas_filter: list[str] | None = None,
        min_prob: float = 5.0,
    ) -> FSLCoordinateResult:
        """Query FSL atlas labels and probabilities for an MNI coordinate.

        Parameters
        ------------
        x: float
            MNI X coordinate in millimeters.
        y: float
            MNI Y coordinate in millimeters.
        z: float
            MNI Z coordinate in millimeters.
        atlas_filter: list[str] | None
            Optional list of atlas keys to filter by. Defaults to None.
        min_prob: float
            Minimum probability threshold (1 to 100). Defaults to 5.0.

        Returns
        --------
            FSLCoordinateResult: FSLCoordinateResult instance
                Matching atlas hits grouped and sorted by probability.
        """
        if not self.is_available():
            err_result = FSLCoordinateResult(
                x=x,
                y=y,
                z=z,
                voxel_id=-1,
                hits=(),
                error_message=f"FSL atlas database not found at {self._db_path}",
            )
            return err_result

        grid_coords = self.mni_to_voxel_coords(x, y, z)
        if grid_coords is None:
            oob_result = FSLCoordinateResult(
                x=x,
                y=y,
                z=z,
                voxel_id=-1,
                hits=(),
                error_message="Coordinates out of MNI152 2mm bounding box",
            )
            return oob_result

        voxel_id: int = self.voxel_coords_to_id(*grid_coords)

        # Open database in read-only mode to prevent lock files
        db_uri: str = f"file:{self._db_path}?mode=ro"
        hits_list: list[FSLAtlasHit] = []

        try:
            conn: sqlite3.Connection = sqlite3.connect(db_uri, uri=True)
            cursor: sqlite3.Cursor = conn.cursor()

            # 1. Fetch packed hits for this voxel
            cursor.execute(
                "SELECT packed_hits FROM voxel_lookup WHERE voxel_id = ?",
                (voxel_id,),
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                conn.close()
                empty_res = FSLCoordinateResult(
                    x=x, y=y, z=z, voxel_id=voxel_id, hits=()
                )
                return empty_res

            packed_blob: bytes = row[0]
            num_hits: int = len(packed_blob) // 4
            raw_tuples: list[tuple[int, int, int]] = []
            for offset in range(0, num_hits * 4, 4):
                a_id, prob, l_idx = struct.unpack_from("<BBH", packed_blob, offset)
                if float(prob) >= min_prob:
                    raw_tuples.append((a_id, prob, l_idx))

            if not raw_tuples:
                conn.close()
                empty_res = FSLCoordinateResult(
                    x=x, y=y, z=z, voxel_id=voxel_id, hits=()
                )
                return empty_res

            # 2. Fetch atlas and label details
            atlas_ids: set[int] = {t[0] for t in raw_tuples}
            id_placeholders: str = ",".join("?" for _ in atlas_ids)
            cursor.execute(
                f"""
                SELECT atlas_id, atlas_key, short_name, full_name, atlas_type
                FROM atlases WHERE atlas_id IN ({id_placeholders})
                """,
                tuple(atlas_ids),
            )
            atlases_map: dict[int, dict[str, Any]] = {
                r[0]: {
                    "key": r[1],
                    "short_name": r[2],
                    "full_name": r[3],
                    "type": r[4],
                }
                for r in cursor.fetchall()
            }

            filter_set: set[str] | None = (
                {f.lower() for f in atlas_filter} if atlas_filter else None
            )

            for a_id, prob, l_idx in raw_tuples:
                a_meta = atlases_map.get(a_id)
                if not a_meta:
                    continue
                if filter_set:
                    key_lower: str = a_meta["key"].lower()
                    short_lower: str = a_meta["short_name"].lower()
                    if key_lower not in filter_set and short_lower not in filter_set:
                        continue

                cursor.execute(
                    """
                    SELECT label_name, cog_mni_x, cog_mni_y, cog_mni_z
                    FROM atlas_labels WHERE atlas_id = ? AND label_index = ?
                    """,
                    (a_id, l_idx),
                )
                lbl_row = cursor.fetchone()
                if lbl_row:
                    label_name: str = lbl_row[0]
                    cog: tuple[float, float, float] = (
                        float(lbl_row[1]),
                        float(lbl_row[2]),
                        float(lbl_row[3]),
                    )
                else:
                    label_name = f"Region {l_idx}"
                    cog = (x, y, z)

                hit: FSLAtlasHit = FSLAtlasHit(
                    atlas_key=a_meta["key"],
                    atlas_name=a_meta["full_name"],
                    atlas_type=a_meta["type"],
                    label_index=l_idx,
                    region_name=label_name,
                    probability=float(prob),
                    cog_mni=cog,
                )
                hits_list.append(hit)

            conn.close()
        except sqlite3.Error as db_err:
            fail_res = FSLCoordinateResult(
                x=x,
                y=y,
                z=z,
                voxel_id=voxel_id,
                hits=(),
                error_message=f"SQLite query error: {db_err}",
            )
            return fail_res

        # Sort hits by probability descending, then by atlas key
        hits_list.sort(key=lambda h: (-h.probability, h.atlas_key))
        final_res: FSLCoordinateResult = FSLCoordinateResult(
            x=x,
            y=y,
            z=z,
            voxel_id=voxel_id,
            hits=tuple(hits_list),
        )
        return final_res

    def search_regions(
        self,
        query: str,
        atlas_filter: list[str] | None = None,
    ) -> list[FSLRegionSearchResult]:
        """Search all atlases for regions matching a query string.

        Parameters
        ------------
        query: str
            Text search string (e.g. 'Amygdala', 'Insula', 'Corticospinal').
        atlas_filter: list[str] | None
            Optional list of atlas keys to filter by. Defaults to None.

        Returns
        --------
            list[FSLRegionSearchResult]: list object
                Matching region search results with MNI center of gravity.
        """
        if not self.is_available():
            empty_list: list[FSLRegionSearchResult] = []
            return empty_list

        clean_query: str = f"%{query.strip().lower()}%"
        results: list[FSLRegionSearchResult] = []
        db_uri: str = f"file:{self._db_path}?mode=ro"

        try:
            conn: sqlite3.Connection = sqlite3.connect(db_uri, uri=True)
            cursor: sqlite3.Cursor = conn.cursor()

            query_sql: str = """
                SELECT a.atlas_key, a.full_name, l.label_index, l.label_name,
                       l.cog_mni_x, l.cog_mni_y, l.cog_mni_z
                FROM atlas_labels l
                JOIN atlases a ON l.atlas_id = a.atlas_id
                WHERE LOWER(l.label_name) LIKE ?
                ORDER BY a.atlas_key, l.label_name
            """
            cursor.execute(query_sql, (clean_query,))
            rows = cursor.fetchall()

            filter_set: set[str] | None = (
                {f.lower() for f in atlas_filter} if atlas_filter else None
            )

            for r in rows:
                a_key: str = r[0]
                a_name: str = r[1]
                l_idx: int = int(r[2])
                l_name: str = r[3]
                cog: tuple[float, float, float] = (
                    float(r[4]),
                    float(r[5]),
                    float(r[6]),
                )

                if filter_set and a_key.lower() not in filter_set:
                    continue

                res = FSLRegionSearchResult(
                    atlas_key=a_key,
                    atlas_name=a_name,
                    label_index=l_idx,
                    region_name=l_name,
                    cog_mni=cog,
                )
                results.append(res)

            conn.close()
        except sqlite3.Error:
            pass

        return results

    def list_atlases(self) -> list[dict[str, Any]]:
        """List all 20 bundled human FSL atlases and their region counts.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                Atlas catalog metadata dictionaries.
        """
        if not self.is_available():
            empty_catalog: list[dict[str, Any]] = []
            return empty_catalog

        db_uri: str = f"file:{self._db_path}?mode=ro"
        catalog: list[dict[str, Any]] = []

        try:
            conn: sqlite3.Connection = sqlite3.connect(db_uri, uri=True)
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                """
                SELECT atlas_id, atlas_key, short_name, full_name,
                       atlas_type, num_labels
                FROM atlases ORDER BY atlas_id
                """
            )
            for r in cursor.fetchall():
                catalog.append(
                    {
                        "atlas_id": r[0],
                        "atlas_key": r[1],
                        "short_name": r[2],
                        "full_name": r[3],
                        "atlas_type": r[4],
                        "num_labels": r[5],
                    }
                )
            conn.close()
        except sqlite3.Error:
            pass

        return catalog


def query_fsl_coordinates(
    x: float,
    y: float,
    z: float,
    atlas_filter: list[str] | None = None,
    min_prob: float = 5.0,
) -> FSLCoordinateResult:
    """Convenience function to query FSL atlas database for coordinates.

    Parameters
    ------------
    x: float
        MNI X coordinate in millimeters.
    y: float
        MNI Y coordinate in millimeters.
    z: float
        MNI Z coordinate in millimeters.
    atlas_filter: list[str] | None
        Optional list of atlas keys to filter by. Defaults to None.
    min_prob: float
        Minimum probability threshold (1 to 100). Defaults to 5.0.

    Returns
    --------
        FSLCoordinateResult: FSLCoordinateResult instance
            Query result container.
    """
    client: FSLAtlasClient = FSLAtlasClient()
    result: FSLCoordinateResult = client.query_coordinate(
        x=x, y=y, z=z, atlas_filter=atlas_filter, min_prob=min_prob
    )
    return result


def search_fsl_regions(
    query: str,
    atlas_filter: list[str] | None = None,
) -> list[FSLRegionSearchResult]:
    """Convenience function to search FSL atlas regions by name.

    Parameters
    ------------
    query: str
        Structure name search term.
    atlas_filter: list[str] | None
        Optional list of atlas keys to filter by. Defaults to None.

    Returns
    --------
        list[FSLRegionSearchResult]: list object
            Matching region results with center-of-gravity MNI coordinates.
    """
    client: FSLAtlasClient = FSLAtlasClient()
    results: list[FSLRegionSearchResult] = client.search_regions(
        query=query, atlas_filter=atlas_filter
    )
    return results
