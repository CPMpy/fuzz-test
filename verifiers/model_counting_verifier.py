import pickle
import time
from cpmpy.exceptions import CPMpyException
import cpmpy as cp
from mutators import *
import traceback
from .verifier import Verifier



class Model_Count_Verifier(Verifier):
    def __init__(self,solver: str, mutations_per_model: int, exclude_dict: dict, max_duration: float, seed: int):
        super().__init__("model count verifier", 'sat',solver,mutations_per_model,exclude_dict,max_duration,seed)
        self.mm_mutators = [xor_morph, and_morph, or_morph, implies_morph, not_morph,
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
                        semanticFusionCounting,
                        semanticFusionCountingMinus,
                        semanticFusionCountingwsum]
    
    def initilize_run(self) -> None:
        with open(self.model_file, 'rb') as fpcl:
            self.cons = pickle.loads(fpcl.read()).constraints
            #if compressed: cons = pickle.loads(brotli.decompress(fpcl.read())).constraints
            assert (len(self.cons)>0), f"{self.model_file} has no constraints"
            self.cons = toplevel_list(self.cons)
            assert (len(self.cons)>0), f"{self.model_file} has no constraints after l2conj"
            self.sol_count = cp.Model(self.cons).solveAll(solver=self.solver,time_limit=max(1,min(250,self.max_duration-time.time())))
            self.mutators = [copy.deepcopy(self.cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
            
    def solve_model(self) -> dict:
        try:
            model = cp.Model(self.cons)
            time_limit=max(1,min(200,self.max_duration-time.time()))

            new_count = model.solveAll(solver=self.solver, time_limit=time_limit)
            if model.status().runtime > time_limit-10:
                # timeout, skip
                print('T', end='', flush=True)
                return None
            elif self.sol_count == new_count:
                # has to be same
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
            return {"type": "internalcrash","model": model, "originalmodel": self.model_file, "mutators": self.mutators,"constraints":self.cons ,"exception": e,"stacktrace":traceback.format_exc() }
        
        # if you got here, the model failed...
        return {"type": "failed_model","model": model, "originalmodel": self.model_file, "mutators": self.mutators, "constraints":self.cons }
        


