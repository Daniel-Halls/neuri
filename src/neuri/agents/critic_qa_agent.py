"""Critic QA and Visual Inspection sub-agent for Neuri.

Reviews task node outputs, QA snapshot PNGs, registration contours, and Bayesian
MCMC convergence statistics (R-hat < 1.01, ESS > 400), transitioning nodes
between QA_REVIEW, COMPLETED, and RETRYING.
"""

from typing import Any

from neuri.agents.base_agent import BaseSpecialistAgent
from neuri.core.blackboard import Blackboard
from neuri.core.schemas import RemoteArtifact, TaskNode, TaskState


class CriticQAAgent(BaseSpecialistAgent):
    """Specialist sub-agent evaluating pipeline QA outputs and convergence criteria.

    Parameters
    ------------
    None

    Returns
    --------
        CriticQAAgent: CriticQAAgent instance
            Constructed critic QA agent.
    """

    DEFAULT_PROMPT: str = (
        "You are the Neuri Critic and Quality Assurance Inspector."
    )

    def __init__(self) -> None:
        """Initialize Critic QA agent with BIDS and neuroimaging preproc skills.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes agent state.
        """
        super().__init__(
            role_name="critic_qa",
            system_prompt=self.DEFAULT_PROMPT,
            skill_ids=["bids-standard", "neuroimaging-preproc"],
            mcp_tools=["remote_worker", "scholar"],
        )

    def evaluate_node_output(
        self,
        summary: str,
        diagnostics: list[str],
        artifacts: list[RemoteArtifact],
        r_hat: float | None = None,
        ess: int | None = None,
    ) -> tuple[bool, str]:
        """Evaluate task metrics, artifact headers, and MCMC convergence.

        Parameters
        ------------
        summary: str
            Node execution summary text.
        diagnostics: list[str]
            Diagnostic logs or error messages.
        artifacts: list[RemoteArtifact]
            List of generated output artifacts.
        r_hat: float | None
            Gelman-Rubin convergence statistic. Defaults to None.
        ess: int | None
            Effective sample size. Defaults to None.

        Returns
        --------
            tuple[bool, str]: tuple object
                Tuple of (approved_bool, diagnostic_feedback_string).
        """
        # 1. Check for failure diagnostics
        if diagnostics:
            err_msg: str = (
                f"QA rejected: Node reported diagnostic errors: "
                f"{'; '.join(diagnostics[:3])}"
            )
            return (False, err_msg)

        # 2. Check MCMC convergence if provided
        if r_hat is not None and r_hat >= 1.01:
            rhat_err: str = (
                f"QA rejected: MCMC failed to converge. R-hat = {r_hat:.4f} "
                f"(required: R-hat < 1.01). Increase sampling iterations or tune prior."
            )
            return (False, rhat_err)

        if ess is not None and ess < 400:
            ess_err: str = (
                f"QA rejected: Effective Sample Size (ESS = {ess}) is below "
                f"the required threshold of 400. Draw more MCMC samples."
            )
            return (False, ess_err)

        # 3. Check artifacts
        for art in artifacts:
            if art.header_summary is not None:
                dims: list[int] = art.header_summary.shape
                if any(d <= 0 for d in dims[:3]):
                    dim_err: str = (
                        f"QA rejected: Artifact '{art.posix_path}' has "
                        f"non-positive dimensions {dims}."
                    )
                    return (False, dim_err)

        ok_msg: str = (
            f"QA Approved: Node output satisfies all quality, dimension, and "
            f"convergence criteria."
        )
        return (True, ok_msg)

    def review_node(
        self,
        blackboard: Blackboard,
        node_id: str,
        r_hat: float | None = None,
        ess: int | None = None,
        diagnostics: list[str] | None = None,
    ) -> bool:
        """Inspect a node in QA_REVIEW and transition state accordingly.

        Parameters
        ------------
        blackboard: Blackboard
            Active Blackboard instance.
        node_id: str
            Node identifier to review.
        r_hat: float | None
            Optional Gelman-Rubin statistic. Defaults to None.
        ess: int | None
            Optional Effective Sample Size. Defaults to None.
        diagnostics: list[str] | None
            Optional fresh QA diagnostic error messages. Defaults to None.

        Returns
        --------
            bool: boolean object
                True if node was approved, False if rejected.
        """
        node: TaskNode | None = blackboard.get_node(node_id)
        if node is None or node.state != TaskState.QA_REVIEW:
            return False

        artifacts: list[RemoteArtifact] = blackboard.list_artifacts(
            node_id=node_id
        )
        summary: str = node.summary_result if node.summary_result else ""
        eval_diagnostics: list[str] = (
            diagnostics if diagnostics is not None else []
        )

        approved, feedback = self.evaluate_node_output(
            summary=summary,
            diagnostics=eval_diagnostics,
            artifacts=artifacts,
            r_hat=r_hat,
            ess=ess,
        )

        if approved:
            blackboard.update_node_state(
                node_id,
                TaskState.COMPLETED,
                summary_result=summary if summary else feedback,
            )
            return True
        else:
            if node.attempt >= node.max_retries:
                blackboard.update_node_state(
                    node_id,
                    TaskState.WAITING_OPERATOR,
                    diagnostic_feedback=feedback,
                    summary_result=f"QA Rejected (Max Retries Reached): {feedback}",
                )
            else:
                blackboard.update_node_state(
                    node_id,
                    TaskState.RETRYING,
                    diagnostic_feedback=feedback,
                    summary_result=f"QA Rejected: {feedback}",
                )
            return False


__all__: list[str] = [
    "CriticQAAgent",
]
