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
]

# Config parsers (one per SiteConfig entry)
_CONFIG = get_config_parsers()

# Full ordered list (default parser is always the fallback, not in this list)
_ALL_PARSERS = _DEDICATED + _CONFIG


def get_parser(url: str, content_selector: str = "") -> object:
    """Return the most specific parser for the given URL."""
    for parser in _ALL_PARSERS:
        if parser.can_handle(url):
            return parser
    return DefaultParser(content_selector)


def detect_site_name(url: str) -> str:
    return get_parser(url).site_name


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
