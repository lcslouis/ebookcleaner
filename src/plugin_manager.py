"""
Plugin manager — downloads, installs, and loads community-contributed
site parsers from the ebookcleaner-plugins registry.

Plugins are JSON files stored in ~/.ebookcleaner/plugins/.
The registry lives at:
  https://raw.githubusercontent.com/lcslouis/ebookcleaner-plugins/main/registry.json
"""
import json
from pathlib import Path

REGISTRY_URL = (
    "https://raw.githubusercontent.com/lcslouis/ebookcleaner-plugins/main/registry.json"
)
RAW_BASE_URL = "https://raw.githubusercontent.com/lcslouis/ebookcleaner-plugins/main/"

PLUGINS_DIR = Path.home() / ".ebookcleaner" / "plugins"


class PluginManager:
    def __init__(self):
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ local

    def get_installed_ids(self) -> set:
        return {p.stem for p in PLUGINS_DIR.glob("*.json")}

    def load_installed(self) -> list:
        """Return list of SiteConfig objects for all installed plugins."""
        from src.parsers.site_configs import SiteConfig
        configs = []
        for path in sorted(PLUGINS_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                cfg = SiteConfig(
                    site_name=data.get("name", path.stem),
                    domains=data.get("domains", []),
                    toc_selectors=data.get("toc_selectors", []),
                    content_selectors=data.get("content_selectors", []),
                    title_selectors=data.get("title_selectors", []),
                    author_selectors=data.get("author_selectors", []),
                    description_selectors=data.get("description_selectors", []),
                    cover_selectors=data.get("cover_selectors", []),
                )
                configs.append(cfg)
            except Exception:
                pass
        return configs

    def get_installed_meta(self) -> list:
        """Return raw metadata dicts for all installed plugins."""
        result = []
        for path in sorted(PLUGINS_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("id", path.stem)
                result.append(data)
            except Exception:
                pass
        return result

    def uninstall(self, plugin_id: str) -> None:
        path = PLUGINS_DIR / f"{plugin_id}.json"
        if path.exists():
            path.unlink()

    def install_from_file(self, path: str) -> str:
        """Install a plugin from a local JSON file. Returns the plugin id."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        plugin_id = data.get("id") or Path(path).stem
        dest = PLUGINS_DIR / f"{plugin_id}.json"
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return plugin_id

    def save_plugin(self, data: dict) -> None:
        """Save a plugin dict directly (used by Provider Studio export)."""
        plugin_id = data.get("id") or data.get("name", "plugin").lower().replace(" ", "_")
        dest = PLUGINS_DIR / f"{plugin_id}.json"
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ remote

    def fetch_registry(self, timeout: int = 15) -> list:
        """Download and return the registry plugin list."""
        import requests
        resp = requests.get(REGISTRY_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("plugins", [])

    def install(self, plugin_meta: dict, timeout: int = 15) -> None:
        """Download a plugin by its registry entry and save locally."""
        import requests
        file_path = plugin_meta.get("file", "")
        if not file_path:
            raise ValueError("Plugin has no file path in registry")
        url = RAW_BASE_URL + file_path
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        plugin_id = plugin_meta.get("id") or Path(file_path).stem
        dest = PLUGINS_DIR / f"{plugin_id}.json"
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ recommendations

    def get_recommended_plugins(self, db, registry: list) -> list:
        """Return registry entries matching library books that aren't installed."""
        from urllib.parse import urlparse
        installed = self.get_installed_ids()
        try:
            books = db.get_all_books()
        except Exception:
            return []
        hostnames = set()
        for book in books:
            url = (book.get("source_url") or "").strip()
            if url:
                try:
                    hostnames.add(urlparse(url).netloc.lower())
                except Exception:
                    pass
        if not hostnames:
            return []
        recommended = []
        for entry in registry:
            if entry.get("id") in installed:
                continue
            for domain in entry.get("domains", []):
                if any(domain in h for h in hostnames):
                    recommended.append(entry)
                    break
        return recommended
