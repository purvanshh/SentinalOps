import pytest
from agents._base.base_agent import BaseAgent
from pydantic import BaseModel


class MockOutput(BaseModel):
    success: bool


class ConcreteAgent(BaseAgent):
    async def run(self, *args, **kwargs) -> MockOutput:
        return MockOutput(success=True)


@pytest.mark.asyncio
async def test_base_agent_initialization() -> None:
    # We mock LLMClient initialization to avoid real client setup if it has checks
    with pytest.raises(TypeError):
        # BaseAgent is abstract and cannot be instantiated directly
        BaseAgent("abstract_agent")

    # ConcreteAgent can be instantiated
    agent = ConcreteAgent("concrete_agent", llm_client=None)
    assert agent.name == "concrete_agent"

    result = await agent.run()
    assert result.success is True
