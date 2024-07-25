import glob
import os
import pickle
import random
from os.path import join
from pathlib import Path
from mutators import *
from .metamorphic_verifier import Metamorphic_Verifier
from .solution_verifier import Solution_Verifier
from .model_counting_verifier import Model_Count_Verifier
from .equivalance_verifier import Equivalance_Verifier
from .optimization_verifier import Optimization_Verifier
import math
import warnings
import traceback
import time
from datetime import datetime


def create_error_output_text(error_data: dict) -> str:
    """
        This helper function will create a more readable text from the error_data dict

        Args:
            error_data (dict): the dict containing all the info about the error that occured
    """
    execution_time_text = str(math.floor(error_data["execution_time"]/60)) + " minutes " + str(math.floor(error_data["execution_time"]%60)) + " seconds"
    verifier_text = ""
    if error_data["error"]["type"] != "fuzz_test_crash":
        verifier_text = "Chosen Verifier: "+error_data["verifier"]
    error_text = ""
    # get all the error details
    for key, value in error_data["error"].items():
        error_text+= '''\
{key}:
    {value}

\
'''.format(key=key,value=value)

    # return a more readable/user friendly error description ready to write to a file 
    return '''\
An error occured while running a test

Used solver: {solver}
{verifier_text}
With {mutations} mutations per model
With seed: {seed}
The test failed in {execution_time}

Error Details:
{error_text}
    \
    '''.format(verifier_text=verifier_text,solver=error_data["solver"], mutations=error_data["mutations_per_model"],seed =error_data["seed"],execution_time=execution_time_text,error_text=error_text)
    


def write_error(error_data: dict, output_dir: str) -> None:
    """
        This helper function is used for writing error data ti a txt and a pickle file
        It will name the output files to the current datetime (YYYY-MM-DD H-M-S-MS)

        Args:
            error_data (dict): the dict containing all the info about the error that occured
            output_dir (string): the directory were the error reports needs to be written to
    """

    date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
    with open(join(output_dir, date_text+'.pickle'), "wb") as ff:
        pickle.dump(error_data, file=ff) 
        ff.close()

    with open(join(output_dir, date_text+'.txt'), "w") as ff:
        ff.write(create_error_output_text(error_data))
        ff.close()

def run_verifiers(current_amount_of_tests, current_amount_of_error, lock, solver: str, mutations_per_model: int, folders: list, max_error_treshold: int, output_dir: str, max_duration: float) -> None:
    """
        This function will be used to run different verifiers

        Args:
            current_amount_of_tests (Value(int)): the value that stores the current amount of test executed
            current_amount_of_error (Value(int)): the value that stores the current amount of errors found
            lock (Lock): the lock that gets used for the mutiprocessing
            solver (string): the name of the solver that is getting used for the tests
            mutations_per_model (int): the amount of mutations 
            folders ([string]): the directories of the models that we are testing
            max_error_treshold (int): the maximimum errors that can be found before quitting the tests
            output_dir (string): the directory were the error reports needs to be written to
            max_duration (float): the maximum timestamp that can be reached (no tests can exeed the duration of this timestamp)
    """
    warnings.filterwarnings("ignore")
    verifiers = [Solution_Verifier(),Optimization_Verifier(),Equivalance_Verifier(),Model_Count_Verifier(),Metamorphic_Verifier()]
    
    exclude_dict = {}
    random_seed = random.random()
    random.seed(random_seed)
    
    try:
        while time.time() < max_duration and current_amount_of_error.value < max_error_treshold:
            random_verifier = random.choice(verifiers)
            fmodels = []
            for folder in folders:
                fmodels.extend(glob.glob(join(folder,random_verifier.getType(), "*")))
                
            fmodel = random.choice(fmodels)
            start_time = time.time()
            error = random_verifier.run(solver, mutations_per_model, fmodel, exclude_dict,max_duration)
            execution_time = math.floor(time.time() - start_time)
            # check if we got an error
            if not (error == None):
                lock.acquire()
                try:
                    error_data = {'verifier':random_verifier.getName(),'solver' : solver, 'mutations_per_model' : mutations_per_model, "seed": random_seed, "execution_time": execution_time, "error" :error}
                    write_error(error_data,output_dir)
                    current_amount_of_error.value +=1
                finally:
                    lock.release() 
            lock.acquire()
            try:
                current_amount_of_tests.value += 1
            finally:
                lock.release()

    except Exception as e:
        print(traceback.format_exc())
        error = {"type": "fuzz_test_crash","exception":e,"stacktrace":traceback.format_exc()}
        lock.acquire()
        try:
            error_data = {'solver' : solver, 'mutations_per_model' : mutations_per_model, "seed": random_seed, "execution_time": execution_time, "error" :error}
            write_error(error_data,output_dir)

            current_amount_of_tests.value += 1
        finally:
            lock.release()
    finally:
        print("I",flush=True,end="")