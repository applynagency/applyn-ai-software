
from app.infrastructure_architect.prompt_builder import InfrastructureArchitectPromptBuilder


def test_prompt_version_present():
    builder = InfrastructureArchitectPromptBuilder()
    assert builder.get_prompt_version()


def test_system_prompt_not_empty():
    builder = InfrastructureArchitectPromptBuilder()
    assert len(builder.get_system_prompt()) > 20


def test_user_prompt_includes_requirement():
    builder = InfrastructureArchitectPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Build app",
        frontend_execution_output={"build_status": "success"},
        backend_execution_output={"build_status": "success"},
        qa_approval_output={"qa_status": "QA_APPROVED"},
    )
    assert "Build app" in prompt


def test_user_prompt_includes_execution_outputs():
    builder = InfrastructureArchitectPromptBuilder()
    prompt = builder.build_user_prompt(
        requirement_text="Req",
        frontend_execution_output={"key": "fe"},
        backend_execution_output={"key": "be"},
        qa_approval_output={"qa_status": "QA_APPROVED"},
    )
    assert "fe" in prompt and "be" in prompt
