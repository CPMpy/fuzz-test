
import glob
import os
import pickle
import random
import time
from os.path import join
import sys
from pathlib import Path

from cpmpy.transformations.normalize import toplevel_list

sys.path.append('../cpmpy')
import cpmpy as cp
from cpmpy.exceptions import CPMpyException

if __name__ == '__main__':
    solver = "ortools"
    iters = 10 # number of metamorphic mutations per model
    sat = True
    enb = 0
    consper = 0.5 # set between 0 and 1
    if Path('cpmpy-bigtest-private').exists():
        os.chdir('cpmpy-bigtest-private')
    resultfile = join(solver + '-metamorphic' + str(iters), 'result')
    if not Path(solver + '-metamorphic'+ str(iters)).exists():
        os.mkdir(solver + '-metamorphic'+ str(iters))
    exclude_dict = {}

    dirname = "models"
    folders = [os.path.join(dirname, 'pickle-test_constraints') ,os.path.join(dirname,'pickle_examples'),os.path.join(dirname,'pickle_test_expression'),os.path.join(dirname,'pickle_test_globals')]
    folders = [os.path.join(dirname, 'pickle-test_constraints'), os.path.join(dirname,'pickle_test_expression'),os.path.join(dirname,'pickle_test_globals')]
    fmodels = []
    print(folders)
    for folder in folders:
        print(Path(folder).exists())
        fmodels.extend(glob.glob(join(folder,'sat', "*")))
    for f in fmodels:
        with open(f, 'rb') as fpcl:
            print(f)
            cons = pickle.loads(fpcl.read()).constraints
            # if compressed: cons = pickle.loads(brotli.decompress(fpcl.read())).constraints
            assert (len(cons) > 0), f"{f} has no constraints"
            # replace lists by conjunctions
            cons = toplevel_list(cons)
            assert (len(cons) > 0), f"{f} has no constraints after l2conj"
            assert (cp.Model(cons).solve()), f"{f} is not sat"