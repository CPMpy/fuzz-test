import argparse
import copy
import os
import pickle
import random
import sys
import time
import warnings
from pathlib import Path
from os.path import join
from glob import glob
from itertools import repeat
from multiprocessing import Pool, cpu_count, set_start_method

from cpmpy.transformations.get_variables import get_variables

from verifiers import *
from fuzz_test_utils import create_error_output_text

def rerun_test(failed_model_file: str, output_dir: str ) -> None:
    """
        function to rerun a previously failed fuzz-tested model to see if the error is still present or not
        if its still present new output files will be generated in the output_dir
        if the error is fixed there will be no output file
        Args:
            failed_model_file (string): the model file to rerun
            output_dir (string): the directory were the error reports needs to be written to
    """
    with open(failed_model_file, 'rb') as fpcl:
        """ The error data is a dict with the following keys:
                solver: the used solver
                verifier: the verifier that got used
                mutations_per_model: the amount of mutations that were used
                seed: the used seed
                error: a dict containing:
                    type: the type of error that occured
                    model: the newly mutated model that failed/crashed
                    originalmodel: the name of the model file that was used
                    mutators: a list with executed mutations
                    constraints: the constraints that made the model fail/crash
        """

        error_data = pickle.loads(fpcl.read())
        random.seed(error_data["seed"])
        if error_data["error"]["type"] != "fuzz_test_crash": # if it is a fuzz_test crash error we skip it
            
            verifier_kwargs = {'solver': error_data["solver"], "mutations_per_model": error_data["mutations_per_model"], "exclude_dict": {}, "max_duration": time.time()*3600, "seed": error_data["seed"]}

            error = lookup_verifier(error_data["verifier"])(**verifier_kwargs).rerun(error_data["error"])
            
            error_data["error"] = error
            
            if error is not None:
                with open(join(output_dir, os.path.basename(failed_model_file)), "wb") as ff:
                    pickle.dump(error_data, file=ff) 
                        
                



def mimnimize_bug(failed_model_file:str ,output_dir: str) -> None:
    """
        function to minimize the constraints of a previously failed model to see which constraints cause the error

        Args:
            failed_model_file (string): the model file to minimize
            output_dir (string): the directory were the error reports needs to be written to
    """
    with open(failed_model_file, 'rb') as fpcl:
        """ The error data is a dict with the following keys:
                solver: the used solver
                verifier: the verifier that got used
                mutations_per_model: the amount of mutations that were used
                seed: the used seed
                error: a dict containing:
                    type: the type of error that occured
                    model: the newly mutated model that failed/crashed
                    originalmodel: the name of the model file that was used
                    mutators: a list with executed mutations
                    constraints: the constraints that made the model fail/crash
        """
        error_data = pickle.loads(fpcl.read())
        original_error = error_data["error"]
        original_cons = error_data["error"]["constraints"]

        if len(original_cons) == 1:
            with open(join(output_dir, "minimized_"+os.path.basename(failed_model_file)), "wb") as ff:
                pickle.dump(error_data, file=ff) 
        else:
            print(len(original_cons),flush=True)
            verifier_kwargs = {'solver': error_data["solver"], "mutations_per_model": error_data["mutations_per_model"], "exclude_dict": {}, "max_duration": time.time()*3600, "seed": error_data["seed"]}
                        
            new_cons = []

            for con in toplevel_list(original_cons):
                test_cons = original_error["constraints"]
                test_cons.remove(con)
                new_error_dict = copy.deepcopy(original_error)
                
                new_error = lookup_verifier(error_data["verifier"])(**verifier_kwargs).rerun(new_error_dict)  
                if new_error is not None: 
                    # if we still get the error than the constraint is responsible so we keep it
                    new_cons.append(con)
            error_data["error"]["constraints"] = new_cons    

            with open(join(output_dir, "minimized_"+os.path.basename(failed_model_file)), "wb") as ff:
                pickle.dump(error_data, file=ff) 
            with open(join(output_dir, "minimized_"+Path(os.path.basename(failed_model_file)).stem+".txt"), "w") as ff:
                    ff.write(create_error_output_text(error_data))


def run_cmd(failed_model_file: str,cmd : str, output_dir: str) -> None:
    """
        Small helper function for choosing the right function based on the cmd

        Args:
            failed_model_file (string): the model file to minimize/rerun
            output_dir (string): the directory were the output (new error or minimized error) needs to be written to 
    """
    warnings.filterwarnings("ignore")
    if cmd == "rerun_test":
        rerun_test(failed_model_file,output_dir) 
    elif cmd == "minimize_report":
        mimnimize_bug(failed_model_file,output_dir)
    else:
        raise ValueError("Error command is not supported, please use: 'rerun_test' or 'minimize_report'")

if __name__ == '__main__':
    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    
    parser = argparse.ArgumentParser(description = "A Python script for rerunning previous failed models (rerun_test) and minimizing the constraints (minimize_report)")
    
    parser.add_argument("-m", "--models", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=False, type=str, default="output")
    parser.add_argument("-c", "--cmd", help = "The cmd to execute rerun_test = rerun the failed model(s) minimize_report= minimize the constraints of the failed model(s)  ", required=False, type=str,choices=["rerun_test","minimize_report"], default="rerun_test")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="bug_output")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to check the models", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process

    
    args = parser.parse_args()

    # create the output dir if it does not yet exist
    if not Path(args.output_dir).exists():
        os.makedirs(args.output_dir)

    # check if we need to run a single test or run multiple 
    files = []
    if os.path.isfile(args.models) :
        files.append(args.models)
    elif os.path.isdir(args.models):
        files.extend(glob(join(args.models, "*.pickle")))
    else:
       raise FileNotFoundError("error "+ args.models +" was not found, please provide a path to a file or directory")
  
    set_start_method("spawn")

    with Pool(args.amount_of_processes) as pool: 
        try:
            result = pool.starmap(run_cmd, zip(files,repeat(args.cmd),repeat(args.output_dir)))
            print("sucessfully checked all the models",flush=True ) 
        except KeyboardInterrupt:
            pass
        finally:
            print("quiting the application",flush=True ) 
            
            sys.exit()
        