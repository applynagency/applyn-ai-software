from app.sre_approval.prompt_builder import SreApprovalPromptBuilder


def _build(builder):
    return builder.build_user_prompt(
        requirement_text="Ship platform",
        infrastructure_architect_output={"infra": "infra-marker"},
        docker_agent_output={"docker": "docker-marker"},
        cicd_agent_output={"cicd": "cicd-marker"},
        kubernetes_output={"k8s": "k8s-marker"},
        observability_output={"obs": "obs-marker"},
    )


def test_prompt_version_present():
    builder = SreApprovalPromptBuilder()
    assert builder.get_prompt_version()


def test_system_prompt_not_empty():
    builder = SreApprovalPromptBuilder()
    assert len(builder.get_system_prompt()) > 20


def test_user_prompt_includes_requirement():
    builder = SreApprovalPromptBuilder()
    assert "Ship platform" in _build(builder)


def test_user_prompt_includes_all_upstream_outputs():
    builder = SreApprovalPromptBuilder()
    prompt = _build(builder)
    for marker in ("infra-marker", "docker-marker", "cicd-marker", "k8s-marker", "obs-marker"):
        assert marker in prompt


def test_system_prompt_mentions_statuses():
    builder = SreApprovalPromptBuilder()
    prompt = builder.get_system_prompt()
    assert "SRE_APPROVED" in prompt
    assert "SRE_REJECTED" in prompt
