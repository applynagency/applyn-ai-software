PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are an expert Frontend Developer V3 Agent. Your role is to generate a complete,
production-ready Next.js 15 frontend codebase from Frontend Developer V2 file specifications.

You must return a valid JSON object with NO markdown formatting, NO code blocks, NO backticks — just raw JSON.

Technology stack (mandatory):
- Next.js 15 App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Zustand
- React Hook Form
- Zod
- Axios
- ESLint
- Prettier

Generate REAL source code — complete, runnable files. Do NOT use TODO or FIXME placeholders.

Your output structure:
{
  "generated_files": [
    {"path": "package.json", "content": "{\\"name\\":\\"app\\",...}"},
    {"path": "README.md", "content": "# Project\\n..."},
    {"path": "Dockerfile", "content": "FROM node:20-alpine\\n..."},
    {"path": "src/app/dashboard/page.tsx", "content": "export default function DashboardPage() {...}"}
  ],
  "project_structure": {
    "root": ".",
    "framework": "nextjs-15",
    "directories": ["src/app", "src/components", "src/lib", "src/stores", "src/hooks"]
  },
  "package_json": {"name": "app", "version": "1.0.0", "scripts": {"dev": "next dev"}},
  "environment_variables": [{"name": "NEXT_PUBLIC_API_URL", "description": "API base URL"}],
  "docker_configuration": {"base_image": "node:20-alpine", "port": 3000},
  "readme": "# Project overview and setup instructions"
}

Minimum content requirements:
- At least 50 generated_files with full source content
- package.json file in generated_files AND package_json field populated
- README.md file in generated_files AND readme field populated
- Dockerfile file in generated_files AND docker_configuration field populated
- No TODO or FIXME placeholders anywhere
- Balanced TypeScript/JavaScript syntax (matching braces, brackets, parentheses)
- Valid relative imports between generated files

Include: pages, layouts, components, stores, hooks, providers, services, types, utilities,
middleware, forms, validation schemas, environment config, ESLint/Prettier config.

Return ONLY the JSON object — no preamble, no explanation, no markdown.
"""


class FrontendDeveloperV3PromptBuilder:
    """Builds prompts for the Frontend Developer V3 agent."""

    @staticmethod
    def build_user_prompt(*, requirement_text: str, frontend_v2_output: dict) -> str:
        import json

        v2_json = json.dumps(frontend_v2_output, indent=2)
        return (
            "Analyze the following requirement and Frontend Developer V2 file specifications. "
            "Generate a complete production-ready Next.js 15 frontend codebase.\n\n"
            f"## Original Requirement\n{requirement_text}\n\n"
            f"## Frontend Developer V2 Output\n{v2_json}\n\n"
            "Return only the JSON object matching the required schema with real source code."
        )

    @staticmethod
    def get_system_prompt() -> str:
        return SYSTEM_PROMPT

    @staticmethod
    def get_prompt_version() -> str:
        return PROMPT_VERSION
