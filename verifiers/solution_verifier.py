from fuzz_test_utils.fuzz_test_errors import FuzzTestErrorType
from verifiers import *
from verifiers.utils import FuzzExit

class Solution_Verifier(Verifier):
    """
        The Solution Verifier will verify if a single solution is kept after running multiple mutations
    """

    def __init__(self,solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        super().__init__("solution verifier", 'sat',solver,mutations_per_model,exclude_dict,time_limit,seed)
        self.mm_mutators = [xor_morph, and_morph, or_morph, implies_morph, not_morph,
                        linearize_constraint_morph,
                        flatten_morph,
                        only_numexpr_equality_morph,
                        normalized_numexpr_morph,
                        reify_rewrite_morph,
                        only_bv_reifies_morph,
                        only_positive_bv_morph,
                        to_cnf_morph,
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
            # Use Model.from_file() to properly synchronize counters with variables in the loaded model
            self.original_model = Model.from_file(self.model_file)
        self.cons = self.original_model.constraints

        assert (len(self.cons)>0), f"{self.model_file} has no constraints"
        self.cons = toplevel_list(self.cons)
        vars = get_variables(self.cons)
        Model(self.cons).solve(
            solver=self.solver, 
            time_limit=max(1,self.time_limit)) # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1
        
        self.solution = [var == var.value() for var in vars if var.value() is not None]
        self.mutators = [(copy.deepcopy(self.cons), self.seed)] #keep track of list of cons alternated with random seed and mutators that transformed it into the next list of cons.
            
    def verify_model(self) -> dict:
        try:
            model = cp.Model(toplevel_list([self.cons, self.solution]))
            time_limit = max(min(200,self.time_limit),1)
            sat = model.solve(solver=self.solver, time_limit=time_limit)

            # Extract initial processed constraints from mutators (stored right after initialize_run())
            initial_processed_cons = None
            if len(self.mutators) > 0:
                if isinstance(self.mutators[0], tuple) and len(self.mutators[0]) == 2:
                    initial_processed_cons = self.mutators[0][0]
                elif isinstance(self.mutators[0], list):
                    initial_processed_cons = self.mutators[0]

            if self.solve_timed_out(model):
                # timeout, skip
                return FuzzExit(
                            type=FuzzTestErrorType.timeout,
                            verifier=self,
                            exception="timeout",
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file,
                            processed_constraints=initial_processed_cons
                        )
            elif sat:
                # has to be sat
                return FuzzExit(
                            type=FuzzTestErrorType.ok,
                            verifier=self,
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file,
                            processed_constraints=initial_processed_cons
                        )
            else:
                return FuzzExit(
                            type=FuzzTestErrorType.failed_model,
                            verifier=self,
                            exception="mutated model is not sat",
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file,
                            processed_constraints=initial_processed_cons
                        )
            
        except Exception as e:
            if isinstance(e, TimeoutError) or "Operation timed out" in str(e):
                # Handle TimeoutError as timeout, not internalcrash
                return FuzzExit(
                            type=FuzzTestErrorType.timeout,
                            verifier=self,
                            exception=e,
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file,
                            processed_constraints=initial_processed_cons
                        )
            elif isinstance(e,(CPMpyException, NotImplementedError)):
                # expected error message
                return FuzzExit(
                            type=FuzzTestErrorType.expected_error,
                            verifier=self,
                            exception=e,
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file,
                            processed_constraints=initial_processed_cons
                        )
            return FuzzExit(
                        type=FuzzTestErrorType.internalcrash,
                        verifier=self,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        mutators=self.mutators,
                        model=model,
                        originalmodel=self.original_model,
                        originalmodel_file=self.model_file,
                        processed_constraints=initial_processed_cons
                    )
        # if you got here, the model failed...
        return FuzzExit(
                    type=FuzzTestErrorType.failed_model,
                    verifier=self,
                    mutators=self.mutators,
                    model=model,
                    originalmodel=self.original_model,
                    originalmodel_file=self.model_file,
                    processed_constraints=initial_processed_cons
                )
        
 
 