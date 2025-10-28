import argparse
import math
import os
import sys
import traceback
import time
from pathlib import Path
from multiprocessing import Process,Lock, Manager, set_start_method,Pool, cpu_count
import csv
from datetime import datetime

import cpmpy as cp

from verifiers.verifier_runner import run_verifiers

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
    
    parser = argparse.ArgumentParser(description = "A python application to fuzz_test your solver(s)")
    parser.add_argument("-s", "--solver", help = "The Solver to use", required = False,type=str,choices=available_solvers, nargs='+', default=[available_solvers[0]])
    parser.add_argument("-m", "--models", help = "The path to load the models", required=False, type=str, default="models")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="output")
    parser.add_argument("-g", "--skip-global-constraints", help = "Skip the global constraints when testing", required=False, default = False)
    parser.add_argument("--max-failed-tests", help = "The maximum amount of test that may fail before quitting the application (by default an infinite amount of tests can fail). if the maximum amount is reached it will quit even if the max-minutes wasn't reached", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("--max-minutes", help = "The maximum time (in minutes) the tests should run (by default the tests will run forever). The tests will quit sooner if max-bugs was set and reached or an keyboardinterrupt occured", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("-mpm","--mutations-per-model", help = "The amount of mutations that will be executed on every model", required=False, default=5 ,type=check_positive)
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    parser.add_argument("--mm-prob", help="The probability that a metamorphic mutation will be chosen in case of a verifier that allows other mutations", required=False, default=1, type=float)
    args = parser.parse_args()
    models = []
    max_failed_tests = args.max_failed_tests
    max_minutes = args.max_minutes

    # create a list with all the directories
    for model in os.listdir(args.models):
        models.append(os.path.join(args.models, model))
    if len(models) == 0:
        print(f"models is empty")
        sys.exit(0)
    # output dir will be created if it does not exist
    os.makedirs(args.output_dir, exist_ok=True)

    # showing the info about the given params to the user
    print("\nUsing solver(s): '" + ", ".join(args.solver)+"' with models in '"+args.models+"' and writing to '"+args.output_dir+"'." ,flush=True,end="\n\n")
    print("Will use "+str(args.amount_of_processes)+ " parallel executions, starting...",flush=True,end="\n\n")

    # creating the vars for the multiprocessing
    set_start_method("spawn")
    start_time = time.time()
    max_time = start_time + 60* args.max_minutes

    manager = Manager()
    current_amount_of_error = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)

    lock = Lock()
    
    # creating processes to run all the tests
    processes = []

    # FOR EXPERIMENTS:
    solvers = ['ortools', 'minizinc', 'choco', 'gurobi']
    verifiers = ["solver_vote_count_verifier", "solver_vote_eq_verifier", "solver_vote_sat_verifier", "solver_vote_sol_verifier", "strengthening_weakening_verifier"]
    solver_counts = {s: manager.Value(f"{s}", 0) for s in solvers}
    verifier_counts = {v: manager.Value(f"{v}", 0) for v in verifiers}
    verifier_run_times = {v: manager.Value(f"{v}", 0) for v in verifiers}
    from itertools import combinations
    solver_combos = [list(c) for c in combinations(solvers, 2)]

    for x in range(args.amount_of_processes):
        process_args = (current_amount_of_tests, current_amount_of_error, lock, solver_combos[x],
                        args.mutations_per_model, models, max_failed_tests, args.output_dir, max_time, args.mm_prob,
                        solver_counts, verifier_counts, verifier_run_times)  # PAS TERUG AAN NA EXPERIMENTEN
        processes.append(Process(target=run_verifiers,args=process_args))

    try:
        # start the processes
        for process in processes:
            process.start()

        for process in processes:
            process.join(timeout=args.max_minutes*60)  # wait max double minutes

        # If any process is still alive after timeout, terminate it
        for process in processes:
            if process.is_alive():
                print(f"Forcefully terminating process {process.pid}", flush=True)
                process.terminate()
                process.join()  # Clean up
            
    except KeyboardInterrupt as e:
        print("interrupting...",flush=True,end="\n")
    except Exception as e: 
        print(f"An unexcpected error occured error:\n{e} \nstacktrace:\n{traceback.format_exc()}",flush=True,end="\n")
    finally:
        print("\nExecuted tests for "+str(math.floor((time.time()-start_time)/60))+" minutes",flush=True,end="\n")
        # terminate all the processes
        for process in processes:
            if process._popen != None: 
                process.terminate()
        print("Quiting fuzz tests \n",flush=True,end="\n")

        if current_amount_of_error.value == max_failed_tests:
            print("Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")
        else:
            print("Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")

        run_name = args.output_dir
        minutes_ran = args.max_minutes
        mpm = args.mutations_per_model
        mm_prob = args.mm_prob
        amnt_tests = current_amount_of_tests.value
        amnt_errors = current_amount_of_error.value
        solver_count_vals = {s: c.value for s, c in solver_counts.items()}
        verifier_count_vals = {v: c.value for v, c in verifier_counts.items()}
        verifier_runtime_vals = {v: t.value for v, t in verifier_run_times.items()}
        print(f"Run \"{run_name}\" ran for {minutes_ran} minutes and executed {amnt_tests} tests of which {amnt_errors} failed.")
        print("Amount of times each solver ran for:", solver_count_vals)
        print("Amount of times each verifier ran:", verifier_count_vals)
        print("Time each verifier ran:", verifier_runtime_vals)

        # Prepare timestamp and filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_filename = f"{run_name}_{timestamp}.csv"

        # Create the rows for the CSV
        headers = ["run_name", "mutations_per_model", "mm_probability", "minutes_ran", "amnt_tests", "amnt_errors"]
        row = [run_name, mpm, mm_prob, minutes_ran, amnt_tests, amnt_errors]

        # Optionally, flatten solver and verifier data into columns
        for s, count in solver_count_vals.items():
            headers.append(f"solver_count_{s}")
            row.append(count)

        for v, count in verifier_count_vals.items():
            headers.append(f"verifier_count_{v}")
            row.append(count)

        for v, t in verifier_runtime_vals.items():
            headers.append(f"verifier_runtime_{v}")
            row.append(t)

        # Save to CSV
        with open(stats_filename, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow(row)

        print(f"Saved run statistics to {stats_filename}")
