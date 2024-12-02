import pickle
import timeit
import argparse
import os
from os.path import join
import sys
import glob

#give this a meaningful name, so we know what branch was tested after the results are safed.
branch = 'main'
#set solver to test (supported: ortools)
solver = 'ortools'

parser = argparse.ArgumentParser(description = "A python application to fuzz_test your solver(s)")
parser.add_argument("-m", "--models", help = "The path to load the models", required=False, type=str, default="models")

args = parser.parse_args()
models = []# create a list with all the directories
for model in os.listdir(args.models):
    models.append(os.path.join(args.models, model))
if len(models) == 0:
    print(f"models is empty")
    sys.exit(0)

fmodels = []
for folder in models:
    fmodels.extend(glob.glob(join(folder, 'sat', "*")))

cons = []
for modfile in fmodels:
    with open(modfile, 'rb') as fpcl:
        cons.extend(pickle.loads(fpcl.read()).constraints)


from cpmpy.solvers import CPM_ortools

# Time the transformation of constraints
transform_time = timeit.timeit(lambda: CPM_ortools.transform(CPM_ortools(), cons), number=1)
print(transform_time)

