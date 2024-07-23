import argparse
import math
import os
from pathlib import Path
import time
from cpmpy import *
import sys
sys.path.append('../cpmpy')

from mutators import *
from multiprocessing import Process, Lock, Manager, set_start_method,Pool, cpu_count

from verifiers.verifier_runner import run_verifiers

def time_out_process(mins : int, current_amount_of_error, max_failed_tests: int, start_time: float) -> None:
    """ 
    A helper function which gets used to time and terminate the execution of the tests
    if the timout or the error treshold is reached the tests will get terminated

    Args:
        mins (int): the amount of mins we want the tests to run
        current_amount_of_error (Value(int)): the value that stores the current amount of errors found
        max_failed_tests (int): the maximimum errors that can be found before quitting the tests
        start_time (float): the starting time when we started executing tests

    """
    end_time = start_time + 60 * mins
    try: 
        while time.time() < end_time and current_amount_of_error.value < max_failed_tests:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally: 
        print("\nExecuted tests for "+str(math.floor((time.time()-start_time)/60))+" minutes",flush=True,end="\n")



if __name__ == '__main__':
    # Getting and checking the input parameters    
    def getsolvernames(solver) -> str:
        """
        Small helper function for getting al the available solvers names from cpmpy
        """
        return solver[0]
    
    # get all the available solvers from cpympy
    available_solvers = [solver[0] for solver in SolverLookup.base_solvers()]# list(map(getsolvernames, SolverLookup.base_solvers()))

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

    # output dir will be created if it does not exist
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)

    # showing the info about the given params to the user
    print("\nUsing solver '"+args.solver+"' with models in '"+args.models+"' and writing to '"+args.output_dir+"'." ,flush=True,end="\n\n")
    print("Will use "+str(args.amount_of_processes)+ " parallel executions, starting...",flush=True,end="\n\n")

    # creating the vars for the multiprocessing
    set_start_method("spawn")
    start_time = time.time()
    manager = Manager()
    current_amount_of_error = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)

    lock = Lock()
    
    # creating processes to run all the tests
    processes = []
    process_args = (current_amount_of_tests, current_amount_of_error, lock, args.solver, args.mutations_per_model ,models ,max_failed_tests,args.output_dir)

    for x in range(args.amount_of_processes):
        processes.append(Process(target=run_verifiers,args=process_args))

    timing_process = Process(target=time_out_process,args=(max_minutes,current_amount_of_error,max_failed_tests,start_time))

    # start the processes
    timing_process.start()
    for process in processes:
        process.start()

    try:
        # only wait for the timing process to finish
        timing_process.join()
        timing_process.terminate()
        
    except KeyboardInterrupt:
        print("interrupting...",flush=True,end="\n")
    finally:
        # terminate all the processes
        for process in processes:
            process.terminate()
        print("Quiting fuzz tests \n",flush=True,end="\n")

        if current_amount_of_error.value == max_failed_tests:
            print("Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")
        else:
            print("Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")