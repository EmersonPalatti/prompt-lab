import argparse
from pathlib import Path

from prompt_lab.experiment import write_results
from prompt_lab.runner import DEFAULT_MODEL, run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt Lab: pontua ou roda um experimento")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="Pontua outputs/ e grava results.json (sem API)")
    score.add_argument("experiment", type=Path)

    run = sub.add_parser("run", help="Chama o modelo, grava outputs/ e pontua")
    run.add_argument("experiment", type=Path)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument(
        "--version",
        action="append",
        dest="versions",
        help="Roda só esta versão (repetir o flag para várias). Default: todas.",
    )

    args = parser.parse_args()
    experiment = args.experiment
    if not experiment.is_dir():
        parser.error(f"pasta de experimento inexistente: {experiment}")
    if not (experiment / "inputs.yaml").is_file():
        parser.error(f"inputs.yaml ausente em {experiment}")

    if args.command == "score":
        destination = write_results(experiment)
    else:
        destination = run_experiment(
            experiment,
            model=args.model,
            repeats=args.repeats,
            versions=args.versions,
        )
    print(destination)


if __name__ == "__main__":
    main()
