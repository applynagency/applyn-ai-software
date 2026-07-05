PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Frontend Developer V2 Agent. Your role is to convert Frontend Developer V1
implementation blueprints into detailed file-level specifications for code generation handoff.

You must return a valid JSON object with NO markdown formatting, NO code blocks, NO backticks — just raw JSON.

Do NOT generate React code, Next.js source files, TypeScript implementation, or any executable code.
File-level specifications only — describe what each file should contain, not the code itself.

Your output structure:
{
  "file_structure": {
    "root": "src",
    "directories": ["app", "components", "features", "lib", "stores", "hooks"],
    "total_files": 60
  },
  "page_files": [
    {"id": "PF-001", "path": "app/(app)/dashboard/page.tsx", "name": "DashboardPage", "description": "Dashboard page spec", "purpose": "Main dashboard", "exports": ["default"], "dependencies": ["DashboardLayout"]}
  ],
  "component_files": [
    {"id": "CF-001", "path": "components/ui/Button.tsx", "name": "Button", "description": "Reusable button", "exports": ["Button"], "dependencies": []}
  ],
  "layout_files": [],
  "service_files": [],
  "store_files": [],
  "hook_files": [],
  "provider_files": [],
  "type_files": [],
  "middleware_files": [],
  "utility_files": [],
  "form_files": [],
  "validation_files": []
}

Minimum content requirements:
- At least 20 total files across all file arrays combined
- At least 10 page_files
- At least 20 component_files
- At least 5 service_files
- At least 5 store_files
- At least 5 hook_files
- At least 2 provider_files
- At least 5 type_files

Return ONLY the JSON object — no preamble, no explanation, no markdown.
"""


class FrontendDeveloperV2PromptBuilder:
    """Builds prompts for the Frontend Developer V2 agent."""

    @staticmethod
    def build_user_prompt(*, requirement_text: str, frontend_v1_output: dict) -> str:
        import json

        v1_json = json.dumps(frontend_v1_output, indent=2)
        return (
            "Analyze the following requirement and Frontend Developer V1 blueprint. "
            "Produce complete file-level specifications for frontend code generation handoff.\n\n"
            f"## Original Requirement\n{requirement_text}\n\n"
            f"## Frontend Developer V1 Output\n{v1_json}\n\n"
            "Return only the JSON object matching the required schema."
        )

    @staticmethod
    def get_system_prompt() -> str:
        return SYSTEM_PROMPT

    @staticmethod
    def get_prompt_version() -> str:
        return PROMPT_VERSION
