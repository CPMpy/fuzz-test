import sys
import os
import pickle
import argparse
import inspect
import pytest
from datetime import datetime
from multiprocessing import Pool, cpu_count, set_start_method

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "A python application to generate models from the cpmpy tests")
    parser.add_argument("-c", "--cpmpy-dir", help = "The directory were cpmpy is located", required=True,type=str )
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="solved_models")
    args = parser.parse_args()

    if os.path.exists(args.cpmpy_dir):
        print("cpmpy_dir found, running tests...")
        # Add CPMPY_DIR to sys.path so that we can import CPMpy
        sys.path.insert(0, os.path.abspath(args.cpmpy_dir))
        from cpmpy import Model
        from cpmpy.solvers import CPM_ortools
        from cpmpy import SolverLookup
        from cpmpy.solvers.ortools import CPM_ortools

        # Monkey patch the solve method
        original_solve = Model.solve

        def patched_solve(self, *args, **kwargs):
            result = original_solve(self, *args, **kwargs)
            # Generate a unique file name based on the call stack and model content
            caller = inspect.stack()[1]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # Generate a timestamp
            filename = f"{caller.function}_{caller.lineno}_{timestamp}.pickle"
            pickle_path = None
            
            if self.objective_ == None and result:
                pickle_path = os.path.join(pickle_dir,"sat" ,filename)
            elif self.objective_ != None:
                pickle_path = os.path.join(pickle_dir,"optimization" ,filename)
            else:
                pickle_path = os.path.join(pickle_dir,"unsat" ,filename)
            # Pickle the model
            with open(pickle_path, 'wb') as f:
                pickle.dump(self, f)
            return result

        # Apply the monkey patch
        Model.solve = patched_solve
        # also need to monkeypatch .add() for ORTools
        ort_add = CPM_ortools.__add__
        def patched_ort_add(self, *args, **kwargs):
            print("Calling patched add")
            if not hasattr(self, "_model"):
                self._model = Model()
            self._model.__add__(*args, **kwargs)
            return ort_add(self, *args, **kwargs)
        CPM_ortools.__add__ = patched_ort_add

        # monkey patch SolverLookup.base_solvers() to only return ortools so we don't run the tests with all solvers.
        def patched_base_solvers():
            return [('ortools', CPM_ortools)]

        original_lookup = SolverLookup.base_solvers
        SolverLookup.base_solvers = patched_base_solvers

        # Create a directory and subdirectorys to store the pickled results
        pickle_dir = args.output_dir
        os.makedirs(pickle_dir, exist_ok=True)
    
        pickle_dir = os.path.abspath(pickle_dir)
        date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
        pickle_dir = os.path.join(pickle_dir,"testsuite_"+date_text)
        os.makedirs(pickle_dir, exist_ok=True)
        os.makedirs(os.path.join(pickle_dir,"sat"), exist_ok=True)
        os.makedirs(os.path.join(pickle_dir,"unsat"), exist_ok=True)
        os.makedirs(os.path.join(pickle_dir,"optimization"), exist_ok=True)

        test_dir = os.path.join(args.cpmpy_dir, "tests")
        print(test_dir)
        pytest.main(["-v", f"{test_dir}/test_constraints.py"])
        SolverLookup.base_solvers = original_lookup
        pytest.main(["-v", f"{test_dir}", "-k", "not test_constraints"])

        print(f"succesfully executed tests and stored generated models in {args.output_dir}_testsuite_{date_text}")
    else:
        print("cpmpy_dir was not found")


