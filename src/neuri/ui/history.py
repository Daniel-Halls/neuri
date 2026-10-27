"""Command and prompt history management and persistence for Neuri TUI.

Provides bash-like persistent history stored in ~/.neuri/history with arrow-key
scrolling, draft preservation, deduplication, and file persistence.
"""

from pathlib import Path


class PromptHistoryManager:
    """Manages in-memory and persistent command/prompt history.

    Parameters
    ------------
    history_file: Path | None
        Path to history persistence file. Defaults to ~/.neuri/history.
    max_entries: int
        Maximum number of history items to retain. Defaults to 1000.

    Returns
    --------
        PromptHistoryManager: PromptHistoryManager instance
            Constructed history manager instance.
    """

    DEFAULT_MAX_ENTRIES: int = 1000

    def __init__(
        self,
        history_file: Path | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        """Initialize history manager and load entries from disk.

        Parameters
        ------------
        history_file: Path | None
            Filesystem location of history file. Defaults to ~/.neuri/history.
        max_entries: int
            Maximum number of entries to keep. Defaults to 1000.

        Returns
        --------
            None: NoneType object
                Initializes manager state.
        """
        resolved_file: Path = (
            history_file
            if history_file is not None
            else Path.home() / ".neuri" / "history"
        )
        self._history_file: Path = resolved_file
        self._max_entries: int = max_entries
        self._entries: list[str] = []
        self._index: int = -1
        self._draft: str = ""
        self.load_history()

    @property
    def history_file(self) -> Path:
        """Return path to history file on disk.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Path to history file.
        """
        target_path: Path = self._history_file
        return target_path

    @property
    def entries(self) -> list[str]:
        """Return list of loaded history commands.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Copy of active history entries.
        """
        copied_entries: list[str] = list(self._entries)
        return copied_entries

    def load_history(self) -> list[str]:
        """Read and parse history entries from filesystem storage.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Loaded history items.
        """
        loaded: list[str] = []
        if self._history_file.is_file():
            try:
                content: str = self._history_file.read_text(encoding="utf-8")
                for line in content.splitlines():
                    cleaned: str = line.strip()
                    if cleaned:
                        unescaped: str = cleaned.replace("\\n", "\n")
                        loaded.append(unescaped)
            except Exception:
                pass

        if len(loaded) > self._max_entries:
            loaded = loaded[-self._max_entries:]

        self._entries = loaded
        self.reset_cursor()
        return loaded

    def save_history(self) -> bool:
        """Persist current history entries to filesystem storage.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if written successfully, False otherwise.
        """
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            escaped_lines: list[str] = [
                e.replace("\r", "").replace("\n", "\\n")
                for e in self._entries[-self._max_entries:]
            ]
            content: str = (
                "\n".join(escaped_lines) + ("\n" if escaped_lines else "")
            )
            self._history_file.write_text(content, encoding="utf-8")
            success: bool = True
        except Exception:
            success = False
        return success

    def add_entry(self, entry: str) -> None:
        """Append a newly submitted command or prompt to history.

        Parameters
        ------------
        entry: str
            User command or prompt string.

        Returns
        --------
            None: NoneType object
                Updates history list and appends to disk file.
        """
        cleaned: str = entry.strip()
        if not cleaned:
            return

        # Avoid consecutive identical commands (bash HISTCONTROL=ignoredups)
        if self._entries and self._entries[-1] == cleaned:
            self.reset_cursor()
            return

        self._entries.append(cleaned)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        self.reset_cursor()
        self.save_history()

    def navigate_up(self, current_text: str) -> str | None:
        """Recall previous (older) history command on up-arrow press.

        Parameters
        ------------
        current_text: str
            Current text in the input box before navigating up.

        Returns
        --------
            str | None: optional string
                Older command text, or None if history is empty.
        """
        if not self._entries:
            return None

        if self._index == -1:
            self._draft = current_text
            self._index = len(self._entries) - 1
            result_entry: str = self._entries[self._index]
            return result_entry

        if self._index > 0:
            self._index -= 1
            older_entry: str = self._entries[self._index]
            return older_entry

        oldest_entry: str = self._entries[0]
        return oldest_entry

    def navigate_down(self) -> str | None:
        """Recall next (newer) history command on down-arrow press.

        Parameters
        ------------
        None

        Returns
        --------
            str | None: optional string
                Newer command text, restored draft, or None if inactive.
        """
        if not self._entries or self._index == -1:
            return None

        if self._index < len(self._entries) - 1:
            self._index += 1
            newer_entry: str = self._entries[self._index]
            return newer_entry

        # Past newest entry: restore user draft
        self._index = -1
        restored: str = self._draft
        self._draft = ""
        return restored

    def reset_cursor(self) -> None:
        """Reset history navigation pointer to latest position.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears navigation index and draft string.
        """
        self._index = -1
        self._draft = ""

    def clear(self) -> None:
        """Clear all in-memory and persisted history.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Empties history list and deletes file.
        """
        self._entries.clear()
        self.reset_cursor()
        try:
            self._history_file.unlink(missing_ok=True)
        except Exception:
            pass


__all__: list[str] = [
    "PromptHistoryManager",
]
