
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    patch_backend_architect_agent,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_execution_context,
)


async def test_product_team_includes_business_analyst():
    from app.models.team import TeamType
    from app.teams.mappings import TeamMappingService

    agents = TeamMappingService.agents_for_team_type(TeamType.PRODUCT)
    assert "product_owner" in agents
    assert "business_analyst" in agents
    assert "backend_architect" in agents
    assert "uiux_designer" in agents
    assert "frontend_architect" in agents
    assert agents.index("product_owner") < agents.index("business_analyst")
    assert agents.index("business_analyst") < agents.index("backend_architect")
    assert agents.index("backend_architect") < agents.index("uiux_designer")
    assert agents.index("uiux_designer") < agents.index("frontend_architect")


async def test_workflow_execution_runs_po_then_ba(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-exec@example.com", username="baexec"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent(), patch_backend_architect_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    assert response.status_code == 201
    assert response.json()["status"] == "WAITING_FOR_APPROVAL"
    agents = [
        agent
        for stage in response.json()["stages"]
        for agent in stage["agents"]
    ]
    internal = [a for a in agents if a.get("internal_agent") in ("product_owner", "business_analyst", "backend_architect", "uiux_designer", "frontend_architect")]
    assert len(internal) >= 5
    po = next(a for a in internal if a["internal_agent"] == "product_owner")
    ba = next(a for a in internal if a["internal_agent"] == "business_analyst")
    assert po["status"] == "COMPLETED"
    assert ba["status"] == "COMPLETED"


async def test_execution_plan_marks_ba_implemented(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-plan@example.com", username="baplan"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent(), patch_backend_architect_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    plan = response.json()["execution_plan_json"]
    agents = plan["stages"][0]["agents"]
    ba = next(a for a in agents if a.get("internal_agent") == "business_analyst")
    assert ba["is_implemented"] is True


async def test_ba_execution_order_after_po(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-order@example.com", username="baorder"
    )
    ctx = await setup_execution_context(client, tokens["access_token"])
    with patch_product_owner_agent(), patch_business_analyst_agent(), patch_backend_architect_agent():
        response = await client.post(
            f"/v1/workflows/{ctx['workflow']['id']}/execute",
            headers=auth_headers(tokens["access_token"]),
            json={
                "project_id": ctx["project"]["id"],
                "requirement_id": ctx["requirement"]["id"],
            },
        )
    agents = response.json()["execution_plan_json"]["stages"][0]["agents"]
    po = next(a for a in agents if a["internal_agent"] == "product_owner")
    ba = next(a for a in agents if a["internal_agent"] == "business_analyst")
    ba_arch = next(a for a in agents if a["internal_agent"] == "backend_architect")
    uiux = next(a for a in agents if a["internal_agent"] == "uiux_designer")
    fa = next(a for a in agents if a["internal_agent"] == "frontend_architect")
    assert po["execution_order"] < ba["execution_order"]
    assert ba["execution_order"] < ba_arch["execution_order"]
    assert ba_arch["execution_order"] < uiux["execution_order"]
    assert uiux["execution_order"] < fa["execution_order"]
