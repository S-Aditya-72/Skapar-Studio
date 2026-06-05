import os
import json
import sqlite3
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from compiler.orchestrator import CompilerEngine

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

app = FastAPI(title="AI Software Factory API")

# Enable CORS for Next.js (Port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE & CRUD LOGIC (From your backend_engine) ---


def get_db_connection():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn


def generate_database(db_schema: dict):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    type_mapping = {"string": "TEXT", "integer": "INTEGER",
                    "boolean": "BOOLEAN", "uuid": "TEXT", "datetime": "TEXT", "float": "REAL"}
    for table in db_schema.get("tables", []):
        columns = []
        for col in table.get("columns", []):
            col_type = type_mapping.get(col.get("type", "string"), "TEXT")
            pk = "PRIMARY KEY" if col.get("is_primary_key") else ""
            columns.append(f"{col['name']} {col_type} {pk}")
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {table['name']} ({', '.join(columns)});")
    conn.commit()
    conn.close()


def get_actual_table_name(cursor, path_val: str):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    base_name = path_val.strip('/').split('/')[0].lower()
    for t in tables:
        t_lower = t.lower()
        if t_lower == base_name or t_lower + "s" == base_name or t_lower == base_name + "s":
            return t
    return None


def setup_api_routes(api_schema: dict):
    endpoints = api_schema.get("endpoints", [])
    for endpoint in endpoints:
        path = endpoint["path"]
        method = endpoint["method"]

        async def dynamic_handler(request: Request, path_val: str = path):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                table_name = get_actual_table_name(cursor, path_val)

                if not table_name:
                    if request.method == "POST":
                        payload = await request.json()
                        return {"status": "success", "message": f"Echo: {path_val}", "data": payload}
                    return {"status": "success", "data": []}

                if request.method == "POST":
                    payload = await request.json()
                    columns = ', '.join(payload.keys())
                    placeholders = ', '.join(['?' for _ in payload])
                    values = tuple(payload.values())
                    cursor.execute(
                        f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
                    conn.commit()
                    return {"status": "success", "message": f"Saved to {table_name}", "data": payload}

                elif request.method == "GET":
                    cursor.execute(f"SELECT * FROM {table_name}")
                    return {"status": "success", "data": [dict(row) for row in cursor.fetchall()]}

            except Exception as e:
                return {"status": "error", "message": str(e)}
            finally:
                if 'conn' in locals():
                    conn.close()

        dynamic_handler.__name__ = f"handler_{path.replace('/', '_').replace('{', '').replace('}', '')}_{method}"
        app.add_api_route(
            path=path, endpoint=dynamic_handler, methods=[method])

# --- SYSTEM ENDPOINTS ---


class PromptRequest(BaseModel):
    prompt: str


@app.post("/api/system/compile")
def compile_app(request: PromptRequest):
    """Takes a prompt, runs the AI compiler, saves JSON, and mounts the DB/Routes"""
    engine = CompilerEngine(api_key=api_key)

    # 1. Compile the JSON
    result_schema = engine.run_compilation(request.prompt)
    app_schema_dict = json.loads(result_schema.model_dump_json())

    # 2. Save it
    with open("compiled_app.json", "w") as f:
        json.dump(app_schema_dict, f, indent=2)

    # 3. Mount Database and Routes dynamically
    generate_database(app_schema_dict.get("database", {}))
    setup_api_routes(app_schema_dict.get("api", {}))

    return {"status": "success", "schema": app_schema_dict}


@app.get("/api/system/schema")
def get_schema():
    """Serves the generated JSON to the Next.js frontend"""
    if os.path.exists("compiled_app.json"):
        with open("compiled_app.json", "r") as f:
            return json.load(f)
    return {"error": "No app compiled yet."}


# Auto-load existing app on startup
if os.path.exists("compiled_app.json"):
    with open("compiled_app.json", "r") as f:
        schema = json.load(f)
        setup_api_routes(schema.get("api", {}))

if __name__ == "__main__":
    print("🚀 Starting AI Backend on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
