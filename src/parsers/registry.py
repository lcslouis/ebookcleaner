from .royalroad_parser import RoyalRoadParser
from .fanfiction_parser import FanFictionParser
from .ao3_parser import AO3Parser
from .scribblehub_parser import ScribbleHubParser
from .default_parser import DefaultParser

_PARSERS = [
    RoyalRoadParser(),
    FanFictionParser(),
    AO3Parser(),
    ScribbleHubParser(),
]


def get_parser(url: str, content_selector: str = "") -> object:
    """Return the most appropriate parser for the given URL."""
    for parser in _PARSERS:
        if parser.can_handle(url):
            return parser
    return DefaultParser(content_selector)


def detect_site_name(url: str) -> str:
    return get_parser(url).site_name
