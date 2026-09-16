"""Agent 运行时依赖契约测试。"""


def test_agent_runtime_dependencies_can_be_imported() -> None:
    import langgraph
    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    assert langgraph is not None
    assert psycopg is not None
    assert AsyncPostgresSaver is not None
