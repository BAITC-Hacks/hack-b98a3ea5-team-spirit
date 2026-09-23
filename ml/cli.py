"""Command-line entry point for local and Brev training."""

from __future__ import annotations

import argparse
import json

from ml.train import train_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Train wind-turbine power models")
    subparsers = parser.add_subparsers(dest="command", required=True)
    train_parser = subparsers.add_parser("train", help="run two-stage GridSearchCV")
    train_parser.add_argument("--config", default="config/training.json")
    train_parser.add_argument("--smoke", action="store_true")
    train_parser.add_argument("--n-jobs", type=int)
    arguments = parser.parse_args()

    if arguments.command == "train":
        result = train_all(
            arguments.config,
            smoke=arguments.smoke,
            n_jobs_override=arguments.n_jobs,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
