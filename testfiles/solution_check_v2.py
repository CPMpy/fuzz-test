
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
import signal
import logging
import atexit
from multiprocessing.pool import ThreadPool



def metamorphic_test(solver, iters,f,exclude_dict):
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
    #with open(f, 'rb') as fpcl:
    
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
                function, argument, e = exc.args
                if isinstance(e,CPMpyException):
                    #expected behavior if we throw a cpmpy exception, do not log
                    return None
                print('IE', end='', flush=True)
                return {"type": "internalfunctioncrash","function":function, "argument": argument, "originalmodel": originalmodel, "exception": e, "mutators": mutators} # no need to solve model we didn't modify..
        
            # enough mutations, time for solving
            try:
                model = cp.Model(toplevel_list([cons, solution]))
                sat = model.solve(solver=solver, time_limit=200)
                if model.status().runtime > 190:
                    # timeout, skip
                    print('s', end='', flush=True)
                    return None
                elif sat:
                    # has to be sat
                    print('.', end='', flush=True)
                    return None
                else:
                    print('X', end='', flush=True)
                    #print('morphs: ', mutators)
            except Exception as e:
                if isinstance(e,(CPMpyException, NotImplementedError)):
                    #expected error message, ignore
                    return None
                print('E', end='', flush=True)
                # if you got here, the model failed...
            
            return {"model": model, "originalmodel": originalmodel, "mutators": mutators}

def solution_check(testResults,current_amount_of_tests, current_error_treshold, lock, hrs,solver,iters, folders, max_error_treshold):
        rseed = 0
        random.seed(rseed)
        if Path('cpmpy-bigtest-private').exists():
            os.chdir('cpmpy-bigtest-private')

        exclude_dict = {}

        fmodels = []
        for folder in folders:
            fmodels.extend(glob.glob(join(folder,'sat', "*")))
        endtime = time.time() + 60 * hrs
        nb_of_models = 0
        errors = []

        amount_of_tests=0

        while time.time() < endtime:
            random.shuffle(fmodels)
            for fmodel in fmodels:
                #print("timeleft: ", endtime - time.time())
                if time.time() > endtime:
                    break
                amount_of_tests+=1

                error = metamorphic_test(solver, iters, fmodel, exclude_dict)
                # check if we got an error
                if not (error == None):
                    errors.append(error)
                    # check if we reached our error treshold
                    lock.acquire()
                    try:
                        current_error_treshold.value +=1
                    finally:
                        lock.release()  
                    if current_error_treshold.value >= max_error_treshold:
                        endtime = 0
                    
                nb_of_models += 1

        lock.acquire()
        try:
            testResults["solution_check"] = {'nb_of_models' : nb_of_models, 'hours' : hrs, 'nb_of_errors' : len(errors), 'solver' : solver, 'testtype' : 'solutioncheck', 'iters' : iters, 'randomseed' : rseed,"errors" :errors}
            current_amount_of_tests.value += amount_of_tests
        finally:
            lock.release()    
        

