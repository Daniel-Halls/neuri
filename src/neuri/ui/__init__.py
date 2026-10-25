"""Presentation and user interface subsystem for Neuri.

Provides the interactive Textual terminal chat interface (NeuriChatApp).
"""

from neuri.ui.terminal_chat import MessageCard, NeuriChatApp, TelemetryBar

__all__: list[str] = [
    "MessageCard",
    "NeuriChatApp",
    "TelemetryBar",
]
