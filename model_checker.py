import argparse
import glob
from itertools import repeat
import os
import pickle
import sys
import cpmpy as cp
from mutators import *
from multiprocessing import set_start_method,Pool, cpu_count
import traceback
from pathlib import Path

def solve_model(model_file: str, solver: str, output_dir: str) -> None:
    """
        A wrapper function for solving a CPMPy model given in a `.pickle` file using a specified solver.
        The function catches any runtime-error and writes the error to a file  in `output_dir`.

        Args:
            model_file (string): the file of the model that we are checking
            solver (string): the name of the solver that is getting used for the solving
            output_dir (string): the directory were the error reports needs to be written to    
    """
    try:
        with open(model_file, 'rb') as fpcl:
                cons = pickle.loads(fpcl.read()).constraints
                assert (len(cons)>0), f"{model_file} has no constraints"
                cons = toplevel_list(cons)
                Model(cons).solve(solver=solver,time_limit=100)
                print(".",flush=True,end="")
                return
        
    except Exception as e:
        print("X",flush=True,end="")
        error_text= "\nsolved model: {model_file}\n\nWith solver: {solver}\n\nexeption: {exeption}\n\nstacktrace: {stacktrace}".format(model_file=model_file,solver=solver,exeption=e,stacktrace=traceback.format_exc())

        with open(os.path.join(output_dir,model_file.replace("\\","_")+'_output.txt'), "w") as ff:
            ff.write(error_text)
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
    parser.add_argument("-m", "--models", help = "Directory containing pickled CPMpy model(s)", required=False, type=str, default="models")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="output")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to check the models", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    args = parser.parse_args()
    folders = []

    # showing the info about the given params to the user
    print("Checking models in {models}\n\nwith solver: {solver}\n\nwriting results to {output_dir}\n\nSolving the models ...".format(models=args.models,solver=args.solver,output_dir=args.output_dir),flush=True)

    # output dir will be created if it does not exist
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)


    fmodels = []
    # fetch all the pickle files from the dir and all the subdirs
    fmodels.extend(glob.glob(os.path.join(args.models,"**", "*.pickle"),recursive=True))

    set_start_method("spawn")
    processes = []
    
    pool = Pool(args.amount_of_processes)

    try:
        result = pool.starmap(solve_model, zip(fmodels,repeat(args.solver),repeat(args.output_dir)))
        pool.close()
    except KeyboardInterrupt:
        pass
    finally:
        pool.join()
        pool.terminate()
        amount_of_errors = result.count(1)
        print("\n\nchecked {amount_models} models".format(amount_models=str(len(result))))
        if amount_of_errors == 0:
            print("all models passed",flush=True ) 
        else:
            print("{amount_errors} models failed".format(amount_errors=str(amount_of_errors)),flush=True ) 


        print("quiting the application",flush=True ) 
        sys.exit()
        