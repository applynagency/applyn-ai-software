from app.tests.conftest import auth_headers, create_authenticated_user, create_workflow


async def test_create_healthcare_compliance_rule(client):
    _, tokens = await create_authenticated_user(
        client, email="rule-health@example.com", username="rulehealth"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.post(
        f"/v1/workflows/{workflow['id']}/rules",
        headers=auth_headers(tokens["access_token"]),
        json={"rule_type": "HEALTHCARE_COMPLIANCE", "configuration_json": {}},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["rule_type"] == "HEALTHCARE_COMPLIANCE"
    assert data["configuration_json"]["required"] is True


async def test_create_financial_security_rule(client):
    _, tokens = await create_authenticated_user(
        client, email="rule-fin-sec@example.com", username="rulefinsec"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.post(
        f"/v1/workflows/{workflow['id']}/rules",
        headers=auth_headers(tokens["access_token"]),
        json={"rule_type": "FINANCIAL_SECURITY", "configuration_json": {}},
    )
    assert response.status_code == 201
    assert response.json()["configuration_json"]["stage_name"] == "Security Review"


async def test_create_financial_risk_rule(client):
    _, tokens = await create_authenticated_user(
        client, email="rule-fin-risk@example.com", username="rulefinrisk"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.post(
        f"/v1/workflows/{workflow['id']}/rules",
        headers=auth_headers(tokens["access_token"]),
        json={"rule_type": "FINANCIAL_RISK", "configuration_json": {}},
    )
    assert response.status_code == 201
    assert response.json()["configuration_json"]["stage_name"] == "Risk Review"


async def test_create_production_approval_rule(client):
    _, tokens = await create_authenticated_user(
        client, email="rule-prod@example.com", username="ruleprod"
    )
    workflow = await create_workflow(client, tokens["access_token"])
    response = await client.post(
        f"/v1/workflows/{workflow['id']}/rules",
        headers=auth_headers(tokens["access_token"]),
        json={"rule_type": "PRODUCTION_APPROVAL", "configuration_json": {}},
    )
    assert response.status_code == 201
    config = response.json()["configuration_json"]
    assert config["approval_required"] is True


async def test_rules_engine_list_definitions():
    from app.workflows.rules_engine import WorkflowRulesEngine

    rules = WorkflowRulesEngine.list_available_rules()
    assert len(rules) == 4
    rule_types = {item["rule_type"] for item in rules}
    assert "HEALTHCARE_COMPLIANCE" in rule_types
    assert "PRODUCTION_APPROVAL" in rule_types


async def test_template_includes_seeded_rules(client):
    _, tokens = await create_authenticated_user(
        client, email="rule-template@example.com", username="ruletemplate"
    )
    response = await client.post(
        "/v1/workflow-templates/apply",
        headers=auth_headers(tokens["access_token"]),
        json={"template_slug": "financial-workflow"},
    )
    assert response.status_code == 201
    rules = response.json()["workflow"]["rules"]
    assert len(rules) >= 2
    rule_types = {rule["rule_type"] for rule in rules}
    assert "FINANCIAL_SECURITY" in rule_types
