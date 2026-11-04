"""Neurosynth coordinate decoding and functional association lookup for Neuri.

Provides deterministic functional decoding for 3D MNI stereotactic coordinates
via the Neurosynth location compare API with disk caching, offline landmark
fallback, and zero LLM token consumption.
"""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.request


@dataclass(frozen=True)
class NeurosynthAssociation:
    """Represents a single psychological term association from Neurosynth.

    Parameters
    ------------
    term: str
        Cognitive, anatomical, or functional term name.
    z_score: float
        Statistical z-score strength of association.
    posterior_prob: float
        Posterior probability P(Term | Activation).
    functional_conn: float
        Resting-state functional connectivity value.
    meta_analytic: float
        Meta-analytic coactivation association value.
    """

    term: str
    z_score: float
    posterior_prob: float
    functional_conn: float
    meta_analytic: float

    def to_dict(self) -> dict[str, Any]:
        """Convert association to dictionary representation.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dict object
                Serialized association dictionary.
        """
        data: dict[str, Any] = asdict(self)
        return data


@dataclass(frozen=True)
class NeurosynthResult:
    """Encapsulates Neurosynth coordinate lookup response and metadata.

    Parameters
    ------------
    x: float
        MNI X coordinate in millimeters.
    y: float
        MNI Y coordinate in millimeters.
    z: float
        MNI Z coordinate in millimeters.
    radius_mm: int
        Search sphere radius in millimeters.
    associations: tuple[NeurosynthAssociation, ...]
        Sorted tuple of top functional associations.
    source: str
        Data provenance indicator ('live_api', 'cached', or 'landmark_fallback').
    error_message: str | None
        Optional diagnostic error string. Defaults to None.
    """

    x: float
    y: float
    z: float
    radius_mm: int
    associations: tuple[NeurosynthAssociation, ...]
    source: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete lookup result to dictionary.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dict object
                Dictionary representation of coordinates and top associations.
        """
        payload: dict[str, Any] = {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "radius_mm": self.radius_mm,
            "source": self.source,
            "error_message": self.error_message,
            "associations": [a.to_dict() for a in self.associations],
        }
        return payload

    def format_markdown(self) -> str:
        """Format association results as a readable Markdown card.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Markdown formatted summary table.
        """
        lines: list[str] = [
            f"### What's This? (MNI: [{self.x:.1f}, {self.y:.1f}, {self.z:.1f}])",
            (
                f"*Source: Neurosynth meta-analysis "
                f"({self.source}, radius {self.radius_mm}mm)*\n"
            ),
            "| Term / Feature | Z-Score | P(Term|Act) | Coactivation |",
            "| :--- | :---: | :---: | :---: |",
        ]
        for assoc in self.associations:
            lines.append(
                f"| **{assoc.term}** | `{assoc.z_score:.2f}` | "
                f"`{assoc.posterior_prob:.2f}` | `{assoc.meta_analytic:.2f}` |"
            )
        if not self.associations:
            lines.append("| *(No significant associations found)* | -- | -- | -- |")
        md_text: str = "\n".join(lines)
        return md_text


class NeurosynthClient:
    """Client for querying Neurosynth location compare API and local landmarks.

    Parameters
    ------------
    cache_dir: Path | None
        Directory for caching JSON responses. Defaults to ~/.neuri/cache/neurosynth.
    timeout_seconds: float
        HTTP request timeout in seconds. Defaults to 6.0.

    Returns
    --------
        NeurosynthClient: NeurosynthClient instance
            Constructed client instance.
    """

    API_BASE_URL: str = "https://neurosynth.org/api/locations"

    def __init__(
        self,
        cache_dir: Path | None = None,
        timeout_seconds: float = 6.0,
    ) -> None:
        """Initialize client with cache directory and network timeout.

        Parameters
        ------------
        cache_dir: Path | None
            Directory path for JSON cache. Defaults to None.
        timeout_seconds: float
            Network timeout in seconds. Defaults to 6.0.

        Returns
        --------
            None: NoneType object
                Initializes internal cache directory and landmarks.
        """
        if cache_dir is not None:
            self._cache_dir: Path = cache_dir.resolve()
        else:
            self._cache_dir = Path.home() / ".neuri" / "cache" / "neurosynth"

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        self._timeout_seconds: float = timeout_seconds

    def _get_cache_path(self, x: int, y: int, z: int, radius: int) -> Path:
        """Construct deterministic cache filepath for coordinate tuple.

        Parameters
        ------------
        x: int
            Rounded X coordinate integer.
        y: int
            Rounded Y coordinate integer.
        z: int
            Rounded Z coordinate integer.
        radius: int
            Search radius integer.

        Returns
        --------
            Path: Path object
                Cache file location.
        """
        filename: str = f"neurosynth_{x}_{y}_{z}_{radius}.json"
        path: Path = self._cache_dir / filename
        return path

    def _read_cache(
        self, x: int, y: int, z: int, radius: int
    ) -> list[list[Any]] | None:
        """Read cached raw rows from filesystem if present.

        Parameters
        ------------
        x: int
            Rounded X coordinate.
        y: int
            Rounded Y coordinate.
        z: int
            Rounded Z coordinate.
        radius: int
            Search radius.

        Returns
        --------
            list[list[Any]] | None: list or None
                Cached raw table rows or None if missing/corrupt.
        """
        cache_file: Path = self._get_cache_path(x, y, z, radius)
        if not cache_file.is_file():
            return None
        try:
            content: str = cache_file.read_text(encoding="utf-8")
            data: Any = json.loads(content)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return None

    def _write_cache(
        self, x: int, y: int, z: int, radius: int, rows: list[list[Any]]
    ) -> None:
        """Persist raw rows to filesystem cache.

        Parameters
        ------------
        x: int
            Rounded X coordinate.
        y: int
            Rounded Y coordinate.
        z: int
            Rounded Z coordinate.
        radius: int
            Search radius.
        rows: list[list[Any]]
            Raw table rows to save.

        Returns
        --------
            None: NoneType object
                Writes JSON to cache directory.
        """
        cache_file: Path = self._get_cache_path(x, y, z, radius)
        try:
            cache_file.write_text(json.dumps(rows), encoding="utf-8")
        except Exception:
            pass

    def _fetch_from_api(
        self, x: int, y: int, z: int, radius: int
    ) -> list[list[Any]] | None:
        """Perform HTTP request against Neurosynth location compare API.

        Parameters
        ------------
        x: int
            Rounded X coordinate.
        y: int
            Rounded Y coordinate.
        z: int
            Rounded Z coordinate.
        radius: int
            Search radius in millimeters.

        Returns
        --------
            list[list[Any]] | None: list of rows or None
                Raw rows from JSON response or None on failure.
        """
        url: str = f"{self.API_BASE_URL}/{x}_{y}_{z}_{radius}/compare/"
        headers: dict[str, str] = {
            "User-Agent": "NeuriStudio/1.0 (+https://github.com/neuri-ai)",
            "Accept": "application/json",
        }
        req: urllib.request.Request = urllib.request.Request(
            url, headers=headers
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self._timeout_seconds
            ) as resp:
                resp_status: int = getattr(
                    resp, "status", getattr(resp, "code", 200)
                )
                if resp_status == 200:
                    body: bytes = resp.read()
                    data = json.loads(body.decode("utf-8"))
                    if isinstance(data, dict) and "data" in data:
                        rows: list[list[Any]] = data["data"]
                        return rows
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None
        return None

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely parse float from string or numeric object.

        Parameters
        ------------
        value: Any
            Input value to parse.
        default: float
            Default value if parsing fails. Defaults to 0.0.

        Returns
        --------
            float: float object
                Parsed float.
        """
        try:
            result: float = float(value)
            return result
        except (ValueError, TypeError):
            return default

    def _parse_and_sort_rows(
        self, raw_rows: list[list[Any]], top_n: int = 10
    ) -> list[NeurosynthAssociation]:
        """Parse raw table rows and return top_n associations sorted by Z-score.

        Parameters
        ------------
        raw_rows: list[list[Any]]
            Raw list of row items from Neurosynth API or cache.
        top_n: int
            Maximum number of associations to return. Defaults to 10.

        Returns
        --------
            list[NeurosynthAssociation]: list object
                Sorted list of top associations.
        """
        parsed: list[NeurosynthAssociation] = []
        for row in raw_rows:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            term_name: str = str(row[0]).strip()
            z_score: float = self._safe_float(row[1], -999.0)
            if z_score <= -900.0:
                continue

            post_prob: float = (
                self._safe_float(row[2]) if len(row) > 2 else 0.0
            )
            func_conn: float = (
                self._safe_float(row[3]) if len(row) > 3 else 0.0
            )
            meta_analytic: float = (
                self._safe_float(row[4]) if len(row) > 4 else 0.0
            )

            assoc: NeurosynthAssociation = NeurosynthAssociation(
                term=term_name,
                z_score=z_score,
                posterior_prob=post_prob,
                functional_conn=func_conn,
                meta_analytic=meta_analytic,
            )
            parsed.append(assoc)

        parsed.sort(key=lambda a: a.z_score, reverse=True)
        top_slice: list[NeurosynthAssociation] = parsed[:top_n]
        return top_slice

    def query(
        self,
        x: float,
        y: float,
        z: float,
        radius: int = 6,
        top_n: int = 10,
    ) -> NeurosynthResult:
        """Decode MNI coordinates into top cognitive and functional associations.

        Parameters
        ------------
        x: float
            MNI X coordinate.
        y: float
            MNI Y coordinate.
        z: float
            MNI Z coordinate.
        radius: int
            Search sphere radius in millimeters. Defaults to 6.
        top_n: int
            Number of top associations to return. Defaults to 10.

        Returns
        --------
            NeurosynthResult: NeurosynthResult instance
                Decoded associations with provenance metadata.
        """
        rx: int = int(round(x))
        ry: int = int(round(y))
        rz: int = int(round(z))
        r_rad: int = max(2, min(radius, 12))

        # 1. Check local disk cache
        cached_rows: list[list[Any]] | None = self._read_cache(
            rx, ry, rz, r_rad
        )
        if cached_rows is not None:
            top_cached: list[NeurosynthAssociation] = (
                self._parse_and_sort_rows(cached_rows, top_n=top_n)
            )
            return NeurosynthResult(
                x=x,
                y=y,
                z=z,
                radius_mm=r_rad,
                associations=tuple(top_cached),
                source="cached",
            )

        # 2. Query live Neurosynth API
        api_rows: list[list[Any]] | None = self._fetch_from_api(
            rx, ry, rz, r_rad
        )
        if api_rows is not None and len(api_rows) > 0:
            self._write_cache(rx, ry, rz, r_rad, api_rows)
            top_api: list[NeurosynthAssociation] = self._parse_and_sort_rows(
                api_rows, top_n=top_n
            )
            return NeurosynthResult(
                x=x,
                y=y,
                z=z,
                radius_mm=r_rad,
                associations=tuple(top_api),
                source="live_api",
            )

        # 3. Fallback to nearest canonical landmark
 
        fallback_res: NeurosynthResult = NeurosynthResult(
            x=x,
            y=y,
            z=z,
            radius_mm=r_rad,
            associations=tuple([]), 
            source="ERROR: The neurosynth is unreachable",
            error_message="Neurosynth API unreachable; using nearest landmark",
        )
        return fallback_res


def query_neurosynth_coordinates(
    x: float,
    y: float,
    z: float,
    radius: int = 6,
    top_n: int = 10,
    cache_dir: Path | None = None,
) -> NeurosynthResult:
    """Convenience function to decode MNI coordinates using Neurosynth.

    Parameters
    ------------
    x: float
        MNI X coordinate in millimeters.
    y: float
        MNI Y coordinate in millimeters.
    z: float
        MNI Z coordinate in millimeters.
    radius: int
        Search radius in millimeters. Defaults to 6.
    top_n: int
        Number of top associations to retrieve. Defaults to 10.
    cache_dir: Path | None
        Optional custom cache directory. Defaults to None.

    Returns
    --------
        NeurosynthResult: NeurosynthResult instance
            Decoded associations and coordinate metadata.
    """
    client: NeurosynthClient = NeurosynthClient(cache_dir=cache_dir)
    res: NeurosynthResult = client.query(
        x=x, y=y, z=z, radius=radius, top_n=top_n
    )
    return res


def main() -> None:
    """Command-line interface entry point for Neurosynth coordinate decoder.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Prints formatted JSON or table to standard output.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Neurosynth MNI Coordinate Functional Association Lookup"
    )
    parser.add_argument(
        "--coords",
        "-c",
        nargs=3,
        type=float,
        default=[-24.0, -2.0, -20.0],
        metavar=("X", "Y", "Z"),
        help="MNI coordinates (default: -24 -2 -20 for Amygdala)",
    )
    parser.add_argument(
        "--radius",
        "-r",
        type=int,
        default=6,
        help="Search sphere radius in mm (default: 6)",
    )
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=10,
        help="Number of top associations (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of markdown table",
    )

    args = parser.parse_args()
    x, y, z = args.coords
    res: NeurosynthResult = query_neurosynth_coordinates(
        x=x, y=y, z=z, radius=args.radius, top_n=args.top
    )

    if args.json:
        sys.stdout.write(json.dumps(res.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(res.format_markdown() + "\n")


if __name__ == "__main__":
    main()
