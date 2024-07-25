import argparse
import glob
from itertools import repeat
import os
import pickle
import sys
from cpmpy import *
from mutators import *

from multiprocessing import Manager, set_start_method,Pool, cpu_count
from os.path import join
import traceback


def solve_model(model_file: str, solver: str, output_dir: str) -> None:
    """
        a function that will solve a single model and check if an Exception occurs, if so then write the exception details to a file

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
                assert (len(cons)>0), f"{model_file} has no constraints after l2conj"
                Model(cons).solve(solver=solver,time_limit=100)
                print(".",flush=True,end="")
                fpcl.close()
                return
    except Exception as e:
        print("X",flush=True,end="")
        error_text= """
\
solved model: {model_file}

With solver: {solver}

exeption: {exeption}

stacktrace: {stacktrace}        
\
                """.format(model_file=model_file,solver=solver,exeption=e,stacktrace=traceback.format_exc())

        with open(join(output_dir,model_file.replace("\\","_")+'_output.txt'), "w") as ff:
            ff.write(error_text)
            ff.close()
        return 1


if __name__ == '__main__':

    # get all the available solvers from cpympy
    available_solvers = [solver[0] for solver in SolverLookup.base_solvers()]
    
    parser = argparse.ArgumentParser(description = "A python application to simply check if all your models can be solved without errors")
    parser.add_argument("-s", "--solver", help = "The Solver to use", required = False,type=str,choices=available_solvers, default=available_solvers[0])
    parser.add_argument("-m", "--models", help = "The path to load the models", required=False, type=str, default="models")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="output")
    args = parser.parse_args()
    folders = []

    # showing the info about the given params to the user
    print("""
    \
        
Checking models in {models}
with solver: {solver}
writing results to {output_dir}

Solving the models ...

    \
    """.format(models=args.models,solver=args.solver,output_dir=args.output_dir),flush=True)

    # create a list with all the directories
    for model in os.listdir(args.models):
        folders.append(os.path.join(args.models, model))

    fmodels = []
    for folder in folders:
        fmodels.extend(glob.glob(join(folder,"*", "*")))
    
    set_start_method("spawn")
    processes = []
    manager = Manager()

    pool = Pool(cpu_count()-1)
    result = pool.starmap(solve_model, zip(fmodels,repeat(args.solver),repeat(args.output_dir)))
    

    try:
        pool.join()
    except KeyboardInterrupt:
        pass
    finally:
        pool.close()
        pool.terminate()
        amount_of_errors = result.count(1)
        if amount_of_errors == 0:
            print("\nall models passed",flush=True ) 
        else:
            print("\n"+str(amount_of_errors)+" models failed",flush=True ) 


        print("quiting the application",flush=True ) 
        sys.exit()
        