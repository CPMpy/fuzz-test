import sys
import pickle

sys.path.append('../cpmpy')

filename = sys.argv[1]

with open(filename, 'rb') as fpcl:
    results = pickle.loads(fpcl.read())
    print(results)
    fpcl.close()