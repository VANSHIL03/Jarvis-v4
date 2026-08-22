"""
JARVIS v4 - File System Tools

Create, read, write, copy, move, rename, delete, search -- all bound to the
existing FileAgent, all speaking one canonical parameter name: `path`. The
planner used to emit `folder_path` while FileAgent read `path`, so "make a folder
called Notes" reported success and created nothing; the aliases below make both
spellings arrive as the same argument.

Section 12/16 shape the levels: reading and creating are SAFE, anything that
overwrites or relocates is LOW_RISK, and delete_file is DANGEROUS with a
confirmation question that names the exact path -- deletion is the one file
operation with no undo.

Nothing here touches the filesystem at import or match time. The matcher's job
is to identify the request; only the tool execution below, after the permission
gate, is allowed to change disk.
"""

from __future__ import annotations

from typing import List

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec

CATEGORY = "files"

#: Every spelling the fast-paths and the LLM have used for "the target path".
PATH_ALIASES = {
    "folder_path": "path",
    "file_path": "path",
    "filepath": "path",
    "dir_path": "path",
    "directory": "path",
    "folder": "path",
    "target": "path",
    "target_path": "path",
    "name": "path",
    "file_name": "path",
    "filename": "path",
}

_PATH = ToolParam(
    "path", "string", required=True,
    description="File or folder path. A bare name resolves to the Desktop; "
                "'downloads/x.txt' resolves under the Downloads folder.",
)
_CONTENT = ToolParam("content", "string", default="", description="Text content.")

_SRC = ToolParam("src", "string", required=True, description="Source path.")
_DST = ToolParam("dst", "string", required=True, description="Destination path.")
_COPY_ALIASES = {
    "source": "src",
    "src_path": "src",
    "from": "src",
    "from_path": "src",
    "path": "src",
    "file_path": "src",
    "destination": "dst",
    "dest": "dst",
    "dst_path": "dst",
    "to": "dst",
    "to_path": "dst",
}


FILE_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="create_folder",
        description="Create a folder (defaults to the Desktop when given a bare name).",
        permission=P.SAFE,
        category=CATEGORY,
        agent="file_agent",
        action="create_folder",
        parameters=(_PATH,),
        aliases=PATH_ALIASES,
        legacy_actions=("make_folder", "new_folder", "create_directory", "mkdir"),
    ),
    ToolSpec(
        name="create_file",
        description="Create a new text file with optional content. Refuses to overwrite an existing file.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="file_agent",
        action="create_file",
        parameters=(_PATH, _CONTENT),
        aliases={**PATH_ALIASES, "text": "content", "body": "content", "data": "content"},
        legacy_actions=("make_file", "new_file"),
    ),
    ToolSpec(
        name="read_file",
        description="Read a text file's contents.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="file_agent",
        action="read_file",
        parameters=(
            _PATH,
            ToolParam("max_chars", "integer", default=8000, description="Truncate after this many characters."),
        ),
        aliases=PATH_ALIASES,
        legacy_actions=("show_file", "open_file_text", "cat_file"),
    ),
    ToolSpec(
        name="write_file",
        description="Write or append text to a file, creating it and its parent folders if needed.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="write_file",
        parameters=(
            _PATH,
            _CONTENT,
            ToolParam("append", "boolean", default=False, description="Append instead of overwriting."),
        ),
        aliases={**PATH_ALIASES, "text": "content", "body": "content", "data": "content"},
        confirm_template="Sir, '{path}' me content likh doon?",
        legacy_actions=("save_file", "append_file", "overwrite_file"),
    ),
    ToolSpec(
        name="copy_file",
        description="Copy a file to another location.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="copy_file",
        parameters=(_SRC, _DST),
        aliases=_COPY_ALIASES,
        confirm_template="Sir, '{src}' ko '{dst}' par copy kar doon?",
        legacy_actions=("copy",),
    ),
    ToolSpec(
        name="move_file",
        description="Move a file to another location.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="move_file",
        parameters=(_SRC, _DST),
        aliases=_COPY_ALIASES,
        confirm_template="Sir, '{src}' ko '{dst}' par move kar doon?",
        legacy_actions=("move",),
    ),
    ToolSpec(
        name="rename_file",
        description="Rename a file or folder in place.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="rename_file",
        parameters=(
            _SRC,
            ToolParam("new_name", "string", required=True, description="New name (not a full path)."),
        ),
        aliases={
            "path": "src", "file_path": "src", "source": "src", "src_path": "src",
            "old_name": "src", "from": "src",
            "name": "new_name", "to": "new_name", "new": "new_name",
        },
        confirm_template="Sir, '{src}' ka naam '{new_name}' kar doon?",
        legacy_actions=("rename", "rename_folder"),
    ),
    ToolSpec(
        name="delete_file",
        description="Delete a file or an entire folder. Irreversible, so it always asks first.",
        permission=P.DANGEROUS,
        category=CATEGORY,
        agent="file_agent",
        action="delete_file",
        parameters=(_PATH,),
        aliases=PATH_ALIASES,
        confirm_template="Sir, '{path}' permanently delete karna hai? Ye wapas nahi aayega. Haan ya na bataiye.",
        legacy_actions=("delete", "remove_file", "delete_folder", "remove_folder", "del"),
    ),
    ToolSpec(
        name="open_folder",
        description="Open a folder in File Explorer (a file's parent folder if given a file).",
        permission=P.SAFE,
        category=CATEGORY,
        agent="file_agent",
        action="open_folder",
        parameters=(_PATH,),
        aliases=PATH_ALIASES,
        legacy_actions=("open_directory", "show_folder", "explorer"),
    ),
    ToolSpec(
        name="search_files",
        description="Find files matching a glob pattern inside a folder.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="file_agent",
        action="search_files",
        parameters=(
            ToolParam("pattern", "string", required=True, description="Glob pattern, e.g. '*.pdf'."),
            ToolParam("dir", "string", default=".", description="Folder to search in."),
        ),
        aliases={
            "path": "dir", "folder": "dir", "directory": "dir", "folder_path": "dir",
            "search_dir": "dir", "in": "dir",
            "query": "pattern", "name": "pattern", "glob": "pattern", "file_name": "pattern",
        },
        legacy_actions=("find_files", "search_file", "find_file"),
    ),
]

__all__ = ["FILE_TOOLS", "PATH_ALIASES"]
