import ctypes
import glob
import math
from typing import Optional
import warnings
from os.path import join
from importlib import reload
import cpmpy as cp
# from timeout import timeout  # REASON: PyPI `timeout` is Python 2-only and fails on Python 3
from contextlib import contextmanager
@contextmanager
def timeout(seconds, exception=TimeoutError):
    yield  # no per-verifier wall-clock limit without a working timeout package

from fuzz_test_utils.fuzz_test_errors import FuzzTestErrorType
from verifiers import *
from verifiers.utils import FuzzExit
from fuzz_test_utils import FuzzTestErrorType
def get_all_verifiers() -> list:
    return [Solution_Verifier,Optimization_Verifier,Model_Count_Verifier,Metamorphic_Verifier,Equivalance_Verifier]

def run_verifiers(
        current_amount_of_tests, current_amount_of_error, current_amount_of_timeouts, 
        lock, 
        solver: str, 
        mutations_per_model: int, 
        folders: list, 
        max_error_treshold: int, 
        output_dir: str, 
        total_time_limit: int, fuzz_time_limit: int, 
        seed:Optional[int]
    ) -> None:
    """
        This function will be used to run different verifiers

        Arguments:
            current_amount_of_tests (Value(int)): the value that stores the current amount of test executed
            current_amount_of_error (Value(int)): the value that stores the current amount of errors found
            current_amount_of_timeouts (Value(int)): the value that stores the current amount of timeouts occured
            lock (Lock): the lock that gets used for the mutiprocessing
            solver (string): the name of the solver that is getting used for the tests
            mutations_per_model (int): the amount of mutations 
            folders ([string]): the directories of the models that we are testing
            max_error_treshold (int): the maximimum errors that can be found before quitting the tests
            output_dir (string): the directory were the error reports needs to be written to
            total_time_limit (int): the maximum duration the total fuzz test can take
            fuzz_time_limit (int): the maximum duration the a single verifier can take
    """
    warnings.filterwarnings("ignore")

    exclude_dict = {}

    # Generate random seed (for reproducability)
    if seed is not None:
        random.seed(seed)
        seed_generator = random.Random(seed)
    else:
        seed_generator = random.Random()

    # Verifier arguments
    verifier_kwargs = {
        "solver":solver, 
        "mutations_per_model":mutations_per_model, 
        "exclude_dict":exclude_dict,
        "time_limit": fuzz_time_limit
    }

    execution_time = 0
    start = time.time()
    
    # Continue while no limits reached
    # 1) stay within time limit (if set)
    # 2) halt if threshold on number of errors has been reached (if set)
    while time.time() - start < total_time_limit and current_amount_of_error.value < max_error_treshold:

        try:


            reload(cp) # resets all global counters
            
            # Create random fuzz
            # 1) random seed
            random_seed = seed_generator.randint(0, 2**32 - 1)
            # 2) random verifier
            random_verifier: Verifier
            random_verifier = random.choice(get_all_verifiers())(**(verifier_kwargs | {"seed": random_seed}))
            # 3) random model
            fmodels = []
            for folder in folders:
                fmodels.extend(glob.glob(join(folder,random_verifier.getType(), "*")))
            if len(fmodels) == 0: continue
            fmodel = random.choice(fmodels) 

            # Run fuzz
            start_time = time.time()
            try:
                with timeout(fuzz_time_limit, TimeoutError):
                    error = random_verifier.run(fmodel)
            except TimeoutError as e:
                error = FuzzExit(
                            type=FuzzTestErrorType.timeout,
                            verifier=random_verifier,
                            originalmodel_file=random_verifier.model_file,
                            exception="timeout",
                            stacktrace=traceback.format_exc(),
                            originalmodel=random_verifier.original_model,
                            model = None,
                        )
            except ctypes.ArgumentError as e: # <- z3 can raise its own timeout exception (maybe should be translated to TimeoutError somewhere closer to where error occurs)
                # optional: inspect the message to be sure it's the Z3 timeout signature
                if "Operation timed out" in str(e):
                    error = FuzzExit(
                        type=FuzzTestErrorType.timeout,
                        verifier=random_verifier,
                        originalmodel_file=random_verifier.model_file,
                        exception=f"ctypes.ArgumentError (timeout): {e}",
                        stacktrace=traceback.format_exc(),
                        originalmodel=random_verifier.original_model,
                        model=None,
                    )
            error.verifier_kwargs = verifier_kwargs | {"seed": random_seed}

            # Expected error -> skip
            if error.type == FuzzTestErrorType.expected_error:
                continue

            # Print status of verifier run
            if error.alternative_label is not None:
                print(error.alternative_label, end='', flush=True)
            else:
                if error.type == FuzzTestErrorType.ok:
                    print('.', end='', flush=True)
                elif error.type == FuzzTestErrorType.timeout:
                    print('T', end='', flush=True)
                elif error.type == FuzzTestErrorType.failed_model:
                    print('X', end='', flush=True)
                elif error.type == FuzzTestErrorType.internalcrash:
                    print('E', end='', flush=True)
                elif error.type == FuzzTestErrorType.internalfunctioncrash:
                    print('I', end='', flush=True)
                else:
                    print('?', end='', flush=True)

            execution_time = math.floor(time.time() - start_time)

            # Check if we got an error
            if (error.type != FuzzTestErrorType.ok) and (error.type != FuzzTestErrorType.timeout):
                # Report back to parent thread (TODO should be separated from this logic, so that verifiers can be run outside of CLI tool)
                lock.acquire()
                try:
                    error_data = {
                        'verifier': random_verifier.getName(),
                        'solver' : solver, 
                        'mutations_per_model' : mutations_per_model, 
                        "seed": random_seed, 
                        "execution_time": execution_time, 
                        "error" :error
                    }

                    # Formatting of error report
                    execution_time_text = f"{str(math.floor(error_data['execution_time']/60))} minutes {str(math.floor(error_data['execution_time']%60))} seconds"
                    verifier_text = ""
                    if error_data["error"].type != FuzzTestErrorType.fuzz_test_crash:
                        verifier_text = "Chosen Verifier: "+error_data["verifier"]
                    error_text = error.text()

                    total_error_text = f"""An error occured while running a test
                    
    Used solver: {error_data['solver']}
    {verifier_text}
    With {error_data['mutations_per_model']} mutations per model
    With seed: {error_data['seed']}
    The test failed in {execution_time_text}

Error Details
===============================================================================

{error_text}

"""
                    # Save error to pickle file
                    base_name = error.write(output_dir) 
                    # Save error report to text file
                    with open(join(output_dir, base_name+".txt"), "w") as ff:
                        ff.write(total_error_text)

                    # Update monitor UI
                    if error.type == FuzzTestErrorType.timeout:
                        current_amount_of_timeouts.value += 1
                    else:
                        current_amount_of_error.value +=1

                finally:
                    lock.release() 

            # Report on completed run (TODO should be separated from this logic)
            lock.acquire()
            try:
                current_amount_of_tests.value += 1
            finally:
                lock.release()


        except Exception as e:
            # TODO does not yet use new dataclass-based error reporting
            # print(traceback.format_exc(),flush=True)
            error = {
                "type": FuzzTestErrorType.fuzz_test_crash,
                "exception":e,
                "stacktrace":traceback.format_exc()
            }

            lock.acquire()
            try:

                error_data = {
                    'solver' : solver, 
                    'mutations_per_model' : mutations_per_model, 
                    "seed": random_seed, 
                    "execution_time": execution_time, 
                    "error": error, 
                    "verifier": random_verifier.getName(),
                    "model": random_verifier.original_model
                }

                write_error(error_data,output_dir)

                current_amount_of_tests.value += 1
            finally:
                lock.release()
    