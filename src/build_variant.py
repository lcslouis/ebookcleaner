"""
Runtime feature flags — set by the PyInstaller runtime hook for lite builds.
"""
import os

IS_LITE = os.environ.get("EBOOKCLEANER_LITE") == "1"


def has_ai() -> bool:
    """True if AI processing packages are available."""
    if IS_LITE:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        from google import genai  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        from openai import OpenAI  # noqa: F401
        return True
    except ImportError:
        pass
    return False


def has_webengine() -> bool:
    """True if QtWebEngineWidgets is available (needed for site login browser)."""
    if IS_LITE:
        return False
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        return True
    except ImportError:
        return False
