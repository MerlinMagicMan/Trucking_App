"""
Infrastructure context extraction for DevOps context injection.
"""

import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class RailwayConfig:
    """Railway deployment configuration."""
    services: List[str] = field(default_factory=list)
    build_command: str = ""
    start_command: str = ""
    health_check_path: str = ""
    environment_variables: List[str] = field(default_factory=list)


@dataclass
class GitHubWorkflow:
    """GitHub Actions workflow configuration."""
    name: str
    file_path: str
    triggers: List[str] = field(default_factory=list)
    jobs: List[str] = field(default_factory=list)


def extract_railway_config(project_root: Path | None = None) -> RailwayConfig | None:
    """Extract Railway configuration from railway.toml or railway.json."""
    if project_root is None:
        project_root = Path("/workspaces/Trucking_App")

    config = RailwayConfig()

    # Check for railway.toml
    toml_path = project_root / "railway.toml"
    if toml_path.exists():
        try:
            content = toml_path.read_text()

            # Extract build command
            match = re.search(r'buildCommand\s*=\s*"([^"]+)"', content)
            if match:
                config.build_command = match.group(1)

            # Extract start command
            match = re.search(r'startCommand\s*=\s*"([^"]+)"', content)
            if match:
                config.start_command = match.group(1)

            # Extract health check
            match = re.search(r'healthcheckPath\s*=\s*"([^"]+)"', content)
            if match:
                config.health_check_path = match.group(1)

            return config
        except Exception:
            pass

    # Check for railway.json
    json_path = project_root / "railway.json"
    if json_path.exists():
        try:
            import json
            data = json.loads(json_path.read_text())
            if "build" in data:
                config.build_command = data["build"].get("buildCommand", "")
            if "deploy" in data:
                config.start_command = data["deploy"].get("startCommand", "")
                config.health_check_path = data["deploy"].get("healthcheckPath", "")
            return config
        except Exception:
            pass

    return None


def extract_github_workflows(project_root: Path | None = None) -> List[GitHubWorkflow]:
    """Extract GitHub Actions workflow configurations."""
    if project_root is None:
        project_root = Path("/workspaces/Trucking_App")

    workflows_dir = project_root / ".github" / "workflows"
    workflows = []

    if not workflows_dir.exists():
        return workflows

    for yaml_file in workflows_dir.glob("*.yml"):
        try:
            content = yaml_file.read_text()

            # Extract name
            name_match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
            name = name_match.group(1).strip() if name_match else yaml_file.stem

            # Extract triggers (on:)
            triggers = []
            on_match = re.search(r'^on:\s*\n((?:\s+.+\n)+)', content, re.MULTILINE)
            if on_match:
                trigger_block = on_match.group(1)
                trigger_matches = re.findall(r'^\s+(\w+):', trigger_block, re.MULTILINE)
                triggers.extend(trigger_matches)

            # Extract jobs
            jobs = []
            jobs_match = re.search(r'^jobs:\s*\n((?:\s+.+\n)+)', content, re.MULTILINE)
            if jobs_match:
                jobs_block = jobs_match.group(1)
                job_matches = re.findall(r'^\s{2}(\w+):', jobs_block, re.MULTILINE)
                jobs.extend(job_matches)

            workflows.append(GitHubWorkflow(
                name=name,
                file_path=str(yaml_file),
                triggers=triggers,
                jobs=jobs,
            ))
        except Exception:
            continue

    return workflows


def extract_env_template(project_root: Path | None = None) -> List[str]:
    """Extract environment variables from .env.example or similar."""
    if project_root is None:
        project_root = Path("/workspaces/Trucking_App")

    env_vars = []

    for env_file in [".env.example", ".env.template", ".env.sample"]:
        env_path = project_root / env_file
        if env_path.exists():
            try:
                content = env_path.read_text()
                # Extract variable names
                matches = re.findall(r'^([A-Z_]+)\s*=', content, re.MULTILINE)
                env_vars.extend(matches)
            except Exception:
                continue

    # Also check backend directory
    backend_env = project_root / "backend" / ".env.example"
    if backend_env.exists():
        try:
            content = backend_env.read_text()
            matches = re.findall(r'^([A-Z_]+)\s*=', content, re.MULTILINE)
            env_vars.extend(matches)
        except Exception:
            pass

    return list(set(env_vars))


def format_infrastructure_for_prompt(
    railway_config: RailwayConfig | None,
    workflows: List[GitHubWorkflow],
    env_vars: List[str],
) -> str:
    """Format infrastructure info for injection into agent prompts."""
    lines = ["## Infrastructure Configuration\n"]

    # Railway
    lines.append("### Railway Deployment\n")
    if railway_config:
        if railway_config.build_command:
            lines.append(f"- Build: `{railway_config.build_command}`")
        if railway_config.start_command:
            lines.append(f"- Start: `{railway_config.start_command}`")
        if railway_config.health_check_path:
            lines.append(f"- Health check: `{railway_config.health_check_path}`")
    else:
        lines.append("No railway.toml found.")
    lines.append("")

    # GitHub Actions
    lines.append("### GitHub Workflows\n")
    if workflows:
        for wf in workflows:
            lines.append(f"- **{wf.name}** (`{Path(wf.file_path).name}`)")
            if wf.triggers:
                lines.append(f"  - Triggers: {', '.join(wf.triggers)}")
            if wf.jobs:
                lines.append(f"  - Jobs: {', '.join(wf.jobs)}")
    else:
        lines.append("No GitHub workflows found.")
    lines.append("")

    # Environment variables
    lines.append("### Environment Variables\n")
    if env_vars:
        for var in sorted(env_vars):
            lines.append(f"- `{var}`")
    else:
        lines.append("No environment template found.")

    return "\n".join(lines)


def get_infrastructure_summary() -> str:
    """Get a formatted summary of infrastructure configuration."""
    railway = extract_railway_config()
    workflows = extract_github_workflows()
    env_vars = extract_env_template()
    return format_infrastructure_for_prompt(railway, workflows, env_vars)
