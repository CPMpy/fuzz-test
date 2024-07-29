import pickle
import random
import time
import cpmpy as cp
from cpmpy.exceptions import CPMpyException
from mutators import *
from .verifier import Verifier
import traceback
class Metamorphic_Verifier(Verifier):

    def run(self,solver: str, mutations_per_model: int, model_file: str, exclude_dict: dict, max_duration: float, seed: float) -> dict:
        """
        This function that will execute a single verifier test

        Args:
            solver (string): the name of the solver that is getting used for the tests
            mutations_per_model (int): the amount of permutations 
            model_file (string): the model file to open
            exclude_dict (dict): a dict of models we want to exclude
            max_duration (float): the maximum timestamp that can be reached (no tests can exeed the duration of this timestamp)
        """
        try:


            # list of mutators.
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
            # choose a random model
            originalmodel = model_file

            with open(model_file, 'rb') as fpcl:
                cons = pickle.loads(fpcl.read()).constraints
                #if compressed: cons = pickle.loads(brotli.decompress(fpcl.read())).constraints
                assert (len(cons)>0), f"{model_file} has no constraints"
                cons = toplevel_list(cons)
                assert (len(cons)>0), f"{model_file} has no constraints after l2conj"
                time_limit = max(max_duration-time.time(),1)
                assert (cp.Model(cons).solve(time_limit=time_limit)), f"{model_file} is not sat"
                mutators = [copy.deepcopy(cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
                random.seed(seed)
                for i in range(mutations_per_model):
                    # choose a metamorphic mutation, don't choose any from exclude_dict
                    if model_file in exclude_dict:
                        valid_mutators = list(set(mm_mutators) - set(exclude_dict[model_file]))
                    else:
                        valid_mutators = mm_mutators
                    m = random.choice(valid_mutators)
                    mutators += [seed]
                    # an error can occur in the transformations, so even before the solve call.
                    # log function and arguments in that case
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
                        elif function == semanticFusion:
                            return None
                            #don't log semanticfusion crash
                            
                        print('I', end='', flush=True)
                        return {"type": "internalfunctioncrash","function":function, "argument": argument, "originalmodel": originalmodel, "exception": e, "mutators": mutators,"stacktrace":traceback.format_exc()} # no need to solve model we didn't modify..
                # enough mutations, time for solving
                try:
                    model = cp.Model(cons)
                    time_limit= min(200,max_duration-time.time())
                    if time_limit <= 1:
                        return None
                    sat = model.solve(solver=solver, time_limit=time_limit)
                    if model.status().runtime > time_limit-10:
                        # timeout, skip
                        print('T', end='', flush=True)
                        return None
                    elif sat:
                        # has to be SAT...
                        print('.', end='', flush=True)
                        return None
                    else:
                        print('X', end='', flush=True)
                        #print('morphs: ', mutators)
                except Exception as e:
                    if isinstance(e,(CPMpyException, NotImplementedError)):
                        #expected error message, ignore
                        print('s', end='', flush=True)
                        return None
                    print('E', end='', flush=True)
                    return {"type": "internalcrash","model": model, "originalmodel": originalmodel, "mutators": mutators,"exception": e,"stacktrace":traceback.format_exc() }

                # if you got here, the model failed...
                return {"type": "failed_model","model": model, "originalmodel": originalmodel, "mutators": mutators }
        
        except Exception as e:
            return {"type": "crashed_model", "originalmodel": originalmodel, "exeption": e,"stacktrace":traceback.format_exc()}
    def getType(self) -> str:
        """This function is used for getting the type of the problem the verifier verifies"""
        return "sat"

    def getName(self) -> str:
        """This function is used for getting the name of the verifier"""
        return "metamorphic verifier"