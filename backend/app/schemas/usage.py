from pydantic import BaseModel, ConfigDict


class ModelUsageRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    call_count: int
    total_tokens: int
    total_cost: float
    is_attributable: bool
