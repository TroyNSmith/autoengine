"""autoengine."""

__version__ = "0.0.1"

from .adapter import InputProvenance, OutputProvenance
from .run import optimization

__all__ = ["optimization", "InputProvenance", "OutputProvenance"]
