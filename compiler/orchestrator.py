from typing import Type
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types

# Import our Domain Specific Language models
from dsl.requirements_schema import RequirementsSchema
from dsl.db_schema import DatabaseSchema
from dsl.auth_schema import AuthSchema
from dsl.api_schema import APISchema
from dsl.ui_schema import UISchema
from dsl import MasterAppSchema


class CrossLayerValidationError(Exception):
    pass


class CompilerEngine:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.5-flash'

    def _call_gemini(self, prompt: str, schema_model: Type[BaseModel]) -> BaseModel:
        """Helper to call Gemini with a strict Pydantic schema"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema_model,
            )
        )
        return schema_model.model_validate_json(response.text)

    def _repair_loop(self, prompt: str, schema_model: Type[BaseModel], max_retries=3) -> BaseModel:
        """Executes generation and automatically repairs Pydantic syntax errors"""
        try:
            return self._call_gemini(prompt, schema_model)
        except Exception as e:
            last_error = str(e)
            for attempt in range(max_retries):
                print(
                    f"    [Repair] Fixing {schema_model.__name__} (Attempt {attempt + 1}/{max_retries})...")
                repair_prompt = f"Fix this JSON. It failed with error: {last_error}\nOriginal prompt context: {prompt}"
                try:
                    return self._call_gemini(repair_prompt, schema_model)
                except Exception as err:
                    last_error = str(err)
            raise ValueError(
                f"Failed to generate {schema_model.__name__} after {max_retries} retries. Last error: {last_error}")

    def validate_ui_against_api(self, ui_schema: UISchema, api_schema: APISchema):
        """Deterministic Linker: Ensures UI buttons/forms call APIs that actually exist"""
        valid_endpoints = {ep.path for ep in api_schema.endpoints}
        for page in ui_schema.pages:
            for comp in page.components:
                # If the component binds to an API, it MUST exist in the API schema
                if hasattr(comp, 'api_endpoint_binding') and comp.api_endpoint_binding:
                    if comp.api_endpoint_binding not in valid_endpoints:
                        raise CrossLayerValidationError(
                            f"Component '{comp.id}' calls '{comp.api_endpoint_binding}', but it does not exist in API Schema."
                        )

    def run_compilation(self, prompt: str) -> MasterAppSchema:
        print("1. Extracting Requirements...")
        reqs = self._repair_loop(
            f"Extract software requirements from this prompt: {prompt}", RequirementsSchema)

        print("2. Generating Database Schema...")
        db = self._repair_loop(
            f"Generate Database Schema for: {reqs.model_dump_json()}", DatabaseSchema)

        print("3. Generating Auth Schema...")
        auth = self._repair_loop(
            f"Generate Auth Schema for: {reqs.model_dump_json()}", AuthSchema)

        print("4. Generating API Schema...")
        api_prompt = f"Generate API Schema matching these Requirements: {reqs.model_dump_json()} and this Database Schema: {db.model_dump_json()}"
        api = self._repair_loop(api_prompt, APISchema)

        print("5. Generating UI Schema...")
        ui_prompt = f"Generate UI Schema matching these Requirements: {reqs.model_dump_json()}. Bind components ONLY to these API endpoints: {api.model_dump_json()}"

        # Custom Repair Loop for Cross-Layer Validation
        ui = None
        last_error = ""
        for attempt in range(4):
            try:
                if attempt == 0:
                    ui = self._call_gemini(ui_prompt, UISchema)
                else:
                    print(
                        f"    [Cross-Layer Repair] Resolving UI Linker Error (Attempt {attempt}/3)...")
                    repair_prompt = f"The UI schema failed cross-layer validation: {last_error}. Fix the UI bindings to match this API Schema: {api.model_dump_json()}"
                    ui = self._call_gemini(repair_prompt, UISchema)

                # Run deterministic linker check
                self.validate_ui_against_api(ui, api)
                break  # Passed validation!
            except (ValidationError, CrossLayerValidationError) as e:
                last_error = str(e)

        if not ui:
            raise ValueError(
                f"Failed to generate valid UI Schema. Last error: {last_error}")

        # Assemble the final application
        try:
            return MasterAppSchema(database=db, auth=auth, api=api, ui=ui)
        except Exception:
            # Fallback in case your MasterAppSchema expects the requirements object too
            return MasterAppSchema(requirements=reqs, database=db, auth=auth, api=api, ui=ui)
