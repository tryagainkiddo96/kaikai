from __future__ import annotations

import os
import random
import string
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    PlaywrightError = RuntimeError
    PlaywrightTimeoutError = RuntimeError
    sync_playwright = None


FIELD_PRIORITY = [
    ("verification_code", ["verification code", "security code", "one-time", "otp", "authenticator", "2fa"], True),
    ("password", ["password", "passcode"], True),
    ("email", ["email", "e-mail"], False),
    ("full_name", ["full name"], False),
    ("first_name", ["first name", "given name", "firstname"], False),
    ("last_name", ["last name", "family name", "surname", "lastname"], False),
    ("username", ["username", "user name", "handle"], False),
    ("phone", ["phone", "mobile", "cell"], False),
    ("birthday", ["date of birth", "birth date", "birthday", "dob"], False),
]

SUCCESS_HINTS = [
    "welcome",
    "account created",
    "you are signed in",
    "you're signed in",
    "verify your email",
    "check your email",
]

CAPTCHA_HINTS = [
    "captcha",
    "i'm not a robot",
    "verify you are human",
    "human verification",
]


class BrowserSignupSession:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.pending: dict | None = None
        self.flow: dict = {}
        self.last_user_log = ""

    def has_pending_input(self) -> bool:
        return bool(self.pending)

    def pending_input_is_sensitive(self) -> bool:
        return bool(self.pending and self.pending.get("sensitive"))

    def consume_user_log(self, fallback: str) -> str:
        if self.last_user_log:
            value = self.last_user_log
            self.last_user_log = ""
            return value
        return fallback

    @property
    def current_url(self) -> str:
        try:
            self._focus_latest_page()
            return self.page.url if self.page is not None else ""
        except Exception:
            return ""

    def start(self, url: str, method: str = "email") -> dict:
        chosen_method = self._normalize_method(method)
        try:
            self._ensure_browser()
            assert self.page is not None
            self.flow = {
                "method": chosen_method,
                "signup_url": url,
                "generated_email": self._generated_email_for(chosen_method),
            }
            self.pending = None
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(800)
            self._focus_latest_page()
            self._click_signup_entrypoint()
            self._choose_method(chosen_method)
            return self._advance("browser_signup_start")
        except Exception as exc:
            return {
                "action": "browser_signup_start",
                "ok": False,
                "status": "error",
                "method": chosen_method,
                "url": url,
                "error": str(exc),
                "user_message": f"I could not start the signup browser flow: {exc}",
            }

    def continue_flow(self, answer: str) -> dict:
        response = (answer or "").strip()
        if not self.pending:
            return {
                "action": "browser_signup_continue",
                "ok": False,
                "status": "idle",
                "user_message": "There is no website signup waiting for your reply right now.",
            }

        pending = dict(self.pending)
        self.last_user_log = (
            f"[Provided {pending.get('field', 'signup')} for browser signup]"
            if pending.get("sensitive")
            else response
        )
        self.pending = None

        if pending.get("field") == "manual_continue":
            return self._advance("browser_signup_continue")

        try:
            self._fill_pending_field(pending, response)
            self._click_continue()
            return self._advance("browser_signup_continue")
        except Exception as exc:
            self.pending = pending
            return {
                "action": "browser_signup_continue",
                "ok": False,
                "status": "error",
                "field": pending.get("field"),
                "url": self.current_url,
                "error": str(exc),
                "user_message": f"I hit a snag while filling the signup flow: {exc}",
            }

    def status(self) -> dict:
        return {
            "action": "browser_signup_status",
            "ok": self.page is not None,
            "status": "awaiting_user_input" if self.pending else "active" if self.page is not None else "idle",
            "url": self.current_url,
            "method": self.flow.get("method"),
            "field": self.pending.get("field") if self.pending else None,
            "question": self.pending.get("question") if self.pending else None,
            "generated_email": self.flow.get("generated_email"),
            "user_message": self._status_message(),
        }

    def cancel(self) -> dict:
        self.pending = None
        self.flow = {}
        self.last_user_log = ""
        self._close_browser()
        return {
            "action": "browser_signup_cancel",
            "ok": True,
            "status": "cancelled",
            "user_message": "I closed the signup browser flow.",
        }

    def _ensure_browser(self) -> None:
        if sync_playwright is None:
            raise RuntimeError("Playwright is not available. Install it with `python -m pip install playwright`.")
        if self.page is not None and not self.page.is_closed():
            return
        self._close_browser()
        try:
            self.playwright = sync_playwright().start()
            headless = os.environ.get("KAI_BROWSER_HEADLESS", "").strip().lower() in {"1", "true", "yes", "on"}
            self.browser = self.playwright.chromium.launch(headless=headless, slow_mo=150 if not headless else 0)
            self.context = self.browser.new_context(viewport={"width": 1440, "height": 960})
            self.page = self.context.new_page()
        except Exception as exc:
            self._close_browser()
            raise RuntimeError(
                "Playwright is installed but the Chromium runtime is not ready. "
                "Run `python -m playwright install chromium` once, then retry."
            ) from exc

    def _close_browser(self) -> None:
        for resource in (self.page, self.context, self.browser):
            try:
                if resource:
                    resource.close()
            except Exception:
                pass
        self.page = None
        self.context = None
        self.browser = None
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.playwright = None

    def _focus_latest_page(self) -> None:
        if not self.context:
            return
        pages = [page for page in self.context.pages if not page.is_closed()]
        if pages:
            self.page = pages[-1]

    def _advance(self, action: str) -> dict:
        self._focus_latest_page()
        assert self.page is not None
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        self.page.wait_for_timeout(800)
        self._maybe_autofill_known_fields()
        return self._inspect_page(action)

    def _maybe_autofill_known_fields(self) -> None:
        fields = self._scan_fields()
        email_value = self.flow.get("generated_email")
        if self.flow.get("method") in {"email", "random_email"} and email_value:
            email_field = self._find_field(fields, "email")
            if email_field and not str(email_field.get("value", "")).strip():
                self._fill_pending_field({"match": email_field}, email_value)
                self._click_continue()

    def _inspect_page(self, action: str) -> dict:
        assert self.page is not None
        try:
            body_text = self.page.locator("body").inner_text(timeout=3000).lower()[:6000]
        except PlaywrightError:
            body_text = ""
        if any(hint in body_text for hint in SUCCESS_HINTS):
            return {
                "action": action,
                "ok": True,
                "status": "completed",
                "method": self.flow.get("method"),
                "url": self.current_url,
                "generated_email": self.flow.get("generated_email"),
                "message": "Signup flow appears complete or is waiting on email verification.",
                "user_message": "The site looks signed in or is asking you to verify the email. Check the browser window to confirm the final state.",
            }
        if any(hint in body_text for hint in CAPTCHA_HINTS):
            return self._set_pending(
                action=action,
                field="manual_continue",
                question="The page is asking for a CAPTCHA or human verification. Solve it in the browser, then reply `continue`.",
                sensitive=False,
            )

        fields = self._scan_fields()
        if "accounts.google." in self.current_url:
            google_email = self._find_field(fields, "email")
            if google_email and not str(google_email.get("value", "")).strip():
                return self._set_pending(
                    action=action,
                    field="email",
                    question="Google sign-in is open. Reply with the Google email address to use, or type it directly in the browser.",
                    sensitive=False,
                    match=google_email,
                )
            google_password = self._find_field(fields, "password")
            if google_password:
                return self._set_pending(
                    action=action,
                    field="password",
                    question="Google is asking for the password. Reply with it and I will fill it in, or type it directly in the browser.",
                    sensitive=True,
                    match=google_password,
                )
            google_code = self._find_field(fields, "verification_code")
            if google_code:
                return self._set_pending(
                    action=action,
                    field="verification_code",
                    question="Google needs a verification code. Reply with the code and I will continue.",
                    sensitive=True,
                    match=google_code,
                )
            return self._set_pending(
                action=action,
                field="manual_continue",
                question="Google sign-in is open. Pick the account or approve the prompt in the browser, then reply `continue`.",
                sensitive=False,
            )

        for field_name, keywords, sensitive in FIELD_PRIORITY:
            match = self._find_field(fields, field_name, keywords=keywords)
            if match and self._field_needs_input(match):
                question = self._question_for(field_name)
                if field_name == "email" and self.flow.get("method") == "random_email" and not self.flow.get("generated_email"):
                    question = (
                        "Random-email signup is not configured yet. Reply with an email address to use, "
                        "or set KAI_SIGNUP_EMAIL / KAI_SIGNUP_EMAIL_DOMAIN for automatic aliases."
                    )
                return self._set_pending(
                    action=action,
                    field=field_name,
                    question=question,
                    sensitive=sensitive,
                    match=match,
                )

        return self._set_pending(
            action=action,
            field="manual_continue",
            question="The signup page is open. If you see a consent prompt, account chooser, or one more button, handle it in the browser and reply `continue` when ready.",
            sensitive=False,
        )

    def _set_pending(self, action: str, field: str, question: str, sensitive: bool, match: dict | None = None) -> dict:
        self.pending = {
            "field": field,
            "question": question,
            "sensitive": sensitive,
            "match": match or {},
        }
        return {
            "action": action,
            "ok": True,
            "status": "awaiting_user_input",
            "method": self.flow.get("method"),
            "url": self.current_url,
            "field": field,
            "question": question,
            "sensitive": sensitive,
            "generated_email": self.flow.get("generated_email"),
            "message": question,
            "user_message": question,
        }

    def _fill_pending_field(self, pending: dict, answer: str) -> None:
        assert self.page is not None
        match = pending.get("match") or self._find_field(self._scan_fields(), pending.get("field", ""))
        if not match:
            raise RuntimeError(f"I could not find the {pending.get('field', 'requested')} field anymore.")
        locator = self.page.locator("input, textarea, select").nth(int(match["dom_index"]))
        tag = str(match.get("tag", "input"))
        field_type = str(match.get("type", "")).lower()
        if tag == "select":
            locator.select_option(label=answer)
            return
        if field_type in {"checkbox", "radio"}:
            normalized = answer.strip().lower()
            if normalized in {"yes", "y", "true", "1", "check"}:
                locator.check()
            else:
                locator.uncheck()
            return
        locator.fill(answer)

    def _click_signup_entrypoint(self) -> None:
        if self._scan_fields():
            return
        self._click_first(["sign up", "create account", "register", "join", "get started"])

    def _choose_method(self, method: str) -> None:
        if method == "google":
            if self._click_first(["continue with google", "sign up with google", "google"]):
                self.page.wait_for_timeout(1200)
                self._focus_latest_page()
        else:
            self._click_first(["continue with email", "sign up with email", "use email instead", "email"])

    def _click_continue(self) -> None:
        self._focus_latest_page()
        if not self._click_first(["continue", "next", "submit", "sign up", "create account", "register", "finish", "done"]):
            try:
                self.page.keyboard.press("Enter")
            except Exception:
                return
        self.page.wait_for_timeout(900)
        self._focus_latest_page()

    def _click_first(self, choices: list[str]) -> bool:
        assert self.page is not None
        clickables = self._scan_clickables()
        for choice in choices:
            for item in clickables:
                text = str(item.get("text", "")).strip().lower()
                if text and choice in text:
                    self.page.locator("button, a, [role='button'], input[type='submit'], input[type='button']").nth(
                        int(item["dom_index"])
                    ).click()
                    self.page.wait_for_timeout(800)
                    self._focus_latest_page()
                    return True
        return False

    def _find_field(self, fields: list[dict], field_name: str, keywords: list[str] | None = None) -> dict | None:
        targets = [token.lower() for token in (keywords or [])]
        for field in fields:
            descriptor = self._field_descriptor(field)
            field_type = str(field.get("type", "")).lower()
            if field_name == "email" and (field_type == "email" or "email" in descriptor):
                return field
            if field_name == "password" and field_type == "password":
                return field
            if field_name == "phone" and (field_type == "tel" or "phone" in descriptor or "mobile" in descriptor):
                return field
            if field_name == "birthday" and (field_type == "date" or "birth" in descriptor or "dob" in descriptor):
                return field
            if targets and any(token in descriptor for token in targets):
                return field
        return None

    def _field_needs_input(self, field: dict) -> bool:
        field_type = str(field.get("type", "")).lower()
        if field_type in {"checkbox", "radio"}:
            return not bool(field.get("checked"))
        return not str(field.get("value", "")).strip()

    def _field_descriptor(self, field: dict) -> str:
        parts = [
            field.get("name", ""),
            field.get("id", ""),
            field.get("placeholder", ""),
            field.get("aria_label", ""),
            field.get("label_text", ""),
            field.get("type", ""),
        ]
        return " ".join(str(part) for part in parts if part).lower()

    def _scan_fields(self) -> list[dict]:
        assert self.page is not None
        return list(
            self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll('input, textarea, select')).map((el, index) => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                  const labels = el.labels ? Array.from(el.labels).map(label => label.innerText.trim()).filter(Boolean) : [];
                  return {
                    dom_index: index,
                    tag: el.tagName.toLowerCase(),
                    type: (el.getAttribute('type') || '').toLowerCase(),
                    name: el.getAttribute('name') || '',
                    id: el.id || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    aria_label: el.getAttribute('aria-label') || '',
                    label_text: labels.join(' '),
                    value: el.value || '',
                    checked: !!el.checked,
                    visible,
                    disabled: !!el.disabled
                  };
                }).filter(item => item.visible && !item.disabled)
                """
            )
        )

    def _scan_clickables(self) -> list[dict]:
        assert self.page is not None
        return list(
            self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll("button, a, [role='button'], input[type='submit'], input[type='button']")).map((el, index) => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                  const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                  return {
                    dom_index: index,
                    text,
                    visible,
                    disabled: !!el.disabled
                  };
                }).filter(item => item.visible && !item.disabled && item.text)
                """
            )
        )

    def _generated_email_for(self, method: str) -> str | None:
        configured_email = os.environ.get("KAI_SIGNUP_EMAIL", "").strip()
        if method == "email" and configured_email:
            return configured_email
        if method != "random_email":
            return configured_email or None
        domain = os.environ.get("KAI_SIGNUP_EMAIL_DOMAIN", "").strip()
        if domain:
            token = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
            return f"kai-{token}@{domain}"
        return configured_email or None

    def _normalize_method(self, method: str) -> str:
        lowered = (method or "email").strip().lower().replace("-", "_").replace(" ", "_")
        if lowered in {"google", "email", "random_email"}:
            return lowered
        return "email"

    def _question_for(self, field_name: str) -> str:
        prompts = {
            "email": "Reply with the email address you want to use for this signup.",
            "password": "Reply with the password to use for this signup, or type it directly into the browser.",
            "verification_code": "Reply with the verification code and I will continue.",
            "full_name": "Reply with the full name to use on the site.",
            "first_name": "Reply with the first name to use on the site.",
            "last_name": "Reply with the last name to use on the site.",
            "username": "Reply with the username you want to use.",
            "phone": "Reply with the phone number to use.",
            "birthday": "Reply with the birthday or date of birth in the format the site expects.",
        }
        return prompts.get(field_name, "Reply with the requested value and I will continue the signup.")

    def _status_message(self) -> str:
        if self.pending:
            return self.pending.get("question", "The signup flow is waiting for your next reply.")
        if self.page is not None:
            current = self.current_url
            if current:
                return f"The signup browser is open at {current}."
            return "The signup browser is open."
        return "There is no active signup browser flow."
