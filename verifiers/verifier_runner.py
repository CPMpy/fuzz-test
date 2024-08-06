import glob
import math
import warnings
from os.path import join

from verifiers import *

def get_all_verifiers() -> list:
    return [Solution_Verifier,Optimization_Verifier,Model_Count_Verifier,Metamorphic_Verifier,Equivalance_Verifier]

def run_verifiers(current_amount_of_tests, current_amount_of_error, lock, solver: str, mutations_per_model: int, folders: list, max_error_treshold: int, output_dir: str, time_limit: float) -> None:
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
            time_limit (float): the maximum timestamp that can be reached (no tests can exeed the duration of this timestamp)
    """
    warnings.filterwarnings("ignore")

    exclude_dict = {}
    random_seed = random.random()
    random.seed(random_seed)

    verifier_kwargs = {"solver":solver, "mutations_per_model":mutations_per_model, "exclude_dict":exclude_dict,"time_limit": time_limit, "seed":random_seed}

    execution_time = 0
    try:
        while time.time() < time_limit and current_amount_of_error.value < max_error_treshold:
            random_verifier = random.choice(get_all_verifiers())(**verifier_kwargs)
            fmodels = []
            for folder in folders:
                fmodels.extend(glob.glob(join(folder,random_verifier.getType(), "*")))

            fmodel = random.choice(fmodels)
            
            start_time = time.time()
            error = random_verifier.run(fmodel)
            execution_time = math.floor(time.time() - start_time)
            # check if we got an error
            if error is not None:
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