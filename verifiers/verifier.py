import random
import time
import traceback
from cpmpy.exceptions import CPMpyException
from mutators import *



class Verifier():
    """
    The base class containing the base functions for each verifier.
    """


    def __init__(self, name: str, type: str, solver: str, mutations_per_model: int, exclude_dict: dict , max_duration: float, seed: int):
        self.name = name
        self.type = type
        self.solver = solver
        self.mutations_per_model = mutations_per_model
        self.exclude_dict = exclude_dict
        self.max_duration = max_duration
        self.seed = seed
        self.mm_mutators = None 
        self.mutators = None


    def generate_mutations(self) -> None:
        """
        Will generate random mutations based on mutations_per_model for the model
        """
        for i in range(self.mutations_per_model):
            # choose a metamorphic mutation, don't choose any from exclude_dict
            if self.model_file in self.exclude_dict:
                valid_mutators = list(set(self.mm_mutators) - set(self.exclude_dict[self.model_file]))
            else:
                valid_mutators = self.mm_mutators
            m = random.choice(valid_mutators)
            self.mutators += [self.seed]
            # an error can occur in the transformations, so even before the solve call.
            # log function and arguments in that case
            self.mutators += [m]
            try:
                self.cons += m(self.cons)  # apply a metamorphic mutation
                self.mutators += [copy.deepcopy(self.cons)]
            except MetamorphicError as exc:
                #add to exclude_dict, to avoid running into the same error
                if self.model_file in self.exclude_dict:
                    self.exclude_dict[self.model_file] += [m]
                else:
                    self.exclude_dict[self.model_file] = [m]
                function, argument, e = exc.args
                if isinstance(e,CPMpyException):
                    #expected behavior if we throw a cpmpy exception, do not log
                    return None
                elif function == semanticFusion:
                    return None
                    #don't log semanticfusion crash
                    
                print('I', end='', flush=True)
                return {"type": "internalfunctioncrash","function":function, "argument": argument, "originalmodel": self.model_file, "mutators": self.mutators,"constraints": self.cons, "exception": e,"stacktrace":traceback.format_exc()} # no need to solve model we didn't modify..
            return None

    def initilize_run(self) -> None:
        """
        Abstract function that gets executed before generating the mutation,
        This function is ued for getting the right data from the model.
        Each verifier needs to implement this function
        """
        pass

    def solve_model(self) -> dict:
        """
        Abstract function that will solve the newly created model with the mutations.
        It will check if the test succeeded or not.
        Each verifier needs to implement this function
        """
        pass

    def run(self, model_file: str) -> dict:
        """
        This function will run a single tests on the given model
        """
        try:
            self.model_file = model_file
            self.initilize_run()
            gen_mutations_error = self.generate_mutations()

            # check if no error occured while generation the mutations
            if gen_mutations_error == None:
                return self.solve_model()
            else:
                return gen_mutations_error
        except AssertionError as e:
            print("A", end='',flush=True)
            type = "crashed_model"
            if "is not sat" in str(e):
                type = "unsat_model"
            elif "has no constraints" in str(e):
                type = "no_constraints_model"
            return {"type": type, "originalmodel": self.model_file, "exception": e,"stacktrace":traceback.format_exc()}
    
        except Exception as e:
            print('C', end='', flush=True)
            return {"type": "crashed_model", "originalmodel": self.model_file, "mutators": self.mutators,"constraints": self.cons, "exception": e,"stacktrace":traceback.format_exc()}
    
        

    def rerun(self,error: dict) -> dict:
        """
        This function will rerun a previous failed test
        """
        try:
            self.model_file = error["originalmodel"]
            self.exclude_dict = {}

            self.initilize_run()


            self.cons = error["constraints"]
            return self.solve_model()
        except AssertionError as e:
            print("A", end='',flush=True)
            type = "crashed_model"
            if "is not sat" in str(e):
                type = "unsat_model"
            elif "has no constraints" in str(e):
                type = "no_constraints_model"
            return {"type": type, "originalmodel": self.model_file, "exception": e,"stacktrace":traceback.format_exc()}
    
        except Exception as e:
            print('C', end='', flush=True)
            return {"type": "crashed_model", "originalmodel": self.model_file, "exception": e,"stacktrace":traceback.format_exc()}


        
    def getType(self) -> str:
        """This function is used for getting the type of the problem the verifier verifies"""
        return self.type
    
    def getName(self) -> str:
        """This function is used for getting the name of the verifier"""
        return self.name

