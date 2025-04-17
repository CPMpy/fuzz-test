from verifiers import *

class Strengthening_Weakening_Verifier(Verifier):
    """
        The Solver Count Verifier will verify if the satisfiability is the same for all solvers after running multiple mutations
    """

    def __init__(self, solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int):
        self.name = "strengthening_weakening_verifier"
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

        assert len(self.solvers) == 2, f"2 solvers required, {len(self.solvers)} given."
        if 'gurobi' in [s.lower() for s in self.solvers]:
            self.sol_lim = 10000  # TODO: is hardcode best idea?

        # assert self.sol_count_1 == self.sol_count_2, f"{self.solvers} don't agree on amount of solutions (before mutations): {self.sol_count_1} and {self.sol_count_2}"

        self.mutators = [copy.deepcopy(
            self.cons)]  # keep track of list of cons alternated with mutators that transformed it into the next list of cons.

    def generate_mutations(self) -> None | dict:
        """
        Will generate random mutations based on mutations_per_model for the model
        """
        for i in range(self.mutations_per_model):

            # choose a mutator. 33% of the time, this will be a strengthening/weakening mutation.
            rand = random.random()
            if rand <= 0.33:
                m = strengthening_weakening_mutator
            elif rand <= 0.8633:  # ~~ remaining 80% of 0.67 (8/15)
                m = random.choice(self.mm_mutators)
            else:
                m = random.choice(self.gen_mutators)  # ~~ remaining 20% to choose gen-type mutator (2/15)

            self.mutators += [self.seed]
            # an error can occur in the transformations, so even before the solve call.
            # log function and arguments in that case
            self.mutators += [m]
            try:
                if m in self.gen_mutators:
                    self.cons = m(self.cons)  # apply a generative (non-metamorphic) mutation and REPLACE constraints
                elif m == strengthening_weakening_mutator:
                    model = cp.Model(self.cons)
                    solver_1 = self.solvers[0]
                    solver_2 = self.solvers[1]
                    if hasattr(self, 'sol_lim'):
                        count_1 = model.solveAll(solver=solver_1, solution_limit=self.sol_lim)
                    else:
                        count_1 = model.solveAll(solver=solver_1)
                    if count_1 > 1:
                        self.cons = m(self.cons, strengthen=True)
                    elif count_1 < 1:
                        self.cons = m(self.cons, strengthen=False)
                    elif random.random() < 0.8:  # If only 1 solution remains, we just go on normally instead
                        m = random.choice(self.mm_mutators)
                        self.cons += m(self.cons)
                    else:
                        m = random.choice(self.gen_mutators)
                        self.cons = m(self.cons)
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


    def verify_model(self, is_rerun=False) -> None | dict:
        try:
            model = cp.Model(self.cons)
            if is_rerun:
                print([(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in get_variables(self.cons)])
            time_limit = max(1, min(200,
                                    self.time_limit - time.time()))  # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1

            solver_1 = self.solvers[0]
            solver_2 = self.solvers[1]
            if hasattr(self, 'sol_lim'):
                new_count_1 = model.solveAll(solver=solver_1, solution_limit=self.sol_lim)
                new_count_2 = model.solveAll(solver=solver_2, solution_limit=self.sol_lim)
            else:
                new_count_1 = model.solveAll(solver=solver_1)
                new_count_2 = model.solveAll(solver=solver_2)

            if model.status().runtime > time_limit - 10:
                # timeout, skip
                print('T', end='', flush=True)
                return None
            elif new_count_1 == new_count_2:
                # has to be same
                print('.', end='', flush=True)
                return None
            else:
                print('X', end='', flush=True)
                return dict(type=Fuzz_Test_ErrorTypes.failed_model,
                            originalmodel_file=self.model_file,
                            exception=f"Amount of solutions of the two solvers are not equal."
                                      f" #Solutions of {solver_1}: {new_count_1}."
                                      f" #Solutions of {solver_2}: {new_count_2}.",
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

    def run(self, model_file: str) -> dict:
        """
        This function will run a single test on the given model
        """
        try:
            random.seed(self.seed)
            self.model_file = model_file
            self.initialize_run()
            gen_mutations_error = self.generate_mutations()

            # check if no error occurred while generation the mutations
            if gen_mutations_error == None:
                return self.verify_model()
            else:
                return gen_mutations_error
        except AssertionError as e:
            print("A", end='', flush=True)
            error_type = Fuzz_Test_ErrorTypes.crashed_model
            if "is not sat" in str(e):
                error_type = Fuzz_Test_ErrorTypes.unsat_model
            elif "has no constraints" in str(e):
                error_type = Fuzz_Test_ErrorTypes.no_constraints_model
            return dict(type=error_type,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        originalmodel=self.original_model
                        )

        except Exception as e:
            print('C', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.crashed_model,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        mutators=self.mutators,
                        originalmodel=self.original_model
                        )

    def rerun(self, error: dict) -> dict:
        """
        This function will rerun a previous failed test
        """
        try:
            random.seed(self.seed)
            self.model_file = error["originalmodel_file"]
            self.original_model = error["originalmodel"]
            self.exclude_dict = {}
            self.initialize_run(is_rerun=True)
            gen_mutations_error = self.generate_mutations()

            # check if no error occured while generation the mutations
            if gen_mutations_error == None:
                return self.verify_model(is_rerun=True)
            else:
                return gen_mutations_error

        except AssertionError as e:
            print("A", end='', flush=True)
            type = Fuzz_Test_ErrorTypes.crashed_model
            if "is not sat" in str(e):
                type = Fuzz_Test_ErrorTypes.unsat_model
            elif "has no constraints" in str(e):
                type = Fuzz_Test_ErrorTypes.no_constraints_model
            return dict(type=type,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        originalmodel=self.original_model
                        )

        except Exception as e:
            print('C', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.crashed_model,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        originalmodel=self.original_model
                        )