import enum
class FuzzTestErrorType(enum.Enum):
    ok = "ok"
    timeout = "timeout"
    internalcrash = "internalcrash"
    failed_model = "failed_model"
    internalfunctioncrash = "internalfunctioncrash"
    crashed_model = "crashed_model"
    unsat_model = "unsat_model"
    no_constraints_model = "no_constraints_model"
    fuzz_test_crash = "fuzz_test_crash"
    expected_error = "expected_error"