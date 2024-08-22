import argparse
import glob
from itertools import repeat
import os
import pickle
import sys
import traceback
from pathlib import Path
from multiprocessing import set_start_method,Pool, cpu_count

import cpmpy as cp
from cpmpy.transformations.normalize import toplevel_list

from mutators import *


 
def solve_model(model_file: str, solver: str, output_dir: str, time_limit: int) -> None:
    """
        A wrapper function for solving a CPMPy model given in a `.pickle` file using a specified solver.
        The function catches any runtime-error and writes the error to a file  in `output_dir`.

        Args:
            model_file (string): the file of the model that we are checking
            solver (string): the name of the solver that is getting used for the solving
            output_dir (string): the directory were the error reports needs to be written to   
            time_limit (int): the time limit to use or solving the model
    """
    try:
        with open(model_file, 'rb') as fpcl:
            model = pickle.loads(fpcl.read())
            cons = model.constraints
            assert (len(cons)>0), f"{model_file} has no constraints"
            cons = toplevel_list(cons)
            cp.Model(cons).solve(solver=solver,time_limit=time_limit)
            print(".",flush=True,end="")
            return
        
    except Exception as e:
        print("X",flush=True,end="")
        error_text= f"\nsolved model file: {model_file}\n\nmodel: {model}\n\nWith solver: {solver}\n\nexception: {e}\n\nstacktrace: {traceback.format_exc()}"

        with open(os.path.join(output_dir, Path(model_file).stem+'_output.txt'), "w") as ff: 
            ff.write(error_text)

        with open(os.path.join(output_dir, Path(model_file).stem+'_output.pickle'), "wb") as ff:
            pickle.dump({"model_file": model_file,"model":model,"solver":solver,"exception":e,"stacktrace":traceback.format_exc() }, file=ff) 
        
        return 1


if __name__ == '__main__':

    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    
    # get all the available solvers from cpympy
    available_solvers = [solver[0] for solver in cp.SolverLookup.base_solvers()]
    parser = argparse.ArgumentParser(description = "A Python script for running a batch of CPMpy models on a specified solver and logging any runtime-errors")
    parser.add_argument("-s", "--solver", help = "The solver to use", required = False,type=str,choices=available_solvers, default=available_solvers[0]) # available_solvers[0] is the default cpmpy solver (ortools)
    parser.add_argument("-m", "--models", help = "Directory containing pickled CPMpy model(s)", required=False, type=str, default="models/")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="output/")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to check the models", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    parser.add_argument("-t", "--time-limit", help = "The maximum duration in seconds, that a single model is allowed to take to find a solution", required=False, type=check_positive, default=100)

    args = parser.parse_args()

    # fetch all the pickle files from the dir and all the subdirs
    fmodels = []
    fmodels.extend(glob.glob(os.path.join(args.models,"**", "Pickled*"),recursive=True))
    #fmodels.extend(glob.glob(os.path.join(args.models,"**", "*.pickle"),recursive=True))

    # showing the info about the given params to the user
    print(f"Checking {len(fmodels)} models from '{args.models}' with solver: '{args.solver}'\nSolving:",flush=True)

    # output dir will be created if it does not exist
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)


    set_start_method("spawn")
    processes = []
    
    # on linux this will work fine when a keyboardinterrupt occurs
    # on windows it will freeze the application and the processes will keep running in the backgroud and need to be manually killed
    with Pool(args.amount_of_processes) as pool:
        result = pool.starmap(solve_model, zip(fmodels,repeat(args.solver),repeat(args.output_dir),repeat(args.time_limit)))

        amount_of_errors = result.count(1)
        if amount_of_errors == 0:
            print(f"\nall {len(result)} models passed", flush=True) 
        else:
            print(f"\n{amount_of_errors}/{len(result)} models failed. Log stored in '{args.output_dir}'.", flush=True)
        sys.exit()
        
