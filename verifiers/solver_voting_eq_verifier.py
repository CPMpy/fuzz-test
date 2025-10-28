from verifiers import *
from verifiers.solver_voting_verifier import Solver_Voting_Verifier


class Solver_Vote_Eq_Verifier(Solver_Voting_Verifier):
    """
        The Solver Equivalence Verifier will verify if the solutions are the same for all solvers after running multiple mutations
    """

    def __init__(self, solver: str, mutations_per_model: int, exclude_dict: dict, time_limit: float, seed: int, mm_prob: float):
        self.name = "solver_vote_eq_verifier"
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
            self.sol_lim = 10000  # Should this be hardcoded?

        self.original_vars = get_variables(self.cons)  # New auxiliary variables will be added so we need to do this here

        self.mutators = [copy.deepcopy(
            self.cons)]  # keep track of list of cons alternated with mutators that transformed it into the next list of cons.


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
            all_sols = [set() for i, s in enumerate(self.solvers)]
            solvers_times = []
            for i, s in enumerate(self.solvers):
                self.nr_solve_checks += 1
                if hasattr(self, 'sol_lim'):
                    res = model.solveAll(solver=s, time_limit=time_limit, display=lambda: all_sols[i].add(
                                tuple([v.value() for v in self.original_vars])), solution_limit=self.sol_lim)
                    solvers_times.append(model.status().runtime)
                else:
                    model.solveAll(solver=s, time_limit=time_limit, display=lambda: all_sols[i].add(
                        tuple([v.value() for v in self.original_vars])))
                    solvers_times.append(model.status().runtime)

            nr_timed_out_solvers = sum([t > time_limit * 0.8 for t in solvers_times])
            if nr_timed_out_solvers > 0:
                # timeout, skip
                self.bug_cause = 'UNKNOWN'
                self.nr_timed_out += nr_timed_out_solvers
                if not is_bug_check:
                    print('T', end='', flush=True)
                return None
            elif all(len(s1.symmetric_difference(s2)) == 0 for i, s1 in enumerate(all_sols) for j, s2 in enumerate(all_sols) if i < j) or (hasattr(self, 'sol_lim') and res == self.sol_lim):
                # has to be same
                if not is_bug_check:
                    print('.', end='', flush=True)
                return None
            else:
                solver_results_str = ""
                from itertools import combinations
                for (i, s1), (j, s2) in combinations(enumerate(all_sols), 2):
                    if len(solver_results_str) > 0:
                        solver_results_str += "\n"
                    solver_name_1 = self.solvers[i]
                    solver_name_2 = self.solvers[j]
                    diff = s1.symmetric_difference(s2)
                    solver_results_str += f"{solver_name_1} vs {solver_name_2}: {len(diff)} differences"
                if is_bug_check:
                    print('X', end='', flush=True)
                return dict(seed=self.seed,
                            mm_prob=self.mm_prob,
                            type=Fuzz_Test_ErrorTypes.failed_model,
                            originalmodel_file=self.model_file,
                            exception=f"Results of the solvers are not equal. Solver results: {solver_results_str}",
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
