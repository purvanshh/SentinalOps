from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TimestampedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
