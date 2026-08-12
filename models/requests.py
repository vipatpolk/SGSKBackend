from pydantic import BaseModel, Field


class SummariesRequest(BaseModel):
    summaries: list[dict[str, str]] = Field(..., max_length=50)


class NavRequest(BaseModel):
    symbols: list[str] = Field(..., max_length=50)
