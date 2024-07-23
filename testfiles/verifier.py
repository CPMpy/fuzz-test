from abc import ABC, abstractmethod

class Verifier(ABC):

    @abstractmethod
    def run(self,solver: str, iters: int, model_file: str, exclude_dict: dict) -> dict:
        """
        This function that will execute a single verifier test

        Args:
            solver (string): the name of the solver that is getting used for the tests
            mutations_per_model (int): the amount of permutations 
            model_file (string): the model file to open
            exclude_dict (dict): a dict of models we want to exclude
        """
        pass

    @abstractmethod
    def getType(self) -> str:
        """This function is used for getting the type of the problem the verifier verifies"""
        pass
    @abstractmethod
    def getName(self) -> str:
        """This function is used for getting the name of the verifier"""
        pass