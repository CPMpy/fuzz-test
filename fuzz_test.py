import argparse

import glob
import pickle
import os
from pathlib import Path
from os.path import join
import time
import json
import sys
sys.path.append('../cpmpy')
from cpmpy.exceptions import CPMpyException
import cpmpy as cp
from mutators import *
from multiprocessing import Process, Lock, Manager
from testfiles.solution_check_v2 import solution_check
from testfiles.optimization_test_v2 import optimization_test
import signal
import atexit
import threading

#from solution_check_v2 import solution_check
#from optimization_test_v2 import optimization_test


"""
optimization tests ok
model counting ok
metamorphic error
equivalance check ok maar finish nie vanzelf
solution check zelfde error                             
"""


''' OMgezet
solution
'''

'''writing the data every second, so we will not loose any date if the program should crash or gets closed'''
def write_test_data(lock,output_dir,testResults):
    while True:
        lock.acquire()
        try:    
            with open(join(output_dir, 'output'), "wb") as ff:
                pickle.dump(testResults, file=ff)  # log some stats

            with open(join(output_dir, 'output.txt'), "w") as ff:
                ff.write(str(testResults))
        finally:
            lock.release()  
            time.sleep(1)




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
        max_error_treshold = 9999999999999999


    # create the output dir if it does not yet exists
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)


    '''creating the vars for the multiprocessing'''
    manager = Manager()
    testResults = manager.dict()
    current_error_treshold = manager.Value("i",0)
    current_amount_of_tests = manager.Value("i",0)
    is_exiting = manager.Value("b",False)
    lock = Lock()

    '''Running all the tests'''
    processes = []
    processes.append(Process(target=solution_check, args=(testResults,current_amount_of_tests, current_error_treshold, lock, args.minutes, args.solver, args.permutations ,models ,max_error_treshold)))
    processes.append(Process(target=write_test_data,args=(lock,args.output_dir,testResults)))

    for process in processes:
        process.start()

    try:
        for process in processes:
            process.join()
        #optimization_test_Process = Process(target=optimization_test, args=(testResults,current_amount_of_tests, current_error_treshold, lock, args.minutes, args.solver, args.permutations ,models ,max_error_treshold))
        #optimization_test_Process.start()
        
        #optimization_test_Process.join()
        
    except KeyboardInterrupt:
        is_exiting.value = True        

    finally:
        for process in processes:
            process.terminate()

        is_exiting.value = True
        print("\n Quiting fuzz tests writing the data...\n")
        
        if current_error_treshold.value == max_error_treshold:
            print("\n Reached error treshold stopped running futher test, executed "+str(current_amount_of_tests.value) +" tests")
        else:
            print("\n Succesfully executed " +str(current_amount_of_tests.value) + " tests, "+str(current_error_treshold.value)+" tests failed")



