"""
SQLAlchemy model extraction for context injection.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class ColumnInfo:
    """Information about a SQLAlchemy column."""
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    foreign_key: str | None = None
    index: bool = False
    unique: bool = False
    default: str | None = None


@dataclass
class ModelInfo:
    """Information about a SQLAlchemy model."""
    name: str
    table_name: str
    file_path: str
    columns: List[ColumnInfo] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)


def _parse_column_call(node: ast.Call) -> ColumnInfo | None:
    """Parse a Column() call to extract column info."""
    if not isinstance(node.func, ast.Name) or node.func.id != "Column":
        return None

    info = ColumnInfo(name="", type="unknown")

    # First positional arg is usually the type
    if node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Name):
            info.type = first_arg.id
        elif isinstance(first_arg, ast.Call):
            if isinstance(first_arg.func, ast.Name):
                info.type = first_arg.func.id
            elif isinstance(first_arg.func, ast.Attribute):
                info.type = first_arg.func.attr

    # Parse keywords
    for kw in node.keywords:
        if kw.arg == "nullable":
            info.nullable = isinstance(kw.value, ast.Constant) and kw.value.value
        elif kw.arg == "primary_key":
            info.primary_key = isinstance(kw.value, ast.Constant) and kw.value.value
        elif kw.arg == "index":
            info.index = isinstance(kw.value, ast.Constant) and kw.value.value
        elif kw.arg == "unique":
            info.unique = isinstance(kw.value, ast.Constant) and kw.value.value
        elif kw.arg == "default":
            if isinstance(kw.value, ast.Constant):
                info.default = str(kw.value.value)

    # Check for ForeignKey in args
    for arg in node.args:
        if isinstance(arg, ast.Call):
            if isinstance(arg.func, ast.Name) and arg.func.id == "ForeignKey":
                if arg.args and isinstance(arg.args[0], ast.Constant):
                    info.foreign_key = arg.args[0].value

    return info


def _extract_table_name(node: ast.ClassDef) -> str | None:
    """Extract __tablename__ from a class."""
    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "__tablename__":
                    if isinstance(item.value, ast.Constant):
                        return item.value.value
    return None


def _is_sqlalchemy_model(node: ast.ClassDef) -> bool:
    """Check if a class is a SQLAlchemy model."""
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Base":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Base":
            return True
    return False


def parse_model_file(file_path: Path) -> List[ModelInfo]:
    """Parse a Python file to extract SQLAlchemy model information."""
    models = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content)
    except (SyntaxError, FileNotFoundError):
        return models

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_sqlalchemy_model(node):
            table_name = _extract_table_name(node)
            if not table_name:
                continue

            model = ModelInfo(
                name=node.name,
                table_name=table_name,
                file_path=str(file_path),
            )

            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                            col_info = _parse_column_call(item.value)
                            if col_info:
                                col_info.name = target.id
                                model.columns.append(col_info)

                            # Check for relationship
                            if isinstance(item.value.func, ast.Name):
                                if item.value.func.id == "relationship":
                                    model.relationships.append(target.id)

            models.append(model)

    return models


def extract_sqlalchemy_models(backend_root: Path | None = None) -> Dict[str, ModelInfo]:
    """
    Extract all SQLAlchemy models from the backend.

    Returns:
        Dict mapping model name to ModelInfo
    """
    if backend_root is None:
        backend_root = Path("/workspaces/Trucking_App/backend")

    models_dir = backend_root / "app" / "models"
    all_models: Dict[str, ModelInfo] = {}

    if not models_dir.exists():
        return all_models

    for py_file in models_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        file_models = parse_model_file(py_file)
        for model in file_models:
            all_models[model.name] = model

    return all_models


def format_models_for_prompt(models: Dict[str, ModelInfo]) -> str:
    """Format models for injection into agent prompts."""
    if not models:
        return "No SQLAlchemy models found."

    lines = ["## Current SQLAlchemy Models\n"]

    for name, model in sorted(models.items()):
        lines.append(f"### {name} (table: `{model.table_name}`)")
        lines.append(f"File: `{model.file_path}`\n")

        if model.columns:
            lines.append("**Columns:**")
            for col in model.columns:
                flags = []
                if col.primary_key:
                    flags.append("PK")
                if col.foreign_key:
                    flags.append(f"FK→{col.foreign_key}")
                if col.index:
                    flags.append("indexed")
                if col.unique:
                    flags.append("unique")
                if not col.nullable:
                    flags.append("NOT NULL")

                flag_str = f" ({', '.join(flags)})" if flags else ""
                lines.append(f"- `{col.name}`: {col.type}{flag_str}")

        if model.relationships:
            lines.append("\n**Relationships:**")
            for rel in model.relationships:
                lines.append(f"- `{rel}`")

        lines.append("")

    return "\n".join(lines)


def get_schema_summary() -> str:
    """Get a formatted summary of the current schema."""
    models = extract_sqlalchemy_models()
    return format_models_for_prompt(models)
