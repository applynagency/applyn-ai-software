from app.workflows.dispatcher import AgentDispatcher


async def test_dispatcher_skips_unimplemented_internal_agent():
    dispatcher = AgentDispatcher()
    result = await dispatcher.dispatch_internal(
        internal_agent="developer_v1",
        requirement_content="Build API",
        session=None,
        requirement_id="req-1",
        user=None,
    )
    assert result.status == "skipped"
    assert result.log_messages
