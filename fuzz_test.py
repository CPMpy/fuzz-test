import argparse
import math
import pickle
import os
from pathlib import Path
from os.path import join
import time
import sys
sys.path.append('../cpmpy')

from mutators import *
from multiprocessing import Process, Lock, Manager, set_start_method
from testfiles.solution_test import solution_tests
from testfiles.optimization_test import optimization_tests
from testfiles.model_counting_test import model_counting_tests
from testfiles.equivalance_test import equivalance_tests
from testfiles.metamorphic_test import metamorphic_tests

def create_output_text(test_results):
    test_result_string = "Fuzz Test output: \nTest Parameters: \n\t\tTested the models: " + test_results["info"]["models"] + "\n\t\tUsed solver: " +  test_results["info"]["solver"] + " \n\t\tRandom seed: " + str(test_results["info"]["seed"]) +"\n"
    test_result_string += "\t\tFuzz test parameters: permutations=" + str(test_results["info"]["permutations"]) + ", skip_global_constraints="+str(test_results["info"]["skip_global_constraints"])
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
def write_test_data(lock,output_dir,test_results,start_time,current_amount_of_tests,current_amount_of_error,solver, models,permutations, skip_global_constraints,rseed):
    try:
        while True:
            lock.acquire()
            try:
                test_results["info"] = {"execution_time":math.floor((time.time()-start_time)/60), "executed_tests": current_amount_of_tests.value, "passed_tests": current_amount_of_tests.value-current_amount_of_error.value, "failed_tests": current_amount_of_error.value,"solver":solver,"models": models,"permutations": permutations, "skip_global_constraints": skip_global_constraints, "seed":rseed }
                
                with open(join(output_dir, 'output'), "wb") as ff:
                    pickle.dump(test_results, file=ff)  # log some stats

                with open(join(output_dir, 'output.txt'), "w") as ff:
                    ff.write(create_output_text(test_results))
            finally:
                lock.release()  
                time.sleep(1)
    except KeyboardInterrupt:
        pass


def time_out_process(hrs,current_amount_of_error,max_error_treshold,start_time):
    end_time = start_time + 60 * hrs
    try: 
        while time.time() < end_time and current_amount_of_error.value < max_error_treshold:
            time.sleep(1)
    except KeyboardInterrupt:
        print("interrupting...")
    finally: 
        print("\n executed tests for "+str(math.floor((time.time()-start_time)/60))+" minutes writing the data...")



if __name__ == '__main__':
    '''Getting and checking the input parameters'''

    available_solvers = ["ortools","z3"]

    def check_positive(value):
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue

    parser = argparse.ArgumentParser(description = "A python application to fuzz_test your solver(s)")
    parser.add_argument("-H", "--Help", help = "To use fuzz test give: the params --solver", required=False, default = "")
    parser.add_argument("-s", "--solver", help = "The Solver to use", required = True,type=str,choices=available_solvers)
    parser.add_argument("-m", "--models", help = "The path to load the models", required=True, type=str)
    parser.add_argument("-o", "--output_dir", help = "The directory to store the output", required=True)
    parser.add_argument("-g", "--skip_global_constraints", help = "Skip the global constraints when testing", required=False, default = False)
    parser.add_argument("-a", "--bug_treshold", help = "The bug treshold when to quit", required=False, default=0 ,type=check_positive)
    parser.add_argument("--minutes", help = "The time in minutes to run the tests", required=False, default=1 ,type=check_positive)
    parser.add_argument("--permutations", help = "The amount of permutations", required=False, default=5 ,type=check_positive)


    args = parser.parse_args()
    models = str.split(args.models,",")

    max_error_treshold = args.bug_treshold
    if max_error_treshold == 0:
        max_error_treshold = math.inf

    for model in models:
        if not Path(model).exists():
            raise ValueError("path to "+model+" model doesn't exist, please check if the path is correct")

    # create the output dir if it does not yet exists
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)

    set_start_method("spawn")
    '''creating the vars for the multiprocessing'''
    start_time = time.time()
    manager = Manager()
    test_results = manager.dict()
    current_amount_of_error = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)

    lock = Lock()
    rseed = 0
    
    '''Running all the tests'''

    processes = []
    process_args = (test_results,current_amount_of_tests, current_amount_of_error, lock, args.solver, args.permutations ,models ,max_error_treshold,rseed)
    
    processes.append(Process(target=solution_tests, args=process_args))
    processes.append(Process(target=optimization_tests, args=process_args))
    processes.append(Process(target=model_counting_tests, args=process_args))
    processes.append(Process(target=equivalance_tests,args=process_args))
    processes.append(Process(target=metamorphic_tests,args=process_args))

    write_test_data_process = Process(target=write_test_data,args=(lock,args.output_dir,test_results,start_time,current_amount_of_tests,current_amount_of_error,args.solver,args.models,args.permutations, args.skip_global_constraints,rseed))

    timing_process = Process(target=time_out_process,args=(args.minutes,current_amount_of_error,max_error_treshold,start_time))
    
    
    #write_process.start()
    write_test_data_process.start()
    timing_process.start()
    for process in processes:
        process.start()

    try:
        timing_process.join()
        timing_process.terminate()
        
    except KeyboardInterrupt:
        print("interrupting...")
    finally:
        #write_process.terminate()
        for process in processes:
            process.terminate()
        print("\n Quiting fuzz tests \n")

        time.sleep(3)
        write_test_data_process.terminate()

        if current_amount_of_error.value == max_error_treshold:
            print("\n Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_amount_of_error.value)+" tests failed")
        else:
            print("\n Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_amount_of_error.value)+" tests failed")