import glob
import math
import os
import random
import warnings
from os.path import join
import gc

from fuzz_test_utils.output_writer import get_logging_dir, write_csv
from verifiers import *
from fuzz_test_utils import Fuzz_Test_ErrorTypes
def get_all_verifiers(single_solver) -> list:
    if single_solver:
        return [Solution_Verifier,Optimization_Verifier,Model_Count_Verifier,Metamorphic_Verifier,Equivalance_Verifier]
    else:
        return [Solver_Vote_Count_Verifier, Solver_Vote_Sat_Verifier, Strengthening_Weakening_Verifier,
                Solver_Vote_Eq_Verifier, Solver_Vote_Sol_Verifier]

def run_verifiers(current_amount_of_tests, current_amount_of_error, lock, solver: list[str], mutations_per_model: int, folders: list, max_error_treshold: int, output_dir: str, time_limit: float, mm_prob: float,
                  solver_counts, verifier_counts, verifier_runtimes) -> None:
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
    solver = solver[0] if len(solver) == 1 else solver  # Take the solver as a string if there is only one

    if solver == 'pysat':
        solver = random.Random().sample(['minizinc', 'ortools', 'gurobi', 'choco'], 2)  # Andere solvers hebben problemen met hun time_limit
        print(f"Running with solvers {solver}")
    verifier_kwargs = {"solver":solver, "mutations_per_model":mutations_per_model, "exclude_dict":exclude_dict,"time_limit": time_limit, "seed":random_seed}

    execution_time = 0
    try:
        while time.time() < time_limit and current_amount_of_error.value < max_error_treshold:
            if isinstance(solver, str):
                random_verifier = random.choice(get_all_verifiers(single_solver=True))(**verifier_kwargs)
            elif isinstance(solver, list):
                verifier_kwargs["mm_prob"] = mm_prob  # add probability to choose mm_mut instead of gen_mut
                random_verifier = random.choice(get_all_verifiers(single_solver=False))(**verifier_kwargs)
            else:
                raise Exception(f"The given solvers are not in the correct format. Should be either a single solver (str) or a list of solvers ([str]), but is {type(solver)}.")
            fmodels = []
            for folder in folders:
                fmodels.extend(glob.glob(join(folder,random_verifier.getType(), "*")))
            if len(fmodels) > 0:
                fmodel = random.Random().choice(fmodels)  # random.choice used the random.seed()! Same models were being tested!

                for s in solver:
                    solver_counts[s].value += 1
                verifier_counts[random_verifier.name].value += 1
                start_time = time.time()
                error = random_verifier.run(fmodel)
                end_time = time.time()
                execution_time = math.floor(end_time - start_time)
                verifier_runtimes[random_verifier.name].value += end_time - start_time

                # check if we got an error
                if error is not None:
                    lock.acquire()
                    try:
                        if 'seed' in error:  # Give every run its own seed, otherwise same mutations happen
                            random_seed = error['seed']
                        error_data = {'verifier':random_verifier.getName(),'solver' : solver, 'mutations_per_model' : mutations_per_model, "seed": random_seed, "execution_time": execution_time, "error" :error}
                        logging_dir = get_logging_dir(error_data, output_dir) if get_logging_dir(error_data, output_dir) else output_dir
                        os.makedirs(logging_dir, exist_ok=True)  # create if it doesn't already exist
                        write_error(error_data, logging_dir)
                        write_csv(error_data, output_dir+'.csv')
                        current_amount_of_error.value += 1
                    finally:
                        lock.release()
                # Memory fix?
                del random_verifier
                import gc
                gc.collect()
                lock.acquire()
                try:
                    current_amount_of_tests.value += 1
                finally:
                    lock.release()
        print(f"Process {os.getpid()} with solvers {solver} exiting at {time.time()} > {time_limit}", flush=True)

    except Exception as e:
        print(traceback.format_exc(),flush=True)
        error = {"type": Fuzz_Test_ErrorTypes.fuzz_test_crash,"exception":e,"stacktrace":traceback.format_exc()}
        lock.acquire()
        try:
            error_data = {'solver' : solver, 'mutations_per_model' : mutations_per_model, "seed": random_seed, "execution_time": execution_time, "error" :error, "verifier": "None"}
            write_error(error_data,output_dir)

            current_amount_of_tests.value += 1
        finally:
            lock.release()