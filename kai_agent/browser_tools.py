"""
Browser Automation for Kai
Adds web browsing, form filling, portal navigation, and document download
to Kai's toolset.

Requires: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


class BrowserTools:
    """Browser automation tools for Kai."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.download_dir = workspace / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._browser = None
        self._page = None
        self._pw = None

    def _ensure_browser(self) -> dict:
        if self._browser and self._page:
            return {"ok": True}

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "ok": False,
                "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            }

        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._page = self._browser.new_page(accept_downloads=True)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def browse(self, url: str) -> str:
        """Navigate to a URL and return page info."""
        result = self._ensure_browser()
        if not result["ok"]:
            return json.dumps({"action": "browse", "ok": False, "error": result["error"]}, indent=2)

        try:
            if not url.startswith("http"):
                url = "https://" + url
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = self._page.title()
            text = self._page.inner_text("body")[:3000]
            return json.dumps({
                "action": "browse",
                "ok": True,
                "url": self._page.url,
                "title": title,
                "text_preview": text,
            }, indent=2)
        except Exception as exc:
            return json.dumps({"action": "browse", "ok": False, "error": str(exc)}, indent=2)

    def search_web_browser(self, query: str, site: str = "") -> str:
        """Search Google and return results."""
        result = self._ensure_browser()
        if not result["ok"]:
            return json.dumps({"action": "search", "ok": False, "error": result["error"]}, indent=2)

        try:
            if site:
                search_url = f"https://www.google.com/search?q=site:{site}+{query.replace(' ', '+')}"
            else:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

            self._page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            results = []
            for el in self._page.query_selector_all("div.g")[:10]:
                try:
                    title_el = el.query_selector("h3")
                    link_el = el.query_selector("a")
                    snippet_el = el.query_selector("div.VwiC3b")
                    if title_el and link_el:
                        results.append({
                            "title": title_el.inner_text(),
                            "url": link_el.get_attribute("href"),
                            "snippet": snippet_el.inner_text() if snippet_el else "",
                        })
                except Exception:
                    continue

            return json.dumps({
                "action": "search",
                "ok": True,
                "query": query,
                "results": results,
            }, indent=2)
        except Exception as exc:
            return json.dumps({"action": "search", "ok": False, "error": str(exc)}, indent=2)

    def get_page_content(self) -> str:
        """Get text content of the current page."""
        if not self._page:
            return json.dumps({"action": "page_content", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            text = self._page.inner_text("body")[:5000]
            url = self._page.url
            title = self._page.title()
            return json.dumps({
                "action": "page_content",
                "ok": True,
                "url": url,
                "title": title,
                "text": text,
            }, indent=2)
        except Exception as exc:
            return json.dumps({"action": "page_content", "ok": False, "error": str(exc)}, indent=2)

    def get_links(self) -> str:
        """Get all links on the current page."""
        if not self._page:
            return json.dumps({"action": "get_links", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            links = []
            for el in self._page.query_selector_all("a[href]")[:50]:
                href = el.get_attribute("href") or ""
                text = el.inner_text().strip()[:100]
                if href and text:
                    links.append({"href": href, "text": text})
            return json.dumps({"action": "get_links", "ok": True, "links": links}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "get_links", "ok": False, "error": str(exc)}, indent=2)

    def click_link(self, text: str) -> str:
        """Click a link by text."""
        if not self._page:
            return json.dumps({"action": "click", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            links = self._page.query_selector_all("a")
            for link in links:
                try:
                    link_text = link.inner_text().strip().lower()
                    if text.lower() in link_text:
                        href = link.get_attribute("href") or ""
                        link.click()
                        time.sleep(1.5)
                        return json.dumps({
                            "action": "click",
                            "ok": True,
                            "clicked_text": link.inner_text().strip(),
                            "href": href,
                            "url": self._page.url,
                            "title": self._page.title(),
                        }, indent=2)
                except Exception:
                    continue
            return json.dumps({"action": "click", "ok": False, "error": f"Link containing '{text}' not found"}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "click", "ok": False, "error": str(exc)}, indent=2)

    def fill_form(self, data: dict[str, str], form_index: int = 0) -> str:
        """Fill form fields on the current page."""
        if not self._page:
            return json.dumps({"action": "fill_form", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            forms = self._page.query_selector_all("form")
            if form_index >= len(forms):
                return json.dumps({"action": "fill_form", "ok": False, "error": f"Form {form_index} not found"}, indent=2)

            form = forms[form_index]
            filled = []
            errors = []

            for field_name, value in data.items():
                try:
                    el = form.query_selector(f"[name='{field_name}']") or form.query_selector(f"#{field_name}")
                    if not el:
                        errors.append(f"Field '{field_name}' not found")
                        continue

                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    input_type = (el.get_attribute("type") or "").lower()

                    if tag == "select":
                        el.select_option(value)
                    elif input_type == "checkbox":
                        if value.lower() in ("true", "1", "yes", "on"):
                            el.check()
                    elif input_type == "radio":
                        el.click()
                    else:
                        el.fill(value)
                    filled.append(field_name)
                except Exception as fe:
                    errors.append(f"Error filling '{field_name}': {fe}")

            return json.dumps({
                "action": "fill_form",
                "ok": len(errors) == 0,
                "filled": filled,
                "errors": errors,
            }, indent=2)
        except Exception as exc:
            return json.dumps({"action": "fill_form", "ok": False, "error": str(exc)}, indent=2)

    def find_forms(self) -> str:
        """Find all forms on the current page."""
        if not self._page:
            return json.dumps({"action": "find_forms", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            forms = self._page.query_selector_all("form")
            form_data = []
            for i, form in enumerate(forms):
                action = form.get_attribute("action") or ""
                method = form.get_attribute("method") or "get"
                fields = []
                for inp in form.query_selector_all("input, select, textarea"):
                    fields.append({
                        "type": inp.get_attribute("type") or "text",
                        "name": inp.get_attribute("name") or "",
                        "id": inp.get_attribute("id") or "",
                        "placeholder": inp.get_attribute("placeholder") or "",
                    })
                form_data.append({"index": i, "action": action, "method": method, "fields": fields})

            return json.dumps({"action": "find_forms", "ok": True, "forms": form_data}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "find_forms", "ok": False, "error": str(exc)}, indent=2)

    def download(self, url: str = None, filename: str = None) -> str:
        """Download a file."""
        try:
            if url:
                import urllib.request
                if not filename:
                    filename = url.split("/")[-1] or "download"
                    # Clean filename
                    filename = re.sub(r'[^\w\-_\.]', '_', filename)
                filepath = self.download_dir / filename
                urllib.request.urlretrieve(url, str(filepath))
                return json.dumps({
                    "action": "download",
                    "ok": True,
                    "path": str(filepath),
                    "filename": filename,
                    "size": filepath.stat().st_size,
                }, indent=2)
            elif self._page:
                # Find downloadable files on page
                pdf_links = []
                for el in self._page.query_selector_all("a[href]"):
                    href = el.get_attribute("href") or ""
                    if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
                        full_url = urljoin(self._page.url, href)
                        text = el.inner_text().strip()[:100]
                        pdf_links.append({"url": full_url, "text": text})

                if not pdf_links:
                    return json.dumps({"action": "download", "ok": False, "error": "No downloadable files found"}, indent=2)

                return json.dumps({
                    "action": "download",
                    "ok": True,
                    "available_files": pdf_links[:10],
                    "message": "Found downloadable files. Use download(url=<url>) to download a specific one.",
                }, indent=2)
            else:
                return json.dumps({"action": "download", "ok": False, "error": "No URL and no page loaded"}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "download", "ok": False, "error": str(exc)}, indent=2)

    def screenshot(self, filename: str = "kai_screenshot.png") -> str:
        """Take a screenshot of the current page."""
        if not self._page:
            return json.dumps({"action": "screenshot", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            filepath = self.download_dir / filename
            self._page.screenshot(path=str(filepath), full_page=True)
            return json.dumps({
                "action": "screenshot",
                "ok": True,
                "path": str(filepath),
            }, indent=2)
        except Exception as exc:
            return json.dumps({"action": "screenshot", "ok": False, "error": str(exc)}, indent=2)

    def close(self) -> None:
        """Close the browser."""
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._page = None
        self._pw = None
