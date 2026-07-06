import sys
import os
import copy
import pickle
import argparse
import inspect
import traceback
import pytest
from datetime import datetime

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "A python application to generate models from the cpmpy tests")
    parser.add_argument("-c", "--cpmpy-dir", help = "The directory were cpmpy is located", required=True,type=str )
    parser.add_argument("-o", "--output-dir", help = "The directory to store the output (will be created if it does not exist).", required=False, type=str, default="solved_models")
    args = parser.parse_args()

    if os.path.exists(args.cpmpy_dir):
        print("cpmpy_dir found, running tests...")
        # Add CPMPY_DIR to sys.path so that we can import CPMpy
        sys.path.insert(0, os.path.abspath(args.cpmpy_dir))
        from cpmpy import Model
        from cpmpy import SolverLookup
        from cpmpy.solvers.ortools import CPM_ortools
        from cpmpy.solvers.gurobi import CPM_gurobi
        from cpmpy.solvers.minizinc import CPM_minizinc
        from cpmpy.solvers.z3 import CPM_z3
        from cpmpy.expressions.core import Expression
        from cpmpy.expressions.variables import _BoolVarImpl, _NumVarImpl, NegBoolView, NDVarArray
        from cpmpy.expressions.globalconstraints import DirectConstraint
        from cpmpy.transformations.get_variables import get_variables_model

        # Create a directory and subdirectorys to store the pickled results
        pickle_dir = args.output_dir
        os.makedirs(pickle_dir, exist_ok=True)

        pickle_dir = os.path.abspath(pickle_dir)
        date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
        pickle_dir = os.path.join(pickle_dir,"testsuite_"+date_text)
        os.makedirs(pickle_dir, exist_ok=True)
        os.makedirs(os.path.join(pickle_dir,"sat"), exist_ok=True)
        os.makedirs(os.path.join(pickle_dir,"unsat"), exist_ok=True)
        os.makedirs(os.path.join(pickle_dir,"optimization"), exist_ok=True)

        # renaming the variables of captured models avoids name clashes with the
        # variables that get created later, during fuzz testing (both use cpmpy's
        # "BV{n}"/"IV{n}" auto-names with counters restarting from 0 in a new process)
        def _rename_variables(model):
            for i, var in enumerate(get_variables_model(model)):
                if isinstance(var, _BoolVarImpl):
                    var.name = "BVV{}".format(i)
                else:
                    var.name = "IVV{}".format(i)

            # NegBoolView.name is frozen at construction time, refresh it
            seen = set()  # expressions are DAGs, don't revisit shared subexpressions
            def refresh(expr):
                if id(expr) in seen:
                    return
                seen.add(id(expr))
                if isinstance(expr, NegBoolView):
                    expr.name = "~{}".format(expr._bv.name)
                elif isinstance(expr, _NumVarImpl):
                    pass  # leaf variable (already renamed; has no .args)
                elif isinstance(expr, NDVarArray):
                    for sub in expr.flat:
                        refresh(sub)
                elif isinstance(expr, Expression):
                    for sub in expr.args:
                        refresh(sub)
                elif isinstance(expr, (list, tuple)):
                    for sub in expr:
                        refresh(sub)

            refresh(model.constraints)
            refresh(model.objective_)

        def capture_model(model, result):
            """Pickle a renamed copy of `model` into sat/unsat/optimization.
               Must never raise: a capture problem may not fail the test being run."""
            try:
                model = copy.deepcopy(model)
                _rename_variables(model)

                # Generate a unique file name based on the call stack and model content
                caller = inspect.stack()[2]
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # Generate a timestamp
                filename = f"{caller.function}_{caller.lineno}_{timestamp}.pickle"

                if model.objective_ is not None:
                    pickle_path = os.path.join(pickle_dir, "optimization", filename)
                elif result:
                    pickle_path = os.path.join(pickle_dir, "sat", filename)
                else:
                    pickle_path = os.path.join(pickle_dir, "unsat", filename)
                with open(pickle_path, 'wb') as f:
                    pickle.dump(model, f)
            except Exception:
                # pytest swallows stdout/stderr of passing tests, log to a file instead
                with open(os.path.join(pickle_dir, "capture_errors.log"), "a") as f:
                    f.write(traceback.format_exc() + "\n")

        # Monkey patch Model.solve to capture every solved Model
        original_solve = Model.solve
        model_solve_depth = 0  # depth counter: Model.solve() may be re-entered from callbacks
        def patched_solve(self, *args, **kwargs):
            global model_solve_depth
            model_solve_depth += 1
            try:
                result = original_solve(self, *args, **kwargs)
            finally:
                model_solve_depth -= 1
            capture_model(self, result)
            return result
        Model.solve = patched_solve

        # Also capture models built directly on a solver instance (e.g.
        # `SolverLookup.get(name, model)` or `s += cons; s.solve()`): mirror all
        # constraints/objectives into a shadow Model and pickle it after solve().
        # Note: solver classes alias `__add__ = add`, so both need rebinding.
        def instrument_solver(cls):
            original_add = cls.add
            original_objective = cls.objective
            original_solver_solve = cls.solve

            def shadow(self):
                if not hasattr(self, "_shadow_model"):
                    self._shadow_model = Model()
                return self._shadow_model

            def has_direct(cpm_expr):
                if isinstance(cpm_expr, DirectConstraint):
                    return True
                if isinstance(cpm_expr, (list, tuple)):
                    return any(has_direct(sub) for sub in cpm_expr)
                return False

            def strip_direct(cpm_expr):
                # DirectConstraints are solver-specific, useless cross-solver
                if isinstance(cpm_expr, DirectConstraint):
                    return None
                if isinstance(cpm_expr, (list, tuple)):
                    return [e for e in (strip_direct(sub) for sub in cpm_expr) if e is not None]
                return cpm_expr

            def patched_add(self, cpm_expr):
                result = original_add(self, cpm_expr)
                try:  # best effort: what a generic Model can't hold is not captured
                    mirror = cpm_expr
                    if has_direct(cpm_expr):
                        # stripping makes the shadow weaker than the real model,
                        # an unsat result would not carry over to it
                        self._shadow_incomplete = True
                        mirror = strip_direct(cpm_expr)
                    if mirror is not None and not (isinstance(mirror, list) and len(mirror) == 0):
                        shadow(self).add(mirror)
                except Exception:
                    self._shadow_incomplete = True
                return result

            def patched_objective(self, expr, minimize):
                result = original_objective(self, expr, minimize)
                try:  # best effort: e.g. Model() rejects float objectives some solvers accept
                    if minimize:
                        shadow(self).minimize(expr)
                    else:
                        shadow(self).maximize(expr)
                except Exception:
                    pass
                return result

            def patched_solver_solve(self, *args, **kwargs):
                result = original_solver_solve(self, *args, **kwargs)
                # skip when called from Model.solve(): that model is captured already
                if model_solve_depth == 0 and hasattr(self, "_shadow_model"):
                    m = self._shadow_model
                    # an incomplete shadow (constraints that could not be mirrored)
                    # is only valid when sat: sat carries over to a subset, unsat does not
                    valid = result or not getattr(self, "_shadow_incomplete", False)
                    if valid and (len(m.constraints) > 0 or m.objective_ is not None):
                        capture_model(m, result)
                return result

            cls.add = patched_add
            cls.__add__ = patched_add
            cls.objective = patched_objective
            cls.solve = patched_solver_solve

        for solver_cls in (CPM_ortools, CPM_gurobi, CPM_minizinc, CPM_z3):
            instrument_solver(solver_cls)

        # monkey patch SolverLookup.base_solvers() to only return ortools so we don't run the tests with all solvers.
        def patched_base_solvers():
            return [('ortools', CPM_ortools)]

        original_lookup = SolverLookup.base_solvers
        SolverLookup.base_solvers = patched_base_solvers

        test_dir = os.path.join(args.cpmpy_dir, "tests")
        try:
            pytest.main(["-v", f"{test_dir}/test_constraints.py"])
        finally:
            SolverLookup.base_solvers = original_lookup
        pytest.main(["-v", f"{test_dir}", f"--ignore={test_dir}/test_constraints.py"])

        print(f"succesfully executed tests and stored generated models in {pickle_dir}")
    else:
        print("cpmpy_dir was not found")
