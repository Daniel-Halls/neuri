"""Hub-and-spoke remote execution fabric for Neuri.

Provides multiplexed SSH ControlMaster connections, automated remote worker
bootstrapping, asynchronous Slurm/tmux job detach-and-reconcile management,
and selective artifact synchronization.
"""

from neuri.remote.bootstrap import RemoteHostBootstrapper
from neuri.remote.monitor import RemoteHostMonitor
from neuri.remote.rsync_artifacts import ArtifactSyncManager
from neuri.remote.shell_executor import (
    ShellCommandExecutor,
    ShellExecutionResult,
)
from neuri.remote.slurm_bridge import DetachAndReconcileManager
from neuri.remote.ssh_pool import SSHControlMasterPool

__all__: list[str] = [
    "ArtifactSyncManager",
    "DetachAndReconcileManager",
    "RemoteHostBootstrapper",
    "RemoteHostMonitor",
    "SSHControlMasterPool",
    "ShellCommandExecutor",
    "ShellExecutionResult",
]
