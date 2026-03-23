#!/usr/bin/env python3
"""
Grade skill evaluation outputs and generate reports.

Reads schema YAML files produced by eval runs, grades them programmatically
against assertions from the eval definition, and generates benchmark reports.

Usage:
    python scripts/grade_evals.py \
        --eval-file evaluations/schema-creator.json \
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


def find_schema_file(results_dir: Path, eval_id: int, config: str) -> Path | None:
    """Find the schema output file for a given eval run.

    Searches common directory layouts:
      - eval-{id}/{config}/outputs/schema.yml    (CI layout)
      - eval-{id}-{name}/{config}/outputs/...     (local layout)
    Falls back to globbing for any YAML file in the outputs directory.
    """
    # Try eval-{id} first (CI layout), then glob for eval-{id}-* (local)
    candidates = [results_dir / f"eval-{eval_id}"]
    candidates.extend(sorted(results_dir.glob(f"eval-{eval_id}-*")))

    for eval_dir in candidates:
        outputs_dir = eval_dir / config / "outputs"
        if not outputs_dir.exists():
            continue
        for ext in ("yml", "yaml"):
            schema = outputs_dir / f"schema.{ext}"
            if schema.exists():
                return schema
        # Fallback: any YAML file in outputs/
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

        for config in ("with_skill", "without_skill"):
            schema_path = find_schema_file(args.results_dir, eval_id, config)

            if schema_path:
                print(f"  Eval {eval_id} {config}: grading {schema_path}")
                grading = grade_schema(schema_path, assertions)
            else:
                print(f"  Eval {eval_id} {config}: no schema file found")
                grading = {
                    "expectations": [
                        {"text": a.get("check", "<missing check>"), "passed": False,
                         "evidence": "No schema file produced"}
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
            if schema_path:
                grading_dir = schema_path.parent.parent
            else:
                grading_dir = args.results_dir / f"eval-{eval_id}" / config
                grading_dir.mkdir(parents=True, exist_ok=True)
            with open(grading_dir / "grading.json", "w") as f:
                json.dump(grading, f, indent=2)

            # Use timing data if available
            timing = {"total_tokens": 0, "duration_ms": 0, "total_duration_seconds": 0}
            timing_path = grading_dir / "outputs" / "timing.json"
            if timing_path.exists():
                with open(timing_path) as f:
                    timing = json.load(f)

            result[config] = {"grading": grading, "timing": timing}

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
