"""
JARVIS v4 - File Explorer Operations Manager
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.logger import logger

class FileManager:
    def create_folder(self, folder_path: str) -> bool:
        """Creates directory folder path."""
        try:
            Path(folder_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Folder created: {folder_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating folder '{folder_path}': {e}")
            return False

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
