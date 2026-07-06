import argparse
import contextlib
import curses
import json
import math
import os
import random
import shutil
import sys
import time
import traceback
from multiprocessing import Lock, Pipe, Process, Value, cpu_count, set_start_method
from multiprocessing.connection import Connection
from pathlib import Path
from typing import List, Optional

os.environ["PYTHONHASHSEED"] = "0"  # Required for reproducibility.

from utils import StdoutPipeRedirector


def check_positive(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is an invalid positive int value")
    return ivalue


def create_parser() -> argparse.ArgumentParser:
    examples = """
Examples:
  python fuzz_test.py --max-minutes 10 -s ortools
  python fuzz_test.py --agent --max-minutes 1 -s ortools
  python fuzz_test.py --dry-run --agent --models models --output-dir output
  python fuzz_test.py --output json --progress none --max-failed-tests 1
  python fuzz_test.py --clean --agent --max-failed-tests 1 -s ortools
"""
    parser = argparse.ArgumentParser(
        description="Run mutation-based fuzz tests for CPMpy solvers.",
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-s", "--solver", help="Solver to use.", default=None, type=str)
    parser.add_argument("-m", "--models", help="Directory containing model folders.", default="models", type=str)
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory to store failure artifacts and run_stats.json.",
        default="output",
        type=str,
    )
    parser.add_argument(
        "--clean",
        help="Remove existing contents of the output directory before starting.",
        action="store_true",
    )
    parser.add_argument(
        "-g",
        "--skip-global-constraints",
        help="Skip global constraints when testing.",
        action="store_true",
    )
    parser.add_argument(
        "--max-failed-tests",
        help="Stop after this many failed tests. Default: no limit.",
        default=math.inf,
        type=check_positive,
    )
    parser.add_argument(
        "--max-minutes",
        help="Maximum run time in minutes. Default: run indefinitely.",
        default=math.inf,
        type=check_positive,
    )
    parser.add_argument(
        "--max-fuzz-seconds",
        help="Maximum time in seconds for a single fuzz test. Default: 10.",
        default=None,
        type=check_positive,
    )
    parser.add_argument(
        "-mpm",
        "--mutations-per-model",
        help="Number of mutations executed on every model.",
        default=5,
        type=check_positive,
    )
    parser.add_argument(
        "-p",
        "--amount-of-processes",
        help="Number of worker processes.",
        default=max(1, cpu_count() - 1),
        type=check_positive,
    )
    parser.add_argument("--seed", help="Master seed for reproducibility.", default=None, type=int)
    parser.add_argument(
        "--agent",
        help="Shortcut for --non-interactive --quiet --output json --progress none.",
        action="store_true",
    )
    parser.add_argument(
        "--non-interactive",
        help="Fail fast and avoid terminal UI behavior.",
        action="store_true",
    )
    parser.add_argument("--quiet", help="Suppress progress and human-readable banners.", action="store_true")
    parser.add_argument(
        "--output",
        help="Final stdout format.",
        choices=("text", "json"),
        default="text",
    )
    parser.add_argument(
        "--progress",
        help="Progress display mode.",
        choices=("auto", "curses", "dots", "none"),
        default="auto",
    )
    parser.add_argument(
        "--dry-run",
        help="Validate configuration and print the planned run without starting workers.",
        action="store_true",
    )
    return parser


def apply_agent_defaults(args) -> None:
    if not args.agent:
        return
    args.non_interactive = True
    args.quiet = True
    args.output = "json"
    args.progress = "none"


def eprint(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def load_cpmpy():
    try:
        import cpmpy as cp
    except Exception as exc:
        vendored_cpmpy = Path(__file__).resolve().parents[1] / "libraries" / "cpmpy"
        if vendored_cpmpy.exists():
            sys.path.insert(0, str(vendored_cpmpy))
            try:
                import cpmpy as cp
            except Exception as vendored_exc:
                raise RuntimeError(
                    "Could not import cpmpy. Install the fuzz-test requirements before running tests. "
                    f"Import error: {vendored_exc}"
                ) from vendored_exc
            return cp
        raise RuntimeError(
            "Could not import cpmpy. Install the fuzz-test requirements before running tests. "
            f"Import error: {exc}"
        ) from exc
    return cp


def validate_solver(cp, solver: Optional[str]) -> str:
    available_solvers = cp.SolverLookup.solvernames()
    if solver is None:
        if not available_solvers:
            raise ValueError("No CPMpy solvers are available.")
        return available_solvers[0]
    if solver not in available_solvers:
        available = ", ".join(available_solvers)
        raise ValueError(f"Unknown solver '{solver}'. Available solvers: {available}")
    return solver


def discover_models(models_dir: str) -> List[str]:
    path = Path(models_dir)
    if not path.exists():
        raise ValueError(
            f"Model directory not found: {models_dir}\n"
            f"Use --models <dir> or generate models first, for example: python model_generator.py -o {models_dir}"
        )
    if not path.is_dir():
        raise ValueError(f"Model path is not a directory: {models_dir}")
    models = [str(path / model) for model in os.listdir(path)]
    if not models:
        raise ValueError(
            f"Model directory is empty: {models_dir}\n"
            f"Use --models <dir> with generated model folders."
        )
    return models


def validate_output_dir(output_dir: str, dry_run: bool) -> None:
    path = Path(output_dir)
    if path.exists() and not path.is_dir():
        raise ValueError(f"Output path exists but is not a directory: {output_dir}")

    check_path = path if path.exists() else path.parent
    if str(check_path) == "":
        check_path = Path(".")
    if not check_path.exists():
        raise ValueError(f"Parent directory for output path does not exist: {check_path}")
    if not os.access(check_path, os.W_OK):
        raise ValueError(f"Output directory is not writable: {check_path}")

    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def clean_output_dir(output_dir: str, dry_run: bool = False) -> bool:
    path = Path(output_dir)
    if not path.exists():
        return False
    if not path.is_dir():
        raise ValueError(f"Output path exists but is not a directory: {output_dir}")
    if dry_run:
        return True
    shutil.rmtree(path)
    return True


def select_progress_mode(args) -> str:
    if args.quiet or args.output == "json":
        return "none"
    if args.progress != "auto":
        return args.progress
    if sys.stdout.isatty() and not args.non_interactive:
        return "curses"
    return "none"


def build_summary(args, status: str, interrupted: bool, start_time: float, exit_code: int) -> dict:
    return {
        "status": status,
        "exit_code": exit_code,
        "total_tests": 0,
        "errors": 0,
        "timeouts": 0,
        "interrupted": interrupted,
        "duration_seconds": int(time.time() - start_time),
        "output_dir": args.output_dir,
        "solver": args.solver,
        "seed": args.seed,
    }


def summary_from_counters(args, status: str, interrupted: bool, start_time: float, exit_code: int, tests, errors, timeouts) -> dict:
    summary = build_summary(args, status, interrupted, start_time, exit_code)
    summary["total_tests"] = tests.value
    summary["errors"] = errors.value
    summary["timeouts"] = timeouts.value
    return summary


def summary_from_values(
    args,
    status: str,
    interrupted: bool,
    start_time: float,
    exit_code: int,
    total_tests: int,
    errors: int,
    timeouts: int,
) -> dict:
    summary = build_summary(args, status, interrupted, start_time, exit_code)
    summary["total_tests"] = total_tests
    summary["errors"] = errors
    summary["timeouts"] = timeouts
    return summary


def dry_run_summary(args, models: List[str], progress_mode: str) -> dict:
    return {
        "status": "dry_run",
        "exit_code": 0,
        "solver": args.solver,
        "models": args.models,
        "model_directories": len(models),
        "output_dir": args.output_dir,
        "clean": args.clean,
        "max_failed_tests": None if args.max_failed_tests == math.inf else args.max_failed_tests,
        "max_minutes": None if args.max_minutes == math.inf else args.max_minutes,
        "max_fuzz_seconds": args.max_fuzz_seconds if args.max_fuzz_seconds is not None else 10,
        "mutations_per_model": args.mutations_per_model,
        "amount_of_processes": args.amount_of_processes,
        "seed": args.seed,
        "non_interactive": args.non_interactive,
        "quiet": args.quiet,
        "output": args.output,
        "progress": progress_mode,
        "would_start_workers": False,
    }


def write_run_stats(output_dir: str, summary: dict) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stats_file = Path(output_dir) / "run_stats.json"
    with stats_file.open("w") as f:
        json.dump(
            {
                "total_tests": summary["total_tests"],
                "errors": summary["errors"],
                "timeouts": summary["timeouts"],
                "interrupted": summary["interrupted"],
                "duration_seconds": summary["duration_seconds"],
                "output_dir": summary["output_dir"],
                "solver": summary["solver"],
                "seed": summary["seed"],
                "status": summary["status"],
            },
            f,
            indent=2,
        )


def print_json(payload: dict) -> None:
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def print_text_summary(summary: dict, max_failed_tests) -> None:
    print(f"\nExecuted tests for {math.floor(summary['duration_seconds'] / 60)} minutes", flush=True)
    if summary["interrupted"]:
        print("Fuzz test was interrupted", flush=True)
    else:
        print("Quitting fuzz tests", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("FINAL STATISTICS", flush=True)
    print("=" * 60, flush=True)
    print(f"Total tests executed: {summary['total_tests']}", flush=True)
    print(f"Errors found: {summary['errors']}", flush=True)
    print(f"Timeouts: {summary['timeouts']}", flush=True)

    if summary["errors"] == max_failed_tests:
        print("Reached error threshold - stopped running further tests", flush=True)
    elif summary["interrupted"]:
        print("Test run was interrupted - partial results shown above", flush=True)
    elif summary["status"] == "failed":
        print("Test run failed before completion", flush=True)
    else:
        print("Test run completed successfully", flush=True)
    print("=" * 60 + "\n", flush=True)


def print_dry_run_text(payload: dict) -> None:
    print("Dry run: fuzz workers were not started.")
    print(f"solver: {payload['solver']}")
    print(f"models: {payload['models']} ({payload['model_directories']} directories)")
    print(f"output_dir: {payload['output_dir']}")
    if payload.get("clean"):
        print("clean: true")
    print(f"processes: {payload['amount_of_processes']}")
    print(f"progress: {payload['progress']}")


def run_worker(pipe_conn, show_progress: bool, *args):
    from verifiers.verifier_runner import run_verifiers

    if show_progress and pipe_conn is not None:
        with StdoutPipeRedirector(pipe_conn):
            run_verifiers(*args, show_progress=show_progress)
        pipe_conn.close()
        return

    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            run_verifiers(*args, show_progress=show_progress)
    if pipe_conn is not None:
        pipe_conn.close()


def read_dots_from_pipes(pipes: List[Connection]):
    while pipes:
        for pipe in list(pipes):
            try:
                while pipe.poll():
                    print(pipe.recv().replace("\n", ""), end="", flush=True)
            except EOFError:
                pipe.close()
                pipes.remove(pipe)
        time.sleep(0.2)


def read_from_pipes(pipes: List[Connection], current_tests, current_errors, current_timeouts):
    """
    Target for the monitoring process.
    Shows progress of fuzz-tester within the console.
    """

    def curses_main(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_BLUE, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_WHITE, -1)
        curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_WHITE)
        curses.init_pair(6, curses.COLOR_RED, curses.COLOR_WHITE)
        curses.init_pair(7, curses.COLOR_YELLOW, curses.COLOR_WHITE)

        stdscr.clear()
        stdscr.nodelay(True)
        height, width = stdscr.getmaxyx()
        output_buffer = ""

        while True:
            any_data = False
            try:
                if len(pipes) == 0:
                    break
                for i, pipe in enumerate(list(pipes)):
                    while pipe.poll():
                        try:
                            msg = pipe.recv()
                            output_buffer += msg.replace("\n", "")
                            any_data = True
                        except EOFError:
                            pipe.close()
                            pipes.remove(pipe)

                if any_data:
                    max_chars = (height - 1) * width
                    visible_output = output_buffer[-max_chars:]

                    stdscr.erase()
                    for row in range(height - 1):
                        line_start = row * width
                        line = visible_output[line_start : line_start + width]
                        for col, ch in enumerate(line):
                            if ch == "X":
                                color = curses.color_pair(1)
                            elif ch in ("E", "I"):
                                color = curses.color_pair(2)
                            elif ch == "T":
                                color = curses.color_pair(3)
                            else:
                                color = curses.color_pair(4)
                            stdscr.addch(row, col, ch, color)

                    banner = (
                        f"[Fuzz Test] Tests: {current_tests.value} | "
                        f"Errors: {current_errors.value} | Timeouts: {current_timeouts.value}"
                    )
                    stdscr.addnstr(height - 1, 0, banner.ljust(width), width - 1, curses.A_REVERSE)

                    legend_items = [
                        ("X", "Failed", 5),
                        ("E/I", "Internal Crash", 6),
                        ("T", "Timeout", 7),
                    ]
                    legend_strings = [f"({sym}) {label}]" for sym, label, _ in legend_items]
                    legend_length = len(" ".join(legend_strings)) + (len(legend_items) - 1)
                    start_x = max(0, width - legend_length - 1)

                    x = start_x
                    for sym, label, color in legend_items:
                        segment = f"({sym}) {label}]"
                        stdscr.addstr(height - 1, x, segment, curses.color_pair(color) | curses.A_BOLD)
                        x += len(segment) + 1

                    stdscr.refresh()
                else:
                    time.sleep(0.2)

            except KeyboardInterrupt:
                for pipe in pipes:
                    pipe.close()
                break
            except BrokenPipeError:
                pipe = pipes[i]
                pipe.close()
                pipes.remove(pipe)
                continue

    curses.wrapper(curses_main)
    try:
        curses.endwin()
    except curses.error:
        pass


def run_fuzz(args, models: List[str], progress_mode: str) -> int:
    set_start_method("spawn", force=True)
    start_time = time.time()
    max_time = args.max_minutes * 60
    max_failed_tests = args.max_failed_tests
    fuzz_time_limit = args.max_fuzz_seconds if args.max_fuzz_seconds is not None else 10
    show_progress = progress_mode in ("curses", "dots")

    pipes = []
    processes: List[Process] = []
    monitor_process = None
    interrupted = False
    failed = False
    failure_message = None
    current_amount_of_error = None
    current_amount_of_tests = None
    current_amount_of_timeouts = None

    if args.seed is not None:
        random.seed(args.seed)

    try:
        current_amount_of_error = Value("i", 0)
        current_amount_of_tests = Value("i", 0)
        current_amount_of_timeouts = Value("i", 0)
        lock = Lock()

        for _ in range(args.amount_of_processes):
            child_seed = random.randint(0, 2**32 - 1)
            parent_conn, child_conn = Pipe()
            pipes.append(parent_conn)
            process_args = (
                child_conn,
                show_progress,
                current_amount_of_tests,
                current_amount_of_error,
                current_amount_of_timeouts,
                lock,
                args.solver,
                args.mutations_per_model,
                models,
                max_failed_tests,
                args.output_dir,
                max_time,
                fuzz_time_limit,
                child_seed,
            )
            processes.append(Process(target=run_worker, args=process_args))

        if progress_mode == "curses":
            monitor_process = Process(
                target=read_from_pipes,
                args=(pipes, current_amount_of_tests, current_amount_of_error, current_amount_of_timeouts),
            )
            monitor_process.start()
        elif progress_mode == "dots":
            monitor_process = Process(target=read_dots_from_pipes, args=(pipes,))
            monitor_process.start()

        for process in processes:
            process.start()

        while any(process.is_alive() for process in processes):
            time.sleep(0.2)

    except KeyboardInterrupt:
        interrupted = True
        if not args.quiet and args.output == "text":
            print("\nInterrupt received, gracefully shutting down...", flush=True)
            print("Waiting for processes to complete current tests...", flush=True)
    except Exception as exc:
        failed = True
        failure_message = str(exc)
        eprint(f"Unexpected error: {exc}")
        if not args.quiet and args.output == "text":
            eprint(f"stacktrace:\n{traceback.format_exc()}")
    finally:
        time.sleep(2)
        if monitor_process is not None and monitor_process.is_alive():
            monitor_process.terminate()

        for process in processes:
            if process._popen is not None:
                process.terminate()

    exit_code = 130 if interrupted else 1 if failed else 0
    status = "interrupted" if interrupted else "failed" if failed else "completed"
    if current_amount_of_tests is None:
        summary = summary_from_values(args, status, interrupted, start_time, exit_code, 0, 0, 0)
    else:
        summary = summary_from_counters(
            args,
            status,
            interrupted,
            start_time,
            exit_code,
            current_amount_of_tests,
            current_amount_of_error,
            current_amount_of_timeouts,
        )
    if failure_message is not None:
        summary["error"] = failure_message
    write_run_stats(args.output_dir, summary)

    if args.output == "json":
        print_json(summary)
    elif not args.quiet:
        print_text_summary(summary, max_failed_tests)

    return exit_code


def main(argv=None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    apply_agent_defaults(args)

    start_time = time.time()
    try:
        cp = load_cpmpy()
        args.solver = validate_solver(cp, args.solver)
        models = discover_models(args.models)
        validate_output_dir(args.output_dir, dry_run=args.dry_run)
        output_dir_cleaned = False
        if args.clean:
            output_dir_cleaned = clean_output_dir(args.output_dir, dry_run=args.dry_run)
            if output_dir_cleaned and not args.dry_run:
                validate_output_dir(args.output_dir, dry_run=False)
        progress_mode = select_progress_mode(args)

        if args.dry_run:
            payload = dry_run_summary(args, models, progress_mode)
            if args.output == "json":
                print_json(payload)
            elif not args.quiet:
                print_dry_run_text(payload)
            return 0

        if not args.quiet and args.output == "text":
            if output_dir_cleaned and not args.dry_run:
                print(f"Cleaned output directory '{args.output_dir}'.", flush=True)
            print(
                f"\nUsing solver '{args.solver}' with models in '{args.models}' "
                f"and writing to '{args.output_dir}'.",
                flush=True,
            )
            print(f"Will use {args.amount_of_processes} parallel executions, starting...\n", flush=True)

        return run_fuzz(args, models, progress_mode)

    except (RuntimeError, ValueError) as exc:
        eprint(f"Error: {exc}")
        eprint("Try: python fuzz_test.py --help")
        if args.dry_run and args.output == "json":
            payload = build_summary(args, "validation_failed", False, start_time, 1)
            payload["error"] = str(exc)
            print_json(payload)
        return 1


if __name__ == "__main__":
    sys.exit(main())
