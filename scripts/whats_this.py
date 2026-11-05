"""CLI utility to query Neurosynth functional associations by MNI coordinates.

Allows researchers to look up the top 10 cognitive, behavioral, and anatomical
associations for any MNI stereotactic coordinate without consuming LLM tokens.
"""

import argparse
import json
import sys

from neuri.viewer.fsl_atlas import (
    FSLCoordinateResult,
    query_fsl_coordinates,
)
from neuri.viewer.neurosynth import (
    NeurosynthResult,
    query_neurosynth_coordinates,
)


def run_whats_this(
    x: float,
    y: float,
    z: float,
    radius: int = 6,
    top_n: int = 10,
    as_json: bool = False,
) -> int:
    """Execute FSL anatomy and Neurosynth lookup and output results.

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
        Number of top associations. Defaults to 10.
    as_json: bool
        Whether to format output as JSON. Defaults to False.

    Returns
    --------
        int: integer object
            Process exit status code (0 for success).
    """
    fsl_res: FSLCoordinateResult = query_fsl_coordinates(x=x, y=y, z=z)
    ns_res: NeurosynthResult = query_neurosynth_coordinates(
        x=x, y=y, z=z, radius=radius, top_n=top_n
    )

    if as_json:
        combined: dict[str, Any] = {
            "x": x,
            "y": y,
            "z": z,
            "fsl_anatomy": fsl_res.to_dict(),
            "neurosynth": ns_res.to_dict(),
        }
        sys.stdout.write(json.dumps(combined, indent=2) + "\n")
    else:
        sys.stdout.write(fsl_res.format_markdown() + "\n\n")
        sys.stdout.write(ns_res.format_markdown() + "\n")
    return 0


def main() -> None:
    """Parse command line arguments and execute lookup.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Exits with return status code.
    """
    parser = argparse.ArgumentParser(
        description="Neuri 'What's This?' Neurosynth MNI Coordinate Lookup"
    )
    parser.add_argument(
        "coords",
        nargs="*",
        type=float,
        help="MNI Coordinates X Y Z (e.g. -24 -2 -20)",
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
        help="Top N associations to return (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of Markdown table",
    )

    args = parser.parse_args()
    if len(args.coords) >= 3:
        x, y, z = args.coords[:3]
    elif len(args.coords) == 0:
        # Default demo coordinates (Left Amygdala)
        x, y, z = -24.0, -2.0, -20.0
    else:
        sys.stderr.write("Error: Expected 3 coordinates (X Y Z), e.g.: 0 -85 0\n")
        sys.exit(1)

    code: int = run_whats_this(
        x=x,
        y=y,
        z=z,
        radius=args.radius,
        top_n=args.top,
        as_json=args.json,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
