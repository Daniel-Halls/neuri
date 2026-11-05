"""CLI utility to query FSL brain atlases by MNI coordinates or region name.

Allows researchers to look up anatomical parcellations and white-matter tracts
across 20 human FSL atlases without having FSL installed.
"""

import argparse
import json
import sys

from neuri.viewer.fsl_atlas import (
    FSLAtlasClient,
    FSLCoordinateResult,
    FSLRegionSearchResult,
)


def run_coordinate_query(
    x: float,
    y: float,
    z: float,
    atlas_filter: list[str] | None = None,
    min_prob: float = 5.0,
    as_json: bool = False,
) -> int:
    """Execute coordinate lookup across FSL atlases and print output.

    Parameters
    ------------
    x: float
        MNI X coordinate in millimeters.
    y: float
        MNI Y coordinate in millimeters.
    z: float
        MNI Z coordinate in millimeters.
    atlas_filter: list[str] | None
        Optional atlas keys filter. Defaults to None.
    min_prob: float
        Minimum probability threshold (1 to 100). Defaults to 5.0.
    as_json: bool
        Whether to output raw JSON. Defaults to False.

    Returns
    --------
        int: integer object
            Process exit status code (0 for success).
    """
    client: FSLAtlasClient = FSLAtlasClient()
    res: FSLCoordinateResult = client.query_coordinate(
        x=x, y=y, z=z, atlas_filter=atlas_filter, min_prob=min_prob
    )

    if as_json:
        sys.stdout.write(json.dumps(res.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(res.format_markdown() + "\n")
    return 0


def run_region_search(
    query: str,
    atlas_filter: list[str] | None = None,
    as_json: bool = False,
) -> int:
    """Search for anatomical regions by name and print MNI coordinates.

    Parameters
    ------------
    query: str
        Text search query (e.g. 'Amygdala').
    atlas_filter: list[str] | None
        Optional atlas keys filter. Defaults to None.
    as_json: bool
        Whether to output raw JSON. Defaults to False.

    Returns
    --------
        int: integer object
            Process exit status code (0 for success).
    """
    client: FSLAtlasClient = FSLAtlasClient()
    results: list[FSLRegionSearchResult] = client.search_regions(
        query=query, atlas_filter=atlas_filter
    )

    if as_json:
        payload = [r.to_dict() for r in results]
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        lines: list[str] = [
            f"### Search Results for '{query}' across FSL Atlases",
            f"*Found {len(results)} matching structures*\n",
            "| Atlas | Region Name | MNI Center of Gravity (X, Y, Z) |",
            "| :--- | :--- | :---: |",
        ]
        for r in results:
            cog_str: str = f"[{r.cog_mni[0]:.1f}, {r.cog_mni[1]:.1f}, {r.cog_mni[2]:.1f}]"
            lines.append(f"| **{r.atlas_name}** | {r.region_name} | `{cog_str}` |")
        if not results:
            lines.append("| *(No matching regions found)* | -- | -- |")
        sys.stdout.write("\n".join(lines) + "\n")
    return 0


def run_list_atlases(as_json: bool = False) -> int:
    """List all available FSL atlases in the database.

    Parameters
    ------------
    as_json: bool
        Whether to output raw JSON. Defaults to False.

    Returns
    --------
        int: integer object
            Process exit status code (0 for success).
    """
    client: FSLAtlasClient = FSLAtlasClient()
    atlases = client.list_atlases()

    if as_json:
        sys.stdout.write(json.dumps(atlases, indent=2) + "\n")
    else:
        lines: list[str] = [
            "### Bundled FSL Atlases in Neuri (20 Human MNI152 Parcellations)",
            "",
            "| Key | Name | Type | Regions |",
            "| :--- | :--- | :---: | :---: |",
        ]
        for a in atlases:
            lines.append(
                f"| `{a['atlas_key']}` | {a['full_name']} | "
                f"{a['atlas_type']} | {a['num_labels']} |"
            )
        sys.stdout.write("\n".join(lines) + "\n")
    return 0


def main() -> None:
    """Parse command line arguments and execute requested FSL atlas operation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Exits with process return code.
    """
    parser = argparse.ArgumentParser(
        description="Neuri FSL Atlas MNI Coordinate and Region Query Utility"
    )
    parser.add_argument(
        "coords",
        nargs="*",
        type=float,
        help="MNI Coordinates X Y Z in mm (e.g. -24 -2 -20)",
    )
    parser.add_argument(
        "--search",
        "-s",
        type=str,
        default="",
        help="Search anatomical structure name to find MNI coordinates",
    )
    parser.add_argument(
        "--list-atlases",
        "-l",
        action="store_true",
        help="List all bundled human FSL atlases",
    )
    parser.add_argument(
        "--atlas",
        "-a",
        nargs="+",
        help="Filter results by specific atlas key(s)",
    )
    parser.add_argument(
        "--min-prob",
        "-p",
        type=float,
        default=5.0,
        help="Minimum probability threshold in percent (default: 5.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of Markdown table",
    )

    args = parser.parse_args()

    if args.list_atlases:
        code: int = run_list_atlases(as_json=args.json)
        sys.exit(code)

    if args.search:
        code = run_region_search(
            query=args.search,
            atlas_filter=args.atlas,
            as_json=args.json,
        )
        sys.exit(code)

    if len(args.coords) >= 3:
        x, y, z = args.coords[:3]
    elif len(args.coords) == 0:
        # Default demo coordinates (Left Amygdala)
        x, y, z = -24.0, -2.0, -20.0
    else:
        sys.stderr.write("Error: Expected 3 coordinates (X Y Z), e.g.: -24 -2 -20\n")
        sys.exit(1)

    code = run_coordinate_query(
        x=x,
        y=y,
        z=z,
        atlas_filter=args.atlas,
        min_prob=args.min_prob,
        as_json=args.json,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
