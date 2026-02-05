"""
Context loaders for extracting actual codebase state.
"""

from .schema import extract_sqlalchemy_models, get_schema_summary
from .routes import extract_fastapi_routes, get_routes_summary
from .frontend import extract_react_components, get_frontend_summary
from .infrastructure import extract_railway_config, get_infrastructure_summary
from .product_boundaries import get_module_boundaries, format_boundaries_for_prompt

__all__ = [
    "extract_sqlalchemy_models",
    "extract_fastapi_routes",
    "extract_react_components",
    "extract_railway_config",
    "get_module_boundaries",
    "get_schema_summary",
    "get_routes_summary",
    "get_frontend_summary",
    "get_infrastructure_summary",
    "format_boundaries_for_prompt",
]
