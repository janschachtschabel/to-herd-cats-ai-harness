"""The agent loop (plan M5 task 6): the one place that imports Pydantic AI
(`tests/test_runtime_imports.py`). It knows models, messages and tool definitions,
nothing of the database: the run executor (`modules/agents/executor.py`) gives it a
`StepHost` that checks and records every step."""
