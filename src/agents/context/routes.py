"""
FastAPI route extraction for context injection.
"""

import ast
import re
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class RouteInfo:
    """Information about a FastAPI route."""
    method: str
    path: str
    function_name: str
    file_path: str
    line_number: int
    parameters: List[str] = field(default_factory=list)
    response_model: str | None = None
    tags: List[str] = field(default_factory=list)
    docstring: str | None = None


def _extract_decorator_route(node: ast.FunctionDef, file_path: str) -> RouteInfo | None:
    """Extract route info from function decorators."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                method = decorator.func.attr
                if method in ("get", "post", "put", "patch", "delete"):
                    path = ""
                    response_model = None
                    tags = []

                    # Get path from first argument
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value

                    # Get response_model and tags from keywords
                    for kw in decorator.keywords:
                        if kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                            response_model = kw.value.id
                        elif kw.arg == "tags" and isinstance(kw.value, ast.List):
                            for elt in kw.value.elts:
                                if isinstance(elt, ast.Constant):
                                    tags.append(elt.value)

                    # Extract parameters
                    params = []
                    for arg in node.args.args:
                        if arg.arg not in ("self", "request", "db"):
                            params.append(arg.arg)

                    # Get docstring
                    docstring = ast.get_docstring(node)

                    return RouteInfo(
                        method=method.upper(),
                        path=path,
                        function_name=node.name,
                        file_path=file_path,
                        line_number=node.lineno,
                        parameters=params,
                        response_model=response_model,
                        tags=tags,
                        docstring=docstring,
                    )
    return None


def parse_route_file(file_path: Path) -> List[RouteInfo]:
    """Parse a Python file to extract FastAPI route information."""
    routes = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except (SyntaxError, FileNotFoundError):
        return routes

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            route_info = _extract_decorator_route(node, str(file_path))
            if route_info:
                routes.append(route_info)

    return routes


def extract_router_prefix(file_path: Path) -> str:
    """Extract the router prefix from a route file."""
    try:
        content = file_path.read_text()
        # Look for APIRouter instantiation with prefix
        match = re.search(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    except FileNotFoundError:
        pass
    return ""


def extract_fastapi_routes(backend_root: Path | None = None) -> Dict[str, List[RouteInfo]]:
    """
    Extract all FastAPI routes from the backend.

    Returns:
        Dict mapping file path to list of routes
    """
    if backend_root is None:
        backend_root = Path("/workspaces/Trucking_App/backend")

    api_dir = backend_root / "app" / "api"
    all_routes: Dict[str, List[RouteInfo]] = {}

    if not api_dir.exists():
        return all_routes

    for py_file in api_dir.glob("*_routes.py"):
        file_routes = parse_route_file(py_file)
        if file_routes:
            # Get router prefix
            prefix = extract_router_prefix(py_file)
            # Update paths with prefix
            for route in file_routes:
                if prefix and not route.path.startswith(prefix):
                    route.path = prefix + route.path
            all_routes[str(py_file)] = file_routes

    # Also check routes.py
    main_routes = backend_root / "app" / "api" / "routes.py"
    if main_routes.exists():
        file_routes = parse_route_file(main_routes)
        if file_routes:
            all_routes[str(main_routes)] = file_routes

    return all_routes


def format_routes_for_prompt(routes: Dict[str, List[RouteInfo]]) -> str:
    """Format routes for injection into agent prompts."""
    if not routes:
        return "No FastAPI routes found."

    lines = ["## Current FastAPI Routes\n"]

    for file_path, file_routes in sorted(routes.items()):
        file_name = Path(file_path).name
        lines.append(f"### {file_name}\n")

        for route in sorted(file_routes, key=lambda r: (r.path, r.method)):
            method_badge = f"**{route.method}**"
            lines.append(f"- {method_badge} `{route.path}` → `{route.function_name}()`")

            if route.parameters:
                lines.append(f"  - Params: {', '.join(route.parameters)}")
            if route.response_model:
                lines.append(f"  - Response: `{route.response_model}`")
            if route.docstring:
                # Truncate long docstrings
                doc = route.docstring.split("\n")[0][:80]
                lines.append(f"  - {doc}")

        lines.append("")

    return "\n".join(lines)


def get_routes_summary() -> str:
    """Get a formatted summary of the current routes."""
    routes = extract_fastapi_routes()
    return format_routes_for_prompt(routes)
