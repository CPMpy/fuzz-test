import argparse
import math
import os
import sys
from pathlib import Path
import time
from multiprocessing import Lock, Manager, set_start_method,Pool, cpu_count
from threading import Thread

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
    parser.add_argument("-s", "--solver", help = "The Solver to use", required = False,type=str,choices=available_solvers, default=available_solvers[0])
    parser.add_argument("-m", "--models", help = "The path to load the models", required=False, type=str, default="models")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="output")
    parser.add_argument("-g", "--skip-global-constraints", help = "Skip the global constraints when testing", required=False, default = False)
    parser.add_argument("--max-failed-tests", help = "The maximum amount of test that may fail before quitting the application (by default an infinite amount of tests can fail). if the maximum amount is reached it will quit even if the max-minutes wasn't reached", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("--max-minutes", help = "The maximum time (in minutes) the tests should run (by default the tests will run forever). The tests will quit sooner if max-bugs was set and reached or an keyboardinterrupt occured", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("-mpm","--mutations-per-model", help = "The amount of mutations that will be executed on every model", required=False, default=5 ,type=check_positive)
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
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
    print("\nUsing solver '"+args.solver+"' with models in '"+args.models+"' and writing to '"+args.output_dir+"'." ,flush=True,end="\n\n")
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
    process_args = (current_amount_of_tests, current_amount_of_error, lock, args.solver, args.mutations_per_model ,models ,max_failed_tests,args.output_dir, max_time)

    for x in range(args.amount_of_processes):
        processes.append(Thread(target=run_verifiers,args=process_args))


    # start the processes
    for process in processes:
        process.start()

    try:
        # only wait for the timing process to finish
        for process in processes:
            process.join()
        
    except KeyboardInterrupt:
        print("interrupting...",flush=True,end="\n")
    finally:
        print("\nExecuted tests for "+str(math.floor((time.time()-start_time)/60))+" minutes",flush=True,end="\n")
        # terminate all the processes
        # for process in processes:
        #     process.terminate()
        print("Quiting fuzz tests \n",flush=True,end="\n")

        if current_amount_of_error.value == max_failed_tests:
            print("Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")
        else:
            print("Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")