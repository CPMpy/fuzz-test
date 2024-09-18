import argparse
import os
import pickle
import sys
import time
from colorama import Fore, Back, Style
from pathlib import Path
from os.path import join

from verifiers import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A Python script for minimizing the constraint for a failed model. It will only keep the constraints that caused the error")
    
    parser.add_argument("-m", "--failed_model_file", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=True, type=str)
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="minimizer_output")
    
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
            original_error = error_data["error"]
            original_cons = error_data["error"]["constraints"]
            amount_of_original_cons = len(error_data["error"]["constraints"])
            if len(original_cons) == 1:
                print(Fore.BLUE +"model only has 1 constraint no minimizing possible")
                
            else:
                new_cons = []

                for con in toplevel_list(original_cons):
                    test_cons = original_error["constraints"]
                    test_cons.remove(con)
                    new_error_dict = copy.deepcopy(original_error)

                    vrf_cls = lookup_verifier(error_data['verifier'])
                    verifier = vrf_cls(solver=error_data['solver'],
                                    mutations_per_model=error_data["mutations_per_model"],
                                    exclude_dict = {},
                                    time_limit = time.time()*3600,
                                    seed = error_data["seed"]
                    )               
                    new_error = verifier.rerun(new_error_dict)

                    if new_error is not None: 
                        # if we still get the error than the constraint is responsible so we keep it
                        new_cons.append(con)

                #copy new constraints to model
                error_data["error"]["constraints"] = new_cons    
                new_model = error_data["error"]["model"]
                new_model.constraints = new_cons
                error_data["error"]["model"] = new_model

                print(Fore.LIGHTBLUE_EX +f"\nminimized model with {amount_of_original_cons} constraints to model with {len(new_cons)} constraints")
                os.makedirs(args.output_dir, exist_ok=True)

                with open(join(args.output_dir, "minimized_"+os.path.basename(args.failed_model_file)), "wb") as ff:
                    pickle.dump(error_data, file=ff) 
                with open(join(args.output_dir, "minimized_"+Path(os.path.basename(args.failed_model_file)).stem+".txt"), "w") as ff:
                        ff.write(create_error_output_text(error_data))
                print(f"stored minimized model in {args.output_dir}")
    else:
        print(Fore.YELLOW +"failed model file not found")
    print(Style.RESET_ALL)