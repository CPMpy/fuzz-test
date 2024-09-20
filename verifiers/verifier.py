from verifiers import *

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
                        flat2cnf_morph,
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
                return dict(type=Fuzz_Test_ErrorTypes.internalfunctioncrash,
                            originalmodel_file=self.model_file,
                            exception=e,
                            function=function,
                            argument=argument,
                            stacktrace=traceback.format_exc(),
                            mutators=self.mutators,
                            constraints=self.cons,
                            originalmodel=self.original_model
                            )
            return None

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


    def run(self, model_file: str) -> dict:
        """
        This function will run a single tests on the given model
        """
        try:
            self.model_file = model_file
            self.initialize_run()
            gen_mutations_error = self.generate_mutations()

            # check if no error occured while generation the mutations
            if gen_mutations_error == None:
                return self.verify_model()
            else:
                return gen_mutations_error
        except AssertionError as e:
            print("A", end='',flush=True)
            error_type = Fuzz_Test_ErrorTypes.crashed_model
            if "is not sat" in str(e):
                error_type = Fuzz_Test_ErrorTypes.unsat_model
            elif "has no constraints" in str(e):
                error_type = Fuzz_Test_ErrorTypes.no_constraints_model
            return dict(type=error_type,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        originalmodel=self.original_model
                        )
    
        except Exception as e:
            print('C', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.crashed_model,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        mutators=self.mutators,
                        originalmodel=self.original_model
                        )
    
        

    def rerun(self,error: dict) -> dict:
        """
        This function will rerun a previous failed test
        """
        try:
            self.model_file = error["originalmodel_file"]
            self.original_model = error["originalmodel"]
            self.exclude_dict = {}
            self.initialize_run()
            gen_mutations_error = self.generate_mutations()

            # check if no error occured while generation the mutations
            if gen_mutations_error == None:
                return self.verify_model()
            else:
                return gen_mutations_error
            # self.cons = error["constraints"]
            # return self.verify_model()
        
        except AssertionError as e:
            print("A", end='',flush=True)
            type = Fuzz_Test_ErrorTypes.crashed_model
            if "is not sat" in str(e):
                type = Fuzz_Test_ErrorTypes.unsat_model
            elif "has no constraints" in str(e):
                type = Fuzz_Test_ErrorTypes.no_constraints_model
            return dict(type=type,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        originalmodel=self.original_model
                        )
    
        except Exception as e:
            print('C', end='', flush=True)
            return dict(type=Fuzz_Test_ErrorTypes.crashed_model,
                        originalmodel_file=self.model_file,
                        exception=e,
                        stacktrace=traceback.format_exc(),
                        constraints=self.cons,
                        originalmodel=self.original_model
                        )


        
    def getType(self) -> str:
        """This function is used for getting the type of the problem the verifier verifies"""
        return self.type
    
    def getName(self) -> str:
        """This function is used for getting the name of the verifier"""
        return self.name
