# Injected by CI before each tagged build.
# In local development, get_version() reads the nearest git tag instead.
__version__ = "dev"


def get_version() -> str:
    """Return the running version string."""
    if __version__ != "dev":
        return __version__
    try:
        import subprocess, os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL,
            cwd=root,
        ).decode().strip().lstrip("v")
        return tag or "dev"
    except Exception:
        return "dev"
