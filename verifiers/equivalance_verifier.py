from verifiers import *

class Equivalance_Verifier(Verifier):
    """
        The Equivalance Verifier will verify if all the solution are the same after running multiple mutations
    """

    def __init__(self,solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        super().__init__("equivalance verifier", 'sat',solver,mutations_per_model,exclude_dict,time_limit,seed)
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
            assert (len(self.cons)>0), f"{self.model_file} has no constraints"
            self.cons = toplevel_list(self.cons)
            self.original_vars = get_variables(self.cons)
            self.original_sols = set()
            cp.Model(self.cons).solveAll(solver=self.solver,time_limit=max(1,min(250,self.time_limit-time.time())), display=lambda: self.original_sols.add(tuple([v.value() for v in self.original_vars])))
            self.mutators = [copy.deepcopy(self.cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
            
    def verify_model(self) -> dict:
        try:
            model = cp.Model(self.cons)
            new_sols = set()
            time_limit = max(1,min(200,self.time_limit-time.time())) # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1

            model.solveAll(
                solver=self.solver, 
                time_limit=time_limit, 
                display=lambda: new_sols.add(tuple([v.value() for v in self.original_vars])))
            
            change = new_sols.symmetric_difference(self.original_sols)
            
            if model.status().runtime > time_limit-10:
                # timeout, skip
                print('T', end='', flush=True)
                return None
            elif len(change) == 0:
                # has to be same
                print('.', end='', flush=True)
                return None
            else:
                print('X', end='', flush=True)
                return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                    originalmodel=self.model_file, 
                    exception=f"symmetric difference between new solutions and old solutions is not 0 it is {len(change)}",
                    constraints=self.cons,
                    mutators=self.mutators, 
                    model=model,
                    )
        
        except Exception as e:
            if isinstance(e,(CPMpyException, NotImplementedError)):
                #expected error message, ignore
                return True
            print('E', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.internalcrash,
                        originalmodel=self.model_file, 
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        mutators=self.mutators,
                        model=model, 
                        )
        # if you got here, the model failed...
        return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                    originalmodel=self.model_file,
                    constraints=self.cons,
                    mutators=self.mutators,
                    model=newModel,
                    )  