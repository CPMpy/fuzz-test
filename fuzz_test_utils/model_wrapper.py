import os
from pathlib import Path
import time

import cpmpy as cp

class Model(cp.Model) :
    def __init__(self, *args, minimize=None, maximize=None):
            if not Path("temp_output").exists():
                os.mkdir("temp_output")
            super().to_file(os.path.join("temp_output","Pickled"+(str(time.time())).replace('.',"")+".pickle"))

            super().__init__(*args,minimize=minimize,maximize=maximize)

    def solve(self, solver=None, time_limit=None, **kwargs):

        if not Path("temp_output").exists():
            os.mkdir("temp_output")

        super().to_file(os.path.join("temp_output","Pickled"+(str(time.time())).replace('.',"")+".pickle"))

        super().solve(solver,time_limit,**kwargs)
    

    def solveAll(self, solver=None, display=None, time_limit=None, solution_limit=None):

        if not Path("temp_output").exists():
            os.mkdir("temp_output")

        super().to_file(os.path.join("temp_output","Pickled"+(str(time.time())).replace('.',"")+".pickle"))

        super().solveAll(solver,display,time_limit,solution_limit)