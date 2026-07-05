from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_code_review,
    setup_frontend_code_review_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-schema@example.com", username="fcrschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "review_score",
        "approval_status",
        "issues",
        "recommendations",
        "category_scores",
        "summary",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-meta@example.com", username="fcrmeta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-history@example.com", username="fcrhistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-code-review/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-complete@example.com", username="fcrcomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_issues_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-issues@example.com", username="fcrissues"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-issues-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-issues-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    issues = created.json()["artifact"]["artifact_json"]["issues"]
    assert len(issues) >= 1
    assert issues[0]["id"].startswith("ISS-")


async def test_recommendations_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-recs@example.com", username="fcrrecs"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-recs-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-recs-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    recommendations = created.json()["artifact"]["artifact_json"]["recommendations"]
    assert len(recommendations) >= 1
    assert recommendations[0]["id"].startswith("REC-")


async def test_category_scores_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-scores@example.com", username="fcrscores"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-scores-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-scores-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    scores = created.json()["artifact"]["artifact_json"]["category_scores"]
    assert "TypeScript" in scores
    assert "Code Quality" in scores


async def test_approval_status_stored_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-approval@example.com", username="fapproval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-approval-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-approval-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert created.json()["approval_status"] == "APPROVED_WITH_WARNINGS"


async def test_review_score_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-score@example.com", username="fcrscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-score-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-score-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert created.json()["review_score"] == 86.5


async def test_summary_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-summary@example.com", username="fcrsummary"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-summary-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-summary-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    summary = created.json()["artifact"]["artifact_json"]["summary"]
    assert "Next.js" in summary
