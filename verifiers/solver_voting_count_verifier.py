from verifiers import *

class Solver_Vote_Count_Verifier(Verifier):
    """
        The Solver Count Verifier will verify if the amount of solutions is the same for all solvers after running multiple mutations
    """

    def __init__(self, solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int, mm_prob: float):
        self.name = "solver_vote_count_verifier"
        self.type = 'sat'

        self.solvers = solver

        self.mutations_per_model = mutations_per_model
        self.exclude_dict = exclude_dict
        self.time_limit = time_limit
        self.seed = random.Random().random()
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
        self.nr_solve_checks = 0
        self.bug_cause = 'STARTMODEL'
        self.nr_timed_out = 0
        self.last_mut = None
        self.mm_prob = mm_prob

    def initialize_run(self) -> None:
        if self.original_model == None:
            with open(self.model_file, 'rb') as fpcl:
                self.original_model = pickle.loads(fpcl.read())
        self.cons = self.original_model.constraints
        assert (len(self.cons) > 0), f"{self.model_file} has no constraints"
        self.cons = toplevel_list(self.cons)
        assert len(self.solvers) > 1, f"More than 1 solver required, given solvers: {self.solvers}."
        if 'gurobi' in [s.lower() for s in self.solvers]:  # Because gurobi can't run solveAll without solution_limit
            self.sol_lim = 10000  # TODO: is hardcode best idea?

        # Optional: Check before applying the mutations. This should never fail...

        self.mutators = [copy.deepcopy(
            self.cons)]  # keep track of list of cons alternated with mutators that transformed it into the next list of cons.

    def generate_mutations(self) -> None | dict:
        """
        Will generate random mutations based on mutations_per_model for the model
        """
        for i in range(self.mutations_per_model):
            # choose a mutation (not in exclude_dict)
            valid_mutators = list(set(self.mm_mutators).union(set(self.gen_mutators)) - set(
                self.exclude_dict[self.model_file])) if self.model_file in self.exclude_dict else list(
                set(self.mm_mutators).union(set(self.gen_mutators)))
            if random.random() <= self.mm_prob:  # mm_prob probability to choose metamorphic mutation
                mutator_list = self.mm_mutators
            else:  # 1-mm_prob to choose generation-based mutation
                mutator_list = self.gen_mutators

            valid = [m for m in mutator_list if m in valid_mutators]
            if valid:
                m = random.choice(valid)
            else:
                continue

            self.mutators += [self.seed]
            # an error can occur in the transformations, so even before the solve call.
            # log function and arguments in that case
            self.mutators += [m]
            try:
                if m in self.gen_mutators:
                    self.bug_cause = 'during GEN'
                    self.cons = m(self.cons)  # apply a generative mutation and REPLACE constraints
                    self.bug_cause = 'GEN'
                else:
                    self.bug_cause = 'during MM'
                    self.cons += m(self.cons)  # apply a metamorphic mutation and add to constraints
                    self.bug_cause = 'MM'
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

                return dict(seed=self.seed,
                            mm_prob=self.mm_prob,
                            type=Fuzz_Test_ErrorTypes.internalfunctioncrash,
                            originalmodel_file=self.model_file,
                            exception=e,
                            function=function,
                            argument=argument,
                            stacktrace=traceback.format_exc(),
                            mutators=self.mutators,
                            constraints=self.cons,
                            variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                               get_variables(self.cons)],
                            originalmodel=self.original_model,
                            nr_solve_checks=self.nr_solve_checks,
                            caused_by=self.bug_cause,
                            nr_timed_out=self.nr_timed_out
                            )
        return None
    def verify_model(self, is_bug_check=False) -> None | dict:
        try:
            model = cp.Model(self.cons)

            # if is_bug_check:
            #     max_search_time = 20
            # else:
            #     max_search_time = 40
            max_search_time = 40

            time_limit = max(1, min(max_search_time,  # TODO: change `max_search_time` back to 200
                                    self.time_limit - time.time()))  # set the max time limit to the given time limit or to 1 if the self.time_limit-time.time() would be smaller then 1

            # Get the actual solver results and their execution times.
            # We do it this way because a solver might crash, meaning the other solver doesn't get a turn.
            solvers_results = []
            solvers_times = []
            for s in self.solvers:
                self.nr_solve_checks += 1
                if hasattr(self, 'sol_lim'):
                    solvers_results.append(model.solveAll(solver=s, solution_limit=self.sol_lim, time_limit=time_limit))
                    solvers_times.append(model.status().runtime)
                else:
                    solvers_results.append(model.solveAll(solver=s, time_limit=time_limit))
                    solvers_times.append(model.status().runtime)

            nr_timed_out_solvers = sum([t > time_limit * 0.8 for t in solvers_times])
            if nr_timed_out_solvers > 0:
                # timeout, skip
                self.bug_cause = 'UNKNOWN'
                self.nr_timed_out += nr_timed_out_solvers
                if not is_bug_check:
                    print('T', end='', flush=True)
                return None
            elif all(s1 == s2 for i, s1 in enumerate(solvers_results) for j, s2 in enumerate(solvers_results) if i < j):
                # has to be same
                if not is_bug_check:
                    print('.', end='', flush=True)
                return None
            else:
                solver_results_str = ", ".join(
                    f"{solver}: {result}" for solver, result in zip(self.solvers, solvers_results))
                if is_bug_check:
                    print('X', end='', flush=True)
                return dict(seed=self.seed,
                            mm_prob=self.mm_prob,
                            type=Fuzz_Test_ErrorTypes.failed_model,
                            originalmodel_file=self.model_file,
                            exception=f"Results of the solvers are not equal. Solver results: {solver_results_str}.",
                            constraints=self.cons,
                            mutators=self.mutators,
                            model=model,
                            variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                               get_variables(self.cons)],
                            originalmodel=self.original_model,
                            nr_solve_checks=self.nr_solve_checks,
                            caused_by=self.bug_cause,
                            nr_timed_out=self.nr_timed_out
                            )

        except Exception as e:
            if isinstance(e, (CPMpyException, NotImplementedError)):
                # expected error message, ignore
                return None
            if is_bug_check:
                print('E', end='', flush=True)

            return dict(seed=self.seed,
                        mm_prob=self.mm_prob,
                        type=Fuzz_Test_ErrorTypes.internalcrash,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        mutators=self.mutators,
                        model=model,
                        variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                               get_variables(self.cons)],
                        originalmodel=self.original_model,
                        nr_solve_checks=self.nr_solve_checks,
                        caused_by=self.bug_cause,
                        nr_timed_out=self.nr_timed_out
                        )

    def run(self, model_file: str) -> dict | None:
        """
        This function will run a single tests on the given model
        """
        try:
            random.seed(self.seed)
            self.model_file = model_file
            self.initialize_run()
            gen_mutations_error = self.generate_mutations()

            # check if no error occured while generation the mutations
            if gen_mutations_error == None:
                # FOLLOWING 5 LINES CHANGED!
                verify_model_error = self.verify_model()
                if verify_model_error == None:
                    return None
                else:
                    return self.find_error_rerun(verify_model_error)
            else:
                return self.find_error_rerun(gen_mutations_error)
        except AssertionError as e:
            print("A", end='', flush=True)
            error_type = Fuzz_Test_ErrorTypes.crashed_model
            if "is not sat" in str(e):
                error_type = Fuzz_Test_ErrorTypes.unsat_model
            elif "has no constraints" in str(e):
                error_type = Fuzz_Test_ErrorTypes.no_constraints_model
            return dict(seed=self.seed,
                        mm_prob=self.mm_prob,
                        type=error_type,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                                   get_variables(self.cons)],
                        originalmodel=self.original_model,
                        nr_solve_checks=self.nr_solve_checks,
                        caused_by=self.bug_cause,
                        nr_timed_out=self.nr_timed_out
                        )

        except Exception as e:
            print('C', end='', flush=True)
            return dict(seed=self.seed,
                        mm_prob=self.mm_prob,
                        type=Fuzz_Test_ErrorTypes.crashed_model,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                                   get_variables(self.cons)],
                        mutators=self.mutators,
                        originalmodel=self.original_model,
                        nr_solve_checks=self.nr_solve_checks,
                        caused_by=self.bug_cause,
                        nr_timed_out=self.nr_timed_out
                        )

    def find_error_rerun(self, error_dict) -> dict:
        try:
            random.seed(self.seed)
            error_type = error_dict['type']
            self.initialize_run()  # initialize empty (self.)model, cons, mutators

            # This should always be the case
            if error_type in [Fuzz_Test_ErrorTypes.internalcrash, Fuzz_Test_ErrorTypes.failed_model]:  # Error type 'E', often during model.solve() or solveAll or type 'X'
                return self.bug_search_run_and_verify_model()
            elif error_type == Fuzz_Test_ErrorTypes.internalfunctioncrash:
                mutations = error_dict['mutators'][2::3]
                return self.bug_search_run_and_verify_model(nr_mutations=len(mutations))

        except AssertionError as e:
            print("A", end='', flush=True)
            type = Fuzz_Test_ErrorTypes.crashed_model
            if "is not sat" in str(e):
                type = Fuzz_Test_ErrorTypes.unsat_model
            elif "has no constraints" in str(e):
                type = Fuzz_Test_ErrorTypes.no_constraints_model
            return dict(seed=self.seed,
                        mm_prob=self.mm_prob,
                        type=type,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                                   get_variables(self.cons)],
                        originalmodel=self.original_model,
                        nr_solve_checks=self.nr_solve_checks,
                        caused_by=self.bug_cause,
                        nr_timed_out=self.nr_timed_out
                        )

        except Exception as e:
            print('C', end='', flush=True)
            return dict(seed=self.seed,
                        mm_prob=self.mm_prob,
                        type=Fuzz_Test_ErrorTypes.crashed_model,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                                   get_variables(self.cons)],
                        originalmodel=self.original_model,
                        nr_solve_checks=self.nr_solve_checks,
                        caused_by=self.bug_cause,
                        nr_timed_out=self.nr_timed_out
                        )

    def bug_search_run_and_verify_model(self, nr_mutations=None) -> dict:
        if nr_mutations is not None:
            self.mutations_per_model = nr_mutations
        for _ in range(self.mutations_per_model):
            last_bug_cause = self.bug_cause

            # Generate the type of mutation that will happen
            valid_mutators = list(set(self.mm_mutators).union(set(self.gen_mutators)) - set(
                self.exclude_dict[self.model_file])) if self.model_file in self.exclude_dict else list(
                set(self.mm_mutators).union(set(self.gen_mutators)))
            if random.random() <= self.mm_prob:  # mm_prob probability to choose metamorphic mutation
                mutator_list = self.mm_mutators
                new_mut_type = 'MM'
            else:  # 1-mm_prob to choose generation-based mutation
                mutator_list = self.gen_mutators
                new_mut_type = 'GEN'

            valid = [m for m in mutator_list if m in valid_mutators]
            if valid:
                m = random.choice(valid)
            else:
                continue

            # Check whether verify_model returns an error before the new mutation, because the cause is then at the old mutation
            if new_mut_type != last_bug_cause:
                verify_model_error = self.verify_model(is_bug_check=True)
                if verify_model_error is not None:
                    return verify_model_error

            # Then, apply the new mutation and check whether it gives an error
            gen_mut_error = self.apply_single_mutation(m)
            if gen_mut_error is not None:
                return gen_mut_error

        # Finally, check the model at the end. This SHOULD give an error
        verify_model_error = self.verify_model(is_bug_check=True)
        if verify_model_error is not None:
            return verify_model_error
        else:
            print('_', end='', flush=True)

    def apply_single_mutation(self, m) -> dict | None:
        """
        Will generate one random mutation and apply it to the model
        """
        self.mutators += [self.seed]
        # an error can occur in the transformations, so even before the solve call.
        # log function and arguments in that case
        self.mutators += [m]
        try:
            if m in self.gen_mutators:
                self.bug_cause = f'during GEN, after {self.bug_cause}'
                self.cons = m(self.cons)  # apply a generative mutation and REPLACE constraints
                self.bug_cause = 'GEN'
            else:
                self.bug_cause = f'during MM, after {self.bug_cause}'
                self.cons += m(self.cons)  # apply a metamorphic mutation and add to constraints
                self.bug_cause = 'MM'
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
            return dict(seed=self.seed,
                        mm_prob=self.mm_prob,
                        type=Fuzz_Test_ErrorTypes.internalfunctioncrash,
                        originalmodel_file=self.model_file,
                        exception=e,
                        function=function,
                        argument=argument,
                        stacktrace=traceback.format_exc(),
                        mutators=self.mutators,
                        constraints=self.cons,
                        variables=[(var, var.lb, var.ub) if not is_boolexpr(var) else (var, "bool") for var in
                                   get_variables(self.cons)],
                        originalmodel=self.original_model,
                        nr_solve_checks=self.nr_solve_checks,
                        caused_by=self.bug_cause,
                        nr_timed_out=self.nr_timed_out
                        )
        return None