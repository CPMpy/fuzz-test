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
import shutil

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
        if error_data["error"]["type"].name != "fuzz_test_crash": # if it is a fuzz_test crash error we skip it
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
    
    parser.add_argument("-m", "--failed_model_file", help = "The path to a single pickle file or the path to a directory containing multiple pickle files", required=False, type=str, default='output')
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="bug_output")
    parser.add_argument("-p","--amount-of-processes", help = "The amount of processes that will be used to run the tests", required=False, default=cpu_count()-1 ,type=check_positive) # the -1 is for the main process
    parser.add_argument("-e","--elaborate", help = "Elaborate print, also show filenames of errors that are re-run", required=False, default=False, type=bool) # the -1 is for the main process
    parser.add_argument("-r","--remove", help = "Remove fixed error files", action="store_true")
    parser.add_argument("-M","--move-dir", help = "Directory to move fixed error files to", type=str)
    set_start_method("spawn")
    args = parser.parse_args()

    current_working_directory = os.getcwd()
    output_dir = os.path.join(current_working_directory, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if args.move_dir:
        move_dir = os.path.join(current_working_directory, args.move_dir)
        os.makedirs(move_dir, exist_ok=True)

    failed_model_file = os.path.join(current_working_directory, args.failed_model_file)

    if os.path.isdir(failed_model_file):
        files = glob.glob(failed_model_file+"/*.pickle")
        with Pool(args.amount_of_processes) as pool: 
            try:
                print(f"rerunning failed models in directory {failed_model_file}",flush=True)
                results = pool.starmap(rerun_file, zip(files,repeat(output_dir)))
                print(Style.RESET_ALL+"\nsucessfully tested all the models",flush=True ) 
                print(Fore.RED+f"{len(results)-results.count(True)} models still fail "+Fore.GREEN +f"{results.count(True)} models no longer fail"+Style.RESET_ALL,flush=True )
                print(f"errors that still fail:", flush=True)
                if args.elaborate:
                    for i,b in enumerate(results):
                        if not b is True:
                            print(f"{files[i]}")

                    print(f"models that no longer fail:", flush=True)
                    for i, b in enumerate(results):
                        if b is True:
                            print(f"{files[i]}")

                if args.remove or args.move_dir:
                    for i, b in enumerate(results):
                        if b is True:
                            txt_file = files[i].replace('.pickle', '.txt')
                            if args.move_dir:
                                if os.path.exists(txt_file):
                                    shutil.move(txt_file, os.path.join(move_dir, os.path.basename(txt_file)))
                                shutil.move(files[i], os.path.join(move_dir, os.path.basename(files[i])))
                                if args.elaborate:
                                    print(f"Moved {files[i]} to {move_dir}")
                            elif args.remove:
                                if os.path.exists(txt_file):
                                    os.remove(txt_file)
                                os.remove(files[i])
                                if args.elaborate:
                                    print(f"Removed {files[i]}")

                print(f"see outputs files for more info", flush=True)
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
            if args.remove or args.move_dir:
                txt_file = failed_model_file.replace('.pickle', '.txt')
                if args.move_dir:
                    if os.path.exists(txt_file):
                        shutil.move(txt_file, os.path.join(move_dir, os.path.basename(txt_file)))
                    shutil.move(failed_model_file, os.path.join(move_dir, os.path.basename(failed_model_file)))
                    print(f"Moved {failed_model_file} to {move_dir}")
                elif args.remove:
                    if os.path.exists(txt_file):
                        os.remove(txt_file)
                    os.remove(failed_model_file)
                    print(f"Removed {failed_model_file}")
    else:
        print(Fore.YELLOW +f"failed model file not found: {failed_model_file}")
    print(Style.RESET_ALL)