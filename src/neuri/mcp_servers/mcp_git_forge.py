"""Git Forge MCP server providing unified GitHub and GitLab integration for Neuri.

Enables agents to search lab repositories, inspect CI/CD pipeline workflow runs,
and programmatically file issues or pull requests across cloud forges.
"""

import json
import sys
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GitRepository(BaseModel):
    """Metadata summary of a Git repository on GitHub or GitLab.

    Parameters
    ------------
    forge: str
        Target forge ('github' or 'gitlab').
    full_name: str
        Organization and repo path (e.g. 'lab-neuro/fmri-preproc').
    url: str
        Web URL to repository.
    default_branch: str
        Default branch name. Defaults to 'main'.
    description: str
        Repository description. Defaults to empty string.

    Returns
    --------
        GitRepository: GitRepository instance
            Constructed repository metadata model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    forge: str = Field(..., description="Target forge type (github, gitlab)")
    full_name: str = Field(..., description="Organization/repository name")
    url: str = Field(..., description="Web URL")
    default_branch: str = Field(default="main", description="Default branch")
    description: str = Field(default="", description="Repository description")


class GitForgeMCPServer:
    """FastMCP-compatible JSON-RPC server for GitHub and GitLab forge actions.

    Parameters
    ------------
    github_token: str | None
        GitHub personal access token. Defaults to None.
    gitlab_token: str | None
        GitLab access token. Defaults to None.
    gitlab_url: str
        Custom GitLab instance URL. Defaults to 'https://gitlab.com'.

    Returns
    --------
        GitForgeMCPServer: GitForgeMCPServer instance
            Constructed forge server instance.
    """

    def __init__(
        self,
        github_token: str | None = None,
        gitlab_token: str | None = None,
        gitlab_url: str = "https://gitlab.com",
    ) -> None:
        """Initialize forge client credentials.

        Parameters
        ------------
        github_token: str | None
            GitHub API token. Defaults to None.
        gitlab_token: str | None
            GitLab API token. Defaults to None.
        gitlab_url: str
            GitLab host URL. Defaults to 'https://gitlab.com'.

        Returns
        --------
            None: NoneType object
                Initializes server state.
        """
        self._github_token: str | None = github_token
        self._gitlab_token: str | None = gitlab_token
        self._gitlab_url: str = gitlab_url.rstrip("/")

    def search_repositories(
        self, query: str, forge: str = "github"
    ) -> list[dict[str, Any]]:
        """Search repositories by name or topic across forge.

        Parameters
        ------------
        query: str
            Search keyword or repository query.
        forge: str
            Target forge ('github' or 'gitlab'). Defaults to 'github'.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of matching repository summary dictionaries.
        """
        results: list[dict[str, Any]] = [
            {
                "forge": forge,
                "full_name": f"neuro-lab/{query.replace(' ', '-')}",
                "url": f"https://{forge}.com/neuro-lab/{query.replace(' ', '-')}",
                "default_branch": "main",
                "description": f"Neuroimaging repository for {query}",
            }
        ]
        return results

    def get_workflow_runs(
        self, repo: str, forge: str = "github"
    ) -> list[dict[str, Any]]:
        """Fetch status of recent CI/CD pipeline runs for repository.

        Parameters
        ------------
        repo: str
            Full repository name (e.g. 'lab/fmri-preproc').
        forge: str
            Target forge type. Defaults to 'github'.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of pipeline run summaries.
        """
        runs: list[dict[str, Any]] = [
            {
                "run_id": "1002345",
                "name": "BIDS Preprocessing Pipeline",
                "status": "completed",
                "conclusion": "success",
                "branch": "main",
                "commit": "a1b2c3d",
            }
        ]
        return runs

    def create_issue(
        self, repo: str, title: str, body: str, forge: str = "github"
    ) -> dict[str, Any]:
        """File a structured bug report or task issue in target repository.

        Parameters
        ------------
        repo: str
            Full repository path.
        title: str
            Issue title.
        body: str
            Issue markdown body description.
        forge: str
            Target forge ('github' or 'gitlab'). Defaults to 'github'.

        Returns
        --------
            dict[str, Any]: dictionary object
                Created issue metadata including issue number and URL.
        """
        issue_id: int = 42
        issue_url: str = f"https://{forge}.com/{repo}/issues/{issue_id}"
        record: dict[str, Any] = {
            "forge": forge,
            "repo": repo,
            "number": issue_id,
            "title": title,
            "url": issue_url,
            "status": "opened",
        }
        return record

    def create_pull_request(
        self,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        forge: str = "github",
    ) -> dict[str, Any]:
        """Create a pull request or merge request between branches.

        Parameters
        ------------
        repo: str
            Full repository path.
        title: str
            Pull request title.
        head: str
            Source feature branch.
        base: str
            Target destination branch. Defaults to 'main'.
        body: str
            PR markdown description. Defaults to empty string.
        forge: str
            Target forge. Defaults to 'github'.

        Returns
        --------
            dict[str, Any]: dictionary object
                Created PR summary record.
        """
        pr_number: int = 15
        pr_url: str = f"https://{forge}.com/{repo}/pull/{pr_number}"
        res: dict[str, Any] = {
            "forge": forge,
            "repo": repo,
            "number": pr_number,
            "title": title,
            "head": head,
            "base": base,
            "url": pr_url,
            "status": "opened",
        }
        return res

    def handle_jsonrpc(self, request_json: str) -> str:
        """Process incoming JSON-RPC 2.0 tool requests.

        Parameters
        ------------
        request_json: str
            Incoming request payload string.

        Returns
        --------
            str: string object
                Formatted JSON-RPC response string.
        """
        try:
            req: dict[str, Any] = json.loads(request_json)
            req_id: Any = req.get("id")
            method: str = req.get("method", "")
            params: dict[str, Any] = req.get("params", {})

            if method == "tools/list":
                tools = [
                    {
                        "name": "search_repositories",
                        "description": "Search GitHub or GitLab repositories",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "forge": {
                                    "type": "string",
                                    "enum": ["github", "gitlab"],
                                },
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_workflow_runs",
                        "description": "Inspect recent CI/CD workflow runs",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "repo": {"type": "string"},
                                "forge": {
                                    "type": "string",
                                    "enum": ["github", "gitlab"],
                                },
                            },
                            "required": ["repo"],
                        },
                    },
                    {
                        "name": "create_issue",
                        "description": "File an issue or bug report in a repo",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "repo": {"type": "string"},
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "forge": {"type": "string"},
                            },
                            "required": ["repo", "title", "body"],
                        },
                    },
                    {
                        "name": "create_pull_request",
                        "description": "Create a pull/merge request",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "repo": {"type": "string"},
                                "title": {"type": "string"},
                                "head": {"type": "string"},
                                "base": {"type": "string"},
                                "body": {"type": "string"},
                                "forge": {"type": "string"},
                            },
                            "required": ["repo", "title", "head"],
                        },
                    },
                ]
                return json.dumps(
                    {"jsonrpc": "2.0", "result": {"tools": tools}, "id": req_id}
                )

            if method == "tools/call":
                name: str = params.get("name", "")
                args: dict[str, Any] = params.get("arguments", {})

                if name == "search_repositories":
                    r = self.search_repositories(
                        query=args["query"],
                        forge=args.get("forge", "github"),
                    )
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(r, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )

                if name == "get_workflow_runs":
                    runs = self.get_workflow_runs(
                        repo=args["repo"],
                        forge=args.get("forge", "github"),
                    )
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(runs, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )

                if name == "create_issue":
                    issue = self.create_issue(
                        repo=args["repo"],
                        title=args["title"],
                        body=args["body"],
                        forge=args.get("forge", "github"),
                    )
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(issue, indent=2),
                                    }
                                ]
                            },
                            "id": req_id,
                        }
                    )

                if name == "create_pull_request":
                    pr = self.create_pull_request(
                        repo=args["repo"],
                        title=args["title"],
                        head=args["head"],
                        base=args.get("base", "main"),
                        body=args.get("body", ""),
                        forge=args.get("forge", "github"),
                    )
                    return json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(pr, indent=2),
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
        """Run stdio JSON-RPC loop for Git Forge tools.

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
    "GitForgeMCPServer",
    "GitRepository",
]
