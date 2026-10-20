# EbookCleaner

A Windows desktop app for downloading, cleaning, and managing web novels and ebooks.

**[Website](https://lcslouis.github.io/ebookcleaner/) · [Download](../../releases/latest) · [Report a Bug](../../issues)**

---

## Features

- **Fetch from web** — download novels from 80+ sites including Royal Road, AO3, Scribble Hub, Wattpad, FanFiction.net, WTR-Lab, FreeWebNovel, and many more
- **AI cleaning** — fix broken OCR, garbled text, split words, and UI overlay artifacts using Anthropic, Gemini, Groq, or a local Ollama model
- **AI rewrite** — rewrite chapters for improved prose while preserving all dialogue
- **Translation** — batch translate chapters to English via Google Translate (no API key required)
- **EPUB export** — export any book to a clean EPUB file
- **Readest sync** — push books to [Readest](https://readest.com) via WebDAV or local folder sync
- **Browser Bridge** — connects to your real Chrome, Edge, or Firefox browser for Cloudflare-protected sites; auto-installs a companion extension
- **Chapter update checker** — check all your books for new chapters and download in bulk
- **In-app updater** — patch-based updates; only changed files are downloaded
- **REST API** — local HTTP API with a built-in web UI for remote access
- **Plugin system** — extend with community-built site plugins via Provider Studio

---

## Download

Get the latest release from the [Releases page](../../releases/latest).

| Installer | Description |
|---|---|
| `EbookCleaner-Setup-*.exe` | Standard installer (recommended) |
| `EbookCleaner-Full-Bundle-Setup-*.exe` | Includes Provider Studio |
| `EbookCleaner-Windows-*.zip` | Portable ZIP |
| `EbookCleaner-Patch-*.zip` | Patch update (apply over existing install) |

No Python required — fully self-contained.

---

## Supported Sites

Dedicated parsers for: Royal Road, Archive of Our Own, Scribble Hub, Wattpad, FanFiction.net, Baka-Tsuki, WTR-Lab, FreeWebNovel (and mirrors), WordPress Fictioneer themes, Blogspot/Blogger, NovelBin, generic WordPress novel themes, and 80+ additional sites via CSS-selector config.

---

## Requirements

- Windows 10 or later (64-bit)

---

## Provider Studio

Provider Studio is a companion tool for creating and submitting custom site parsers (plugins). Available as a standalone download from the [Releases page](../../releases/latest) or included in the Full Bundle installer.

---

## Bug Reports & Feature Requests

Please [open an issue](../../issues) and include:
- Your OS and app version (shown in the title bar)
- The site URL you were trying to fetch from (if applicable)
- What you expected to happen and what actually happened
