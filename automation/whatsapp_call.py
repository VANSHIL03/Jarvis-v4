"""
JARVIS v4 - WhatsApp Desktop Voice & Video Call Automation
Drives the native WhatsApp Desktop (WinUI + WebView2) window through Windows UI Automation:
searches a contact by name, verifies the correct chat actually opened, then places the call.
"""

import re
import time
import difflib
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from utils.logger import logger

try:
    from pywinauto import Desktop
except ImportError:
    Desktop = None
    logger.warning("pywinauto not installed. WhatsApp call automation disabled.")

try:
    import pyautogui
except ImportError:
    pyautogui = None

WINDOW_CLASS = "WinUIDesktopWin32WindowClass"
WINDOW_TITLE = "WhatsApp"
SEARCH_BOX_NAME = "Search or start a new chat"
RESULTS_GRID_NAME = "Search results."
VIDEO_CALL_NAME = "Video call"
VOICE_CALL_NAME = "Voice call"

# Sections WhatsApp renders inside the search results grid. "Messages" matches on message
# *body* text, so a chat can surface there for a completely unrelated contact - never call from it.
SECTION_CONTACTS = ("Chats", "Contacts", "Groups")
SECTION_IGNORED = ("Messages", "Channels", "Status updates")

TREE_MAX_DEPTH = 45          # interactive elements live at depth 16-22 in the WebView2 tree
HEADER_BOTTOM_Y = 145        # the chat header strip sits above this window-relative Y
LIST_PANE_RIGHT_X = 700      # the chat list pane ends around x=653
MIN_ROW_WIDTH = 540         # a real result row spans the list pane (~575px); title lines are ~464px
TITLE_LINE_MIN_W = 280       # the row's title line (name + timestamp) is ~451-464px
TITLE_LINE_MAX_W = 545
FUZZY_THRESHOLD = 0.82

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿️‍←-⇿⬀-⯿]",
    flags=re.UNICODE,
)
# Trailing timestamp WhatsApp appends to a chat row's title line.
_DATE_TAIL_RE = re.compile(
    r"\s+(?:yesterday|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{1,2}:\d{2}(?:\s*[ap]\.?m\.?)?)\s*$",
    flags=re.IGNORECASE,
)
_BLOCKED_RE = re.compile(r"contact is blocked", flags=re.IGNORECASE)


def _safe(text: str) -> str:
    """Console-safe rendering for logs - the Windows console is cp1252 and dies on emoji."""
    return (text or "").encode("ascii", "replace").decode("ascii")


def _normalize(name: str) -> str:
    """Lowercases and strips emoji/punctuation so spoken names compare cleanly against UI labels."""
    text = _EMOJI_RE.sub(" ", name or "")
    text = re.sub(r"\((?:you|business)\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[^0-9a-z\s]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


class WhatsAppCallController:
    """Places and ends WhatsApp Desktop voice/video calls via UI Automation."""

    def __init__(self, launch_wait: float = 6.0, search_wait: float = 2.4):
        self.launch_wait = launch_wait
        self.search_wait = search_wait

    # ---------------------------------------------------------------- window plumbing

    def _get_window(self, launch: bool = True):
        """Returns the visible WhatsApp window, launching/restoring it from the tray if needed."""
        if Desktop is None:
            return None

        for attempt in range(2):
            try:
                win = Desktop(backend="uia").window(class_name=WINDOW_CLASS, title=WINDOW_TITLE)
                if win.exists(timeout=2) and win.is_visible():
                    try:
                        if win.is_minimized():
                            win.restore()
                        win.set_focus()
                    except Exception:
                        pass
                    time.sleep(0.5)
                    return win
            except Exception as e:
                logger.debug(f"WhatsApp window lookup attempt {attempt + 1} failed: {e}")

            if not launch or attempt:
                break
            logger.info("WhatsApp window not active - launching via whatsapp: URI.")
            try:
                subprocess.Popen(["cmd", "/c", "start", "", "whatsapp:"], shell=False)
            except Exception as e:
                logger.error(f"Failed to launch WhatsApp Desktop: {e}")
                return None
            time.sleep(self.launch_wait)

        return None

    def _walk(self, root, match, max_depth: int = TREE_MAX_DEPTH) -> List[Any]:
        """Depth-first walk of the UIA tree, deduped - WebView2 reports each subtree twice."""
        found: List[Any] = []
        seen = set()

        def visit(element, depth: int):
            try:
                info = element.element_info
                rect = info.rectangle
                if rect.right > rect.left and match(info):
                    key = (info.control_type, (info.name or "")[:60], rect.left, rect.top)
                    if key not in seen:
                        seen.add(key)
                        found.append(element)
            except Exception:
                pass
            if depth >= max_depth:
                return
            try:
                for child in element.children():
                    visit(child, depth + 1)
            except Exception:
                pass

        visit(root, 0)
        return found

    def _first(self, root, match, max_depth: int = TREE_MAX_DEPTH):
        results = self._walk(root, match, max_depth)
        return results[0] if results else None

    # ---------------------------------------------------------------- search + resolve

    def _find_search_box(self, win):
        """Locates the chat search box.

        WhatsApp exposes the placeholder ("Search or start a new chat") as the Edit's accessible
        name, but that name goes EMPTY as soon as the box holds text or focus - so fall back to
        the only unnamed Edit sitting in the chat-list pane's search strip.
        """
        named = self._first(
            win, lambda i: i.control_type == "Edit" and (i.name or "").strip() == SEARCH_BOX_NAME
        )
        if named is not None:
            return named
        return self._first(
            win,
            lambda i: i.control_type == "Edit"
            and not (i.name or "").strip()
            and i.rectangle.left < LIST_PANE_RIGHT_X
            and 80 < i.rectangle.top < 200,
        )

    def _type_query(self, win, query: str) -> bool:
        """Focuses the chat search box and types the contact name, verifying it landed."""
        for attempt in range(3):
            # Re-assert foreground every attempt: without this, a second search in the same
            # session types into whatever window stole focus and the box keeps its old text.
            try:
                win.set_focus()
                time.sleep(0.25)
            except Exception:
                pass

            search = self._find_search_box(win)
            if search is None:
                # We may be parked on the Calls/Status tab - go back to Chats and retry.
                chats = self._first(
                    win, lambda i: i.control_type == "Button" and (i.name or "") == "Chats"
                )
                if chats is not None:
                    try:
                        chats.click_input()
                        time.sleep(1.2)
                    except Exception:
                        pass
                search = self._find_search_box(win)
            if search is None:
                continue

            try:
                search.click_input()
            except Exception:
                continue
            time.sleep(0.3)

            if pyautogui is not None:
                pyautogui.hotkey("ctrl", "a")
                pyautogui.press("backspace")
                time.sleep(0.2)

            if query.isascii() and pyautogui is not None:
                pyautogui.write(query, interval=0.04)
            else:
                self._paste(query)

            time.sleep(self.search_wait)

            # Verify the text landed; retry if it didn't.
            try:
                actual = search.get_value()
                if actual == query:
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        return False

    def _paste(self, text: str):
        """Clipboard fallback so non-ASCII contact names can still be typed."""
        try:
            subprocess.run("clip", input=text.encode("utf-16-le"), shell=True, timeout=5)
            if pyautogui is not None:
                pyautogui.hotkey("ctrl", "v")
        except Exception as e:
            logger.error(f"Clipboard paste failed for contact query: {e}")

    def _row_label(self, row) -> str:
        """Extracts a clean contact name from a search-result row, dropping the timestamp tail."""
        title = ""
        for child in self._walk(row, lambda i: i.control_type == "DataItem", max_depth=6):
            try:
                rect = child.element_info.rectangle
                width = rect.right - rect.left
                if TITLE_LINE_MIN_W <= width <= TITLE_LINE_MAX_W:
                    title = child.element_info.name or ""
                    break
            except Exception:
                continue
        if not title:
            try:
                title = row.element_info.name or ""
            except Exception:
                title = ""
        return _DATE_TAIL_RE.sub("", title).strip()

    def _collect_candidates(self, win, timeout: float = 8.0) -> List[Dict[str, Any]]:
        """Reads the search results grid, keeping only rows from contact/chat sections.

        Polls rather than reading once: after a cold launch WhatsApp can take several seconds to
        swap the grid from "Chat list" to "Search results." and render the matching rows.
        """
        deadline = time.time() + timeout
        wanted = RESULTS_GRID_NAME.strip().rstrip(".").lower()
        candidates: List[Dict[str, Any]] = []

        while time.time() < deadline:
            grid = self._first(
                win,
                lambda i: i.control_type == "DataGrid"
                and (i.name or "").strip().rstrip(".").lower() == wanted,
            )
            if grid is not None:
                candidates = self._parse_rows(grid)
                if candidates:
                    return candidates
            time.sleep(0.6)

        return candidates

    def _parse_rows(self, grid) -> List[Dict[str, Any]]:
        """Turns result-grid rows into scored candidates, tracking which section each row is under."""
        rows = self._walk(
            grid,
            lambda i: i.control_type == "DataItem"
            and i.rectangle.left < LIST_PANE_RIGHT_X
            and (i.rectangle.right - i.rectangle.left) >= MIN_ROW_WIDTH,
            max_depth=4,
        )
        rows.sort(key=lambda r: r.element_info.rectangle.top)

        candidates: List[Dict[str, Any]] = []
        seen = set()
        section = "Chats"
        for row in rows:
            try:
                name = (row.element_info.name or "").strip()
                height = row.element_info.rectangle.bottom - row.element_info.rectangle.top
            except Exception:
                continue

            # Section headers are short rows whose entire label is the section name.
            if height < 60 and name in SECTION_CONTACTS + SECTION_IGNORED:
                section = name
                continue
            if section in SECTION_IGNORED:
                continue

            label = self._row_label(row)
            if not label:
                continue
            key = (_normalize(label), section)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "label": label,
                    "norm": _normalize(label),
                    "section": section,
                    "blocked": bool(_BLOCKED_RE.search(name)),
                    "element": row,
                }
            )
        return candidates

    def _pick(self, requested: str, candidates: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """Scores candidates: exact match wins, then prefix, then fuzzy. Ambiguity returns no pick."""
        want = _normalize(requested)
        if not want:
            return None, []

        usable = [c for c in candidates if not c["blocked"]]

        exact = [c for c in usable if c["norm"] == want]
        if exact:
            return exact[0], [c["label"] for c in exact]

        prefix = [c for c in usable if c["norm"].startswith(want)]
        if len(prefix) == 1:
            return prefix[0], [prefix[0]["label"]]
        if len(prefix) > 1:
            return None, [c["label"] for c in prefix]

        scored = []
        for c in usable:
            ratio = difflib.SequenceMatcher(None, want, c["norm"]).ratio()
            if ratio >= FUZZY_THRESHOLD:
                scored.append((ratio, c))
        scored.sort(key=lambda t: t[0], reverse=True)
        if len(scored) == 1:
            return scored[0][1], [scored[0][1]["label"]]
        if len(scored) > 1:
            if scored[0][0] - scored[1][0] >= 0.08:
                return scored[0][1], [scored[0][1]["label"]]
            return None, [c["label"] for _, c in scored]

        return None, []

    def _open_chat_header(self, win, expected: str) -> Optional[str]:
        """Returns the open chat's title if the header confirms the intended contact, else None."""
        want = _normalize(expected)
        buttons = self._walk(
            win,
            lambda i: i.control_type == "Button"
            and i.rectangle.top < HEADER_BOTTOM_Y
            and i.rectangle.left > LIST_PANE_RIGHT_X
            and (i.rectangle.right - i.rectangle.left) > 200,
        )
        for button in buttons:
            title = (button.element_info.name or "").strip()
            if not title or title in (VIDEO_CALL_NAME, VOICE_CALL_NAME, "Search", "Menu", "Profile details"):
                continue
            got = _normalize(title)
            if got == want or got.startswith(want) or want in got:
                return title
            if difflib.SequenceMatcher(None, want, got).ratio() >= FUZZY_THRESHOLD:
                return title
        return None

    def _header_call_button(self, win, video: bool):
        """Finds the header call button by EXACT name - chat history holds decoy 'Video call 7 minutes' buttons."""
        target = VIDEO_CALL_NAME if video else VOICE_CALL_NAME
        return self._first(
            win,
            lambda i: i.control_type == "Button"
            and (i.name or "").strip() == target
            and i.rectangle.top < HEADER_BOTTOM_Y
            and i.rectangle.left > LIST_PANE_RIGHT_X,
        )

    # ---------------------------------------------------------------- public API

    def resolve_contact(self, contact: str) -> Dict[str, Any]:
        """Dry run: searches for a contact and reports what would be called, without calling."""
        if Desktop is None:
            return {"status": "error", "message": "pywinauto is required for WhatsApp call automation."}

        win = self._get_window()
        if win is None:
            return {"status": "error", "message": "Could not open the WhatsApp Desktop window."}
        if not self._type_query(win, contact):
            return {"status": "error", "message": "Could not find the WhatsApp search box."}

        candidates = self._collect_candidates(win)
        pick, shortlist = self._pick(contact, candidates)
        if pick is not None:
            return {
                "status": "success",
                "contact": pick["label"],
                "section": pick["section"],
                "message": f"Resolved '{contact}' to WhatsApp contact '{pick['label']}'.",
                "candidates": [c["label"] for c in candidates],
            }
        if shortlist:
            return {
                "status": "ambiguous",
                "message": f"'{contact}' matches multiple WhatsApp contacts.",
                "candidates": shortlist,
            }
        return {
            "status": "not_found",
            "message": f"No WhatsApp contact matched '{contact}'.",
            "candidates": [c["label"] for c in candidates],
        }

    def place_call(self, contact: str, video: bool = True) -> Dict[str, Any]:
        """Searches for the contact, verifies the right chat opened, then starts a video/voice call."""
        kind = "video" if video else "voice"
        if Desktop is None:
            return {"status": "error", "message": "pywinauto is required for WhatsApp call automation."}
        if not (contact or "").strip():
            return {"status": "error", "message": "No contact name was provided to call."}

        win = self._get_window()
        if win is None:
            return {"status": "error", "message": "Could not open the WhatsApp Desktop window."}

        if not self._type_query(win, contact):
            return {"status": "error", "message": "Could not find the WhatsApp search box."}

        candidates = self._collect_candidates(win)
        pick, shortlist = self._pick(contact, candidates)

        if pick is None:
            blocked = [c["label"] for c in candidates if c["blocked"] and _normalize(contact) in c["norm"]]
            if blocked:
                return {
                    "status": "error",
                    "contact": contact,
                    "message": f"'{blocked[0]}' is blocked on WhatsApp, so the call was not placed.",
                }
            if shortlist:
                logger.warning(f"Ambiguous WhatsApp contact '{_safe(contact)}': {_safe(', '.join(shortlist))}")
                return {
                    "status": "ambiguous",
                    "contact": contact,
                    "candidates": shortlist,
                    "message": f"'{contact}' matches {len(shortlist)} contacts, so no call was placed.",
                }
            return {
                "status": "not_found",
                "contact": contact,
                "message": f"No WhatsApp contact matched '{contact}', so no call was placed.",
            }

        target = pick["label"]
        logger.info(f"Opening WhatsApp chat for '{_safe(target)}' to place a {kind} call.")
        try:
            pick["element"].click_input()
        except Exception as e:
            return {"status": "error", "message": f"Could not open the chat for '{target}': {e}"}
        time.sleep(1.8)

        # Safety gate: only call once the header proves the intended chat is actually open.
        confirmed = None
        for _ in range(3):
            confirmed = self._open_chat_header(win, target)
            if confirmed:
                break
            time.sleep(1.0)
        if not confirmed:
            return {
                "status": "error",
                "contact": target,
                "message": f"Opened a chat but could not confirm it belongs to '{target}' - call aborted.",
            }

        button = self._header_call_button(win, video)
        if button is None:
            return {
                "status": "error",
                "contact": confirmed,
                "message": f"No {kind} call button is available in the chat with '{confirmed}'.",
            }

        try:
            button.click_input()
        except Exception as e:
            return {"status": "error", "contact": confirmed, "message": f"Failed to click the {kind} call button: {e}"}

        logger.info(f"WhatsApp {kind} call started with '{_safe(confirmed)}'.")
        return {
            "status": "success",
            "contact": confirmed,
            "call_type": kind,
            "message": f"WhatsApp {kind} call started with {confirmed}.",
        }

    def end_call(self) -> Dict[str, Any]:
        """Hangs up an in-progress WhatsApp call by clicking its End call button."""
        if Desktop is None:
            return {"status": "error", "message": "pywinauto is required for WhatsApp call automation."}

        try:
            windows = Desktop(backend="uia").windows()
        except Exception as e:
            return {"status": "error", "message": f"Could not enumerate windows: {e}"}

        wanted = ("end call", "leave call", "hang up", "decline")
        for win in windows:
            try:
                if not win.is_visible():
                    continue
            except Exception:
                continue
            button = self._first(
                win,
                lambda i: i.control_type == "Button" and (i.name or "").strip().lower() in wanted,
                max_depth=TREE_MAX_DEPTH,
            )
            if button is not None:
                try:
                    button.click_input()
                    logger.info("WhatsApp call ended.")
                    return {"status": "success", "message": "WhatsApp call ended."}
                except Exception as e:
                    return {"status": "error", "message": f"Failed to click End call: {e}"}

        return {"status": "error", "message": "No active WhatsApp call window was found."}
