"""
React component extraction for context injection.
"""

import re
from pathlib import Path
from typing import Dict, List, Set
from dataclasses import dataclass, field


@dataclass
class ComponentInfo:
    """Information about a React component."""
    name: str
    file_path: str
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    props: List[str] = field(default_factory=list)
    hooks_used: List[str] = field(default_factory=list)
    is_page: bool = False


@dataclass
class TypeInfo:
    """Information about a TypeScript type/interface."""
    name: str
    file_path: str
    kind: str  # interface, type, enum


def extract_component_name(content: str, file_path: str) -> List[str]:
    """Extract component names from file content."""
    components = []

    # Match export const ComponentName = ...
    const_exports = re.findall(
        r'export\s+const\s+(\w+)\s*[:=]\s*(?:React\.)?(?:FC|FunctionComponent|memo)',
        content
    )
    components.extend(const_exports)

    # Match export function ComponentName
    func_exports = re.findall(
        r'export\s+function\s+(\w+)\s*[<(]',
        content
    )
    components.extend(func_exports)

    # Match export default function ComponentName
    default_exports = re.findall(
        r'export\s+default\s+function\s+(\w+)',
        content
    )
    components.extend(default_exports)

    # Match const ComponentName: React.FC = ... followed by export
    named_components = re.findall(
        r'(?:const|function)\s+(\w+)\s*[:=]\s*(?:React\.)?(?:FC|FunctionComponent)',
        content
    )

    # Filter to PascalCase (component convention)
    all_names = set(components + named_components)
    return [name for name in all_names if name[0].isupper()]


def extract_imports(content: str) -> List[str]:
    """Extract import statements."""
    imports = []

    # Match import { X } from 'Y' or import X from 'Y'
    import_matches = re.findall(
        r"import\s+(?:{([^}]+)}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]",
        content
    )

    for named, default, source in import_matches:
        if named:
            imports.extend([n.strip() for n in named.split(",")])
        if default:
            imports.append(default)

    return imports


def extract_hooks(content: str) -> List[str]:
    """Extract React hooks used in the component."""
    hooks = set()

    # Match use* function calls
    hook_matches = re.findall(r'\b(use[A-Z]\w+)\s*\(', content)
    hooks.update(hook_matches)

    return sorted(hooks)


def extract_props(content: str, component_name: str) -> List[str]:
    """Extract props interface for a component."""
    props = []

    # Look for interface ComponentNameProps
    pattern = rf'interface\s+{component_name}Props\s*\{{\s*([^}}]+)\}}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        props_content = match.group(1)
        # Extract property names
        prop_matches = re.findall(r'(\w+)\s*[?]?\s*:', props_content)
        props.extend(prop_matches)

    return props


def parse_component_file(file_path: Path) -> ComponentInfo | None:
    """Parse a React component file."""
    try:
        content = file_path.read_text()
    except FileNotFoundError:
        return None

    components = extract_component_name(content, str(file_path))
    if not components:
        return None

    # Use the main component (usually matches filename)
    file_stem = file_path.stem
    main_component = next(
        (c for c in components if c.lower() == file_stem.lower().replace("page", "")),
        components[0] if components else file_stem
    )

    return ComponentInfo(
        name=main_component,
        file_path=str(file_path),
        exports=components,
        imports=extract_imports(content),
        props=extract_props(content, main_component),
        hooks_used=extract_hooks(content),
        is_page="Page" in file_path.name or "pages" in str(file_path),
    )


def extract_types(file_path: Path) -> List[TypeInfo]:
    """Extract TypeScript type definitions."""
    types = []

    try:
        content = file_path.read_text()
    except FileNotFoundError:
        return types

    # Match export interface Name
    interfaces = re.findall(r'export\s+interface\s+(\w+)', content)
    for name in interfaces:
        types.append(TypeInfo(name=name, file_path=str(file_path), kind="interface"))

    # Match export type Name
    type_aliases = re.findall(r'export\s+type\s+(\w+)', content)
    for name in type_aliases:
        types.append(TypeInfo(name=name, file_path=str(file_path), kind="type"))

    # Match export enum Name
    enums = re.findall(r'export\s+enum\s+(\w+)', content)
    for name in enums:
        types.append(TypeInfo(name=name, file_path=str(file_path), kind="enum"))

    return types


def extract_react_components(frontend_root: Path | None = None) -> Dict[str, ComponentInfo]:
    """
    Extract all React components from the frontend.

    Returns:
        Dict mapping component name to ComponentInfo
    """
    if frontend_root is None:
        frontend_root = Path("/workspaces/Trucking_App/frontend")

    src_dir = frontend_root / "src"
    all_components: Dict[str, ComponentInfo] = {}

    if not src_dir.exists():
        return all_components

    # Scan for .tsx files
    for tsx_file in src_dir.rglob("*.tsx"):
        if "node_modules" in str(tsx_file):
            continue

        component = parse_component_file(tsx_file)
        if component:
            all_components[component.name] = component

    return all_components


def extract_typescript_types(frontend_root: Path | None = None) -> Dict[str, TypeInfo]:
    """
    Extract all TypeScript types from the frontend.

    Returns:
        Dict mapping type name to TypeInfo
    """
    if frontend_root is None:
        frontend_root = Path("/workspaces/Trucking_App/frontend")

    types_dir = frontend_root / "src" / "types"
    all_types: Dict[str, TypeInfo] = {}

    if not types_dir.exists():
        return all_types

    for ts_file in types_dir.glob("*.ts"):
        file_types = extract_types(ts_file)
        for t in file_types:
            all_types[t.name] = t

    return all_types


def format_components_for_prompt(components: Dict[str, ComponentInfo]) -> str:
    """Format components for injection into agent prompts."""
    if not components:
        return "No React components found."

    lines = ["## Current React Components\n"]

    # Group by type
    pages = [c for c in components.values() if c.is_page]
    other = [c for c in components.values() if not c.is_page]

    if pages:
        lines.append("### Pages\n")
        for comp in sorted(pages, key=lambda c: c.name):
            lines.append(f"- **{comp.name}** (`{comp.file_path}`)")
            if comp.hooks_used:
                lines.append(f"  - Hooks: {', '.join(comp.hooks_used[:5])}")
        lines.append("")

    if other:
        lines.append("### Components\n")
        for comp in sorted(other, key=lambda c: c.name):
            rel_path = Path(comp.file_path).relative_to(
                Path("/workspaces/Trucking_App/frontend")
            ) if "/workspaces" in comp.file_path else comp.file_path
            lines.append(f"- **{comp.name}** (`{rel_path}`)")
            if comp.props:
                lines.append(f"  - Props: {', '.join(comp.props[:5])}")
        lines.append("")

    return "\n".join(lines)


def get_frontend_summary() -> str:
    """Get a formatted summary of the frontend."""
    components = extract_react_components()
    return format_components_for_prompt(components)
