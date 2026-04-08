#!/usr/bin/env python3
"""
Grade skill evaluation outputs and generate reports.

Reads schema YAML files produced by eval runs, grades them programmatically
against assertions from the eval definition, and generates benchmark reports.

Usage:
    python scripts/grade_evals.py \
        --eval-file evaluations/managing-schemas.json \
        --results-dir eval-results \
        --output-dir eval-report
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml  # noqa: F401 — needed by grade_schema
except ImportError:
    print("PyYAML is required: pip install pyyaml")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from run_evals import grade_schema, build_benchmark, generate_markdown_report


def find_output_file(results_dir: Path, eval_id: int) -> Path | None:
    """Find the output file for a given eval run.

    Searches:
      - eval-{id}/outputs/output.yml    (CI layout)
      - eval-{id}/outputs/*.yml          (fallback)
      - eval-{id}-*/outputs/*.yml        (local layout)
    """
    candidates = [results_dir / f"eval-{eval_id}"]
    candidates.extend(sorted(results_dir.glob(f"eval-{eval_id}-*")))

    for eval_dir in candidates:
        outputs_dir = eval_dir / "outputs"
        if not outputs_dir.exists():
            continue
        for ext in ("yml", "yaml"):
            output = outputs_dir / f"output.{ext}"
            if output.exists():
                return output
        yamls = list(outputs_dir.glob("*.yml")) + list(outputs_dir.glob("*.yaml"))
        if yamls:
            return yamls[0]

    return None


def main():
    parser = argparse.ArgumentParser(description="Grade skill eval outputs")
    parser.add_argument("--eval-file", type=Path, required=True,
                        help="Path to eval JSON definition file")
    parser.add_argument("--results-dir", type=Path, required=True,
                        help="Directory containing eval outputs")
    parser.add_argument("--output-dir", type=Path, default=Path("eval-report"),
                        help="Directory to write reports to")
    args = parser.parse_args()

    with open(args.eval_file) as f:
        eval_data = json.load(f)

    skill_name = eval_data["skill_name"]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    print(f"Grading {len(eval_data['evals'])} evals for {skill_name}")

    for ev in eval_data["evals"]:
        eval_id = ev["id"]
        assertions = ev.get("assertions", [])
        result = {"eval_id": eval_id, "eval_name": f"eval-{eval_id}"}

        output_path = find_output_file(args.results_dir, eval_id)

        if output_path:
            print(f"  Eval {eval_id}: grading {output_path}")
            grading = grade_schema(output_path, assertions)
        else:
            print(f"  Eval {eval_id}: no output file found")
            grading = {
                "expectations": [
                    {"text": a.get("check", ""), "passed": False,
                     "evidence": "No output file produced"}
                    for a in assertions
                ],
                "summary": {
                    "passed": 0, "failed": len(assertions),
                    "total": len(assertions), "pass_rate": 0.0,
                },
            }

        s = grading["summary"]
        print(f"    {s['passed']}/{s['total']} passed ({s['pass_rate']*100:.0f}%)")

        # Save grading file
        grading_dir = output_path.parent.parent if output_path else (
            args.results_dir / f"eval-{eval_id}")
        grading_dir.mkdir(parents=True, exist_ok=True)
        with open(grading_dir / "grading.json", "w") as f:
            json.dump(grading, f, indent=2)

        result["grading"] = grading
        all_results.append(result)

    # Generate benchmark and report
    benchmark = build_benchmark(all_results, skill_name, "ci")

    with open(args.output_dir / "benchmark.json", "w") as f:
        json.dump(benchmark, f, indent=2)

    report = generate_markdown_report(benchmark)
    with open(args.output_dir / "report.md", "w") as f:
        f.write(report)

    print(f"\nReport written to {args.output_dir / 'report.md'}")
    print(report)


if __name__ == "__main__":
    main()
