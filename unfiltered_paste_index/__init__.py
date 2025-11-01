"""unfiltered-paste-index package."""

from importlib import metadata

__all__ = ["__version__"]


def __getattr__(name: str) -> str:
    if name == "__version__":
        try:
            return metadata.version("unfiltered-paste-index")
        except metadata.PackageNotFoundError:  # pragma: no cover
            return "0.0.0"
    raise AttributeError(name)
