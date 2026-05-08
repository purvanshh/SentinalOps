from pydantic import BaseModel, Field


class ServiceNode(BaseModel):
    name: str
    depends_on: list[str] = Field(default_factory=list)
    owner: str | None = None
    tier: str | None = None
