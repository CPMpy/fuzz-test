import math
import pickle
import csv
import glob
import os
from os.path import join
from datetime import datetime
from fuzz_test_utils.mutators import type_aware_operator_replacement, type_aware_expression_replacement, strengthening_weakening_mutator


def create_error_output_text(error_data: dict) -> str:
    """
        This helper function will create a more readable text from the error_data dict

        Args:
            error_data (dict): the dict containing all the info about the error that occured
    """
    execution_time_text = f"{str(math.floor(error_data['execution_time']/60))} minutes {str(math.floor(error_data['execution_time']%60))} seconds"
    verifier_text = ""
    if error_data["error"]["type"] != "fuzz_test_crash":
        verifier_text = "Chosen Verifier: "+error_data["verifier"]
    error_text = ""
    # get all the error details
    for key, value in error_data["error"].items():
        error_text+= f"\n{key}:\n\t{value}"
        if key == "mutators":
            error_text += f"\ntransformations:\n\t{[value[x] for x in range(len(value)) if x % 3 == 2]}"

    # return a more readable/user friendly error description ready to write to a file 
    return f"An error occured while running a test\n\nUsed solver: {error_data['solver']}\n{verifier_text}\nWith {error_data['mutations_per_model']} mutations per model\nWith seed: {error_data['seed']}\nThe test failed in {execution_time_text}\n\nError Details:\n{error_text}"

def match_conditions(exc_str):
    return [
        (lambda s: any(x in s for x in ["'bool' object is not iterable", "'_BoolVarImpl' object is not iterable"]), "01_bool_obj_not_iterable/"),
        (lambda s: "slice indices must be integers or None or have an __index__ method" in s, "02_slice_indices_must_be_ints/"),
        (lambda s: all(x in s for x in ["Expecting value: line", "column ", "(char "]), "03_line_x_column_x/"),
        (lambda s: any(x in s for x in ["lhs cannot be an integer at this point!", "not supported: model.get_or_make_boolean_index(boolval(False))"]), "04_lhs_no_int/"),
        (lambda s: "'bool' object has no attribute 'implies'" in s, "05_bool_obj_no_implies/"),
        (lambda s: " has no constraints" in s, "06_no_constraints_TO_FIX/"),
        (lambda s: any(x in s for x in ["or-tools does not accept a 'modulo' operation where '0' is in the domain of the divisor", "An int_mod must have a strictly positive modulo argument", "The domain of the divisor cannot contain 0", "Modulo with a divisor domain containing 0 is not supported.", "Power operator: For integer values, exponent must be non-negative:"]), "07_div0_pow-neg/"),
        (lambda s: "object of type '_BoolVarImpl' has no len()" in s, "08_object_type_boolvarimpl_no_len/"),
        (lambda s: "'int' object has no attribute 'lb'" in s, "09_int_obj_no_attr_lb/"),
        (lambda s: all(x in s for x in ["Cannot convert", "to Choco variable"]), "10_cannot_convert_to_choco_var/"),
        (lambda s: any(x in s for x in ["Translation of gurobi status 11 to CPMpy status not implemented", "KeyboardInterrupt", "cannot access local variable 'proc' where it is not associated with a value"]), "11_keyboard_interrupt/"),
        (lambda s: "Cannot modify read-only attribute 'args', use 'update_args()'" in s, "12_cant_modify_args/"),
        (lambda s: "Gurobi only supports division by constants, but got " in s, "13_gurobi_only_div_cst/"),
        (lambda s: any(x in s for x in ["Could not resolve host: ", "Maximum number of failing server authorization attempts reached"]), "_temp/"),
        (lambda s: "'int' object has no attribute 'get_bounds'" in s, "14_int_objc_no_attr_getbounds/"),
        (lambda s: all(x in s for x in ["Domain of ", " only contains 0"]), "15_dom_only_contains_0/"),
        (lambda s: "'int' object has no attribute 'handle'" in s, "16_int_obj_no_attr_handle/"),
        (lambda s: "not an linear expression: " in s, "17_not_lin_expr_bool/"),
        (lambda s: "empty range for randrange()" in s, "18_empty_randrange/"),
        (lambda s: "Results of the solvers are not equal. Solver results:" in s, "19_amnt_sol_neq/"),
        (lambda s: "in method 'int_array_set', argument 2 of type 'int'" in s, "20_argx_type_y/"),
        (lambda s: "'bool' object has no attribute 'has_subexpr'" in s, "21_bool_obj_no_has_subexpr/"),
        (lambda s: "'int' object has no attribute 'is_bool'" in s, "22_int_obj_no_is_bool/"),
        (lambda s: "not supported: model.get_or_make_boolean_index(" in s, "23_not_supported_get_or_make_boolean_index/"),
        (lambda s: any(x in s for x in ["'BoolVal' object has no attribute 'get_integer_var_value_map'", "Not a known var "]), "24_not_known_var/")
    ]

def get_logging_dir(error_data, logging_dir):
    logging_dir += "/"
    error = error_data["error"]
    exception = error["exception"]
    exc_str = str(exception)

    # Check whether the exception matches some format
    for condition, path in match_conditions(exc_str):
        if condition(exc_str):
            logging_dir += path
            break
    else:
        logging_dir += "UNKNOWN/"

    return logging_dir

def write_error(error_data: dict, output_dir: str) -> None:
    """
        This helper function is used for writing error data ti a txt and a pickle file
        It will name the output files to the current datetime (YYYY-MM-DD H-M-S-MS)

        Args:
            error_data (dict): the dict containing all the info about the error that occured
            output_dir (string): the directory were the error reports needs to be written to
    """

    date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
    with open(join(output_dir, f"{error_data['error']['type'].name}_{date_text}.pickle"), "wb") as ff:
        pickle.dump(error_data, file=ff) 

    with open(join(output_dir, f"{error_data['error']['type'].name}_{date_text}.txt"), "w") as ff:
        ff.write(create_error_output_text(error_data))


# Below are all help functions for writing the csv file
def get_bug_class(error_data):
    exc_str = str(error_data['error']['exception'])
    # Check whether the exception matches some format
    for condition, classification in match_conditions(exc_str):
        if condition(exc_str):
            bug_class = classification[3:-1]
            break
    else:
        bug_class = "UNKNOWN"
    return bug_class


def get_verifier(error_data):
    return error_data['verifier']


def get_solvers(error_data):
    return error_data['solver']


def get_seed(error_data):
    return error_data['error']['seed']


def get_time_taken(error_data):
    return error_data['execution_time']


def get_bug_type(error_data):
    return error_data['error']['type']


def get_exception(error_data):
    return error_data['error']['exception']


def get_original_cons(error_data):
    return error_data['error']['originalmodel'].constraints


def get_current_cons(error_data):
    return error_data['error']['constraints']


def get_mutations(error_data):
    if 'mutators' in error_data['error']:
        return error_data['error']['mutators'][2::3]
    else:
        return []


def get_nr_mm_mutations(error_data):
    return len([m for m in get_mutations(error_data) if
                m not in {type_aware_expression_replacement, type_aware_operator_replacement,
                          strengthening_weakening_mutator}])


def get_nr_gen_mutations(error_data):
    return len([m for m in get_mutations(error_data) if
                m in {type_aware_expression_replacement, type_aware_operator_replacement,
                      strengthening_weakening_mutator}])


def get_nr_mutations(error_data):
    return len(get_mutations(error_data))


def get_bugged_solver(error_data):
    error = error_data['error']
    all_solvers = ['minizinc', 'ortools', 'gurobi', 'choco', 'z3']
    if 'stacktrace' in error:
        stacktrace = error['stacktrace']
        for solver in all_solvers:
            if solver in str(stacktrace):
                return solver
    elif 'exception' in error:  # In case of a failed model (no crash)
        exc = error['exception']
        possibly_bugged = [s for s in all_solvers if s in str(exc)]
        if possibly_bugged:
            return possibly_bugged
    return 'UNKNOWN'


def get_objective(error_data):
    return error_data['error']['originalmodel'].objective


def get_variables(error_data):
    return error_data['error']['variables']


def get_nr_solve_checks(error_data):
    return error_data['error']['nr_solve_checks']


def get_cause(error_data):
    return error_data['error']['caused_by']


def get_nr_timed_out_solve_calls(error_data):
    return error_data['error']['nr_timed_out']


def extract_last_stacktrace_lines(error_data) -> str:
    stacktrace = error_data['error']['stacktrace']
    lines = stacktrace.strip().splitlines()
    last_file_index = None

    for i, line in enumerate(lines):
        if line.strip().startswith("File"):
            last_file_index = i

    if last_file_index is not None:
        return '\n'.join(lines[last_file_index:]).strip()
    else:
        return ''


def write_csv(error_data: dict, output_path) -> None:
    columns_and_functions = [
        ("bug_class", get_bug_class),
        ("verifier", get_verifier),
        ("solvers", get_solvers),
        ("seed", get_seed),
        ("time_taken", get_time_taken),
        ("bug_type", get_bug_type),
        ("exception", get_exception),
        ("last_stacktrace_line", extract_last_stacktrace_lines),
        ("original_constraints", get_original_cons),
        ("current_constraints", get_current_cons),
        ("total_nr_mutations", get_nr_mutations),
        ("nr_mm_mutations", get_nr_mm_mutations),
        ("nr_gen_mutations", get_nr_gen_mutations),
        ("mutations", get_mutations),
        ("bugged_solver", get_bugged_solver),
        ("objective", get_objective),
        ("variables", get_variables),
        ("nr_solve_checks", get_nr_solve_checks),
        ("bug_cause", get_cause),
        ("nr_timed_out_solve_calls", get_nr_timed_out_solve_calls)
    ]

    file_exists = os.path.isfile(output_path)

    with open(output_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        if not file_exists:
            # Write header
            headers = [col for col, _ in columns_and_functions]
            writer.writerow(headers)

        # Write the error data row
        row = []
        for _, func in columns_and_functions:
            try:
                value = func(error_data)
            except Exception as e:
                value = f"ERROR: {e}"
            row.append(value)
        writer.writerow(row)
