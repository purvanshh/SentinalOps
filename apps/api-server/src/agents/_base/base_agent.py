import abc
from pydantic import BaseModel
from core.llm_client import LLMClient

class BaseAgent(abc.ABC):
    def __init__(self, name: str, llm_client: LLMClient | None = None) -> None:
        self.name = name
        self.llm_client = llm_client or LLMClient()

    @abc.abstractmethod
    async def run(self, *args, **kwargs) -> BaseModel:
        pass
