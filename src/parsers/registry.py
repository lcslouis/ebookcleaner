"""
Parser registry.

Resolution order (first match wins):
  1. Dedicated parsers (most precise, handles complex/API-based sites)
  2. Config-based parsers (CSS-selector driven, one per SiteConfig entry)
  3. Default parser (density heuristics + optional CSS selector override)
"""
from .royalroad_parser import RoyalRoadParser
from .fanfiction_parser import FanFictionParser
from .ao3_parser import AO3Parser
from .scribblehub_parser import ScribbleHubParser
from .wattpad_parser import WattpadParser
from .bakatsuki_parser import BakaTsukiParser
from .fictioneer_parser import FictioneerParser
from .blogspot_parser import BlogspotParser
from .novelbin_parser import NovelBinParser
from .lightnovel_wp_parser import LightNovelWPParser
from .config_parser import get_config_parsers
from .default_parser import DefaultParser

# Dedicated parsers instantiated once at import time
_DEDICATED = [
    RoyalRoadParser(),
    FanFictionParser(),
    AO3Parser(),
    ScribbleHubParser(),
    WattpadParser(),
    BakaTsukiParser(),
    FictioneerParser(),
    BlogspotParser(),
    NovelBinParser(),
    LightNovelWPParser(),
]

# Config parsers (one per SiteConfig entry)
_CONFIG = get_config_parsers()

# Community plugins installed via Plugin Manager
def _load_plugin_parsers():
    try:
        from src.plugin_manager import PluginManager
        from src.parsers.config_parser import ConfigParser
        return [ConfigParser(cfg) for cfg in PluginManager().load_installed()]
    except Exception:
        return []

_PLUGINS = _load_plugin_parsers()

# Full ordered list — plugins checked after bundled configs, before default
_ALL_PARSERS = _DEDICATED + _CONFIG + _PLUGINS


def get_parser(url: str, content_selector: str = "", soup=None) -> object:
    """Return the most specific parser for the given URL.

    If soup is provided, parsers that didn't match by URL get a second chance
    via can_handle_soup() — used to detect themes like Fictioneer on unknown domains.
    """
    for parser in _ALL_PARSERS:
        if parser.can_handle(url):
            return parser
    if soup is not None:
        for parser in _ALL_PARSERS:
            if hasattr(parser, "can_handle_soup") and parser.can_handle_soup(soup):
                return parser
    return DefaultParser(content_selector)


def get_parser_info(url: str) -> dict:
    """Return site name and parser tier for a URL.

    parser_type values: 'Dedicated' | 'Config' | 'Default'
    """
    for parser in _DEDICATED:
        if parser.can_handle(url):
            return {"site_name": parser.site_name, "parser_type": "Dedicated"}
    for parser in _CONFIG:
        if parser.can_handle(url):
            return {"site_name": parser.site_name, "parser_type": "Config"}
    return {"site_name": "Unknown site", "parser_type": "Default"}


def detect_site_name(url: str) -> str:
    return get_parser(url).site_name


def get_parser_by_name(site_name: str):
    """Return the parser whose site_name matches (case-insensitive), or None."""
    target = site_name.strip().lower()
    for p in _ALL_PARSERS:
        if p.site_name.lower() == target:
            return p
    return None


def list_parser_names() -> list[tuple]:
    """Return sorted (site_name, parser_type) pairs for the override UI."""
    result = []
    for p in _DEDICATED:
        result.append((p.site_name, "Dedicated"))
    for p in _CONFIG:
        result.append((p.site_name, "Config"))
    result.append((DefaultParser().site_name, "Default"))
    return sorted(result, key=lambda x: x[0].lower())


def reload_plugins() -> None:
    """Re-scan ~/.ebookcleaner/plugins/ and update _ALL_PARSERS in place.

    Called by the Plugin Manager dialog after install/uninstall so the new
    parsers are available immediately without restarting the app.
    """
    global _PLUGINS, _ALL_PARSERS
    _PLUGINS = _load_plugin_parsers()
    _ALL_PARSERS = _DEDICATED + _CONFIG + _PLUGINS


def list_supported_sites() -> list:
    """Return a sorted list of all site names and their domains."""
    sites = []
    for p in _ALL_PARSERS:
        domains = getattr(p, "_config", None)
        if domains:
            # ConfigParser — expose domain list
            domain_str = ", ".join(p._config.domains[:3])
            if len(p._config.domains) > 3:
                domain_str += f" (+{len(p._config.domains) - 3} more)"
        else:
            domain_str = ", ".join(
                pat.replace(r"\.", ".").strip(r"^$") for pat in (p.url_patterns or [])[:3]
            )
        sites.append({"name": p.site_name, "domains": domain_str})
    return sorted(sites, key=lambda s: s["name"].lower())
