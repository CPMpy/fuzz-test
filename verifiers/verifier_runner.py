import glob
import math
import warnings

from os.path import join
from numpy.random import RandomState
from verifiers import *

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

    exclude_dict = {}
    random_seed = random.randint(0, 2**32 - 1) # the 2**32 - 1 is the max int
    random_state = RandomState(random_seed)
    
    verifier_args = [solver, mutations_per_model, exclude_dict, max_duration, random_seed]

    verifiers = [Solution_Verifier(*verifier_args),Optimization_Verifier(*verifier_args),Equivalance_Verifier(*verifier_args),Model_Count_Verifier(*verifier_args),Metamorphic_Verifier(*verifier_args)]
    execution_time = 0
    try:
        while time.time() < max_duration and current_amount_of_error.value < max_error_treshold:
            random_verifier = random_state.choice(verifiers)
            fmodels = []
            for folder in folders:
                fmodels.extend(glob.glob(join(folder,random_verifier.getType(), "*")))

            fmodel = random_state.choice(fmodels)
            
            start_time = time.time()
            error = random_verifier.run(fmodel)
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
        print(traceback.format_exc(),flush=True)
        error = {"type": "fuzz_test_crash","exception":e,"stacktrace":traceback.format_exc()}
        lock.acquire()
        try:
            error_data = {'solver' : solver, 'mutations_per_model' : mutations_per_model, "seed": random_seed, "execution_time": execution_time, "error" :error}
            write_error(error_data,output_dir)

            current_amount_of_tests.value += 1
        finally:
            lock.release()