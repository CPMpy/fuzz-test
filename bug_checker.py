import argparse
from itertools import repeat
from multiprocessing import Lock, Manager, Pool, Process, cpu_count, set_start_method
import os
import pickle
import random
import sys
import time
import warnings
from cpmpy import *
from pathlib import Path
from os.path import join
from glob import glob
from verifiers.solution_verifier import Solution_Verifier
from verifiers.optimization_verifier import Optimization_Verifier
from verifiers.model_counting_verifier import Model_Count_Verifier
from verifiers.metamorphic_verifier import Metamorphic_Verifier
from verifiers.equivalance_verifier import Equivalance_Verifier


def rerun_test(failed_model_file: str, output_dir: str ) -> None:
    #verifiers = {Solution_Verifier.getName() : Solution_Verifier(), Optimization_Verifier.getName(): Optimization_Verifier(),Equivalance_Verifier.getName(): Equivalance_Verifier(),Model_Count_Verifier.getName(): Model_Count_Verifier(), Metamorphic_Verifier.getName(): Metamorphic_Verifier()}
    
    with open(failed_model_file, 'rb') as fpcl:
        error_data = pickle.loads(fpcl.read())
        fpcl.close()
        random.seed(error_data["seed"])
        if error_data["error"]["type"] != "fuzz_test_crash": # if it is a fuzz_test crash error we skip it
            
            verifier_args = [error_data["solver"], error_data["mutations_per_model"], {}, time.time()*3600, error_data["seed"]]
            verifiers = {"solution verifier" : Solution_Verifier(*verifier_args),"optimization verifier": Optimization_Verifier(*verifier_args), "model count verifier": Model_Count_Verifier(*verifier_args), "metamorphic verifier": Metamorphic_Verifier(*verifier_args),"equivalance verifier":Equivalance_Verifier(*verifier_args)}
            error = verifiers[error_data["verifier"]].rerun(error_data["error"])
            
            new_error_Data = error_data
            new_error_Data["error"] = error
            if error != None:
                    with open(join(output_dir, os.path.basename(failed_model_file)), "wb") as ff:
                        pickle.dump(new_error_Data, file=ff) 
                        ff.close()
                
#


def run_cmd(model: str,cmd : str, output_dir: str) -> None:
    warnings.filterwarnings("ignore")
    if cmd == "rerun_test":
        rerun_test(model,output_dir) 
    elif cmd == "minimize_report":
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A python application to fuzz test your model(s)")
    
    parser.add_argument("-m", "--models", help = "The path to a single pickle file or the path to a directory containing multiple .pickle files", required=False, type=str, default="output")
    parser.add_argument("-c", "--cmd", help = "The path to load the models", required=False, type=str,choices=["rerun_test","minimize_report"], default="rerun_test")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="bug_output")
    args = parser.parse_args()

    # create the output dir if it does not yet exist
    if not Path(args.output_dir).exists():
        os.mkdir(args.output_dir)

    # check if we need to run a single test or run multiple 
    files = []
    if os.path.isfile(args.models) :
        files.append(args.models)
    elif os.path.isdir(args.models):
        files.extend(glob(join(args.models, "*.pickle")))
    else:
       raise FileNotFoundError("error "+ args.models +" was not found, please provide a path to a file or directory")
  
    set_start_method("spawn")

    
    pool = Pool(cpu_count()-1)
    result = pool.starmap(run_cmd, zip(files,repeat(args.cmd),repeat(args.output_dir)))
    
    try:
        pool.join()
        print("sucessfully checked all the models",flush=True ) 
    except KeyboardInterrupt:
        pass
    finally:
        print("quiting the application",flush=True ) 

        pool.close()
        pool.terminate()
          
        sys.exit()
        