import os
import json
import subprocess
import time
from dotenv import load_dotenv
from compiler.orchestrator import CompilerEngine
import uvicorn
from runtime.backend_engine import app, generate_database, setup_api_routes


def main():
    print("🤖 Welcome to the AI Software Factory 🤖")
    print("="*40)

    # 1. Ask for prompt
    prompt = input(
        "\nEnter your app prompt (or press Enter to instantly boot the CRM we just compiled!):\n> ")

    if prompt.strip():
        # Compile new app
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        engine = CompilerEngine(api_key=api_key)

        print("\n⚙️ Compiling software... (This takes 1-2 minutes)")
        result_schema = engine.run_compilation(prompt)

        with open("compiled_app.json", "w") as f:
            f.write(result_schema.model_dump_json(indent=2))
        print("✅ Compilation complete! Saved to compiled_app.json")
    else:
        # Use existing test output
        print("\nUsing existing test_output.json...")
        with open("test_output.json", "r") as f:
            data = json.load(f)
        with open("compiled_app.json", "w") as f:
            json.dump(data, f, indent=2)

    # 2. Setup Backend Engine
    with open("compiled_app.json", "r") as f:
        app_schema = json.load(f)

    print("\n🗄️ Setting up Database...")
    generate_database(app_schema.get("database", {}))

    print("🔌 Setting up API Routes...")
    setup_api_routes(app, app_schema.get("api", {}))

    # 3. Start Servers
    print("\n🚀 Booting up Runtime Environments...")

    backend_process = subprocess.Popen(
        ["uvicorn", "runtime.backend_engine:app",
            "--host", "127.0.0.1", "--port", "8000"]
    )

    time.sleep(2)  # Give backend a second to start

    print("🖥️ Starting Streamlit UI...")
    try:
        subprocess.run(["streamlit", "run", "runtime/frontend_engine.py"])
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    finally:
        backend_process.terminate()
        print("Goodbye!")


if __name__ == "__main__":
    main()
