"""
JARVIS v4 - File Explorer Operations Manager
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.logger import logger

class FileManager:
    #: Spoken shorthands for the common Windows folders.
    well_known = {
        "desktop": Path.home() / "Desktop",
        "documents": Path.home() / "Documents",
        "downloads": Path.home() / "Downloads",
        "pictures": Path.home() / "Pictures",
        "music": Path.home() / "Music",
        "videos": Path.home() / "Videos",
        "home": Path.home(),
    }

    def resolve_path(self, raw_path: str) -> Path:
        """
        Turns a spoken path into a real one.

        A bare name means the Desktop, matching create_folder's long-standing
        behaviour, so "notes.txt banao" lands somewhere the user can see rather
        than in whatever directory JARVIS happens to be running from.
        """
        text = str(raw_path or "").strip().strip('"').strip("'")
        if not text:
            return Path.home() / "Desktop"

        expanded = Path(os.path.expandvars(os.path.expanduser(text)))
        if expanded.is_absolute():
            return expanded

        first, _, rest = text.replace("\\", "/").partition("/")
        base = self.well_known.get(first.strip().lower())
        if base is not None:
            return base / rest if rest else base
        return Path.home() / "Desktop" / expanded

    def create_folder(self, folder_path: str) -> bool:
        """Creates directory folder path. Resolves relative path to Desktop if not absolute."""
        try:
            path = Path(folder_path)
            if not path.is_absolute():
                path = Path.home() / "Desktop" / path.name
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Folder created on Desktop: {path}")
            return True
        except Exception as e:
            logger.error(f"Error creating folder '{folder_path}': {e}")
            return False

    def create_file(self, file_path: str, content: str = "") -> Dict[str, Any]:
        """Creates a text file (refusing to clobber an existing one)."""
        path = self.resolve_path(file_path)
        try:
            if path.exists():
                return {
                    "status": "error",
                    "path": str(path),
                    "message": f"'{path.name}' already exists. Use write_file to overwrite it.",
                }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content or "", encoding="utf-8")
            logger.info(f"File created: {path}")
            return {"status": "success", "path": str(path), "bytes": len(content or "")}
        except Exception as e:
            logger.error(f"Error creating file '{file_path}': {e}")
            return {"status": "error", "path": str(path), "message": str(e)}

    def read_file(self, file_path: str, max_chars: int = 8000) -> Dict[str, Any]:
        """Reads a text file, truncating very long content."""
        path = self.resolve_path(file_path)
        try:
            if not path.exists():
                return {"status": "not_found", "path": str(path), "message": f"'{path}' not found."}
            if path.is_dir():
                return {"status": "error", "path": str(path), "message": f"'{path}' is a folder."}
            text = path.read_text(encoding="utf-8", errors="replace")
            truncated = len(text) > max_chars
            return {
                "status": "success",
                "path": str(path),
                "text": text[:max_chars],
                "truncated": truncated,
                "chars": len(text),
            }
        except Exception as e:
            logger.error(f"Error reading file '{file_path}': {e}")
            return {"status": "error", "path": str(path), "message": str(e)}

    def write_file(self, file_path: str, content: str = "", append: bool = False) -> Dict[str, Any]:
        """Writes (or appends) text to a file, creating parent folders as needed."""
        path = self.resolve_path(file_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a" if append else "w", encoding="utf-8") as handle:
                handle.write(content or "")
            logger.info(f"{'Appended to' if append else 'Wrote'} file: {path}")
            return {
                "status": "success",
                "path": str(path),
                "appended": bool(append),
                "bytes": len(content or ""),
            }
        except Exception as e:
            logger.error(f"Error writing file '{file_path}': {e}")
            return {"status": "error", "path": str(path), "message": str(e)}

    def open_folder(self, folder_path: str) -> Dict[str, Any]:
        """Opens a folder (or a file's containing folder) in File Explorer."""
        path = self.resolve_path(folder_path)
        try:
            if not path.exists():
                return {"status": "not_found", "path": str(path), "message": f"'{path}' not found."}
            target = path if path.is_dir() else path.parent
            os.startfile(str(target))
            logger.info(f"Opened folder in Explorer: {target}")
            return {"status": "success", "path": str(target)}
        except Exception as e:
            logger.error(f"Error opening folder '{folder_path}': {e}")
            return {"status": "error", "path": str(path), "message": str(e)}

    def rename_file(self, src_path: str, new_name: str) -> bool:
        """Renames file or folder."""
        try:
            src = Path(src_path)
            dst = src.parent / new_name
            src.rename(dst)
            logger.info(f"Renamed '{src_path}' -> '{dst}'")
            return True
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            return False

    def delete_file(self, target_path: str) -> bool:
        """Deletes file or directory."""
        try:
            path = Path(target_path)
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            logger.info(f"Deleted path: {target_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting path '{target_path}': {e}")
            return False

    def copy_file(self, src_path: str, dst_path: str) -> bool:
        """Copies file to destination."""
        try:
            shutil.copy2(src_path, dst_path)
            logger.info(f"Copied '{src_path}' -> '{dst_path}'")
            return True
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            return False

    def move_file(self, src_path: str, dst_path: str) -> bool:
        """Moves file to destination."""
        try:
            shutil.move(src_path, dst_path)
            logger.info(f"Moved '{src_path}' -> '{dst_path}'")
            return True
        except Exception as e:
            logger.error(f"Error moving file: {e}")
            return False

    def search_files(self, search_dir: str, pattern: str) -> List[str]:
        """Searches files matching glob pattern inside search directory."""
        try:
            path = Path(search_dir)
            matches = [str(p) for p in path.rglob(pattern)]
            return matches[:50]
        except Exception as e:
            logger.error(f"Error searching files in '{search_dir}': {e}")
            return []
