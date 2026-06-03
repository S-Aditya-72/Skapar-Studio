from pydantic import BaseModel, Field
from enum import Enum


class ComponentType(str, Enum):
    TEXT = "Text"
    FORM = "Form"
    TABLE = "Table"
    BUTTON = "Button"


class PayloadMapping(BaseModel):
    ui_input_name: str = Field(description="Name of the UI input")
    api_field_name: str = Field(
        description="Name of the corresponding API field")


class Component(BaseModel):
    id: str = Field(description="Unique component ID")
    type: ComponentType = Field(description="Component type")
    label: str = Field(description="Display label or text")
    api_endpoint_binding: str = Field(
        description="API path this component binds to, or empty", default="")
    payload_mapping: list[PayloadMapping] = Field(
        description="Maps UI inputs to API fields", default_factory=list)


class Page(BaseModel):
    name: str = Field(description="Page name")
    route: str = Field(description="Page route, e.g., /home")
    components: list[Component] = Field(
        description="List of UI components on this page", default_factory=list)


class UISchema(BaseModel):
    pages: list[Page] = Field(
        description="List of pages", default_factory=list)
    nav_menu: list[str] = Field(
        description="List of page names in the navigation menu", default_factory=list)
