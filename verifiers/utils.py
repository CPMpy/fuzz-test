import os
import math
import pickle
from dataclasses import dataclass, field
from datetime import datetime

from typing import Dict, List, Optional
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
    mutators: List[callable] = field(default_factory=lambda: [])
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
        transformed = [self.mutators[x].__name__ for x in range(len(self.mutators)) if x % 3 == 2]
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
    
    @property
    def constraints(self) -> List[cp.expressions.core.Expression]:
        return toplevel_list(self.model.constraints)
    
    def text(self) -> str:
        model_text = "\t" + str(self.model).rstrip().replace('\n', '\n\t') if self.model is not None else ""
        return super().text() + f"\nmodel:\n{model_text}"


@dataclass(kw_only=True)
class MutationExit(Exit):
    function: Optional[callable] = None
    argument: Optional[object] = None

    def text(self) -> str:
        return super().text() + f"\nfunction: {self.function}\nargument: {self.argument}"
    
@dataclass(kw_only=True)
class VerifierExit(Exit):
    function: Optional[callable] = None
    argument = None

    def text(self) -> str:
        return super().text() + f"\nfunction: {self.function}\nargument: {self.argument}"
    

@dataclass(kw_only=True)
class InitializeExit:
    pass
    # TODO what should the "constraints" be here?

