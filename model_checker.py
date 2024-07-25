import argparse
import glob
import os
import pickle
import sys
from cpmpy import *
from mutators import *

from multiprocessing import Process, Lock, Manager, set_start_method,Pool, cpu_count
from os.path import join
import traceback


def solve_model(lock,current_index,model_files,solver,output_dir):
    try:
        while current_index.value < len(model_files)-1:
            model_file = ""
            lock.acquire(timeout=2)
            try:
                model_file = model_files[current_index.value]
                current_index.value +=1
            finally:
                lock.release() 
            try:
                with open(model_file, 'rb') as fpcl:
                        cons = pickle.loads(fpcl.read()).constraints
                        assert (len(cons)>0), f"{model_file} has no constraints"
                        cons = toplevel_list(cons)
                        assert (len(cons)>0), f"{model_file} has no constraints after l2conj"
                        Model(cons).solve(solver=solver,time_limit=100)
                        print(".",flush=True,end="")
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

    except Exception as e: 
        pass


if __name__ == '__main__':
    # Getting and checking the input parameters    
    def getsolvernames(solver) -> str:
        """
        Small helper function for getting al the available solvers names from cpmpy
        """
        return solver[0]
    
    # get all the available solvers from cpympy
    available_solvers = list(map(getsolvernames, SolverLookup.base_solvers()))

    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    
    parser = argparse.ArgumentParser(description = "A python application to fuzz_test your solver(s)")
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
    current_index = manager.Value("i",0)
    lock = Lock()

    for x in range(cpu_count()-1):
        processes.append(Process(target=solve_model,args=(lock,current_index,fmodels,args.solver,args.output_dir)))

    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nsucessfully checked the models",flush=True ) 
        for process in processes:
            process.terminate()
          
        sys.exit()
        