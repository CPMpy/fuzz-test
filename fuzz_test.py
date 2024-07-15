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
    for key, value in test_results.items():
        print(key, value)



'''writing the data every second, so we will not loose any date if the program should crash or gets closed'''
def write_test_data(lock,output_dir,test_results):
    try:
        while True:
            lock.acquire()
            try:    
                with open(join(output_dir, 'output'), "wb") as ff:
                    pickle.dump(test_results, file=ff)  # log some stats

                with open(join(output_dir, 'output.txt'), "w") as ff:
                    ff.write(str(test_results))
            finally:
                lock.release()  
                time.sleep(1)
    except KeyboardInterrupt:
        pass


def time_out_process(hrs,current_error_treshold,max_error_treshold):
    start_time = time.time()
    end_time = start_time + 60 * hrs
    try: 
        while time.time() < end_time and current_error_treshold.value < max_error_treshold:
            time.sleep(1)
    except KeyboardInterrupt:
        print("interrupting...")
    finally: 
        print("\n executed tests for "+str(math.floor((time.time()-start_time)/60))+" minutes")



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


    # create the output dir if it does not yet exists
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)

    set_start_method("spawn")
    '''creating the vars for the multiprocessing'''
    manager = Manager()
    test_results = manager.dict()
    current_error_treshold = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)
    lock = Lock()

    '''Running all the tests'''

    create_output_text({"test1": 25, "geen idee": "lolol"})
    processes = []
    process_args = (test_results,current_amount_of_tests, current_error_treshold, lock, args.solver, args.permutations ,models ,max_error_treshold)
    
    processes.append(Process(target=solution_tests, args=process_args))
    processes.append(Process(target=optimization_tests, args=process_args))
    processes.append(Process(target=model_counting_tests, args=process_args))
    processes.append(Process(target=equivalance_tests,args=process_args))
    processes.append(Process(target=metamorphic_tests,args=process_args))

    processes.append(Process(target=write_test_data,args=(lock,args.output_dir,test_results)))

    timing_process = Process(target=time_out_process,args=(args.minutes,current_error_treshold,max_error_treshold))
    
    
    #write_process.start()
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

        print("\n Quiting fuzz tests writing the data...\n")
        
        if current_error_treshold.value == max_error_treshold:
            print("\n Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests, "+str(current_error_treshold.value)+" tests failed")
        else:
            print("\n Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_error_treshold.value)+" tests failed")



