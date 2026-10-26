"""Unified Neuro-Resource Registry and MCP server for Neuri.

Maintains a canonical database of standard TemplateFlow stereotaxic spaces,
brain parcellation atlases, BIDS filename entity validation rules, and verified
Apptainer neuroimaging containers.
"""

import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TemplateSpaceInfo(BaseModel):
    """Metadata describing a stereotaxic reference template space.

    Parameters
    ------------
    name: str
        TemplateFlow standard space identifier (e.g. 'MNI152NLin2009cAsym').
    description: str
        Descriptive explanation of the template space.
    resolutions_mm: list[float]
        Standard voxel resolutions available (e.g. [1.0, 2.0]).
    species: str
        Target species ('human', 'macaque', 'mouse'). Defaults to 'human'.

    Returns
    --------
        TemplateSpaceInfo: TemplateSpaceInfo instance
            Constructed template space metadata model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., description="TemplateFlow space identifier")
    description: str = Field(..., description="Template description")
    resolutions_mm: list[float] = Field(..., description="Resolutions in mm")
    species: str = Field(default="human", description="Target species")


class AtlasInfo(BaseModel):
    """Metadata describing a canonical brain parcellation atlas.

    Parameters
    ------------
    name: str
        Atlas identifier (e.g. 'Schaefer2018', 'Glasser_HCP_MMP1.0').
    space: str
        Native stereotaxic space (e.g. 'MNI152NLin2009cAsym', 'fsLR').
    parcels_count: int
        Total number of cortical or subcortical parcels.
    networks: list[str]
        Functional network decompositions supported (e.g. ['7Networks', '17Networks']).

    Returns
    --------
        AtlasInfo: AtlasInfo instance
            Constructed atlas model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., description="Atlas identifier")
    space: str = Field(..., description="Reference space")
    parcels_count: int = Field(..., description="Total parcel count")
    networks: list[str] = Field(default_factory=list, description="Network schemes")


class NeuroResourceRegistry:
    """Local SQLite registry and MCP server for standard neuroimaging assets.

    Parameters
    ------------
    db_path: Path | None
        Path to registry SQLite database. Defaults to ~/.neuri/resources/registry.db.

    Returns
    --------
        NeuroResourceRegistry: NeuroResourceRegistry instance
            Constructed resource registry instance.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize and seed neuro-resource database.

        Parameters
        ------------
        db_path: Path | None
            Database file path. Defaults to ~/.neuri/resources/registry.db.

        Returns
        --------
            None: NoneType object
                Initializes database schema and seed records.
        """
        self._db_path: Path = (
            db_path
            if db_path is not None
            else Path.home() / ".neuri" / "resources" / "registry.db"
        )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Create tables and populate canonical seed records.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Executes DDL statements.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS templates (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    resolutions_json TEXT NOT NULL,
                    species TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS atlases (
                    name TEXT PRIMARY KEY,
                    space TEXT NOT NULL,
                    parcels_count INTEGER NOT NULL,
                    networks_json TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS containers (
                    name TEXT PRIMARY KEY,
                    tag TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    description TEXT NOT NULL
                );
                """
            )

            # Seed templates
            conn.execute(
                """
                INSERT OR IGNORE INTO templates VALUES
                (
                    'MNI152NLin2009cAsym',
                    'ICBM 2009c Nonlinear Asymmetric Template',
                    '[1.0, 2.0]',
                    'human'
                ),
                (
                    'MNI152NLin6Asym',
                    'FSL legacy MNI152 linear asymmetric template',
                    '[1.0, 2.0]',
                    'human'
                ),
                (
                    'fsaverage',
                    'FreeSurfer spherical average cortical surface',
                    '[]',
                    'human'
                ),
                (
                    'fsLR',
                    'HCP fs_LR standard cortical surface space',
                    '[]',
                    'human'
                );
                """
            )

            # Seed atlases
            conn.execute(
                """
                INSERT OR IGNORE INTO atlases VALUES
                (
                    'Schaefer2018_100Parcels',
                    'MNI152NLin2009cAsym',
                    100,
                    '["7Networks", "17Networks"]'
                ),
                (
                    'Schaefer2018_400Parcels',
                    'MNI152NLin2009cAsym',
                    400,
                    '["7Networks", "17Networks"]'
                ),
                ('Glasser_HCP_MMP1.0', 'fsLR', 360, '["HCP_Multimodal"]'),
                ('DesikanKilliany', 'fsaverage', 68, '["Anatomical"]'),
                (
                    'HarvardOxford',
                    'MNI152NLin6Asym',
                    48,
                    '["Subcortical", "Cortical"]'
                );
                """
            )

            # Seed containers
            conn.execute(
                """
                INSERT OR IGNORE INTO containers VALUES
                (
                    'fmriprep',
                    '24.0.0',
                    'docker://nipreps/fmriprep:24.0.0',
                    'BIDS fMRI Preprocessing'
                ),
                (
                    'qsiprep',
                    '0.21.4',
                    'docker://pennbbl/qsiprep:0.21.4',
                    'Diffusion MRI Preprocessing'
                ),
                (
                    'mrtrix3',
                    '3.0.4',
                    'docker://mrtrix3/mrtrix3:3.0.4',
                    'MRtrix3 Tractography Framework'
                ),
                (
                    'freesurfer',
                    '7.4.1',
                    'docker://freesurfer/freesurfer:7.4.1',
                    'Cortical Reconstruction'
                );
                """
            )

    def list_templates(self) -> list[dict[str, Any]]:
        """List all registered stereotaxic reference templates.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                List of template specification dictionaries.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM templates ORDER BY name ASC;").fetchall()
            results: list[dict[str, Any]] = [
                {
                    "name": r["name"],
                    "description": r["description"],
                    "resolutions_mm": json.loads(r["resolutions_json"]),
                    "species": r["species"],
                }
                for r in rows
            ]
            return results

    def list_atlases(self) -> list[dict[str, Any]]:
        """List all canonical brain parcellation atlases.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                List of atlas metadata dictionaries.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM atlases ORDER BY name ASC;").fetchall()
            results: list[dict[str, Any]] = [
                {
                    "name": r["name"],
                    "space": r["space"],
                    "parcels_count": r["parcels_count"],
                    "networks": json.loads(r["networks_json"]),
                }
                for r in rows
            ]
            return results

    def list_containers(self) -> list[dict[str, Any]]:
        """List verified Apptainer neuroimaging containers.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                List of container records.
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM containers ORDER BY name ASC;"
            ).fetchall()
            results: list[dict[str, Any]] = [
                {
                    "name": r["name"],
                    "tag": r["tag"],
                    "uri": r["uri"],
                    "description": r["description"],
                }
                for r in rows
            ]
            return results

    def validate_bids_entities(self, filename: str) -> dict[str, Any]:
        """Validate filename against official BIDS entity order and syntax.

        Parameters
        ------------
        filename: str
            Filename to validate (e.g. 'sub-01_ses-1_task-rest_bold.nii.gz').

        Returns
        --------
            dict[str, Any]: dictionary object
                Validation result with extracted entities and validity flag.
        """
        stem: str = filename.replace(".nii.gz", "").replace(".nii", "")
        parts: list[str] = stem.split("_")

        entities: dict[str, str] = {}
        suffix: str = ""

        canonical_order: list[str] = [
            "sub", "ses", "task", "acq", "ce", "rec", "dir", "run", "echo",
            "space", "res", "den", "label", "desc"
        ]

        for p in parts:
            if "-" in p:
                k, v = p.split("-", 1)
                entities[k] = v
            else:
                suffix = p

        is_valid: bool = "sub" in entities and bool(suffix)
        order_valid: bool = True
        last_idx: int = -1

        for k in entities.keys():
            if k in canonical_order:
                cur_idx = canonical_order.index(k)
                if cur_idx < last_idx:
                    order_valid = False
                last_idx = cur_idx

        return {
            "filename": filename,
            "is_valid_bids": is_valid and order_valid,
            "entities": entities,
            "suffix": suffix,
            "order_compliant": order_valid,
        }

    def handle_jsonrpc(self, request_json: str) -> str:
        """Handle incoming JSON-RPC 2.0 tool requests.

        Parameters
        ------------
        request_json: str
            Incoming request string.

        Returns
        --------
            str: string object
                JSON-RPC response string.
        """
        try:
            req: dict[str, Any] = json.loads(request_json)
            req_id: Any = req.get("id")
            method: str = req.get("method", "")
            params: dict[str, Any] = req.get("params", {})

            if method == "tools/list":
                tools = [
                    {
                        "name": "list_templates",
                        "description": "List stereotaxic spaces",
                    },
                    {
                        "name": "list_atlases",
                        "description": "List parcellation atlases",
                    },
                    {
                        "name": "list_containers",
                        "description": "List verified Apptainer images",
                    },
                    {
                        "name": "validate_bids_entities",
                        "description": (
                            "Validate BIDS filename entities and ordering"
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {"filename": {"type": "string"}},
                            "required": ["filename"],
                        },
                    },
                ]
                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "result": {"tools": tools},
                        "id": req_id,
                    }
                )

            if method == "tools/call":
                name: str = params.get("name", "")
                args: dict[str, Any] = params.get("arguments", {})

                if name == "list_templates":
                    res = self.list_templates()
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(res, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )
                if name == "list_atlases":
                    res_a = self.list_atlases()
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(res_a, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )
                if name == "list_containers":
                    res_c = self.list_containers()
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(res_c, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )
                if name == "validate_bids_entities":
                    res_v = self.validate_bids_entities(args["filename"])
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(res_v, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )

                return json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": f"Tool '{name}' not found",
                        },
                        "id": req_id,
                    }
                )

            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Unsupported method: {method}",
                    },
                    "id": req_id,
                }
            )

        except Exception as err:
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(err)},
                    "id": None,
                }
            )

    def run_stdio_server(self) -> None:
        """Run stdio JSON-RPC loop for resource tools.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Loops over sys.stdin lines and writes responses.
        """
        for line in sys.stdin:
            stripped = line.strip()
            if not stripped:
                continue
            response_str: str = self.handle_jsonrpc(stripped)
            sys.stdout.write(response_str + "\n")
            sys.stdout.flush()


__all__: list[str] = [
    "AtlasInfo",
    "NeuroResourceRegistry",
    "TemplateSpaceInfo",
]
