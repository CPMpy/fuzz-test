import glob
import os
import pickle
import time
from os.path import join
import sys
from pathlib import Path
import signal

sys.path.append('../cpmpy')

import cpmpy as cp
from cpmpy.exceptions import CPMpyException

from mutators import *

def metamorphic_test(solver, iters,f,exclude_dict):
    # list of mutators
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
        model = pickle.loads(fpcl.read())
        cons = model.constraints
        assert (len(cons)>0), f"{f} has no constraints"
        # replace lists by conjunctions
        cons = toplevel_list(cons)
        objective = model.objective_
        mininimize = model.objective_is_min
        model = cp.Model(cons)
        mutators = [copy.deepcopy(cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
        if mininimize:
            model.minimize(objective)
        else:
            model.maximize(objective)
        assert (model.solve()), f"{f} is not sat"
        value_before = model.objective_value() #store objective value to compare after transformations
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
            # log function and arguments in that case
            mutators += [m]
            try:
                cons += m(cons)  # apply a metamorphic mutation
                mutators += [copy.deepcopy(cons)]
            except MetamorphicError as exc:
                # add to exclude_dict, to avoid running into the same error
                if f in exclude_dict:
                    exclude_dict[f] += [m]
                else:
                    exclude_dict[f] = [m]
                function, argument, e = exc.args
                if isinstance(e,CPMpyException):
                    #expected behavior if we throw a cpmpy exception, do not log
                    return None
                elif function == semanticFusion:
                    return None
                    #don't log semanticfusion crash
                print('IE', end='', flush=True)
                print(function)
                return {"type": "internalfunctioncrash","function":function, "argument": argument, "originalmodel": originalmodel, "exception": e, "mutators": mutators} # no need to solve model we didn't modify..


        # enough mutations, time for solving
        try:
            newModel = cp.Model(cons)
            if mininimize:
                newModel.minimize(objective)
            else:
                newModel.maximize(objective)
            sat = newModel.solve(solver=solver, time_limit=200)
            if newModel.status().runtime > 190:
                # timeout, skip
                print('s', end='', flush=True)
                return None
            elif newModel.objective_value() != value_before:
                #objective value changed
                print('c', end='', flush=True)
            elif sat:
                # has to be SAT...
                print('.', end='', flush=True)
                return None
            else:
                print('X', end='', flush=True)
                print('morphs: ', mutators)
        except Exception as e:
            print('E', end='', flush=True)
            print(e)

        # if you got here, the model failed...
        return {"model": model, "originalmodel": originalmodel, "mutators": mutators}

def optimization_test(testResults,current_amount_of_tests, current_error_treshold, lock, hrs,solver,iters, folders, max_error_treshold):
    rseed = 0
    random.seed(rseed)
    
    if Path('cpmpy-bigtest-private').exists():
        os.chdir('cpmpy-bigtest-private')

    exclude_dict = {}

    fmodels = []
    for folder in folders:
        fmodels.extend(glob.glob(join(folder,'optimization', "*")))
    endtime = time.time() + 60 * hrs
    nb_of_models = 0
    errors = []
    amount_of_tests=0

    def signal_handle(_signal, frame):
        print("kkkkkkkkkkkkkkkkkk")
        print(amount_of_tests)
        print("kkkkkkkkkkkkkkkkkk")
    signal.signal(signal.SIGINT, signal_handle)
    while time.time() < endtime:
        random.shuffle(fmodels)
        for fmodel in fmodels:
            #print('time left: ', time.time() - endtime)
            if time.time() > endtime:
                break
            amount_of_tests+=1
            print("did a test")
            """error = metamorphic_test(solver, iters, fmodel, exclude_dict)
            if not (error == None):
                errors.append(error)
                # check if we reached our error treshold
                lock.acquire()
                try:
                    current_error_treshold.value +=1
                finally:
                    lock.release()  
                if current_error_treshold.value >= max_error_treshold:
                    endtime = 0"""
                
            nb_of_models += 1

    lock.acquire()
    try:
        print("aaaaaaaaaaaaaaaaaa")
        print(amount_of_tests)
        print("aaaaaaaaaaaaaaaaaa")
        testResults["optimization_tests"] = {'nb_of_models' : nb_of_models, 'hours' : hrs, 'nb_of_errors' : len(errors), 'solver' : solver, 'testtype' : 'optimization_tests', 'iters' : iters, 'randomseed' : rseed,"errors" :errors}
        current_amount_of_tests.value += amount_of_tests
    finally:
        lock.release()        

