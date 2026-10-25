"""CLI and command-line execution interface for Neuri.

Provides the primary executable command (`neuri`) and headless runners.
"""

from neuri.cli.main import NeuriCLI, app

__all__: list[str] = [
    "NeuriCLI",
    "app",
]
