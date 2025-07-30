import os
os.environ["PYTHONHASHSEED"] = "0" # <- required for reproducability, otherwise hashes are consistent between runs

import random
import numpy as np
import argparse
import curses
import math
import signal
import sys
import threading
import traceback
import time
from pathlib import Path
from multiprocessing import Process,Lock, Manager, set_start_method,Pool, cpu_count

import cpmpy as cp

from utils import StdoutPipeRedirector
from verifiers.verifier_runner import run_verifiers


def run_with_pipe(pipe_conn, *args):
    """
    Target for worker threads.
    Runs fuzz-test verifiers.
    """
    with StdoutPipeRedirector(pipe_conn): # capture to pipe for manager
        run_verifiers(*args)
    pipe_conn.close()


def read_from_pipes(pipes, current_tests, current_errors, current_timeouts):
    """
    Target for the monitoring thread.
    Shows progress of fuzz-tester within the console.
    """
    def curses_main(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()

        # Define color pairs
        curses.init_pair(1, curses.COLOR_BLUE, -1)      # Failed model
        curses.init_pair(2, curses.COLOR_RED, -1)       # Internal crash / Internal function crash
        curses.init_pair(3, curses.COLOR_YELLOW, -1)    # Timeout
        curses.init_pair(4, curses.COLOR_WHITE, -1)     # OK

        # - same colors, but now with white background (for legend)
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
                # Collect data from worker pipes
                if len(pipes) == 0:
                    break
                for i,p in enumerate(pipes):
                    while p.poll():
                        try:
                            msg = p.recv()
                            output_buffer += msg.replace("\n", "")
                            any_data = True
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
                        if ch == 'X':
                            stdscr.addch(i, j, ch, curses.color_pair(1))
                        elif ch == 'E' or ch == 'I':
                            stdscr.addch(i, j, ch, curses.color_pair(2))
                        elif ch == 'T':
                            stdscr.addch(i, j, ch, curses.color_pair(3))
                        else:
                            stdscr.addch(i, j, ch, curses.color_pair(4))

                # Draw status banner
                banner = f"[Fuzz Test] Tests: {current_tests.value} | Errors: {current_errors.value} | Timeouts: {current_timeouts.value}"
                stdscr.addnstr(height - 1, 0, banner.ljust(width), width - 1, curses.A_REVERSE)

                # Legend items (colored, no reverse)
                legend_items = [
                    ('X', 'Failed', 5),
                    ('E/I', 'Internal Crash', 6),
                    ('T', 'Timeout', 7),
                ]

                # Create legend text and calculate total length
                legend_strings = [f"({sym}) {label}]" for sym, label, _ in legend_items]
                legend_text = ' '.join(legend_strings)
                legend_length = len(legend_text) + (len(legend_items) - 1)

                # Calculate start x-position for right alignment
                start_x = max(0, width - legend_length - 1)

                # Draw colored legend on top of banner (overwriting part of it)
                x = start_x
                for sym, label, color in legend_items:
                    segment = f"({sym}) {label}]"
                    stdscr.addstr(height - 1, x, segment, curses.color_pair(color) | curses.A_BOLD)
                    x += len(segment) + 1

                stdscr.refresh()

                if not any_data:
                    time.sleep(0.2)

            except KeyboardInterrupt as e:
                for pipe in pipes:
                    pipe.close()
                break
            except ConnectionResetError as e:
                break
            except BrokenPipeError as e:
                # If pipe unexpectedly dies, remove it as to not hault the others
                # TODO restart another pipe?
                pipes[i].close()
                del pipes[i]
                continue

    curses.wrapper(curses_main)
    curses.endwin()

    print("Exiting monitor")

if __name__ == '__main__':
    # get all the available solvers from cpympy
    available_solvers = cp.SolverLookup.solvernames()
    
    # Getting and checking the input parameters    
    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    
    # CLI argument parser
    parser = argparse.ArgumentParser(description = "A python application to fuzz_test your solver(s)")
    parser.add_argument("-s", "--solver", help = "The Solver to use", required = False,type=str,choices=available_solvers, default=available_solvers[0])
    parser.add_argument("-m", "--models", help = "The path to load the models", required=False, type=str, default="models")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="output")
    parser.add_argument("-g", "--skip-global-constraints", help = "Skip the global constraints when testing", required=False, default = False)
    parser.add_argument("--max-failed-tests", help = "The maximum amount of test that may fail before quitting the application (by default an infinite amount of tests can fail). if the maximum amount is reached it will quit even if the max-minutes wasn't reached", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("--max-minutes", help = "The maximum time (in minutes) the tests should run (by default the tests will run forever). The tests will quit sooner if max-bugs was set and reached or an keyboardinterrupt occured", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("--max-fuzz-seconds", help = "The maximum time (in seconds) a single test is allowed to take before timeout.", required=False, default=None, type=check_positive)
    parser.add_argument("-mpm","--mutations-per-model", help = "The amount of mutations that will be executed on every model", required=False, default=5 ,type=check_positive)
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    parser.add_argument("--seed", help = "The master seed (for reproducability)", required=False, default=None, type=int)
    args = parser.parse_args()

    models = []
    max_failed_tests = args.max_failed_tests

    # create a list with all the directories
    for model in os.listdir(args.models):
        models.append(os.path.join(args.models, model))
    if len(models) == 0:
        print(f"models is empty")
        sys.exit(0)
    # output dir will be created if it does not exist
    os.makedirs(args.output_dir, exist_ok=True)

    # showing the info about the given params to the user
    print("\nUsing solver '"+args.solver+"' with models in '"+args.models+"' and writing to '"+args.output_dir+"'." ,flush=True,end="\n\n")
    print("Will use "+str(args.amount_of_processes)+ " parallel executions, starting...",flush=True,end="\n\n")

    # creating the vars for the multiprocessing
    set_start_method("spawn")
    start_time = time.time()
    max_time = args.max_minutes * 60

    manager = Manager()
    current_amount_of_error = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)
    current_amount_of_timeouts = manager.Value("i",0)

    lock = Lock()
    
    # creating processes to run all the tests
    processes = []

    from multiprocessing import Pipe

    pipes = []
    seeds = []
    processes = []

    master_seed = args.seed
    if master_seed is not None:
        random.seed(master_seed)

    for _ in range(args.amount_of_processes):
        child_seed = random.randint(0, 2**32 - 1)

        # Create pipe for stdout
        parent_conn, child_conn = Pipe()
        pipes.append(parent_conn)

        # Pass child_conn into the process
        fuzz_time_limit = args.max_fuzz_seconds if args.max_fuzz_seconds is not None else 20
        process_args = (child_conn, current_amount_of_tests, current_amount_of_error, current_amount_of_timeouts, lock, args.solver, args.mutations_per_model, models, max_failed_tests, args.output_dir, max_time, fuzz_time_limit, child_seed)
        processes.append(Process(target=run_with_pipe,args=process_args))

    try:
        # Start minitoring process
        monitor_process = Process(target=read_from_pipes, args=(pipes, current_amount_of_tests, current_amount_of_error, current_amount_of_timeouts))
        monitor_process.start()
                
        # Start the worker processes
        for process in processes:
            process.start()

        start = time.time()
        # Wait for workers to finish
        while any(process.is_alive() for process in processes):
            time.sleep(0.2)


    except KeyboardInterrupt as e:
        print("interrupting...",flush=True,end="\n")
    except Exception as e: 
        print(f"An unexcpected error occured error:\n{e} \nstacktrace:\n{traceback.format_exc()}",flush=True,end="\n")
    finally:
        time.sleep(2) # Some delay to not miss any results from worker processes

        # Close monitoring process
        if monitor_process.is_alive():
            monitor_process.terminate()
 
        print("\nExecuted tests for "+str(math.floor((time.time()-start_time)/60))+" minutes",flush=True,end="\n")

        # Terminate all the worker processes (if they have not exited already)
        for process in processes:
            if process._popen != None: 
                process.terminate()
        print("Quiting fuzz tests \n",flush=True,end="\n")

        if current_amount_of_error.value == max_failed_tests:
            print("Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")
        else:
            print("Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")

        sys.exit()

