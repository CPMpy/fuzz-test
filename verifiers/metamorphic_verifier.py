from verifiers import *

class Metamorphic_Verifier(Verifier):
    """
        The Metamorphic Verifier will verify if amount of model is still Satisifiability after running multiple mutations
    """
    
    def __init__(self,solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        super().__init__("metamorphic verifier", 'sat',solver,mutations_per_model,exclude_dict,time_limit,seed)
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
                        semanticFusion,
                        semanticFusionMinus,
                        semanticFusionwsum]
        

    def initilize_run(self) -> None:
        with open(self.model_file, 'rb') as fpcl:
            self.cons = pickle.loads(fpcl.read()).constraints
            assert (len(self.cons)>0), f"{self.model_file} has no constraints"
            self.cons = toplevel_list(self.cons)
            time_limit = max(self.time_limit-time.time(),1)
            assert (cp.Model(self.cons).solve(solver= self.solver, time_limit=time_limit)), f"{self.model_file} is not sat"
            self.mutators = [copy.deepcopy(self.cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
            
    def verify_model(self) -> dict:
        try:
            model = cp.Model(self.cons)
            time_limit= max(1,min(200,self.time_limit-time.time())) # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1

            sat = model.solve(solver=self.solver, time_limit=time_limit)
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
            return dict(type=Fuzz_Test_ErrorTypes.internalcrash,model=model, originalmodel=self.model_file, mutators=self.mutators,constraints=self.cons ,exception=e,stacktrace=traceback.format_exc())
        
        # if you got here, the model failed...
        return dict(type=Fuzz_Test_ErrorTypes.failed_model,model=model, originalmodel=self.model_file, mutators=self.mutators, constraints=self.cons)
        