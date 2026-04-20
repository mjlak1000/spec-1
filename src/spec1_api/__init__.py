"""spec1_api — FastAPI application for SPEC-1 Intelligence Engine."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("spec1-engine")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
