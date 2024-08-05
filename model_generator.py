import argparse
import os
from pathlib import Path
from glob import glob
import shutil
import subprocess

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "A python application to fuzz_test your solver(s)")
    parser.add_argument("-t", "--test-dir", help = "The path to load the models", required=False, type=str, default="tests")
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="models_output")
    args = parser.parse_args()

    result = None
    try:
        # run the pytests to create the models
        result = subprocess.Popen("python -m pytest tests", text=True,shell=True)
        result.wait()
    except KeyboardInterrupt:
        result.terminate()
    finally:
        if Path("temp_output").exists():
            # if the output dir exists copy all the files
            if Path(args.output_dir).exists():
                files = []
                files.extend(glob(os.path.join("temp_output", "*.pickle")))
                for file_name in files:
                    shutil.move(file_name, args.output_dir)
            else:
                 # if the output dir does not just rename the dir
                os.rename("temp_output",args.output_dir)
        
            
    

