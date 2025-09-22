from fuzz_test_utils.fuzz_test_errors import FuzzTestErrorType
from verifiers import *
from verifiers.utils import FuzzExit
class Model_Count_Verifier(Verifier):
    """
        The Model Count Verifier will verify if amount of solution is the same after running multiple mutations
    """

    def __init__(self,solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        super().__init__("model count verifier", 'sat',solver,mutations_per_model,exclude_dict,time_limit,seed)
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
    
    def initialize_run(self) -> None:
        if self.original_model == None:
            with open(self.model_file, 'rb') as fpcl:
                self.original_model = pickle.loads(fpcl.read())
        self.cons = self.original_model.constraints
        assert (len(self.cons)>0), f"{self.model_file} has no constraints"
        self.cons = toplevel_list(self.cons)
        self.sol_count = cp.Model(self.cons).solveAll(solver=self.solver,time_limit=max(1,min(250,self.time_limit)))
        self.mutators = [(copy.deepcopy(self.cons), self.seed)] #keep track of list of cons alternated with mutators that transformed it into the next list of cons.
        
    def verify_model(self) -> dict:
        try:
            model = cp.Model(self.cons)
            time_limit=max(1,min(200,self.time_limit)) # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1

            new_count = model.solveAll(solver=self.solver, time_limit=time_limit)

            if self.model_timed_out(model):
                # timeout
                return FuzzExit(
                            type=FuzzTestErrorType.timeout,
                            verifier=self,
                            exception="timeout",
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file
                        )
            elif self.sol_count == new_count:
                # has to be same
                return FuzzExit(
                            type=FuzzTestErrorType.ok,
                            verifier=self,
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file
                        )
            else:
                return FuzzExit(
                            type=FuzzTestErrorType.failed_model,
                            verifier=self,
                            exception=f"new solution count is not equal to original solution count, new solution count: {new_count}, original solution count: {self.sol_count}",
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model,
                            originalmodel_file=self.model_file
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
                            originalmodel_file=self.model_file
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
                            originalmodel_file=self.model_file
                        )
            return FuzzExit(
                        type=FuzzTestErrorType.internalcrash,
                        verifier=self,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        mutators=self.mutators,
                        model=model,
                        originalmodel=self.original_model,
                        originalmodel_file=self.model_file
                    )
        # if you got here, the model failed...
        return FuzzExit(
                    type=FuzzTestErrorType.failed_model,
                    verifier=self,
                    mutators=self.mutators,
                    model=model,
                    originalmodel=self.original_model,
                    originalmodel_file=self.model_file
                )

        

