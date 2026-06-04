import time
import json
import os
from dotenv import load_dotenv
import sys

# Add root folder to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compiler.orchestrator import CompilerEngine  # noqa: E402

PROMPTS = [
    "Build a CRM with login, contacts, dashboard, and role access.",
    "Build a blog system where users can write posts, leave comments, and like articles.",
    "Build a system.",  # Extremely vague
    "Make an app with a button that creates a user and another button that deletes a user but there is no database.",  # Conflicting
]


def run_benchmark():
    load_dotenv()
    engine = CompilerEngine(api_key=os.getenv("GOOGLE_API_KEY"))

    results = []
    print("🧪 Starting Evaluation Benchmark (with API Throttling)...\n")

    for i, prompt in enumerate(PROMPTS):
        print(f"[{i+1}/{len(PROMPTS)}] Testing: '{prompt}'")
        start_time = time.time()
        success = False
        error_msg = None
        error_type = None  # <--- Define it before the try block

        try:
            engine.run_compilation(prompt)
            success = True
            print("   ✅ Passed!")
        except Exception as e:
            success = False
            error_msg = str(e)
            # <--- Capture the type inside the except block
            error_type = type(e).__name__
            print(f"   ❌ Failed: {error_msg}")

        latency = time.time() - start_time

        results.append({
            "prompt": prompt,
            "success": success,
            "latency_seconds": round(latency, 2),
            "error_type": error_type,  # <--- Use the captured variable
            "error_message": error_msg
        })

        # Don't sleep after the very last prompt
        if i < len(PROMPTS) - 1:
            print("   ⏳ Sleeping for 30 seconds to respect Gemini API rate limits...\n")
            time.sleep(30)

    # Generate Report
    success_rate = sum(1 for r in results if r["success"]) / len(results) * 100
    avg_latency = sum(r["latency_seconds"] for r in results) / len(results)

    print("\n" + "="*40)
    print("📈 BENCHMARK REPORT")
    print("="*40)
    print(f"Total Prompts: {len(PROMPTS)}")
    print(f"Success Rate: {success_rate}%")
    print(f"Average Latency: {avg_latency:.2f} seconds")

    with open("eval/benchmark_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nDetailed report saved to eval/benchmark_report.json")


if __name__ == "__main__":
    run_benchmark()
