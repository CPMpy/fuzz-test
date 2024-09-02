import brotli
import glob
import os
import pickle
import time
from os.path import join

from cpmpy import *
from cpmpy.transformations.flatten_model import flatten_constraint
from cpmpy.transformations.reification import only_bv_implies, reify_rewrite
from cpmpy.transformations.comparison import only_numexpr_equality


def print_model_stats(dirname):
    times = dict([('pickle', 0.0),
                  ('flatten', 0.0),
                  ('reify', 0.0),
                  ('numexpr', 0.0),
                  ('bv_implies', 0.0),
                  ('model', 0.0),
                  ('solve', 0.0),
                  ('solver', 0.0),
                 ])
    slowest = ("X", 0.0)
    for f in sorted(glob.glob(join(dirname, "17b*.bt")))[0:10]:
        try:
            with open(f, 'rb') as fpcl:
                print('.', end='', flush=True)
                t0 = time.time()
                model = pickle.loads(brotli.decompress(fpcl.read()))
                cpm_cons = model.constraints
                times['pickle'] += time.time() - t0

                t0 = time.time()
                cpm_cons = flatten_constraint(cpm_cons)
                times['flatten'] += time.time() - t0

                t0 = time.time()
                cpm_cons = reify_rewrite(cpm_cons, supported=frozenset(['sum', 'wsum']))
                times['reify'] += time.time() - t0

                t0 = time.time()
                cpm_cons = only_numexpr_equality(cpm_cons, supported=frozenset(['sum', 'wsum']))
                times['numexpr'] += time.time() - t0

                t0 = time.time()
                cpm_cons = only_bv_implies(cpm_cons)
                times['bv_implies'] += time.time() - t0
                v = time.time() - t0
                if v > slowest[1]:
                    slowest = (f, v)

                s = SolverLookup.get("ortools")
                t0 = time.time()
                s += cpm_cons
                times['model'] += time.time() - t0

                t0 = time.time()
                sat = s.solve(time_limit=120, num_workers=1)
                times['solve'] += time.time() - t0
                times['solver'] += s.status().runtime

                if not sat:
                    print(f"\tWARNING, {f} was unsat")
                #print([f"{k}: {v:.2f}" for (k,v) in times.items()])
        except Exception as e:
            print(f, "CRASHES", e)

    print("")  # after all the .'s
    for (k,v) in times.items():
        print(f"{k}: {v:.2f}")
    print("Slowest", slowest)


if __name__ == '__main__':
    dirname = "models"
    print_model_stats(dirname)
