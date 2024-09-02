import glob
import os.path
import pickle
from os.path import join

folder = 'pickle-test_constraints'
folder = 'pickle_examples'
folder = 'pickle_test_expression'
#folder = 'pickle_test_globals'
models = glob.glob(join('models',folder, "Pickle*"))


for f in models:
    with open(f, 'rb') as pickl:
        model = pickle.load(pickl)
        print(model.solve())
        if model.objective_ is not None:
            name = os.path.basename(f)
            pickl.close()
            os.rename(f,f[:len(f)-len(name)]+'optimization\\'+name)
            print('optimization')
        elif not model.solve():
            pickl.close()
            name = os.path.basename(f)
            os.rename(f,f[:len(f) - len(name)] + 'unsat\\' + name)
            print('false')
        try:
            model.solve()
            name = os.path.basename(f)
            pickl.close()
            os.rename(f, f[:len(f) - len(name)] + 'sat\\' + name)
        except Exception as e:
            name = os.path.basename(f)
            pickl.close()
            print(e)
            print(model.constraints)
            os.rename(f, f[:len(f) - len(name)] + 'error\\' + name)