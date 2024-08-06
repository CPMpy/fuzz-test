import math
import pickle
from os.path import join
from datetime import datetime

def create_error_output_text(error_data: dict) -> str:
    """
        This helper function will create a more readable text from the error_data dict

        Args:
            error_data (dict): the dict containing all the info about the error that occured
    """
    execution_time_text = f"{str(math.floor(error_data["execution_time"]/60))} minutes {str(math.floor(error_data["execution_time"]%60))} seconds"
    verifier_text = ""
    if error_data["error"]["type"] != "fuzz_test_crash":
        verifier_text = "Chosen Verifier: "+error_data["verifier"]
    error_text = ""
    # get all the error details
    for key, value in error_data["error"].items():
        error_text+= f"\n{key}:\n\t{value}"

    # return a more readable/user friendly error description ready to write to a file 
    return f"An error occured while running a test\n\nUsed solver: {error_data['solver']}\n{verifier_text}\nWith {error_data['mutations_per_model']} mutations per model\nWith seed: {error_data['seed']}\nThe test failed in {execution_time_text}\n\nError Details:\n{error_text}"


def write_error(error_data: dict, output_dir: str) -> None:
    """
        This helper function is used for writing error data ti a txt and a pickle file
        It will name the output files to the current datetime (YYYY-MM-DD H-M-S-MS)

        Args:
            error_data (dict): the dict containing all the info about the error that occured
            output_dir (string): the directory were the error reports needs to be written to
    """

    date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
    with open(join(output_dir, date_text+'.pickle'), "wb") as ff:
        pickle.dump(error_data, file=ff) 

    with open(join(output_dir, date_text+'.txt'), "w") as ff:
        ff.write(create_error_output_text(error_data))
