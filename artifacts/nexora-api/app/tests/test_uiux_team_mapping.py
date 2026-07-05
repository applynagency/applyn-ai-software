from app.tests.conftest import EXPECTED_PRODUCT_TEAM_AGENTS, create_authenticated_user, create_team


async def test_product_team_includes_uiux_designer_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-product-uiux@example.com", username="mapproductuiux"
    )
    team = await create_team(client, tokens["access_token"], team_type="PRODUCT")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == EXPECTED_PRODUCT_TEAM_AGENTS


async def test_ui_ux_team_mapping(client):
    _, tokens = await create_authenticated_user(
        client, email="map-uiux-team@example.com", username="mapuiuxteam"
    )
    team = await create_team(client, tokens["access_token"], team_type="UI_UX")
    agents = [m["internal_agent"] for m in sorted(team["agent_mappings"], key=lambda x: x["execution_order"])]
    assert agents == ["uiux_designer", "design_reviewer"]
