"""Measure counting accuracy against a hand count.

    python -m smartgate.eval_count --truth eval/truth.json --runs eval/

truth.json (count each test video by hand once):
    {"gate1.mp4": {"IN": {"car": 12, "truck": 3}, "OUT": {"car": 9}}}
eval/ holds one CSV per video produced by:
    python -m smartgate.run_gate --source videos/gate1.mp4 --line ... --dry-run --csv eval/gate1.csv

Accuracy per video and direction = 1 - |predicted - true| / true (floored at 0).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def count_csv(path: Path) -> dict[str, Counter]:
    out = {"IN": Counter(), "OUT": Counter()}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["direction"]][row["vehicle_type"]] += 1
    return out


def accuracy(pred: int, true: int) -> float:
    if true == 0:
        return 1.0 if pred == 0 else 0.0
    return max(0.0, 1 - abs(pred - true) / true)


def evaluate(truth: dict, runs: Path) -> dict:
    report, total_pred, total_true = {}, 0, 0
    for video, expected in truth.items():
        csv_path = runs / (Path(video).stem + ".csv")
        pred = count_csv(csv_path)
        rows = {}
        for direction in ("IN", "OUT"):
            exp = expected.get(direction, {})
            p, t = sum(pred[direction].values()), sum(exp.values())
            total_pred, total_true = total_pred + min(p, t), total_true + max(p, t)
            rows[direction] = {"pred": p, "true": t, "accuracy": round(accuracy(p, t), 3),
                               "by_type": {k: [pred[direction].get(k, 0), v] for k, v in exp.items()}}
        report[video] = rows
    report["overall_accuracy"] = round(total_pred / total_true, 3) if total_true else 1.0
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--runs", type=Path, required=True)
    args = ap.parse_args()
    report = evaluate(json.loads(args.truth.read_text(encoding="utf-8")), args.runs)
    for video, rows in report.items():
        if video == "overall_accuracy":
            continue
        for d, r in rows.items():
            print(f"{video:20s} {d:3s} predicted={r['pred']:3d} true={r['true']:3d} accuracy={r['accuracy']:.1%}")
    print(f"\nOVERALL counting accuracy: {report['overall_accuracy']:.1%}")


if __name__ == "__main__":
    main()
