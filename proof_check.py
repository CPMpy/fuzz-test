import sys
import time
import random
import pickle
from os import path, mkdir, remove
from glob import glob
from pathlib import Path
import cpmpy
from cpmpy import Model, SolverLookup
from cpmpy.exceptions import CPMpyException

from mutators import *

def write_gcs_cc_api_cals(file, api_calls):
    with open(file, "w") as f:
        # TODO: write some more C++ boilerplate here to make this just run
        print(api_calls, file=f)


def proof_fuzz_test(iters, model_path, num_failed, output_dir):
    with open(model_path, "rb") as model_file:
        constraints = pickle.loads(model_file.read()).constraints

        assert len(constraints) > 0, f"{model_path} has no constraints"
        constraints = toplevel_list(constraints)
        assert len(constraints) > 0, f"{model_path} has no constraints after l2conj"

        # TODO: apply some mutators here
        mutators = []
        error_model_id = "lasterrormodel" + str(num_failed)
        try:
            model = Model(constraints)
            gcs = SolverLookup.get("gcs", model)
            gcs.solve(
                time_limit=30,
                verify=True,
                display_verifier_output=False,
                proof_location=output_dir,
                proof_name=error_model_id,
            )
            if gcs.status().runtime > 190:
                print("s", end="", flush=True)
                return True
            elif not gcs.proof_verification_failed:
                remove(path.join(output_dir, error_model_id) + ".opb")
                remove(path.join(output_dir, error_model_id) + ".pbp")
                print(".", end="", flush=True)
                return True
            else:
                print("X", end="", flush=True)
        except Exception as e:
            if isinstance(e, (CPMpyException, NotImplementedError)):
                # expected error message, ignore
                print("s", end="", flush=True)
                return True
            print(e)
            print("E", end="", flush=True)

        with open(path.join(output_dir, error_model_id + ".pickle"), "wb") as f:
            pickle.dump([model, model_path, mutators], file=f)

        write_gcs_cc_api_cals(
            path.join(output_dir, error_model_id + ".cc"), gcs.gcs.get_api_calls_str()
        )
        num_failed += 1
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        hrs = float(sys.argv[1])
        iters = int(sys.argv[2])
    else:
        hrs = 1
        iters = 5  # number of metamorphic mutations per model
    num_failed = 0
    output_dir = "gcs-proof" + str(iters)
    if not Path(output_dir).exists():
        mkdir(output_dir)
    for old_file in glob(path.join(output_dir, "*")):
        remove(old_file)

    dirname = "models"
    folders = [
        path.join(dirname, "pickle-test_constraints"),
        path.join(dirname, "pickle_examples"),
        path.join(dirname, "pickle_test_expression"),
        path.join(dirname, "pickle_test_globals"),
    ]

    fmodels = []
    print(folders)
    for folder in folders:
        # For proof testing we can do UNSAT and OPT models too
        fmodels.extend(glob(path.join(folder, "*", "*")))

    # fmodels = ["models/fail1.pickle"]
    print(len(fmodels))

    endtime = time.time() + 3600 * hrs

    while time.time() < endtime:
        # random.shuffle(fmodels)
        for fmodel in fmodels:
            if time.time() > endtime:
                break
            passed = proof_fuzz_test(iters, fmodel, num_failed, output_dir)
            if not passed:
                num_failed += 1
            
