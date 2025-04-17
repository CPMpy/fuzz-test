import math
import pickle
from os.path import join
from datetime import datetime

from fuzz_test_utils import type_aware_operator_replacement, type_aware_expression_replacement


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
        (lambda s: "'bool' object is not iterable" in s, "01_bool_obj_not_iterable/"),
        (lambda s: "slice indices must be integers or None or have an __index__ method" in s, "02_slice_indices_must_be_ints/"),
        (lambda s: all(x in s for x in ["Expecting value: line", "column ", "(char "]), "03_line_x_column_x/"),
        (lambda s: any(x in s for x in ["lhs cannot be an integer at this point!", "not supported: model.get_or_make_boolean_index(boolval(False))"]), "04_lhs_no_int/"),
        (lambda s: "'bool' object has no attribute 'implies'" in s, "05_bool_obj_no_implies/"),
        (lambda s: " has no constraints" in s, "06_no_constraints_TO_FIX/"),
        (lambda s: any(x in s for x in ["An int_mod must have a strictly positive modulo argument", "The domain of the divisor cannot contain 0", "Modulo with a divisor domain containing 0 is not supported.", "Power operator: For integer values, exponent must be non-negative:"]), "07_div0_pow-neg/"),
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
        (lambda s: "not an linear expression: boolval(True)" in s, "17_not_lin_expr_boolval/"),
        (lambda s: "empty range for randrange()" in s, "18_empty_randrange/"),
        (lambda s: "Amount of solutions of the two solvers are not equal." in s, "19_amnt_sol_neq/"),
        (lambda s: "in method 'int_array_set', argument 2 of type 'int'" in s, "20_argx_type_y/"),
        (lambda s: "'bool' object has no attribute 'has_subexpr'" in s, "21_bool_obj_no_has_subexpr"),
        (lambda s: len(s) == 0, "22_empty_exception"),
        (lambda s: "Not a known var " in s, "23_wsum_second_arg_vars")
    ]

def get_output_dir(error_data):
    output_dir = "test_output/"
    error = error_data["error"]
    exception = error["exception"]
    exc_str = str(exception)
    mutators = error['mutators'][2::3]
    # Split into two different directories for errors including generation-type mutations
    if any([fn in {type_aware_operator_replacement, type_aware_expression_replacement} for fn in mutators]):
        output_dir += "GEN/"
    else:
        output_dir += "MUT/"

    # Check whether the exception matches some format
    for condition, path in match_conditions(exc_str):
        if condition(exc_str):
            output_dir += path
            break
    else:
        output_dir += "UNKNOWN/"

    return output_dir

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