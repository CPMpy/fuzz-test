import argparse
import math
import pickle
import os
from pathlib import Path
from os.path import join
import time
from cpmpy import *
import sys
sys.path.append('../cpmpy')

from mutators import *
from multiprocessing import Process, Lock, Manager, set_start_method
from testfiles.solution_test import solution_tests
from testfiles.optimization_test import optimization_tests
from testfiles.model_counting_test import model_counting_tests
from testfiles.equivalance_test import equivalance_tests
from testfiles.metamorphic_test import metamorphic_tests

def create_output_text(test_results: dict) -> str:
    """
    A helper function that creates a more readable and userfriendly test results output given a dict

    Args:
        test_results (dict): the dictionary containing the data of test results
    """
        
    test_result_string = "Fuzz Test output: \nTest Parameters: \n\t\tTested the models: " + test_results["info"]["models"] + "\n\t\tUsed solver: " +  test_results["info"]["solver"] + " \n\t\tRandom seed: " + str(test_results["info"]["seed"]) +"\n"
    test_result_string += "\t\tFuzz test parameters: mutations_per_model=" + str(test_results["info"]["mutations_per_model"]) + ", skip_global_constraints="+str(test_results["info"]["skip_global_constraints"])
    test_result_string += "\n\nExecuted " + str(test_results["info"]["executed_tests"]) + " tests in " + str(test_results["info"]["execution_time"]) + " minutes,  " + str(test_results["info"]["passed_tests"]) + " tests passed " +  str(test_results["info"]["failed_tests"]) + " tests failed"
    for key, value in test_results.items():
        if not (key == "info"):
            test_result_string += "\n\n" + key + ":\n\tamount of executed tests: " + str(value['amount_of_tests']) + ", passed tests " +  str(value['amount_of_tests']-value['nb_of_errors']) + " failed test " + str(value['nb_of_errors'])
    test_result_string += "\n\nFailed Tests:"

    for key, value in test_results.items():
        if not (key == "info"):
            test_result_string+="\n\n\t"+key+":"
            if len(value["errors"]) == 0:
                test_result_string += "\n\t\tNo failed tests"
            else:
                index = 1
                for error in value["errors"]:
                    if error["type"] == "fuzz_test_crash":
                        test_result_string += "\n\t\tfailed test "+str(index)+":\n\t\t\ttype: fuzz_test_crash"+"\n\t\texception: \n\t\t\t\t"+str(error["exception"])
                for error in value["errors"]:
                    if error["type"] == "internalfunctioncrash":
                        test_result_string += "\n\t\tfailed test "+str(index)+":\n\t\t\ttype: internalfunctioncrash"+"\n\t\t\function: \n\t\t\t\t"+str(error["function"])+"\n\t\t\argument: \n\t\t\t\t"+str(error["argument"])+"\n\t\t\exception: \n\t\t\t\t"+str(error["exception"])+"\n\t\t\toriginalmodel: \n\t\t\t\t"+ str(error["originalmodel"]).replace("\n"," ")+"\n\t\t\tmutators: \n\t\t\t\t"+ str(error["mutators"])
                        index +=1
                for error in value["errors"]:
                    if error["type"] == "failed_model":
                        test_result_string += "\n\t\tfailed test "+str(index)+":\n\t\t\ttype: failed_model"+"\n\t\t\tmodel: \n\t\t\t\t"+ str(error["model"]).replace("\n"," ")+"\n\t\t\toriginalmodel: \n\t\t\t\t"+ str(error["originalmodel"]).replace("\n"," ")+"\n\t\t\tmutators: \n\t\t\t\t"+ str(error["mutators"])
                        index +=1
    
    return test_result_string

'''writing the data every second, so we will not loose any date if the program should crash or gets closed'''
def write_test_data(lock, output_dir: str, test_results: dict, start_time: float, current_amount_of_tests, current_amount_of_error, solver: str, models: list, mutations_per_model: int, skip_global_constraints: bool, rseed: int) -> None:
    """
    A helper function which will read the test data every second and write it as a txt and a pickle file

    Args:
        lock (Lock): the lock that gets used for the mutiprocessing
        output_dir (string): the directory were we are writing the output files to
        test_results (dict): the dict containing the test result data
        start_time (float): the starting time when we started executing tests
        current_amount_of_tests (Value(int)): the value that stores the current amount of test executed
        current_amount_of_error (Value(int)): the value that stores the current amount of errors found
        solver (string): the name of the solver that is getting used for the tests
        models ([string]): the directories of the models that we are testing
        mutations_per_model (int): the amount of mutations_per_model that we are using for the tests
        skip_global_constraints (bool): the value of skipping the global constraints
        rseed (int): the random seed that is getting used for the tests
    """
    try:
        while True:
            lock.acquire()
            try:
                test_results["info"] = {"execution_time":math.floor((time.time()-start_time)/60), "executed_tests": current_amount_of_tests.value, "passed_tests": current_amount_of_tests.value-current_amount_of_error.value, "failed_tests": current_amount_of_error.value,"solver":solver,"models": models,"mutations_per_model": mutations_per_model, "skip_global_constraints": skip_global_constraints, "seed":rseed }
                
                with open(join(output_dir, 'run_fuzz_test_output.pickle'), "wb") as ff:
                    # use copy since the normal test results is a multiprocessing.managers.DictProxy while we need a normal dict
                    pickle.dump(test_results.copy(), file=ff) 

                with open(join(output_dir, 'run_fuzz_test_output.txt'), "w") as ff:
                    ff.write(create_output_text(test_results))
            finally:
                lock.release()  
                time.sleep(1)
    except KeyboardInterrupt:
        pass


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
    finally: 
        print("Executed tests for "+str(math.floor((time.time()-start_time)/60))+" minutes",flush=True,end="\n")



if __name__ == '__main__':
    

    # Getting and checking the input parameters    
    def getsolvernames(solver) -> str:
        """
        Small helper function for getting al the available solvers names from cpmpy
        """
        return solver[0]
    
    # get all the available solvers from cpympy
    available_solvers = list(map(getsolvernames, SolverLookup.base_solvers()))

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
    parser.add_argument("--max-failed-tests", help = "The maximum amount of test that may fail before quitting the application (by default an infinite amount of tests can fail). if the maximum amount is reached it will uit even if the max-minutes wasn't reached", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("--max-minutes", help = "The maximum time (in minutes) the tests should run (by default the tests will run forever). The tests will quit sooner if max-bugs was set and reached or an keyboardinterrupt occured", required=False, default=math.inf ,type=check_positive)
    parser.add_argument("-mpm","--mutations-per-model", help = "The amount of mutations that will be executed on every model", required=False, default=5 ,type=check_positive)
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=5 ,type=check_positive)


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
    test_results = manager.dict()
    current_amount_of_error = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)

    lock = Lock()
    rseed = 0 # random.random()
    
    # creating processes to run all the tests

    processes = []
    process_args = (test_results,current_amount_of_tests, current_amount_of_error, lock, args.solver, args.mutations_per_model ,models ,max_failed_tests,rseed)
    
    processes.append(Process(target=solution_tests, args=process_args))
    processes.append(Process(target=optimization_tests, args=process_args))
    processes.append(Process(target=model_counting_tests, args=process_args))
    processes.append(Process(target=equivalance_tests,args=process_args))
    processes.append(Process(target=metamorphic_tests,args=process_args))

    write_test_data_process = Process(target=write_test_data,args=(lock,args.output_dir,test_results,start_time,current_amount_of_tests,current_amount_of_error,args.solver,args.models,args.mutations_per_model, args.skip_global_constraints,rseed))

    timing_process = Process(target=time_out_process,args=(max_minutes,current_amount_of_error,max_failed_tests,start_time))
    
    
    # start the processes
    write_test_data_process.start()
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
        # terminate all the test processes
        for process in processes:
            process.terminate()
        print("Quiting fuzz tests \n",flush=True,end="\n")

        # wait 3 seconds before terminating the write_test_data_process so that we are sure that all the data is written
        time.sleep(3)
        write_test_data_process.terminate()

        if current_amount_of_error.value == max_failed_tests:
            print("Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")
        else:
            print("Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_amount_of_error.value)+" tests failed",flush=True,end="\n")