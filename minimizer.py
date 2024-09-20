import argparse
import os
import pickle
import sys
import time
import glob
from colorama import Fore, Back, Style
from pathlib import Path
from os.path import join
from multiprocessing import Pool, cpu_count,set_start_method
from itertools import repeat

from verifiers import *


def minimize_model(failed_model_file,output_dir):
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
        amount_of_original_cons = len(error_data["error"]["constraints"])

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
                # if we still get the error than the constraint is responsible we keep it
                new_cons.append(con)

        #copy new constraints to model
        error_data["error"]["constraints"] = new_cons   
        if "model" in  error_data["error"]:
            new_model = error_data["error"]["model"]
            new_model.constraints = new_cons
            error_data["error"]["model"] = new_model
        #Fore.LIGHTBLUE_EX +

        with open(join(output_dir, "minimized_"+os.path.basename(failed_model_file)), "wb") as ff:
            pickle.dump(error_data, file=ff) 
        with open(join(output_dir, "minimized_"+Path(os.path.basename(failed_model_file)).stem+".txt"), "w") as ff:
                ff.write(create_error_output_text(error_data))

        return f"minimized {failed_model_file} with {amount_of_original_cons} constraints to model with {len(new_cons)} constraints"
       
        



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A Python script for minimizing the constraint for a failed model. It will only keep the constraints that caused the error")
    def check_positive(value):
        """
        Small helper function used in the argparser for checking if the input values are positive or not
        """
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
        return ivalue
    parser.add_argument("-m", "--failed_model_file", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=True, type=str)
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="minimizer_output")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)

    if os.path.isfile(args.failed_model_file):
        result = minimize_model(args.failed_model_file,args.output_dir)
        print(Fore.LIGHTBLUE_EX +"\n"+result)
        print(Style.RESET_ALL+f"stored minimized model in {args.output_dir}")

    elif os.path.isdir(args.failed_model_file):
        set_start_method("spawn")
        print("detected directory")
        files = glob.glob(args.failed_model_file+"/*.pickle")
        with Pool(args.amount_of_processes) as pool: 
            try:
                print("rerunning failed models in directory",flush=True)
                results = pool.starmap(minimize_model, zip(files,repeat(args.output_dir)))
                print("\n")
                [print(Fore.LIGHTBLUE_EX + result) for result in results]
                # for result in results:
                #     print(Fore.LIGHTBLUE_EX +result)
                print(Style.RESET_ALL+"\nsucessfully minimized all the models",flush=True ) 
            except KeyboardInterrupt:
                pass
            finally:
                print("quiting the application",flush=True ) 
        print(Style.RESET_ALL+f"stored minimized models in {args.output_dir}")
    else:
        print(Fore.YELLOW +"failed model file not found")
    print(Style.RESET_ALL)