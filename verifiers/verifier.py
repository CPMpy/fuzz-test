import random
import copy
import logging
from typing import List, Tuple, Union
from contextlib import contextmanager

import numpy as np
import cpmpy as cp
from cpmpy.solvers.solver_interface import ExitStatus

from fuzz_test_utils.fuzz_test_errors import FuzzTestErrorType
from verifiers import *
from verifiers.utils import FuzzExit, MutationExit, VerifierExit, InitializeExit, Exit

# Set up logger for mutation replay debugging
logger = logging.getLogger('mutation_replay')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler('mutation_replay_debug.log')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

@contextmanager
def temporary_random_seed(seed):
    """
    Temporarily change the random seed within this context.
    Restore the original seed afterwards.
    """
    original_state = copy.deepcopy(random.getstate())
    original_np_state = copy.deepcopy(np.random.get_state())
    random.seed(seed)
    np.random.seed(seed)
    try:
        yield
    finally:
        random.setstate(original_state)
        np.random.set_state(original_np_state)


def apply_mutator(verifier, m):
    self = verifier
    try:
        self.cons += m(self.cons)  # apply a metamorphic mutation
        #self.mutators += [copy.deepcopy(self.cons)]
        return MutationExit(
                    type=FuzzTestErrorType.ok,
                    verifier=self,
                    mutators=self.mutators,
                    originalmodel=self.original_model,
                    originalmodel_file=self.model_file
                )
    except MetamorphicError as exc:
        #add to exclude_dict, to avoid running into the same error
        if self.model_file in self.exclude_dict:
            self.exclude_dict[self.model_file] += [m]
        else:
            self.exclude_dict[self.model_file] = [m]
        function, argument, e = exc.args
        if isinstance(e,CPMpyException):
            #expected behavior if we throw a cpmpy exception, do not log
            # expected error message
            return MutationExit(
                        type=FuzzTestErrorType.expected_error,
                        verifier=self,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        function=function,
                        argument=argument,
                        mutators=self.mutators,
                        originalmodel=self.original_model,
                        originalmodel_file=self.model_file
                    )
        elif function == semanticFusion:
            # expected error message
            return MutationExit(
                        type=FuzzTestErrorType.expected_error,
                        verifier=self,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        function=function,
                        argument=argument,
                        mutators=self.mutators,
                        originalmodel=self.original_model,
                        originalmodel_file=self.model_file
                    )
            #don't log semanticfusion crash
            
        return MutationExit(
                    type=FuzzTestErrorType.internalfunctioncrash,
                    verifier=self,
                    exception=e,
                    stacktrace=traceback.format_exc(),
                    function=function,
                    argument=argument,
                    mutators=self.mutators,
                    originalmodel=self.original_model,
                    originalmodel_file=self.model_file
                )

class Verifier():
    """
    The base class containing the base functions for each verifier.
    """

    def __init__(self, name: str, type: str, solver: str, mutations_per_model: int, exclude_dict: dict , time_limit: float, seed: int):
        self.name = name
        self.type = type
        self.solver = solver
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
                        to_cnf_morph,
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
        self.mutators = []
        self.original_model = None

    @staticmethod
    def semantic_fusion_allowed(cons):
        return cons == cp.transformations.safening.no_partial_functions(cons, safen_toplevel={"element", "div", "mod"})

    def apply_mutations(self, mutators:List[Tuple[callable, int]]):

        # Apply each mutation one by one
        for mutator, seed in mutators:
            with temporary_random_seed(seed):
                gen_mutations_error = apply_mutator(self, mutator)

            # If mutation fails, early exit
            if gen_mutations_error.type != FuzzTestErrorType.ok:
                return gen_mutations_error
            
        # All mutations applied successfully
        return MutationExit(
                type=FuzzTestErrorType.ok,
                verifier=self,
                mutators=mutators,
                originalmodel=self.original_model,
                originalmodel_file=self.model_file
            )

    
    def generate_mutations(self) -> List[Tuple[callable, int]]:
        """
        Will generate random mutations based on mutations_per_model for the model
        """

        mutators = [] # To collect randomly selected mutators

        for _ in range(self.mutations_per_model):
            # choose a metamorphic mutation, don't choose any from exclude_dict
            if self.model_file in self.exclude_dict:
                valid_mutators = list(set(self.mm_mutators) - set(self.exclude_dict[self.model_file]))  
            else:
                valid_mutators = self.mm_mutators

            if not self.semantic_fusion_allowed(self.cons):
                valid_mutators = set(valid_mutators)
                valid_mutators -= set([
                        semanticFusionCounting,
                        semanticFusionCountingMinus,
                        semanticFusionCountingwsum,
                        semanticFusion,
                        semanticFusionCountingMinus,
                        semanticFusionwsum
                    ])
                valid_mutators = list(valid_mutators)
                
            mutator = random.choice(valid_mutators) # random mutator
            mutator_seed = random.Random().randint(0, 2**32 - 1)   # random seed to run the mutator with
            mutators += [(mutator, mutator_seed)]

        return mutators
    
    def load_mutations(self, mutators: List, is_internal_crash=False):
        # Re-apply the exact same mutators in the exact same sequence
        # The mutators list contains: [initial_state, seed, function, state_after_function, seed, function, ...]
        # IMPORTANT: Do NOT set random seeds here - the rerun() method already wraps this in temporary_random_seed()

        # For internalfunctioncrash, don't use stored states since they're incomplete/corrupted
        if not is_internal_crash:
            # CRITICAL: Start from the exact same initial state as the original run
            # The first item in mutators is the processed constraint state after initialize_run()
            if len(mutators) > 0 and isinstance(mutators[0], list):
                self.cons = copy.deepcopy(mutators[0])
                logger.debug(f"Starting with initial state: {len(self.cons)} constraints")

        # Reset mutators list to track the replay
        self.mutators = [copy.deepcopy(self.cons)]

        # Process mutators in groups
        i = 0
        while i < len(mutators):
            item = mutators[i]

            if is_internal_crash:
                # For internalfunctioncrash, only look for seed -> function pairs (ignore stored states)
                if isinstance(item, int) and i + 1 < len(mutators):
                    next_item = mutators[i + 1]
                    if hasattr(next_item, "__name__"):
                        # Found seed -> function pair
                        seed = item
                        function = next_item

                        logger.debug(f"Applying mutator {function.__name__} (seed was {seed}) [internal crash replay]")

                        # Store the seed in mutators list (to match original pattern)
                        self.mutators += [seed]
                        self.mutators += [function]

                        # Apply the mutator function - random state is already set by temporary_random_seed()
                        gen_mutations_error = apply_mutator(self, function)
                        if gen_mutations_error.type != FuzzTestErrorType.ok:
                            return gen_mutations_error

                        i += 2  # Skip seed and function
                        continue
            else:
                # For normal replays, look for seed -> function -> state triples
                if isinstance(item, int) and i + 2 < len(mutators):
                    next_item = mutators[i + 1]
                    state_item = mutators[i + 2]
                    if hasattr(next_item, "__name__") and isinstance(state_item, list):
                        # Found seed -> function -> state triple
                        seed = item
                        function = next_item
                        expected_state = state_item

                        logger.debug(f"Applying mutator {function.__name__} (seed was {seed})")

                        # Store the seed in mutators list (to match original pattern)
                        self.mutators += [seed]
                        self.mutators += [function]

                        # Apply the mutator function - random state is already set by temporary_random_seed()
                        gen_mutations_error = apply_mutator(self, function)
                        if gen_mutations_error.type != FuzzTestErrorType.ok:
                            return gen_mutations_error

                        # Verify the result matches expected state and log any differences
                        current_constraints = [str(c) for c in self.cons]
                        expected_constraints = [str(c) for c in expected_state]

                        if current_constraints != expected_constraints:
                            logger.warning(f"Mutation {function.__name__} produced different result - non-deterministic behavior detected")
                            logger.debug(f"Expected: {len(expected_constraints)} constraints")
                            logger.debug(f"Got: {len(current_constraints)} constraints")
                            logger.debug(f"First few expected: {expected_constraints[:3]}")
                            logger.debug(f"First few got: {current_constraints[:3]}")
                            # Don't fall back - let the different result proceed to catch non-determinism

                        i += 3  # Skip seed, function, and state
                        continue

            # Skip non-matching items
            i += 1

        # Verification: Check if the replayed mutations produced the same final model
        # Get the final constraint state from original mutators (last constraint list)
        original_final_state = None
        for item in reversed(mutators):
            if isinstance(item, list) and len(item) > len(self.original_model.constraints):
                original_final_state = item
                break

        if original_final_state is not None:
            # Compare current constraint state with original final state
            current_constraints = [str(c) for c in self.cons]
            original_constraints = [str(c) for c in original_final_state]

            if current_constraints != original_constraints:
                logger.warning("Mutation replay mismatch!")
                logger.warning(f"Original final constraints: {len(original_constraints)}")
                logger.warning(f"Replayed final constraints: {len(current_constraints)}")
                logger.warning(f"First 3 original: {original_constraints[:3]}")
                logger.warning(f"First 3 replayed: {current_constraints[:3]}")

                # Create a special error to indicate replay failure
                return MutationExit(
                    type=FuzzTestErrorType.fuzz_test_crash,  # Mark as crash to indicate replay issue
                    verifier=self,
                    mutators=self.mutators,
                    originalmodel=self.original_model,
                    originalmodel_file=self.model_file
                )

        return MutationExit(
                type=FuzzTestErrorType.ok,
                verifier=self,
                mutators=self.mutators,  # Use the new mutators list from replay
                originalmodel=self.original_model,
                originalmodel_file=self.model_file
            )

    def initialize_run(self) -> None:
        """
        Abstract function that gets executed before generating the mutation,
        This function is ued for getting the right data from the model.
        Each verifier needs to implement this function
        """
        raise NotImplementedError(f"method 'initialize_run' is not implemented for class {type(self)}")

    def verify_model(self) -> dict:
        """
        Abstract function that will solve the newly created model with the mutations.
        It will check if the test succeeded or not.
        Each verifier needs to implement this function
        """
        raise NotImplementedError(f"method 'verify_model' is not implemented for class {type(self)}")


    def run(self, model_file: str) -> Union[FuzzExit, MutationExit]:
        """
        This function will run a single tests on the given model
        """
        try:
            with temporary_random_seed(self.seed):
                self.model_file = model_file
                self.initialize_run()

                assert (len(self.cons) > 0), f"{model_file} has no constraints"

                # make a random selection of mutators
                mutators = self.generate_mutations()
                self.mutators += mutators

                # apply mutators
                gen_mutations_error = self.apply_mutations(mutators)

                # check if no error occured while applying the mutations
                if gen_mutations_error.type == FuzzTestErrorType.ok:
                    return self.verify_model() # mutations succeeded, continue with verifier
                else:
                    return gen_mutations_error # mutations failed (encountered bug when creating model?)
        
        except AssertionError as e:
            error_type = FuzzTestErrorType.crashed_model
            if "is not sat" in str(e):
                error_type = FuzzTestErrorType.unsat_model
            elif "has no constraints" in str(e):
                error_type = FuzzTestErrorType.no_constraints_model

            return InitializeExit(
                        type=error_type,
                        verifier=self,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        originalmodel=self.original_model,
                        originalmodel_file=self.model_file,
                        alternative_label="A"
                    )   
        

    def rerun(self, error: Exit) -> dict:
        """
        This function will rerun a previous failed test
        """
        try:
            with temporary_random_seed(self.seed):
                self.model_file = error.originalmodel_file
                self.original_model = error.originalmodel

                # Restore the exclude_dict from the original run to ensure same mutator choices
                self.exclude_dict = error.verifier_kwargs.get('exclude_dict', {})

                # Reset CPMPy global counters BEFORE initialize_run() to match original sequence
                import cpmpy as cp
                from importlib import reload
                reload(cp)

                self.initialize_run()

                # Pass flag to indicate if this is an internalfunctioncrash
                is_internal_crash = (error.type == FuzzTestErrorType.internalfunctioncrash)

                # Apply mutators (same selection with same seeds as original run)
                gen_mutations_error = self.apply_mutations(error.mutators[1:])
                # gen_mutations_error = self.load_mutations(error.mutators, is_internal_crash)

                # check if no error occured while generation the mutations
                if gen_mutations_error.type == FuzzTestErrorType.ok:
                    return self.verify_model()
                else:
                    return gen_mutations_error

        except AssertionError as e:
            type = FuzzTestErrorType.crashed_model
            if "is not sat" in str(e):
                type = FuzzTestErrorType.unsat_model
            elif "has no constraints" in str(e):
                type = FuzzTestErrorType.no_constraints_model

            return InitializeExit(
                        type=type,
                        verifier=self,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        #constraints=self.cons,
                        originalmodel=self.original_model
                    )

    def rerun_selective(self, error: Exit, selected_indices: List[int]) -> dict:
        """
        This function will rerun a previous failed test with only a subset of mutators
        TODO: very experimental
        """
        try:
            with temporary_random_seed(self.seed):
                self.model_file = error.originalmodel_file
                self.original_model = error.originalmodel

                # Restore the exclude_dict from the original run to ensure same mutator choices
                self.exclude_dict = error.verifier_kwargs.get('exclude_dict', {})

                # Reset CPMPy global counters BEFORE initialize_run() to match original sequence
                import cpmpy as cp
                from importlib import reload
                reload(cp)

                self.initialize_run()

                # Handle the "none" case (empty list) - apply no mutators
                if len(selected_indices) == 0:
                    print("Running with no mutations (--mutator-indices=none)")
                    return self.verify_model()

                # Filter mutators to only selected indices
                original_mutators = error.mutators[1:]  # Skip the first element (initial state)
                if not original_mutators:
                    # No mutators to apply
                    return self.verify_model()

                selected_mutators = []
                for i in selected_indices:
                    if 0 <= i < len(original_mutators):
                        selected_mutators.append(original_mutators[i])
                    else:
                        print(f"Warning: Mutator index {i} is out of range (0-{len(original_mutators)-1}), skipping")

                if not selected_mutators:
                    print("Warning: No valid mutator indices provided, running with no mutations")
                    return self.verify_model()

                # Apply only selected mutators
                gen_mutations_error = self.apply_mutations(selected_mutators)

                # check if no error occured while generation the mutations
                if gen_mutations_error.type == FuzzTestErrorType.ok:
                    return self.verify_model()
                else:
                    return gen_mutations_error

        except AssertionError as e:
            # TODO does not yet use new dataclass-based error reporting
            print("A", end='',flush=True)
            type = FuzzTestErrorType.crashed_model
            if "is not sat" in str(e):
                type = FuzzTestErrorType.unsat_model
            elif "has no constraints" in str(e):
                type = FuzzTestErrorType.no_constraints_model

            return InitializeExit(
                        type=type,
                        verifier=self,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        #constraints=self.cons,
                        originalmodel=self.original_model
                    )

        except Exception as e:
            print('C', end='', flush=True)
            return InitializeExit(
                        type=FuzzTestErrorType.crashed_model,
                        verifier=self,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        #constraints=self.cons,
                        originalmodel=self.original_model
                        )


        
    def getType(self) -> str:
        """This function is used for getting the type of the problem the verifier verifies"""
        return self.type
    
    def getName(self) -> str:
        """This function is used for getting the name of the verifier"""
        return self.name

    @classmethod
    def solve_timed_out(self, model) -> bool:
        return (model.status().exitstatus == ExitStatus.FEASIBLE and model.has_objective()) or (model.status().exitstatus == ExitStatus.UNKNOWN)
    

    @classmethod
    def solveAll_timed_out(self, model) -> bool:
        return (model.status().exitstatus == ExitStatus.FEASIBLE) or (model.status().exitstatus == ExitStatus.UNKNOWN)
