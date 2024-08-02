from verifiers import *

class Optimization_Verifier(Verifier):
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
    
    def initilize_run(self) -> None:
        with open(self.model_file, 'rb') as fpcl:
                model = pickle.loads(fpcl.read())
                self.cons = model.constraints
                assert (len(self.cons)>0), f"{self.model_file} has no constraints"
                # replace lists by conjunctions
                self.cons = toplevel_list(self.cons)
                self.objective = model.objective_
                self.mininimize = model.objective_is_min
                model = cp.Model(self.cons)
                self.mutators = [copy.deepcopy(self.cons)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
                if self.mininimize:
                    model.minimize(self.objective)
                else:
                    model.maximize(self.objective)
                assert (model.solve(solver=self.solver, time_limit=max(self.time_limit-time.time(),1))), f"{self.model_file} is not sat"
                self.value_before = model.objective_value() #store objective value to compare after transformations
                
    def verify_model(self) -> dict:
        try:
            newModel = cp.Model(self.cons)
            if self.mininimize:
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
            elif sat:
                # has to be SAT...
                print('.', end='', flush=True)
                return None
            else:
                print('X', end='', flush=True)
                #print('morphs: ', mutators)
        except Exception as e:
            print('E', end='', flush=True)
            return dict(type="internalcrash",model=newModel, originalmodel=self.model_file, mutators=self.mutators,constraints=self.cons ,exception=e,stacktrace=traceback.format_exc())
        
        # if you got here, the model failed...
        return dict(type="failed_model",model=newModel, originalmodel=self.model_file, mutators=self.mutators, constraints=self.cons)
        