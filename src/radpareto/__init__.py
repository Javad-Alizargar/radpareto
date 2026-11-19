"""RadPareto: evidence-aware cost comparisons, not radiation qualification."""
from .compare import batch_compare, compare
from .validation import EvidenceError, validate_document

__version__ = "0.1.0a1"
__all__ = ["compare", "batch_compare", "validate_document", "EvidenceError"]
