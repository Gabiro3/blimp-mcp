"""
Central registry of all available helper functions.
Used by Gemini to understand what operations are available.
"""

from .gmail_helpers import GMAIL_FUNCTIONS
from .gcalendar_helpers import GCALENDAR_FUNCTIONS
from .notion_helpers import NOTION_FUNCTIONS
from .slack_helpers import SLACK_FUNCTIONS
from .discord_helpers import DISCORD_FUNCTIONS


# Map app names to their function registries
FUNCTION_REGISTRY = {
    "gmail": GMAIL_FUNCTIONS,
    "gcalendar": GCALENDAR_FUNCTIONS,
    "notion": NOTION_FUNCTIONS,
    "slack": SLACK_FUNCTIONS,
    "discord": DISCORD_FUNCTIONS
}


def get_functions_for_apps(app_names: list[str]) -> dict:
    """
    Get function registry for specified apps.
    
    Args:
        app_names: List of app names (e.g., ["gmail", "gcalendar"])
        
    Returns:
        Dict mapping app names to their available functions
    """
    return {
        app: FUNCTION_REGISTRY.get(app.lower(), {})
        for app in app_names
    }
