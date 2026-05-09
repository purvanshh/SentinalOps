from pydantic import BaseModel


class ResumeCommand(BaseModel):
    approved: bool
    note: str = ""
    approved_by: str = ""
    approval_token: str = ""
