from app.tests.conftest import auth_headers, create_authenticated_user


async def test_list_workflow_templates(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-list@example.com", username="wftlist"
    )
    response = await client.get(
        "/v1/workflow-templates", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    slugs = {item["slug"] for item in data["items"]}
    assert slugs == {
        "crm-workflow",
        "healthcare-workflow",
        "financial-workflow",
        "ecommerce-workflow",
    }


async def test_get_workflow_template(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-get@example.com", username="wftget"
    )
    response = await client.get(
        "/v1/workflow-templates/crm-workflow",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CRM Workflow"
    assert data["stage_count"] >= 5


async def test_apply_crm_workflow_template(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-crm@example.com", username="wftcrm"
    )
    response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "crm-workflow"},
    )
    assert response.status_code == 201
    workflow = response.json()["workflow"]
    assert workflow["name"] == "CRM Delivery Workflow"
    assert len(workflow["stages"]) >= 5
    assert workflow["team_assignment_count"] >= 5


async def test_apply_healthcare_workflow_template(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-health@example.com", username="wfthealth"
    )
    response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "healthcare-workflow"},
    )
    assert response.status_code == 201
    workflow = response.json()["workflow"]
    stage_names = [stage["name"] for stage in workflow["stages"]]
    assert "Compliance Review" in stage_names
    assert len(workflow["rules"]) >= 1


async def test_apply_financial_workflow_template(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-fin@example.com", username="wftfin"
    )
    response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "financial-workflow"},
    )
    assert response.status_code == 201
    workflow = response.json()["workflow"]
    stage_names = [stage["name"] for stage in workflow["stages"]]
    assert "Security Review" in stage_names
    assert "Risk Review" in stage_names


async def test_apply_ecommerce_workflow_template(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-ecom@example.com", username="wftecom"
    )
    response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "ecommerce-workflow"},
    )
    assert response.status_code == 201
    assert response.json()["workflow"]["stage_count"] >= 5


async def test_apply_unknown_workflow_template(client):
    _, tokens = await create_authenticated_user(
        client, email="wft-unknown@example.com", username="wftunknown"
    )
    response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "missing-template"},
    )
    assert response.status_code == 404
