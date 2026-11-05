"""Interactive neuroimaging visualization and NiiVue WebGL2 bridge for Neuri.

Provides embedded local HTTP streaming and declarative scene management for
multiplanar volume rendering, surface meshes, and streamline tractography.
"""

from neuri.viewer.fsl_atlas import (
    FSLAtlasClient,
    FSLAtlasHit,
    FSLCoordinateResult,
    FSLRegionSearchResult,
    query_fsl_coordinates,
    search_fsl_regions,
)
from neuri.viewer.local_explorer import LocalFileExplorer
from neuri.viewer.neurosynth import (
    NeurosynthAssociation,
    NeurosynthClient,
    NeurosynthResult,
    query_neurosynth_coordinates,
)
from neuri.viewer.niivue_bridge import (
    NiiVueBridge,
    NiiVueBridgeHandler,
    NiiVueHTTPServer,
)

__all__: list[str] = [
    "FSLAtlasClient",
    "FSLAtlasHit",
    "FSLCoordinateResult",
    "FSLRegionSearchResult",
    "LocalFileExplorer",
    "NeurosynthAssociation",
    "NeurosynthClient",
    "NeurosynthResult",
    "NiiVueBridge",
    "NiiVueBridgeHandler",
    "NiiVueHTTPServer",
    "query_fsl_coordinates",
    "query_neurosynth_coordinates",
    "search_fsl_regions",
]
