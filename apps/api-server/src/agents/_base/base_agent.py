import abc

from core.llm_client import LLMClient
from pydantic import BaseModel


class BaseAgent(abc.ABC):
    def __init__(self, name: str, llm_client: LLMClient | None = None) -> None:
        self.name = name
        self.llm_client = llm_client or LLMClient()

    @abc.abstractmethod
    async def run(self, *args, **kwargs) -> BaseModel:
        pass
