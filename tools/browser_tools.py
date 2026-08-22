"""
JARVIS v4 - Browser & Web Tools

Everything web-facing routed through the existing Playwright browser: URLs,
Google, YouTube (including playback control of the tab JARVIS itself opened),
Maps, and direct downloads.

Levels are deliberately low here. Opening a page or searching is exactly what a
user expects to happen instantly when they ask for it, and Section 16 says not to
nag about harmless actions. download_file is the one entry that writes bytes from
the internet onto disk, so it carries a confirmation question that names the URL
-- auto-allowed by default, but a single edit to permissions.json turns it into a
prompt without touching this file.
"""

from __future__ import annotations

from typing import List

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec

CATEGORY = "web"


def _media_tool(name: str, action: str, description: str, *legacy: str) -> ToolSpec:
    """The YouTube transport controls take no parameters and differ only in wording."""
    return ToolSpec(
        name=name,
        description=description,
        permission=P.SAFE,
        category=CATEGORY,
        agent="browser_agent",
        action=action,
        legacy_actions=legacy,
    )


BROWSER_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="open_url",
        description="Open a website in the browser. Accepts a full URL or a bare domain like 'github.com'.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="browser_agent",
        action="open_url",
        parameters=(
            ToolParam("url", "string", required=True, description="URL or domain to open."),
        ),
        aliases={"website": "url", "site": "url", "link": "url", "address": "url", "query": "url"},
        legacy_actions=("open_website", "open_site", "browse", "open_link"),
    ),
    ToolSpec(
        name="search_google",
        description="Search Google and read back the top result snippet.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="browser_agent",
        action="search_google",
        parameters=(
            ToolParam("query", "string", required=True, description="What to search for."),
        ),
        aliases={"search_term": "query", "q": "query", "text": "query", "term": "query"},
        legacy_actions=("google", "search", "web_search", "google_search"),
    ),
    ToolSpec(
        name="play_youtube",
        description="Search YouTube and start playing the first result.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="browser_agent",
        action="play_youtube",
        parameters=(
            ToolParam("search_term", "string", required=True, description="Song, video or channel to play."),
        ),
        aliases={"query": "search_term", "song": "search_term", "video": "search_term", "term": "search_term"},
        legacy_actions=("youtube", "play_song", "play_music", "play_video_youtube"),
    ),
    ToolSpec(
        name="open_maps",
        description="Show a place on Google Maps.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="browser_agent",
        action="open_maps",
        parameters=(
            ToolParam("location", "string", required=True, description="Place to look up."),
        ),
        aliases={"query": "location", "place": "location", "address": "location", "destination": "location"},
        legacy_actions=("search_maps", "find_location", "maps"),
    ),
    ToolSpec(
        name="navigate_maps",
        description="Get directions and travel distance between two places on Google Maps.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="browser_agent",
        action="navigate_maps",
        parameters=(
            ToolParam("destination", "string", required=True, description="Where to go."),
            ToolParam("origin", "string", default="", description="Starting point (blank means current location)."),
        ),
        aliases={
            "to": "destination", "location": "destination", "place": "destination",
            "from": "origin", "start": "origin", "source": "origin",
        },
        legacy_actions=("get_distance", "maps_directions", "navigate", "directions"),
    ),

    # ------------------------------------------------- YouTube transport
    _media_tool("pause_video", "pause_video", "Pause the playing YouTube video.", "pause", "pause_music", "pause_song"),
    _media_tool("resume_video", "resume_video", "Resume the paused YouTube video.", "resume", "play_video", "unpause", "resume_music"),
    _media_tool("skip_video", "skip_video", "Skip forward 10 seconds in the YouTube video.", "skip", "forward", "seek_forward"),
    _media_tool("rewind_video", "rewind_video", "Rewind 10 seconds in the YouTube video.", "rewind", "back", "seek_back"),
    _media_tool("next_video", "next_video", "Jump to the next YouTube video in the queue.", "next", "next_song", "next_track"),

    ToolSpec(
        name="download_file",
        description="Download a file from a URL into the Downloads folder.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="browser_agent",
        action="download",
        parameters=(
            ToolParam("url", "string", required=True, description="Direct URL of the file."),
            ToolParam("save_dir", "string", default="", description="Folder to save into (default: Downloads)."),
            ToolParam("file_name", "string", default="", description="Override the saved file name."),
        ),
        aliases={
            "link": "url", "address": "url",
            "dir": "save_dir", "folder": "save_dir", "path": "save_dir", "save_to": "save_dir",
            "name": "file_name", "filename": "file_name",
        },
        confirm_template="Sir, '{url}' se file download kar loon?",
        legacy_actions=("download_url", "save_from_web", "fetch_file"),
    ),
]

__all__ = ["BROWSER_TOOLS"]
