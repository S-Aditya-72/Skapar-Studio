from pydantic import BaseModel, Field


class RequirementsSchema(BaseModel):
    features: list[str] = Field(
        description="List of core features", default_factory=list)
    entities: list[str] = Field(
        description="List of data entities (e.g., User, Product)", default_factory=list)
    assumptions: list[str] = Field(
        description="List of assumptions made from the prompt", default_factory=list)
