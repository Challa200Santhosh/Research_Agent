"""
CLI Launcher for Autonomous Deep Academic Literature Agent.
Usage:
    python main.py --prompt "Find 15 papers on VLM based Autonomous Navigation from 2021 to 2026"
"""

import sys
import os

# Add src/ folder to Python search path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import argparse
from academic_agent import build_academic_agent_graph

# Fix Windows Proactor Event Loop close warnings on Python 3.10+
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def run_agent(prompt_text: str):
    """Executes the academic literature agent with the given natural language prompt."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("[INFO] Initializing Autonomous Deep Academic Literature Agent...")
    print(f"[INPUT] Prompt: '{prompt_text}'\n")

    app = build_academic_agent_graph()

    initial_state = {
        "user_prompt": prompt_text,
        "params": None,
        "raw_papers": [],
        "processed_papers": [],
        "excel_path": None,
        "generate_paper": False,
        "paper_tex_path": None,
        "paper_pdf_path": None,
        "ai_density": None,
        "overleaf_zip_path": None,
        "status_message": "Started"
    }

    final_state = await app.ainvoke(initial_state)

    print("\n" + "=" * 65)
    print("[SUCCESS] EXECUTION COMPLETE")
    print("=" * 65)
    print(f"  * Search Topic Extracted     : {final_state['params'].search_topic}")
    print(f"  * Target Paper Count         : {final_state['params'].target_count}")
    print(f"  * Year Window                 : {final_state['params'].start_year} - {final_state['params'].end_year}")
    print(f"  * Title Similarity Threshold  : > 75.0% Required")
    print(f"  * Total Literature Exported   : {len(final_state['processed_papers'])} papers (Sorted by Citations)")
    print(f"  * Output Excel File           : {final_state['excel_path']}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Deep Academic Literature Agent")
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default="Find 15 papers on VLM based Autonomous Navigation from 2021 to 2026",
        help="Natural language research prompt."
    )

    args = parser.parse_args()
    asyncio.run(run_agent(args.prompt))
