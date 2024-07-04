"""
Tests all models in the `models/` folder, which are known to be SAT

Will only run solver tests on solvers that are installed
"""
import sys
sys.path.append('../cpmpy')
from glob import glob
from os.path import join
import pickle
import timeit
import os
from pathlib import Path

path = os.path.join('cpmpy-bigtest-private','models','sat')
print(path)
MODELS = sorted(glob(join(path, "*.bt")))
print(MODELS)
solver = 'ortools'
decomps = []
solvetimes = {}

def open_model(model):
    import brotli
    import pickle
    with open(model, 'rb') as fpcl:
        return pickle.loads(brotli.decompress(fpcl.read()))

for i in range(3):
    for fmodel in MODELS:
        decomps = []
        model = open_model(fmodel)
        decomps += [model]
        print(fmodel)
        setup = "from __main__ import decomps, solver; from cpmpy import SolverLookup; model = decomps[0]; s = SolverLookup.get('ortools',model)"
        stmt = "s.solve(num_search_workers=1)".format(fmodel)
        #stmt = "model.solve(solver)".format(fmodel)
        time = timeit.timeit(setup=setup,stmt=stmt, number=1)
        if i == 0:
            solvetimes[fmodel] = time
        else:
            solvetimes[fmodel] += time
        print(time)

filename = join('timings', "standard.pickle")
if not Path('timings').exists():
    os.mkdir('timings')
with open(filename, "wb") as ff:
    pickle.dump(solvetimes, file=ff) #log timings