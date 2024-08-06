import enum
class Fuzz_Test_ErrorTypes(enum.Enum):
    internalcrash = 1
    failed_model = 2
    internalfunctioncrash = 3
    crashed_model = 4
    unsat_model = 5
    no_constraints_model = 6
    fuzz_test_crash = 7