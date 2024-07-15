
import glob
import pickle
import os
from pathlib import Path
from os.path import join
import time
import sys
sys.path.append('../cpmpy')
from cpmpy.exceptions import CPMpyException
import cpmpy as cp
from mutators import *



def metamorphic_test(solver, iters,f,enb,exclude_dict):
    # List of mutators.
    mm_mutators = [xor_morph, and_morph, or_morph, implies_morph, not_morph,
                   linearize_constraint_morph,
                   flatten_morph,
                   only_numexpr_equality_morph,
                   normalized_numexpr_morph,
                   reify_rewrite_morph,
                   only_bv_reifies_morph,
                   only_positive_bv_morph,
                   flat2cnf_morph,
                   toplevel_list_morph,
                   decompose_in_tree_morph,
                   push_down_negation_morph,
                   simplify_boolean_morph,
                   canonical_comparison_morph,
                   aritmetic_comparison_morph,
                   semanticFusion,
                   semanticFusionMinus,
                   semanticFusionwsum]

    originalmodel = f
    with open(f, 'rb') as fpcl:
        cons = pickle.loads(fpcl.read()).constraints
        #if compressed: cons = pickle.loads(brotli.decompress(fpcl.read())).constraints
        assert (len(cons)>0), f"{f} has no constraints"
        cons = toplevel_list(cons)
        assert (len(cons)>0), f"{f} has no constraints after l2conj"
        vars = get_variables(cons)
        Model(cons).solve()
        solution = [var == var.value() for var in vars if var.value() is not None]
        mutators = [copy.deepcopy(cons)] #keep track of list of cons alternated with random seed and mutators that transformed it into the next list of cons.
        for i in range(iters):
            # choose a metamorphic mutation, don't choose any from exclude_dict
            if f in exclude_dict:
                valid_mutators = list(set(mm_mutators) - set(exclude_dict[f]))
            else:
                valid_mutators = mm_mutators
            m = random.choice(valid_mutators)
            seed = random.random()
            random.seed(seed)
            mutators += [seed]
            # an error can occur in the transformations, so even before the solve call.
            # log randomseed, function and arguments in that case
            mutators += [m]
            try:
                 cons += m(cons)  # apply a metamorphic mutation
                 mutators += [copy.deepcopy(cons)]
            except MetamorphicError as exc:
                #add to exclude_dict, to avoid running into the same error
                if f in exclude_dict:
                    exclude_dict[f] += [m]
                else:
                    exclude_dict[f] = [m]
                enb += 1
                function, argument, e = exc.args
                if isinstance(e,CPMpyException):
                    #expected behavior if we throw a cpmpy exception, do not log
                    return True
                filename = join(solver + '-solutioncheck' + str(iters), "internalfunctioncrash"+str(enb)+".pickle")
                with open(filename, "wb") as ff:
                    pickle.dump([function, argument, originalmodel, e, mutators], file=ff) # log function and arguments that caused exception
                print('IE', end='', flush=True)
                return False # no need to solve model we didn't modify..
        # enough mutations, time for solving
        try:
            model = cp.Model(toplevel_list([cons, solution]))
            sat = model.solve(solver=solver, time_limit=200)
            if model.status().runtime > 190:
                # timeout, skip
                print('s', end='', flush=True)
                return True
            elif sat:
                # has to be sat
                print('.', end='', flush=True)
                return True
            else:
                print('X', end='', flush=True)
                #print('morphs: ', mutators)
        except Exception as e:
            if isinstance(e,(CPMpyException, NotImplementedError)):
                #expected error message, ignore
                return True
            print('E', end='', flush=True)


        # if you got here, the model failed...
        enb += 1
        with open(join(solver + '-solutioncheck' + str(iters), "lasterrormodel" + str(enb)+".pickle"), "wb") as f:
            pickle.dump([model, originalmodel, mutators], file=f)
        return False


if __name__ == '__main__':
    if len(sys.argv) > 2:
        solver = sys.argv[1]
        hrs = float(sys.argv[2])
        iters = int(sys.argv[3])
    else:
        hrs = 1
        solver = "ortools"
        iters = 5 # number of metamorphic mutations per model
    rseed = 0
    random.seed(rseed)
    sat = True
    enb = 0
    consper = 0.5 # set between 0 and 1
    if Path('cpmpy-bigtest-private').exists():
        os.chdir('cpmpy-bigtest-private')
    resultfile = join(solver + '-solutioncheck' + str(iters), 'result_solutioncheck')
    if not Path(solver + '-solutioncheck' + str(iters)).exists():
        os.mkdir(solver + '-solutioncheck' + str(iters))
    exclude_dict = {}
    dirname = "models"
    folders = [os.path.join(dirname, 'pickle-test_constraints'), os.path.join(dirname, 'pickle_examples'),
               os.path.join(dirname, 'pickle_test_expression'), os.path.join(dirname, 'pickle_test_globals')]
    folders = [os.path.join(dirname, 'pickle-test_constraints'), os.path.join(dirname, 'pickle_test_expression'),
               os.path.join(dirname, 'pickle_test_globals')]
    folders = [os.path.join(dirname, 'pickle-test_constraints')]
    fmodels = []
    for folder in folders:
        fmodels.extend(glob.glob(join(folder,'sat', "*")))
    endtime = time.time() + 3600 * hrs
    nb_of_models = 0
    while time.time() < endtime:
        random.shuffle(fmodels)
        for fmodel in fmodels:
            #print("timeleft: ", endtime - time.time())
            if time.time() > endtime:
                break
            sat = metamorphic_test(solver, iters, fmodel, enb, exclude_dict)
            if not sat:
                enb += 1
            nb_of_models += 1

    with open(resultfile, "wb") as ff:
        pickle.dump({'nb_of_models' : nb_of_models, 'hours' : hrs, 'nb_of_errors' : enb, 'solver' : solver, 'testtype' : 'solutioncheck', 'iters' : iters, 'randomseed' : rseed}, file=ff)  # log some stats
