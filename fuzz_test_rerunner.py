import argparse
import os
import pickle
import random
import sys
import time

from colorama import Fore, Back, Style
from datetime import datetime
from pathlib import Path
from os.path import join

from verifiers import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A Python script for rerunning previous failed models")
    
    parser.add_argument("-m", "--failed_model_file", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=True, type=str)
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="bug_output")

    args = parser.parse_args()
    if os.path.isfile(args.failed_model_file):
        with open(args.failed_model_file, 'rb') as fpcl:
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
                    print(Fore.RED + f"\nFound Error: {error_data['error']['exception']}, see the output file for more details")
                    date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
                    os.makedirs(args.output_dir, exist_ok=True)

                    with open(join(args.output_dir, f"rerun_{Path(args.failed_model_file).stem}.pickle"), "wb") as ff:
                        pickle.dump(error_data, file=ff) 

                    with open(join(args.output_dir, f"rerun_{Path(args.failed_model_file).stem}.txt"), "w") as ff:
                        ff.write(create_error_output_text(error_data))
                else:
                    print(Back.GREEN +"\nNo errors were found")
    else:
        print(Fore.YELLOW +"failed model file not found")
    print(Style.RESET_ALL)