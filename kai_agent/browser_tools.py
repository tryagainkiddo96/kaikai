"""
Browser Automation for Kai
Adds web browsing, form filling, portal navigation, and document download
to Kai's toolset.

Requires: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import quote_plus
from urllib.parse import unquote
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib import request


class BrowserTools:
    """Browser automation tools for Kai."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.download_dir = workspace / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._browser = None
        self._page = None
        self._pw = None
        self._queue: queue.Queue[tuple[str, tuple[Any, ...], dict[str, Any], queue.Queue[tuple[bool, Any]]]] = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, name="kai-browser-tools", daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            method_name, args, kwargs, result_queue = self._queue.get()
            try:
                method = getattr(self, method_name)
                result_queue.put((True, method(*args, **kwargs)))
            except Exception as exc:
                result_queue.put((False, exc))

    def _call(self, method_name: str, *args: Any, **kwargs: Any) -> str:
        result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
        self._queue.put((method_name, args, kwargs, result_queue))
        ok, payload = result_queue.get()
        if ok:
            return payload
        return json.dumps({"action": method_name, "ok": False, "error": str(payload)}, indent=2)

    def _ensure_browser_impl(self) -> dict:
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

    def _browse_impl(self, url: str) -> str:
        result = self._ensure_browser_impl()
        if not result["ok"]:
            return json.dumps({"action": "browse", "ok": False, "error": result["error"]}, indent=2)

        try:
            if not url.startswith("http"):
                url = "https://" + url
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = self._page.title()
            text = self._page.inner_text("body")[:3000]
            return json.dumps(
                {
                    "action": "browse",
                    "ok": True,
                    "url": self._page.url,
                    "title": title,
                    "text_preview": text,
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "browse", "ok": False, "error": str(exc)}, indent=2)

    def browse(self, url: str) -> str:
        """Navigate to a URL and return page info."""
        return self._call("_browse_impl", url)

    def _search_web_browser_impl(self, query: str, site: str = "") -> str:
        result = self._ensure_browser_impl()
        if not result["ok"]:
            return json.dumps({"action": "search", "ok": False, "error": result["error"]}, indent=2)

        try:
            search_query = f"site:{site} {query}".strip() if site else query
            engines = [
                f"https://duckduckgo.com/html/?q={quote_plus(search_query)}",
                f"https://www.google.com/search?q={quote_plus(search_query)}",
            ]

            results = []
            for search_url in engines:
                self._page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                results = self._extract_search_results()
                if results:
                    break
            if not results:
                results = self._fetch_search_results_http(search_query)

            return json.dumps(
                {
                    "action": "search",
                    "ok": True,
                    "query": query,
                    "site": site,
                    "results": results,
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "search", "ok": False, "error": str(exc)}, indent=2)

    def _extract_search_results(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        selectors = [
            "div.result",
            "article[data-testid='result']",
            "div.g",
        ]
        title_selectors = [
            "a.result__a",
            "h2 a",
            "h3",
            "a[data-testid='result-title-a']",
            "a",
        ]
        snippet_selectors = [
            ".result__snippet",
            "[data-result='snippet']",
            "div.VwiC3b",
            ".snippet",
        ]

        for selector in selectors:
            cards = self._page.query_selector_all(selector)
            if not cards:
                continue
            for el in cards[:10]:
                item = self._extract_result_card(el, title_selectors, snippet_selectors)
                if item and item.get("url"):
                    results.append(item)
            if results:
                return results

        for anchor in self._page.query_selector_all("a[href]")[:40]:
            href = anchor.get_attribute("href") or ""
            text = anchor.inner_text().strip()
            if href.startswith("http") and text and len(text) > 8:
                results.append({"title": text[:180], "url": href, "snippet": ""})
        return results[:10]

    def _extract_result_card(self, el, title_selectors: list[str], snippet_selectors: list[str]) -> dict[str, str] | None:
        title = ""
        url = ""
        snippet = ""

        for selector in title_selectors:
            try:
                node = el.query_selector(selector)
                if not node:
                    continue
                if not title:
                    title = node.inner_text().strip()
                if not url:
                    href = node.get_attribute("href") or ""
                    if href.startswith("http"):
                        url = href
                if title and url:
                    break
            except Exception:
                continue

        for selector in snippet_selectors:
            try:
                node = el.query_selector(selector)
                if node:
                    snippet = node.inner_text().strip()
                    if snippet:
                        break
            except Exception:
                continue

        if not title or not url:
            return None
        return {"title": title[:180], "url": url, "snippet": snippet[:280]}

    def _fetch_search_results_http(self, query: str) -> list[dict[str, str]]:
        urls = [
            f"https://duckduckgo.com/html/?q={quote_plus(query)}",
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
        ]
        headers = {"User-Agent": "Mozilla/5.0"}
        for url in urls:
            try:
                req = request.Request(url, headers=headers)
                with request.urlopen(req, timeout=30) as response:
                    html = response.read().decode("utf-8", errors="replace")
            except Exception:
                continue

            results: list[dict[str, str]] = []
            matches = re.findall(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            for href, raw_title in matches[:10]:
                title = re.sub(r"<[^>]+>", "", raw_title)
                title = unescape(title).strip()
                href = self._normalize_result_url(unescape(href).strip())
                if href and title:
                    results.append({"title": title[:180], "url": href, "snippet": ""})
            if results:
                return results
        return []

    def _normalize_result_url(self, href: str) -> str:
        if href.startswith("//"):
            href = "https:" + href
        try:
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            if "uddg" in query and query["uddg"]:
                return unquote(query["uddg"][0])
        except Exception:
            pass
        return href

    def search_web_browser(self, query: str, site: str = "") -> str:
        """Search Google and return results."""
        return self._call("_search_web_browser_impl", query, site)

    def _get_page_content_impl(self) -> str:
        if not self._page:
            return json.dumps({"action": "page_content", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            text = self._page.inner_text("body")[:5000]
            url = self._page.url
            title = self._page.title()
            return json.dumps(
                {
                    "action": "page_content",
                    "ok": True,
                    "url": url,
                    "title": title,
                    "text": text,
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "page_content", "ok": False, "error": str(exc)}, indent=2)

    def get_page_content(self) -> str:
        """Get text content of the current page."""
        return self._call("_get_page_content_impl")

    def _get_links_impl(self) -> str:
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

    def get_links(self) -> str:
        """Get all links on the current page."""
        return self._call("_get_links_impl")

    def _click_link_impl(self, text: str) -> str:
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
                        return json.dumps(
                            {
                                "action": "click",
                                "ok": True,
                                "clicked_text": link.inner_text().strip(),
                                "href": href,
                                "url": self._page.url,
                                "title": self._page.title(),
                            },
                            indent=2,
                        )
                except Exception:
                    continue
            return json.dumps({"action": "click", "ok": False, "error": f"Link containing '{text}' not found"}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "click", "ok": False, "error": str(exc)}, indent=2)

    def click_link(self, text: str) -> str:
        """Click a link by text."""
        return self._call("_click_link_impl", text)

    def _fill_form_impl(self, data: dict[str, str], form_index: int = 0) -> str:
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

            return json.dumps(
                {
                    "action": "fill_form",
                    "ok": len(errors) == 0,
                    "filled": filled,
                    "errors": errors,
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "fill_form", "ok": False, "error": str(exc)}, indent=2)

    def fill_form(self, data: dict[str, str], form_index: int = 0) -> str:
        """Fill form fields on the current page."""
        return self._call("_fill_form_impl", data, form_index)

    def _find_forms_impl(self) -> str:
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
                    fields.append(
                        {
                            "type": inp.get_attribute("type") or "text",
                            "name": inp.get_attribute("name") or "",
                            "id": inp.get_attribute("id") or "",
                            "placeholder": inp.get_attribute("placeholder") or "",
                        }
                    )
                form_data.append({"index": i, "action": action, "method": method, "fields": fields})

            return json.dumps({"action": "find_forms", "ok": True, "forms": form_data}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "find_forms", "ok": False, "error": str(exc)}, indent=2)

    def find_forms(self) -> str:
        """Find all forms on the current page."""
        return self._call("_find_forms_impl")

    def _download_impl(self, url: str | None = None, filename: str | None = None) -> str:
        try:
            if url:
                result = self._ensure_browser_impl()
                if result["ok"]:
                    browser_download = self._download_via_browser(url, filename)
                    if browser_download.get("ok"):
                        return json.dumps(browser_download, indent=2)

                import urllib.request

                if not filename:
                    filename = url.split("/")[-1] or "download"
                    filename = re.sub(r"[^\w\-_\.]", "_", filename)
                filepath = self.download_dir / filename
                urllib.request.urlretrieve(url, str(filepath))
                return json.dumps(
                    {
                        "action": "download",
                        "ok": True,
                        "path": str(filepath),
                        "filename": filename,
                        "size": filepath.stat().st_size,
                    },
                    indent=2,
                )
            if self._page:
                downloadable_links = []
                for el in self._page.query_selector_all("a[href]"):
                    href = el.get_attribute("href") or ""
                    if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
                        full_url = urljoin(self._page.url, href)
                        text = el.inner_text().strip()[:100]
                        downloadable_links.append({"url": full_url, "text": text})

                if not downloadable_links:
                    return json.dumps({"action": "download", "ok": False, "error": "No downloadable files found"}, indent=2)

                return json.dumps(
                    {
                        "action": "download",
                        "ok": True,
                        "available_files": downloadable_links[:10],
                        "message": "Found downloadable files. Use download(url=<url>) to download a specific one.",
                    },
                    indent=2,
                )
            return json.dumps({"action": "download", "ok": False, "error": "No URL and no page loaded"}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "download", "ok": False, "error": str(exc)}, indent=2)

    def _download_via_browser(self, url: str, filename: str | None = None) -> dict[str, Any]:
        if not self._page:
            return {"action": "download", "ok": False, "error": "No page loaded"}

        try:
            target_url = url
            matched_link = None
            for el in self._page.query_selector_all("a[href]"):
                href = el.get_attribute("href") or ""
                full_url = urljoin(self._page.url, href)
                if full_url == url:
                    matched_link = el
                    target_url = full_url
                    break

            with self._page.expect_download(timeout=30000) as download_info:
                if matched_link is not None:
                    matched_link.click()
                else:
                    self._page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

            download = download_info.value
            suggested = download.suggested_filename or Path(urlparse(target_url).path).name or "download"
            safe_name = filename or suggested
            safe_name = re.sub(r"[^\w\-_\.]", "_", safe_name)
            filepath = self.download_dir / safe_name
            download.save_as(str(filepath))
            return {
                "action": "download",
                "ok": True,
                "path": str(filepath),
                "filename": filepath.name,
                "size": filepath.stat().st_size,
                "url": target_url,
            }
        except Exception as exc:
            return {"action": "download", "ok": False, "error": str(exc), "url": url}

    def download(self, url: str | None = None, filename: str | None = None) -> str:
        """Download a file."""
        return self._call("_download_impl", url, filename)

    def _screenshot_impl(self, filename: str = "kai_screenshot.png") -> str:
        if not self._page:
            return json.dumps({"action": "screenshot", "ok": False, "error": "No page loaded"}, indent=2)

        try:
            filepath = self.download_dir / filename
            self._page.screenshot(path=str(filepath), full_page=True)
            return json.dumps({"action": "screenshot", "ok": True, "path": str(filepath)}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "screenshot", "ok": False, "error": str(exc)}, indent=2)

    def screenshot(self, filename: str = "kai_screenshot.png") -> str:
        """Take a screenshot of the current page."""
        return self._call("_screenshot_impl", filename)

    def _close_impl(self) -> None:
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

    def close(self) -> None:
        """Close the browser."""
        self._call("_close_impl")
