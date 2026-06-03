import os
from dotenv import load_dotenv
from compiler.orchestrator import CompilerEngine

# 1. Load the .env file so it finds your API key
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(
        "⚠️ GOOGLE_API_KEY not found. Make sure it is in your .env file.")

print("Initializing Compiler Engine...")
# 2. Pass the api_key into the engine (This is required now!)
engine = CompilerEngine(api_key=api_key)

prompt = "Build a CRM with login, contacts, dashboard, and role-based access. Admins can see analytics."
print(f"Prompt: '{prompt}'\n")
print("Starting compilation... (This will take 1-2 minutes)")

try:
    # Run the compiler
    result_schema = engine.run_compilation(prompt)

    print("\n✅ --- COMPILATION SUCCESSFUL --- ✅")

    # Save it to a file so we can inspect the generated JSON
    with open("test_output.json", "w") as f:
        f.write(result_schema.model_dump_json(indent=2))
    print("Saved output to test_output.json. You can open this file to see the AI's work!")

except Exception as e:
    print("\n❌ --- COMPILATION FAILED --- ❌")
    print(f"Error: {e}")
