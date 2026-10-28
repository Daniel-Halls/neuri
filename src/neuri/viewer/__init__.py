"""Interactive neuroimaging visualization and NiiVue WebGL2 bridge for Neuri.

Provides embedded local HTTP streaming and declarative scene management for
multiplanar volume rendering, surface meshes, and streamline tractography.
"""

from neuri.viewer.local_explorer import LocalFileExplorer
from neuri.viewer.niivue_bridge import (
    NiiVueBridge,
    NiiVueBridgeHandler,
    NiiVueHTTPServer,
)

__all__: list[str] = [
    "LocalFileExplorer",
    "NiiVueBridge",
    "NiiVueBridgeHandler",
    "NiiVueHTTPServer",
]
