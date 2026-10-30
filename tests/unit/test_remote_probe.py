"""Tests for Neuri-side remote execution and harness tool capability."""

from neuri.adapters.antigravity import AntigravityAdapter
from neuri.adapters.ollama_local import OllamaLocalAdapter
from neuri.remote.remote_probe import RemoteIntent, RemoteProbePlanner


class TestRemoteProbe:
    """Tests for RemoteProbePlanner and the supports_tools capability."""

    HOSTS: list[str] = ["localhost", "axon"]

    def test_supports_tools_flags(self) -> None:
        """Ollama is tool-less; agentic harnesses are tool-capable.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts capability flags.
        """
        assert OllamaLocalAdapter().supports_tools is False
        assert AntigravityAdapter().supports_tools is True

    def test_detects_module_avail_typo_on_axon(self) -> None:
        """The original failing prompt yields a runnable command.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts detected intent.
        """
        text: str = (
            "ok a test. You are to go on axon and tell me the two modules "
            "avaial for the brc_pipeline. Use module avial to do this."
        )
        intent: RemoteIntent | None = RemoteProbePlanner(self.HOSTS).detect(
            text
        )
        assert intent == RemoteIntent(host="axon", command="module avail 2>&1")

    def test_backtick_command_wins(self) -> None:
        """Backtick-quoted commands are used verbatim.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts extracted command.
        """
        intent: RemoteIntent | None = RemoteProbePlanner(self.HOSTS).detect(
            "ssh to axon and run `squeue -u me`"
        )
        assert intent == RemoteIntent(host="axon", command="squeue -u me")

    def test_intent_without_command(self) -> None:
        """Host plus action verb but no command gives command=None.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts intent without command.
        """
        intent: RemoteIntent | None = RemoteProbePlanner(self.HOSTS).detect(
            "go on axon and tidy things up"
        )
        assert intent == RemoteIntent(host="axon", command=None)

    def test_short_name_matches_fqdn_host(self) -> None:
        """A short name like 'axon' resolves to the registered FQDN alias.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts the full alias is returned.
        """
        fqdn: str = "axon.nottingham.ac.uk"
        intent: RemoteIntent | None = RemoteProbePlanner(
            ["localhost", fqdn]
        ).detect("go on axon and run module avail")
        assert intent == RemoteIntent(host=fqdn, command="module avail 2>&1")

    def test_no_intent_cases(self) -> None:
        """Unrelated, host-only, augmented and local texts are ignored.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts no intent is detected.
        """
        planner: RemoteProbePlanner = RemoteProbePlanner(self.HOSTS)
        marker: str = RemoteProbePlanner.OUTPUT_MARKER
        assert planner.detect("summarise this paper") is None
        assert planner.detect("axon is a cool name") is None
        assert planner.detect(f"run on axon {marker}: x]") is None
        assert planner.detect("run it on localhost") is None
