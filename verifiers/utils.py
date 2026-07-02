import os
import math
import pickle
from dataclasses import dataclass, field
from datetime import datetime

from typing import Dict, List, Optional, Tuple
from typing import TypeVar, Type

import cpmpy as cp
from cpmpy.transformations.normalize import toplevel_list

from fuzz_test_utils.fuzz_test_errors import FuzzTestErrorType

T = TypeVar("T", bound="Exit")  # T is any subclass of Exit

@dataclass(kw_only=True)
class Exit:
    type: FuzzTestErrorType
    verifier: "Verifier"
    exception: Optional[str] = None
    stacktrace: Optional[str] = None
    originalmodel: cp.Model
    originalmodel_file: os.PathLike
    mutators: List[Tuple[callable, int]] = field(default_factory=lambda: [])
    verifier_kwargs: Dict = field(default_factory=lambda: {})
    alternative_label: Optional[str] = None

    def __post_init__(self):
        date_text = datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
        self.base_name = f"{self.type.name}_{date_text}"

    def write(self, output_dir:os.PathLike, base_name:Optional[str]=None) -> str:
        # TODO export callables as strings, re-import them later

        if base_name is None:
            base_name = self.base_name

        with open(os.path.join(output_dir, base_name + ".pickle"), "wb") as ff:
            pickle.dump(self, file=ff) 

        return base_name
    
    @classmethod
    def load(cls: Type[T], file_path: os.PathLike) -> T:
        with open(file_path, "rb") as ff:
            obj = pickle.load(ff)
        if not isinstance(obj, cls):
            raise TypeError(f"Loaded object is not an instance of {cls.__name__}")
        return obj



    def text(self) -> str:
        stacktrace = "\n\t" + self.stacktrace.replace('\n', '\n\t') if self.stacktrace is not None else "N/A"

        # Prepare mutator transformations
        # Handle two formats:
        # 1. List of tuples with callables: [(callable, int), ...] - from original errors
        # 2. Flat list: [initial_state, seed1, function1, seed2, function2, ...] - from reruns
        transformed = []
        if len(self.mutators) > 0:
            # Check if we have tuples with callables (format 1)
            has_callable_tuples = any(
                isinstance(item, tuple) and len(item) == 2 and hasattr(item[0], "__name__") and callable(item[0])
                for item in self.mutators
            )
            
            if has_callable_tuples:
                # Format 1: List of tuples with callables
                transformed = [(self.mutators[x][0].__name__, self.mutators[x][1]) for x in range(len(self.mutators)) if isinstance(self.mutators[x], tuple) and len(self.mutators[x]) == 2 and hasattr(self.mutators[x][0], "__name__")]
            else:
                # Format 2: Flat list - look for seed -> function pairs
                i = 0
                while i < len(self.mutators):
                    # Skip initial state (list/tuple) or other non-int items
                    if isinstance(self.mutators[i], int) and i + 1 < len(self.mutators):
                        seed = self.mutators[i]
                        function = self.mutators[i + 1]
                        if hasattr(function, "__name__") and callable(function):
                            transformed.append((function.__name__, seed))
                            i += 2
                            continue
                    i += 1
        
        mutators_text = "transformations:\n\t" + str(transformed)

        # Prepare verifier kwargs
        verifier_text = "\n".join(f"{k}: {v}" for k, v in self.verifier_kwargs.items() if k not in ["exclude_dict"])

        original_model_text = "\t" + str(self.originalmodel).rstrip().replace('\n', '\n\t') if self.originalmodel is not None else ""

        # Compose the final multiline string
        return f"""\
type: {self.type}
exception: {self.exception}
stacktrace: {stacktrace}
file: {self.originalmodel_file}
mutators:
{mutators_text}
{verifier_text}
original_model:
{original_model_text}"""



@dataclass(kw_only=True)
class FuzzExit(Exit):
    model: cp.Model
    processed_constraints: Optional[List[cp.expressions.core.Expression]] = None
    
    @property
    def constraints(self) -> List[cp.expressions.core.Expression]:
        return toplevel_list(self.model.constraints)
    
    def text(self) -> str:
        base_text = super().text()
        model_text = "\t" + str(self.model).rstrip().replace('\n', '\n\t') if self.model is not None else ""
        result = base_text + f"\nmodel:\n{model_text}"
        
        # Also show processed constraints after toplevel_list() if available
        if self.processed_constraints is not None:
            processed_model_text = "\t" + str(cp.Model(self.processed_constraints)).rstrip().replace('\n', '\n\t') if len(self.processed_constraints) > 0 else "\tConstraints:\n\tObjective: None"
            result += f"\nprocessed_model:\n{processed_model_text}"
        
        return result


@dataclass(kw_only=True)
class MutationExit(Exit):
    function: Optional[callable] = None
    argument: Optional[object] = None
    pre_failure_constraints: Optional[List[cp.expressions.core.Expression]] = None

    def text(self) -> str:
        base_text = super().text() + f"\nfunction: {self.function}\nargument: {self.argument}"
        
        # Add pre-failure model state if available
        if self.pre_failure_constraints is not None:
            try:
                pre_failure_model = cp.Model(self.pre_failure_constraints)
                pre_failure_text = "\t" + str(pre_failure_model).rstrip().replace('\n', '\n\t')
            except Exception:
                pre_failure_text = "\t" + str(self.pre_failure_constraints)
            base_text += f"\npre_failure_model:\n{pre_failure_text}"
        
        return base_text
    
@dataclass(kw_only=True)
class VerifierExit(Exit):
    function: Optional[callable] = None
    argument = None

    def text(self) -> str:
        return super().text() + f"\nfunction: {self.function}\nargument: {self.argument}"
    

@dataclass(kw_only=True)
class InitializeExit(Exit):
    processed_constraints: Optional[List[cp.expressions.core.Expression]] = None
    
    def text(self) -> str:
        base_text = super().text()
        if self.processed_constraints is not None:
            processed_model_text = "\t" + str(cp.Model(self.processed_constraints)).rstrip().replace('\n', '\n\t') if len(self.processed_constraints) > 0 else "\tConstraints:\n\tObjective: None"
            return base_text + f"\nprocessed_model:\n{processed_model_text}"
        return base_text

