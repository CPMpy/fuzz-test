import os
os.environ["PYTHONHASHSEED"] = "0" # <- required for reproducability, otherwise hashes are consistent between runs

import sys
import time
import glob
import random
import argparse
import curses
import queue
import shutil
import pickle
import warnings
import logging
from colorama import Fore, Back, Style
import multiprocessing
from multiprocessing import Lock, Manager, Pipe, Pool, Process, cpu_count,set_start_method
from importlib import reload

import cpmpy as cp
from verifiers import *
from verifiers.utils import Exit
from utils import StdoutPipeRedirector
from fuzz_test_utils.fuzz_test_errors import FuzzTestErrorType

# Set up logging for debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fuzz_rerunner_debug.log'),
    ]
)
logger = logging.getLogger(__name__)


def rerun_file(
        failed_model_file,                                          # fuzz test output file to rerun
        output_dir,                                                 # where to save output of rerun
        lock, current_amount_of_tests, current_amount_of_errors,    # for TUI
        max_fuzz_seconds,                                           # time limit on rerun
        mutator_indices=None                                        # indices of mutators to re-apply
    ):
    """
    Function for re-running a fuzz-test error.
    """

    # Load error from file 
    error = Exit.load(failed_model_file)

    # Set random seed
    random.seed(error.verifier_kwargs["seed"])

    # Construct verifier options
    verifier_kwargs = error.verifier_kwargs
    verifier_kwargs["time_limit"] = max_fuzz_seconds # add / update time limit in kwargs

    # Parse mutator indices if provided
    selected_indices = None
    if mutator_indices is not None:
        if mutator_indices.lower().strip() == "none":
            selected_indices = []  # Empty list means no mutators
        else:
            try:
                selected_indices = [int(x.strip()) for x in mutator_indices.split(',')]
            except ValueError:
                print(f"Warning: Invalid mutator indices format '{mutator_indices}', using all mutators")
                selected_indices = None

    # Track execution time
    start_time = time.time()
    # Re-run verifier with selective mutators
    verifier_instance = lookup_verifier(error.verifier.getName())(**verifier_kwargs)
    if selected_indices is not None:
        rerun_error = verifier_instance.rerun_selective(error, selected_indices)
    else:
        rerun_error = verifier_instance.rerun(error)
    execution_time = time.time() - start_time
    rerun_error.verifier_kwargs = verifier_kwargs # store used options

    # Log if rerun produces a different outcome (success vs failure)
    original_is_error = error.type != FuzzTestErrorType.ok
    rerun_is_error = rerun_error.type != FuzzTestErrorType.ok

    if original_is_error and not rerun_is_error:
        logger.debug(f"Rerun resolved error: {failed_model_file} -> {error.type} became {rerun_error.type}")
    elif not original_is_error and rerun_is_error:
        logger.debug(f"Rerun introduced error: {failed_model_file} -> {error.type} became {rerun_error.type}")
    elif original_is_error and rerun_is_error and error.type != rerun_error.type:
        logger.debug(f"Rerun changed error type: {failed_model_file} -> {error.type} became {rerun_error.type}")

    # Print status to monitor
    if rerun_error.alternative_label is not None: # if error defines a custom label to be printed
        print(rerun_error.alternative_label, end='', flush=True)
    else:
        if rerun_error.type.value == error.type.value:  # same error, nothing special - compare values not objects
            print('.', end='', flush=True)
        elif rerun_error.type == FuzzTestErrorType.ok:  # bug has been fixed!
            print('*', end='', flush=True)
        else:                                           # error changed?
            print("[", rerun_error.type, error.type, "]")
            logger.debug(f"Error type mismatch detected:")
            logger.debug(f"  rerun_error.type = {rerun_error.type}")
            logger.debug(f"  error.type = {error.type}")
            logger.debug(f"  rerun_error.type.value = '{rerun_error.type.value}'")
            logger.debug(f"  error.type.value = '{error.type.value}'")
            logger.debug(f"  rerun_error.type == error.type = {rerun_error.type == error.type}")
            logger.debug(f"  rerun_error.type is error.type = {rerun_error.type is error.type}")
            logger.debug(f"  Original file: {failed_model_file}")
            print('F', end='', flush=True)

    # Update statistics for TUI monitor
    lock.acquire()
    try:
        current_amount_of_tests.value += 1
    finally:
        lock.release()

    # Always write output files for consistent comparison (including resolved errors)
    # TODO should share code with 'run_verifiers'
    error_data = {
                    'verifier':rerun_error.verifier.getName(),
                    'solver' : rerun_error.verifier_kwargs["solver"],
                    'mutations_per_model' : rerun_error.verifier_kwargs["mutations_per_model"],
                    "seed": rerun_error.verifier_kwargs["seed"],
                    # "execution_time": execution_time,
                    "error" :rerun_error  # Use rerun_error instead of original error
                }

    # Formatting of error report
    verifier_text = ""
    if rerun_error.type != FuzzTestErrorType.fuzz_test_crash:
        verifier_text = "Chosen Verifier: "+error_data["verifier"]

    # Format execution time similar to original fuzzer
    execution_time_text = f"{str(int(execution_time//60))} minutes {str(int(execution_time%60))} seconds"

    if rerun_error.type == FuzzTestErrorType.ok:
        # Special case for resolved errors
        total_error_text = f"""Rerun result: RESOLVED

    Original error was resolved in rerun
    Used solver: {error_data['solver']}
    {verifier_text}
    With {error_data['mutations_per_model']} mutations per model
    With seed: {error_data['seed']}
    Rerun execution time: {execution_time_text}

Result: Test passed successfully on rerun
===============================================================================
Original error: {error.type}
Rerun result: {rerun_error.type}
"""
    else:
        # Standard error case
        error_text = rerun_error.text()
        total_error_text = f"""An error occured while running a test

    Used solver: {error_data['solver']}
    {verifier_text}
    With {error_data['mutations_per_model']} mutations per model
    With seed: {error_data['seed']}
    Rerun execution time: {execution_time_text}

Error Details
===============================================================================

{error_text}

"""

    # Save error to pickle file (always)
    rerun_error.write(output_dir, base_name=error.base_name)
    # Save error report to text file (always)
    output_file_path = os.path.join(output_dir, error.base_name+".txt")
    with open(output_file_path, "w") as ff:
        ff.write(total_error_text)

    # Log the output files for debugging
    logger.debug(f"  Rerun output files: {os.path.join(output_dir, error.base_name + '.pickle')} and {output_file_path}")

    # Update error count only if there's still an error
    if rerun_error.type != FuzzTestErrorType.ok:
        lock.acquire()
        try:
            current_amount_of_errors.value += 1
        finally:
            lock.release()

    return rerun_error


def worker(job_queue, pipe, lock, result_queue, output_dir, current_amount_of_tests, current_amount_of_errors, current_amount_of_workers, elaborate=False, max_fuzz_seconds=10, mutator_indices=None):
    """
    Target for worker processes.
    """
    
    # Register worker in monitor UI
    lock.acquire()
    try:
        current_amount_of_workers.value += 1
    finally:
        lock.release()

    while True:
        """
        Continiously fetch for now jobs to perform, if none left, exit.
        """
        try:
            file = job_queue.get(timeout=1)
        except queue.Empty:
            result_queue.put(None)
            break
        try:
            with StdoutPipeRedirector(pipe):
                warnings.filterwarnings("ignore")
                result = rerun_file(file, output_dir, lock, current_amount_of_tests, current_amount_of_errors, max_fuzz_seconds, mutator_indices)
                lock.acquire()
                try:
                    result_queue.put((file, result))
                except Exception as e:
                    raise e
                finally:
                    lock.release()

                if elaborate:
                    print(f"Processed: {file}")

        except Exception as e:
            lock.acquire()
            try:
                result_queue.put((file, None))
            except Exception as e:
                raise e
            finally:
                lock.release()

            print(f"Error processing {file}: {e}")
            # traceback.print_exc()

        job_queue.task_done()
            
    # De-register worker
    lock.acquire()
    try:
        current_amount_of_workers.value -= 1
    except:
        pass
    finally:
        lock.release()


import select

def read_from_pipes(pipes, current_tests, current_errors, total_tests, current_amount_of_workers):
    def curses_main(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()

        # Define color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Blue on default
        curses.init_pair(2, curses.COLOR_RED, -1)    # Red on default
        curses.init_pair(3, curses.COLOR_WHITE, -1)  # Default text

        stdscr.clear()
        stdscr.nodelay(True)
        height, width = stdscr.getmaxyx()
        output_buffer = ""

        while True:
            try:
                if current_amount_of_workers.value == 0 and current_tests.value > 0:
                    break
                for p in pipes:
                    if p.poll():
                        try:
                            msg = p.recv()
                            output_buffer += msg.replace("\n", "")
                        except EOFError:
                            pass

                # Trim to visible screen
                max_chars = (height - 1) * width
                visible_output = output_buffer[-max_chars:]

                # Clear screen and draw characters with color
                stdscr.erase()
                for i in range(height - 1):
                    line_start = i * width
                    line = visible_output[line_start:line_start + width]
                    for j, ch in enumerate(line):
                        if ch == '*':
                            stdscr.addch(i, j, ch, curses.color_pair(1))
                        elif ch == 'F':
                            stdscr.addch(i, j, ch, curses.color_pair(2))
                        else:
                            stdscr.addch(i, j, ch, curses.color_pair(3))

                # Draw status banner
                banner = f"[Fuzz Rerunner] Workers: {current_amount_of_workers.value} | Tests: {current_tests.value} / {total_tests} ({(100 * current_tests.value / total_tests):.2f}%)| Errors: {current_errors.value} | Fixed: {current_tests.value - current_errors.value}"
                stdscr.addnstr(height - 1, 0, banner.ljust(width), width - 1, curses.A_REVERSE)

                stdscr.refresh()
                time.sleep(0.2)

            except KeyboardInterrupt as e:
                for pipe in pipes:
                    pipe.close()
                break
            except ConnectionResetError as e:
                break
            except BrokenPipeError as e:
                break

        curses.endwin()

    curses.wrapper(curses_main)


# Import
from cpu_cores import CPUCoresCounter

# We build an instance for the current operating system
# instance = CPUCoresCounter.factory()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A Python script for rerunning previous failed models")
    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    
    parser.add_argument("-m", "--failed_model_file", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=False, type=str, default='output')
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="bug_output")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1, type=check_positive) # the -1 is for the main process
    parser.add_argument("-e","--elaborate", help = "Elaborate print, also show filenames of errors that are re-run", required=False, default=False, type=bool) # the -1 is for the main process
    parser.add_argument("-r","--remove", help = "Remove fixed error files", action="store_true")
    parser.add_argument("-M","--move-dir", help = "Directory to move fixed error files to", type=str)
    parser.add_argument("--max-fuzz-seconds", help = "", required=False, default=10, type=check_positive)
    parser.add_argument("--mutator-indices", help = "Comma-separated list of mutator indices to re-apply (e.g., '0,2,4'), or 'none' to apply no mutators. If not provided, all mutators are re-applied.", type=str)

    set_start_method("spawn")
    args = parser.parse_args()

    current_working_directory = os.getcwd()
    output_dir = os.path.join(current_working_directory, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if args.move_dir:
        move_dir = os.path.join(current_working_directory, args.move_dir)
        os.makedirs(move_dir, exist_ok=True)

    failed_model_file = os.path.join(current_working_directory, args.failed_model_file)

    if os.path.isdir(failed_model_file):
        """
        Rerun all models within provided directory using a multiprocessing job queue.
        """
        all_files = glob.glob(failed_model_file + "/*.pickle")

        # Filter out fuzz_test_crash files
        files = []
        skipped_crash_files = []

        for file in all_files:
            try:
                # Load error to check its type
                # Try to load as Exit object first
                try:
                    error = Exit.load(file)
                    if error.type == FuzzTestErrorType.fuzz_test_crash:
                        skipped_crash_files.append(file)
                    else:
                        files.append(file)
                except (TypeError, AttributeError):
                    # If Exit.load fails, try loading as raw pickle (dictionary format)
                    import pickle
                    with open(file, 'rb') as f:
                        error_data = pickle.load(f)

                    # Check if it's dictionary format with nested error
                    if isinstance(error_data, dict) and 'error' in error_data:
                        error_type = error_data['error'].get('type')
                        if error_type == FuzzTestErrorType.fuzz_test_crash:
                            skipped_crash_files.append(file)
                        else:
                            files.append(file)
                    else:
                        # Unknown format, include in regular processing
                        files.append(file)
            except Exception:
                # If we can't load the file at all, include it in the regular processing
                files.append(file)

        # Statistics reporting between monitor and worker threads
        manager = Manager()
        current_amount_of_errors = manager.Value("i",0)
        current_amount_of_tests = manager.Value("i",0)
        current_amount_of_workers = manager.Value("i",0)
        skipped_count = len(skipped_crash_files)

        lock = Lock() # prevent concurrent updates to above datastructures
        
        job_queue = multiprocessing.JoinableQueue() # queue for work to be performed
        result_queue = multiprocessing.Queue()      # queue for collecting results
        processes = []
        pipes = []
        
        for file in files:
            job_queue.put(file)
        
        print(f"rerunning failed models in directory {failed_model_file}", flush=True)
        if skipped_count > 0:
            print(f"Skipping {skipped_count} fuzz_test_crash instances (not suitable for retesting)", flush=True)

        # Create worker processes
        for _ in range(args.amount_of_processes):
            parent_conn, child_conn = Pipe() # communication pipe between worker and monitor
            pipes.append(parent_conn)
            p = multiprocessing.Process(
                target=worker,
                args=(job_queue, child_conn, lock, result_queue, output_dir,current_amount_of_tests, current_amount_of_errors, current_amount_of_workers, args.elaborate, args.max_fuzz_seconds, args.mutator_indices)
            )
            processes.append(p)

        try:
            # Create and start monitoring process
            monitor_process = Process(target=read_from_pipes, args=(pipes, current_amount_of_tests, current_amount_of_errors, len(files), current_amount_of_workers))
            monitor_process.start()

            # Start worker processes
            for process in processes:
                process.start()

            # Wait for all jobs to be completed
            job_queue.join()
        
        except KeyboardInterrupt as e:
            print("interrupting...",flush=True,end="\n")
        except Exception as e: 
            print(f"An unexcpected error occured error:\n{e} \nstacktrace:\n{traceback.format_exc()}",flush=True,end="\n")
        finally:

            print("exited loop")

            # Close monitor (if needed)
            if monitor_process.is_alive():
                monitor_process.terminate()

            # Collect results from results-queue
            results = {}
            num_todo = len(processes)
            num_done = 0
            while num_done < num_todo:
                
                lock.acquire()
                try:
                    r = result_queue.get(timeout=1)
                    if r is None:
                        num_done += 1
                        continue
                    else:
                        file, result = r
                        results[file] = result
                except queue.Empty:
                    break
                finally:
                    lock.release()
                                        
            # Collect statistics after complete rerun
            still_fails = {k: v for k, v in results.items() if v is not None and hasattr(v, 'type') and v.type != FuzzTestErrorType.ok}
            fixed = {k: v for k, v in results.items() if v is not None and hasattr(v, 'type') and v.type == FuzzTestErrorType.ok}

            print(Style.RESET_ALL + "\nsuccessfully tested all the models", flush=True)
            print(Fore.RED + f"{len(still_fails)} models still fail " +
                    Fore.GREEN + f"{len(fixed)} models no longer fail " +
                    Fore.YELLOW + f"{skipped_count} models skipped (fuzz_test_crash)" + Style.RESET_ALL, flush=True)

            if args.elaborate:
                print(f"\n{Fore.RED}Still failing models:{Style.RESET_ALL}")
                for f in still_fails:
                    print(f)
                print(f"\n{Fore.GREEN}Fixed models:{Style.RESET_ALL}")
                for f in fixed:
                    print(f)

            if args.remove or args.move_dir:
                for f, result in results.items():
                    if result is not None and hasattr(result, 'type') and result.type == FuzzTestErrorType.ok:
                        txt_file = f.replace('.pickle', '.txt')
                        if args.move_dir:
                            if os.path.exists(txt_file):
                                shutil.move(txt_file, os.path.join(move_dir, os.path.basename(txt_file)))
                            shutil.move(f, os.path.join(move_dir, os.path.basename(f)))
                            if args.elaborate:
                                print(f"Moved {f} to {move_dir}")
                        elif args.remove:
                            if os.path.exists(txt_file):
                                os.remove(txt_file)
                            os.remove(f)
                            if args.elaborate:
                                print(f"Removed {f}")

            print("see output files for more info", flush=True)
            
    elif os.path.isfile(failed_model_file):
        """
        Rerun a single model
        """
        # Check if this is a fuzz_test_crash file
        try:
            # Try to load as Exit object first
            try:
                error = Exit.load(failed_model_file)
                if error.type == FuzzTestErrorType.fuzz_test_crash:
                    print(f"Skipping {failed_model_file} - fuzz_test_crash instances are not suitable for retesting")
                    sys.exit(0)
            except (TypeError, AttributeError):
                # If Exit.load fails, try loading as raw pickle (dictionary format)
                import pickle
                with open(failed_model_file, 'rb') as f:
                    error_data = pickle.load(f)

                # Check if it's dictionary format with nested error
                if isinstance(error_data, dict) and 'error' in error_data:
                    error_type = error_data['error'].get('type')
                    if error_type == FuzzTestErrorType.fuzz_test_crash:
                        print(f"Skipping {failed_model_file} - fuzz_test_crash instances are not suitable for retesting")
                        sys.exit(0)
        except Exception:
            # If we can't load the file, proceed with normal processing
            pass

        manager = Manager()
        current_amount_of_errors = manager.Value("i",0)
        current_amount_of_tests = manager.Value("i",0)
        current_amount_of_workers = manager.Value("i",0)

        lock = Lock()
        print("detected file")
        result = rerun_file(failed_model_file,output_dir,lock,current_amount_of_tests,current_amount_of_errors, args.max_fuzz_seconds, args.mutator_indices)
        print("\nsucessfully tested model")
        if result is not None and hasattr(result, 'type') and result.type != FuzzTestErrorType.ok:
            print(Fore.RED + f"Found Error: {result.exception}, see the output file for more details")
        else:
            print(Fore.GREEN +"\nNo errors were found")
            if args.remove or args.move_dir:
                txt_file = failed_model_file.replace('.pickle', '.txt')
                if args.move_dir:
                    if os.path.exists(txt_file):
                        shutil.move(txt_file, os.path.join(move_dir, os.path.basename(txt_file)))
                    shutil.move(failed_model_file, os.path.join(move_dir, os.path.basename(failed_model_file)))
                    print(f"Moved {failed_model_file} to {move_dir}")
                elif args.remove:
                    if os.path.exists(txt_file):
                        os.remove(txt_file)
                    os.remove(failed_model_file)
                    print(f"Removed {failed_model_file}")
    else:
        print(Fore.YELLOW +f"failed model file not found: {failed_model_file}")
    print(Style.RESET_ALL)