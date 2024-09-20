from verifiers import *

class Optimization_Verifier(Verifier):
    """
        The Optimization Verifier will verify if all objective value remains unchanged after multiple muations
    """

    def __init__(self,solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        super().__init__("optimization verifier", 'optimization',solver,mutations_per_model,exclude_dict,time_limit,seed)
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
    
    def initialize_run(self) -> None:
        if self.original_model == None:
            with open(self.model_file, 'rb') as fpcl:
                self.original_model = pickle.loads(fpcl.read())
        self.cons = self.original_model.constraints
        assert (len(self.cons)>0), f"{self.model_file} has no constraints"
        # replace lists by conjunctions
        self.cons = toplevel_list(self.cons)
        self.objective = self.original_model.objective_
        self.minimize = self.original_model.objective_is_min
        model = cp.Model(self.cons)
        self.mutators = [copy.deepcopy(self.cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
        if self.minimize:
            model.minimize(self.objective)
        else:
            model.maximize(self.objective)
        assert (model.solve(solver=self.solver, time_limit=max(self.time_limit-time.time(),1))), f"{self.model_file} is not sat"
        self.value_before = model.objective_value() #store objective value to compare after transformations
        
    def verify_model(self) -> dict:
        try:
            newModel = cp.Model(self.cons)
            if self.minimize:
                newModel.minimize(self.objective)
            else:
                newModel.maximize(self.objective)

            time_limit=max(min(200,self.time_limit-time.time()),1) # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1
            
            sat = newModel.solve(solver=self.solver, time_limit=time_limit)
            if newModel.status().runtime > time_limit-10:
                # timeout, skip
                print('T', end='', flush=True)
                return None
            elif newModel.objective_value() != self.value_before:
                #objective value changed
                print('c', end='', flush=True)
                return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                    originalmodel_file=self.model_file, 
                    exception=f"mutated model objective_value has changed new objective_value: {newModel.objective_value()}, original objective_value: {self.value_before}",
                    constraints=self.cons,
                    mutators=self.mutators, 
                    model=model,
                    originalmodel=self.original_model
                )
            elif sat:
                # has to be SAT...
                print('.', end='', flush=True)
                return None
            else:
                print('X', end='', flush=True)
                return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                    originalmodel_file=self.model_file, 
                    exception=f"mutated model is not sat",
                    constraints=self.cons,
                    mutators=self.mutators, 
                    model=model,
                    originalmodel=self.original_model
                    )

        except Exception as e:
            print('E', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.internalcrash,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        mutators=self.mutators,
                        model=newModel,
                        originalmodel=self.original_model
                        )
        
        # if you got here, the model failed...
        return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                    originalmodel_file=self.model_file,
                    constraints=self.cons,
                    mutators=self.mutators,
                    model=newModel,
                    originalmodel=self.original_model
                    )
        