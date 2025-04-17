from verifiers import *

class Solver_Vote_Sat_Verifier(Verifier):
    """
        The Solver Count Verifier will verify if the satisfiability is the same for all solvers after running multiple mutations
    """

    def __init__(self, solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        self.name = "solver_vote_sat_verifier"
        self.type = 'sat'

        self.solvers = solver

        self.mutations_per_model = mutations_per_model
        self.exclude_dict = exclude_dict
        self.time_limit = time_limit
        self.seed = seed
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
                            semanticFusionCountingwsum,
                            semanticFusionCounting,
                            semanticFusionCountingMinus,
                            semanticFusionCountingwsum]
        self.gen_mutators = [type_aware_operator_replacement, type_aware_expression_replacement]
        self.mutators = []
        self.original_model = None

    def initialize_run(self, is_rerun=False) -> None:
        if self.original_model == None:
            with open(self.model_file, 'rb') as fpcl:
                self.original_model = pickle.loads(fpcl.read())
        self.cons = self.original_model.constraints
        assert (len(self.cons) > 0), f"{self.model_file} has no constraints"
        self.cons = toplevel_list(self.cons)
        if is_rerun:
            print([(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in get_variables(self.cons)])

        # No other preparation necessary

        self.mutators = [copy.deepcopy(
            self.cons)]  # keep track of list of cons alternated with mutators that transformed it into the next list of cons.

    def generate_mutations(self) -> None:
        """
        Will generate random mutations based on mutations_per_model for the model
        """
        for i in range(self.mutations_per_model):

            # choose a mutation
            if random.random() < 0.8:
                m = random.choice(self.mm_mutators)
            else:
                m = random.choice(self.gen_mutators)  # 20% chance to choose gen-type mutator

            self.mutators += [self.seed]
            # an error can occur in the transformations, so even before the solve call.
            # log function and arguments in that case
            self.mutators += [m]
            try:
                if m in self.gen_mutators:
                    self.cons = m(self.cons)  # apply a generative mutation and REPLACE constraints
                else:
                    self.cons += m(self.cons)  # apply a metamorphic mutation and add to constraints
                self.mutators += [copy.deepcopy(self.cons)]
            except MetamorphicError as exc:
                # add to exclude_dict, to avoid running into the same error
                if self.model_file in self.exclude_dict:
                    self.exclude_dict[self.model_file] += [m]
                else:
                    self.exclude_dict[self.model_file] = [m]
                function, argument, e = exc.args
                if isinstance(e, CPMpyException):
                    # expected behavior if we throw a cpmpy exception, do not log
                    return None
                elif function == semanticFusion:
                    return None
                    # don't log semanticfusion crash

                print('I', end='', flush=True)
                return dict(type=Fuzz_Test_ErrorTypes.internalfunctioncrash,
                            originalmodel_file=self.model_file,
                            exception=e,
                            function=function,
                            argument=argument,
                            stacktrace=traceback.format_exc(),
                            mutators=self.mutators,
                            constraints=self.cons,
                            originalmodel=self.original_model
                            )
        return None

    def verify_model(self, is_rerun=False) -> dict:
        try:
            model = cp.Model(self.cons)
            time_limit = max(1, min(200,
                                    self.time_limit - time.time()))  # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1

            # choosing the solvers
            solver_1 = self.solvers[0]
            solver_2 = self.solvers[1]
            solver_1_is_sat = model.solve(solver=solver_1, time_limit=time_limit)
            solver_2_is_sat = model.solve(solver=solver_2, time_limit=time_limit)
            # for prettier exception printing
            solver_1_print = "sat" if solver_1_is_sat else "unsat"
            solver_2_print = "sat" if solver_2_is_sat else "unsat"

            if model.status().runtime > time_limit - 10:
                # timeout, skip
                print('T', end='', flush=True)
                return None
            elif solver_1_is_sat == solver_2_is_sat:
                # has to be same
                print('.', end='', flush=True)
                return None
            else:
                print('X', end='', flush=True)
                return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                            originalmodel_file=self.model_file,
                            exception=f"Results of the two solvers are not equal."
                                      f" Result of {solver_1}: {solver_1_print}."
                                      f" Result of {solver_2}: {solver_2_print}.",
                            constraints=self.cons,
                            mutators=self.mutators,
                            model=model,
                            originalmodel=self.original_model
                            )

        except Exception as e:
            if isinstance(e, (CPMpyException, NotImplementedError)):
                # expected error message, ignore
                return None
            print('E', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.internalcrash,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        mutators=self.mutators,
                        model=model,
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
