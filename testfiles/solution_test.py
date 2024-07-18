
import glob
import pickle
import os
from pathlib import Path
from os.path import join
import sys
sys.path.append('../cpmpy')
from cpmpy.exceptions import CPMpyException
import cpmpy as cp
from mutators import *

def metamorphic_test(solver: str, iters: int, model_file: str, exclude_dict: dict) -> dict:
    """
    A helper function that will execute a single solution test

    Args:
        solver (string): the name of the solver that is getting used for the tests
        iters (int): the amount of permutations 
        model_file (string): the model file to open
        exclude_dict (dict): a dict of models we want to exclude
    """
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

    originalmodel = model_file
    #with open(f, 'rb') as fpcl:
    
    with open(model_file, 'rb') as fpcl:
        cons = pickle.loads(fpcl.read()).constraints
        
        #if compressed: cons = pickle.loads(brotli.decompress(fpcl.read())).constraints
        assert (len(cons)>0), f"{model_file} has no constraints"
        cons = toplevel_list(cons)
        assert (len(cons)>0), f"{model_file} has no constraints after l2conj"
        vars = get_variables(cons)
        Model(cons).solve()
        solution = [var == var.value() for var in vars if var.value() is not None]
        mutators = [copy.deepcopy(cons)] #keep track of list of cons alternated with random seed and mutators that transformed it into the next list of cons.
        for i in range(iters):
            # choose a metamorphic mutation, don't choose any from exclude_dict
            if model_file in exclude_dict:
                valid_mutators = list(set(mm_mutators) - set(exclude_dict[model_file]))
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
                if model_file in exclude_dict:
                    exclude_dict[model_file] += [m]
                else:
                    exclude_dict[model_file] = [m]
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
        return {"type": "failed_model","model": model, "originalmodel": originalmodel, "mutators": mutators}

def solution_tests(test_results: dict, current_amount_of_tests, current_amount_of_error, lock, solver: str, iters: int, folders: list, max_error_treshold: int, rseed: int) -> None:
    """
        A function that will execute multiple solution tests

        Args:
            test_results (dict): the dict containing the test result data
            current_amount_of_tests (Value(int)): the value that stores the current amount of test executed
            current_amount_of_error (Value(int)): the value that stores the current amount of errors found
            lock (Lock): the lock that gets used for the mutiprocessing
            solver (string): the name of the solver that is getting used for the tests
            iters (int): the amount of permutations 
            folders ([string]): the directories of the models that we are testing
            max_error_treshold (int): the maximimum errors that can be found before quitting the tests
            rseed (int): the random seed that is getting used for the tests
    """
    
    exclude_dict = {}
    fmodels = []
    nb_of_models = 0
    errors = []
    amount_of_tests=0
    random.seed(rseed)
    try:
        if Path('cpmpy-bigtest-private').exists():
            os.chdir('cpmpy-bigtest-private')
        for folder in folders:
            fmodels.extend(glob.glob(join(folder,'sat', "*")))
        while current_amount_of_error.value < max_error_treshold:
            random.shuffle(fmodels)
            for fmodel in fmodels:
                error = metamorphic_test(solver, iters, fmodel, exclude_dict)
                amount_of_tests+=1
                # check if we got an error
                if not (error == None) and current_amount_of_error.value < max_error_treshold:
                    errors.append(error)
                    lock.acquire()
                    try:
                        current_amount_of_error.value +=1
                    finally:
                        lock.release()  
                    
                nb_of_models += 1

                lock.acquire()
                try:
                    test_results["solution_tests"] = {'amount_of_tests': amount_of_tests,'nb_of_models' : nb_of_models, 'nb_of_errors' : len(errors), 'solver' : solver, 'iters' : iters ,"errors" :errors}
                    current_amount_of_tests.value += 1
                finally:
                    lock.release()
    except Exception as e:
        lock.acquire()
        errors.append({"type": "fuzz_test_crash","exception":e})
        try:
            test_results["solution_tests"] = {'amount_of_tests': amount_of_tests, 'nb_of_models' : nb_of_models, 'nb_of_errors' : len(errors), 'solver' : solver, 'iters' : iters ,"errors" :errors}
            current_amount_of_tests.value += 1
        finally:
            lock.release()