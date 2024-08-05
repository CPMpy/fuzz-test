import os
import time
from pathlib import Path

from cpmpy import Model

def save_test_constraints(constraints):
    if not Path("temp_output").exists():
        os.mkdir("temp_output")
    Model(constraints).to_file(os.path.join("temp_output","Pickled"+(str(time.time())).replace('.',"")+".pickle"))

def save_test_model(model):
    if not Path("temp_output").exists():
        os.mkdir("temp_output")
    model.to_file(os.path.join("temp_output","Pickled"+(str(time.time())).replace('.',"")+".pickle"))