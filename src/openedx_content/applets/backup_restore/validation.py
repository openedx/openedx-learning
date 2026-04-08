"""
This is an archive-agnostic validation of the data models. I might actually just
move this to api.py, since most of this work will be done in schema.py
"""
import attrs

from pydantic_core import InitErrorDetails
from fsspec import AbstractFileSystem

from .schema import CompletePackageInputData
from .payload import UnvalidatedLearningPackageInput

@attrs.define(frozen=True)
class ValidatedLearningPackageInput:
    data: CompletePackageInputData | None  # None if it's too broken

    fs: AbstractFileSystem

    # All these names are terrible.

    # These are the errors that mean this is actually malformed, i.e. JSON
    # Schema level validation.
    structural_errors: list[InitErrorDetails]

    deeper_errors: list  # This is stuff we have to dig deeper for, e.g. missing parent-child relationship

def validate(
    unvalidated_lp: UnvalidatedLearningPackageInput,
) -> ValidatedLearningPackageInput:
    """ """
    validated = CompletePackageInputData.model_validate(unvalidated_lp.raw_data)
    # pretty_print(validated)

    return ValidatedLearningPackageInput(
        data=validated,
        fs=unvalidated_lp.fs,
        structural_errors=[],
        deeper_errors=[],
    )