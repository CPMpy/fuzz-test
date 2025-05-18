import pickle
import time
import traceback
import random

from cpmpy.exceptions import CPMpyException
import cpmpy as cp

from fuzz_test_utils import *
from .verifier import Verifier
from .metamorphic_verifier import Metamorphic_Verifier
from .solution_verifier import Solution_Verifier
from .model_counting_verifier import Model_Count_Verifier
from .equivalance_verifier import Equivalance_Verifier
from .optimization_verifier import Optimization_Verifier
from .solver_voting_sat_verifier import Solver_Vote_Sat_Verifier
from .solver_voting_count_verifier import Solver_Vote_Count_Verifier
from .strengthening_weakening_verifier import Strengthening_Weakening_Verifier
from .solver_voting_eq_verifier import Solver_Vote_Eq_Verifier
from .verifier_runner import run_verifiers, get_all_verifiers


def lookup_verifier(verfier_name: str) -> Verifier:
    if verfier_name == "solution verifier":
        return Solution_Verifier
    
    elif verfier_name == "optimization verifier":
        return Optimization_Verifier
    
    elif verfier_name == "model count verifier":
        return Model_Count_Verifier
    
    elif verfier_name == "metamorphic verifier":
        return Metamorphic_Verifier
    
    elif verfier_name == "equivalance verifier":
        return Equivalance_Verifier

    elif verfier_name == "solver_vote_sat_verifier":
        return Solver_Vote_Sat_Verifier

    elif verfier_name == "solver_vote_count_verifier":
        return Solver_Vote_Count_Verifier

    elif verfier_name == "strengthening_weakening_verifier":
        return Strengthening_Weakening_Verifier

    elif verfier_name == "solver_vote_eq_verifier":
        return Solver_Vote_Eq_Verifier

    else:
        raise ValueError(f"Error verifier with name {verfier_name} does not exist")
        return None