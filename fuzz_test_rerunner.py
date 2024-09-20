import argparse
import os
import pickle
import random
import sys
import time
import glob
from multiprocessing import Pool, cpu_count,set_start_method
from itertools import repeat
from colorama import Fore, Back, Style
from datetime import datetime
from pathlib import Path
from os.path import join

from verifiers import *


def rerun_file(failed_model_file,output_dir ):
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
            verifier_kwargs = {'solver': error_data["solver"], "mutations_per_model": error_data["mutations_per_model"], "exclude_dict": {}, "time_limit": time.time()*3600, "seed": error_data["seed"]}
            error = lookup_verifier(error_data["verifier"])(**verifier_kwargs).rerun(error_data["error"])
            error_data["error"] = error
            
            if error is not None:
                with open(join(output_dir, f"rerun_{Path(failed_model_file).stem}.pickle"), "wb") as ff:
                    pickle.dump(error_data, file=ff) 

                with open(join(output_dir, f"rerun_{Path(failed_model_file).stem}.txt"), "w") as ff:
                    ff.write(create_error_output_text(error_data))
                return error_data
            else:
                return True
           #return error is not None



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A Python script for rerunning previous failed models")
    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    
    parser.add_argument("-m", "--failed_model_file", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=True, type=str)
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="bug_output")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    set_start_method("spawn")
    args = parser.parse_args()

    current_working_directory = os.getcwd()
    output_dir = os.path.join(current_working_directory, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    failed_model_file = os.path.join(current_working_directory, args.failed_model_file)

    if os.path.isdir(failed_model_file):
        print("detected directory")
        files = glob.glob(failed_model_file+"/*.pickle")
        with Pool(args.amount_of_processes) as pool: 
            try:
                print("rerunning failed models in directory",flush=True)
                results = pool.starmap(rerun_file, zip(files,repeat(output_dir)))
                print(Style.RESET_ALL+"\nsucessfully tested all the models",flush=True ) 
                print(Fore.RED+f"{results.count(True)} models failed "+Fore.GREEN +f"{len(results)-results.count(True)} models passed"+Style.RESET_ALL,flush=True ) 
                print(f"see outputs files for more info",flush=True ) 
            except KeyboardInterrupt:
                pass
            finally:
                print("quiting the application",flush=True ) 
            
    elif os.path.isfile(failed_model_file):
        print("detected file")
        result = rerun_file(failed_model_file,output_dir)
        print("\nsucessfully tested model")
        if result != True:
            print(Fore.RED + f"Found Error: {result['error']['exception']}, see the output file for more details")
        else:
            print(Fore.GREEN +"\nNo errors were found")
    else:
        print(Fore.YELLOW +"failed model file not found")
    print(Style.RESET_ALL)