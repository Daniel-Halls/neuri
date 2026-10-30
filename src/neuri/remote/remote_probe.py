"""Neuri-side remote command detection for tool-less harnesses.

Harnesses such as local Ollama only perform text completion and cannot run
shell or SSH commands. This module detects when a task instruction asks for a
command to be run on a configured remote machine so Neuri itself can run it
and hand the real output to the model.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RemoteIntent:
    """Detected request to run a command on a remote machine.

    Parameters
    ------------
    host: str
        Remote host alias mentioned in the instruction.
    command: str | None
        Shell command to run, or None if intent was detected but no
        runnable command could be extracted.

    Returns
    --------
        RemoteIntent: RemoteIntent instance
            Constructed intent model.
    """

    host: str
    command: str | None


class RemoteProbePlanner:
    """Detects remote execution intent in natural-language instructions.

    Parameters
    ------------
    hosts: list[str]
        Known host aliases. Local aliases are ignored.

    Returns
    --------
        RemoteProbePlanner: RemoteProbePlanner instance
            Constructed planner.
    """

    OUTPUT_MARKER: str = "[Neuri remote execution"
    LOCAL_ALIASES: tuple[str, ...] = ("localhost", "local", "127.0.0.1")
    INTENT_PATTERN: re.Pattern[str] = re.compile(
        r"\b(ssh|log\s?in|login|go\s+on|connect|run|execute|check)\b",
        re.IGNORECASE,
    )
    BACKTICK_PATTERN: re.Pattern[str] = re.compile(r"`([^`\n]+)`")
    MODULE_AVAIL_PATTERN: re.Pattern[str] = re.compile(
        r"\bmodule\s+(?:avail|avial)\b", re.IGNORECASE
    )

    def __init__(self, hosts: list[str]) -> None:
        """Initialize planner with known host aliases.

        Parameters
        ------------
        hosts: list[str]
            Known host aliases. Local aliases are ignored.

        Returns
        --------
            None: NoneType object
                Initializes planner state.
        """
        self._hosts: list[str] = [
            h for h in hosts if h.lower() not in self.LOCAL_ALIASES
        ]

    def _find_host(self, instruction: str) -> str | None:
        """Find the first known remote host named in the instruction.

        Parameters
        ------------
        instruction: str
            Task instruction text.

        Returns
        --------
            str | None: string object
                Matching host alias, or None if no host is mentioned.
        """
        for host in self._hosts:
            names: list[str] = [host]
            short_name: str = host.split(".")[0]
            if not host.replace(".", "").isdigit() and short_name != host:
                names.append(short_name)
            for name in names:
                pattern: str = rf"(?<![\w-]){re.escape(name)}(?![\w-])"
                if re.search(pattern, instruction, re.IGNORECASE):
                    return host
        return None

    def _extract_command(self, instruction: str) -> str | None:
        """Extract a runnable shell command from the instruction.

        Backtick-quoted text wins. Otherwise a ``module avail`` request
        (including the common ``module avial`` typo) is recognized.

        Parameters
        ------------
        instruction: str
            Task instruction text.

        Returns
        --------
            str | None: string object
                Shell command, or None if none could be extracted.
        """
        quoted: re.Match[str] | None = self.BACKTICK_PATTERN.search(
            instruction
        )
        if quoted is not None:
            return quoted.group(1).strip()
        module_match: re.Match[str] | None = (
            self.MODULE_AVAIL_PATTERN.search(instruction)
        )
        if module_match is not None:
            return "module avail 2>&1"
        return None

    def detect(self, instruction: str) -> RemoteIntent | None:
        """Detect remote execution intent in an instruction.

        Parameters
        ------------
        instruction: str
            Task instruction text.

        Returns
        --------
            RemoteIntent | None: RemoteIntent instance
                Intent when a remote host is named alongside an action or
                command, otherwise None.
        """
        if self.OUTPUT_MARKER in instruction:
            return None
        host: str | None = self._find_host(instruction)
        if host is None:
            return None
        command: str | None = self._extract_command(instruction)
        if command is None and self.INTENT_PATTERN.search(instruction) is None:
            return None
        return RemoteIntent(host=host, command=command)


__all__: list[str] = [
    "RemoteIntent",
    "RemoteProbePlanner",
]
