"""Summarize saved independent ratings; does not run or judge an LLM."""
import json
import sys
from pathlib import Path


def summarize(directory):
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))

    inputs = read("inputs.json")
    reviews = read("review.json")
    mapping = read("mapping.json")
    metrics = list(read("protocol.json")["metrics"])
    ids = [row["id"] for row in inputs]
    if len(ids) != len(set(ids)) or [row["id"] for row in reviews] != ids:
        raise ValueError("Rating IDs must match input IDs exactly")
    counts = {condition: {metric: 0 for metric in metrics + ["overall_pass"]}
              for condition in ("baseline", "skill")}
    failures = {condition: [] for condition in counts}
    for row in reviews:
        labels = mapping[row["id"]]
        if set(labels.values()) != set(counts):
            raise ValueError("Each case must contain both conditions")
        for label, condition in labels.items():
            rating = row[label]
            if any(type(rating[key]) is not bool for key in metrics + ["overall_pass"]):
                raise ValueError("Ratings must be boolean")
            if rating["overall_pass"] != all(rating[key] for key in metrics):
                raise ValueError("Overall rating conflicts with metric ratings")
            for key in counts[condition]:
                counts[condition][key] += int(rating[key])
            if not rating["overall_pass"]:
                failures[condition].append(row["id"])
    return {"cases_per_condition": len(ids), "passed": counts, "failed_cases": failures,
            "limitation": "Saved same-model, separate-context ratings; no general accuracy claim"}


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "2026-10-10"
    print(json.dumps(summarize(folder), ensure_ascii=False, indent=2))
