"""
Site login browser — runs as a subprocess via:
    python main.py --webview-login <url> <output_json>

Opens a pywebview/WebView2 window so the user can log in normally.
A floating "Done — Save Login" button injects into every page.
When clicked, all cookies (including httpOnly via window.get_cookies())
are written to the output JSON file and the window closes.
"""
import json
import threading


_DONE_BTN_JS = """
(function() {
    if (document.getElementById('_ec_done_btn')) return;
    var b = document.createElement('button');
    b.id = '_ec_done_btn';
    b.textContent = '✓ Done — Save Login';
    b.style.cssText = [
        'position:fixed', 'bottom:18px', 'right:18px',
        'z-index:2147483647', 'padding:9px 20px',
        'background:#1d4ed8', 'color:#fff',
        'border:none', 'border-radius:6px',
        'font-size:14px', 'font-weight:600',
        'cursor:pointer',
        'box-shadow:0 2px 10px rgba(0,0,0,.4)'
    ].join(';');
    b.onmouseenter = function() { this.style.background = '#1e40af'; };
    b.onmouseleave = function() { this.style.background = '#1d4ed8'; };
    b.onclick = function() { pywebview.api.save_and_close(); };
    document.body.appendChild(b);
})();
"""


def run_login_browser(url: str, output_file: str) -> None:
    import webview

    result: dict = {"cookies": [], "final_url": ""}
    _window = None

    class _Api:
        def save_and_close(self):
            nonlocal result
            try:
                cookies = _window.get_cookies()
                result["cookies"] = [
                    {
                        "name":   c.name,
                        "value":  c.value,
                        "domain": getattr(c, "domain", ""),
                        "path":   getattr(c, "path", "/"),
                        "secure": bool(getattr(c, "secure", False)),
                    }
                    for c in cookies
                ]
            except Exception:
                # Fallback: only non-httpOnly cookies via JS
                try:
                    raw = _window.evaluate_js("document.cookie") or ""
                    cookies_list = []
                    for part in raw.split(";"):
                        part = part.strip()
                        if "=" in part:
                            name, _, value = part.partition("=")
                            cookies_list.append({"name": name.strip(), "value": value.strip()})
                    result["cookies"] = cookies_list
                except Exception:
                    pass

            try:
                result["final_url"] = _window.get_current_url() or ""
            except Exception:
                pass

            _window.destroy()

    api = _Api()
    _window = webview.create_window(
        "Login — EbookCleaner",
        url,
        js_api=api,
        width=1100,
        height=800,
    )

    def _inject():
        try:
            _window.evaluate_js(_DONE_BTN_JS)
        except Exception:
            pass

    _window.events.loaded += _inject

    webview.start()

    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
