"""
Frontend Developer Agent - Owns React components and UX.
"""

from typing import Dict, Any, List
from pathlib import Path

from ..types import AgentRole, Task, Message, Module
from ..context.frontend import extract_react_components
from ..context.product_boundaries import MODULE_BOUNDARIES
from .base import ImplementerAgent, AgentResponse


class FrontendDevAgent(ImplementerAgent):
    """
    Frontend Developer owns React components and TypeScript types.

    Must follow:
    - No premium UI in base tier (cosmetic gating)
    - Frontend entitlements are NOT security boundary
    - Money as strings (Decimal serialization)
    """

    def __init__(self):
        super().__init__(AgentRole.FRONTEND_DEV)
        self.frontend_root = Path("/workspaces/Trucking_App/frontend")

    async def implement(self, task: Task) -> AgentResponse:
        """Implement a frontend task."""
        self.log(f"Implementing: {task.description}")

        # Analyze what's needed
        approach = self._plan_implementation(task)

        return AgentResponse(
            success=True,
            message="Frontend implementation plan ready",
            data={
                "task_id": task.id,
                "approach": approach,
                "components_to_create": approach.get("new_components", []),
                "components_to_modify": approach.get("modify_components", []),
                "types_needed": approach.get("types", []),
                "api_calls_needed": approach.get("api_calls", []),
            },
        )

    def _plan_implementation(self, task: Task) -> Dict[str, Any]:
        """Plan the frontend implementation."""
        desc_lower = task.description.lower()
        plan: Dict[str, Any] = {
            "new_components": [],
            "modify_components": [],
            "types": [],
            "api_calls": [],
            "entitlement_gated": False,
        }

        # Check if this is a premium feature
        if task.module:
            boundary = MODULE_BOUNDARIES.get(task.module)
            if boundary and boundary.tier.value != "base":
                plan["entitlement_gated"] = True
                plan["entitlement_module"] = task.module.value

        # Determine components needed
        if "page" in desc_lower:
            plan["new_components"].append({
                "type": "page",
                "path": "src/pages/",
            })
        elif "component" in desc_lower or "section" in desc_lower:
            plan["new_components"].append({
                "type": "component",
                "path": "src/components/",
            })

        return plan

    def generate_component_template(
        self,
        component_name: str,
        module: Module,
        entitlement_gated: bool = False,
        props: List[str] | None = None,
    ) -> str:
        """Generate a React component template."""
        props_interface = ""
        props_destructure = ""

        if props:
            props_interface = f'''
interface {component_name}Props {{
  {chr(10).join(f"  {p}: string;" for p in props)}
}}
'''
            props_destructure = f"{{ {', '.join(props)} }}: {component_name}Props"
        else:
            props_destructure = ""

        entitlement_import = ""
        entitlement_check = ""

        if entitlement_gated:
            entitlement_import = """
import { useEntitlement } from '../hooks/useEntitlement';
import { Module } from '../types/entitlements';
import { UpgradePrompt } from './UpgradePrompt';
"""
            entitlement_check = f'''
  const hasAccess = useEntitlement(Module.{module.value});

  if (!hasAccess) {{
    return <UpgradePrompt module="{module.value}" feature="{component_name}" />;
  }}
'''

        return f'''import React from 'react';
{entitlement_import}
{props_interface}
export const {component_name}: React.FC{f"<{component_name}Props>" if props else ""} = ({props_destructure}) => {{
{entitlement_check}
  return (
    <div className="{component_name.lower().replace("_", "-")}">
      {{/* TODO: Implement {component_name} */}}
    </div>
  );
}};
'''

    def generate_api_service_template(
        self,
        function_name: str,
        endpoint: str,
        method: str = "GET",
        return_type: str = "unknown",
    ) -> str:
        """Generate an API service function template."""
        return f'''
export const {function_name} = async (
  // TODO: Add parameters
): Promise<{return_type} | null> => {{
  try {{
    const response = await api.{method.lower()}<{return_type}>('{endpoint}');
    return response.data;
  }} catch {{
    return null;  // Graceful degradation
  }}
}};
'''

    def generate_type_template(
        self,
        type_name: str,
        fields: Dict[str, str],
    ) -> str:
        """Generate a TypeScript interface template."""
        field_lines = "\n".join(f"  {name}: {typ};" for name, typ in fields.items())
        return f'''export interface {type_name} {{
{field_lines}
}}
'''

    async def handle_message(self, message: Message) -> AgentResponse:
        """Handle messages from other agents."""
        self.log(f"Message from {message.from_agent.value}: {message.subject}")

        if "template" in message.subject.lower():
            if "component" in message.content.lower():
                template = self.generate_component_template(
                    component_name="ExampleComponent",
                    module=Module.TRUCK_CORE,
                )
                return AgentResponse(
                    success=True,
                    message="Component template generated",
                    data={"template": template},
                )

        return AgentResponse(
            success=True,
            message="Message acknowledged",
        )
