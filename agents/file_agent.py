"""
JARVIS v4 - File Operations & Office Document Agent
"""

from typing import Dict, Any
from pathlib import Path
from agents.base_agent import BaseAgent
from automation.file_manager import FileManager
from automation.office import OfficeAutomation

class FileAgent(BaseAgent):
    def __init__(self, file_manager: FileManager, office_auto: OfficeAutomation):
        self.file_mgr = file_manager
        self.office = office_auto

    @property
    def agent_name(self) -> str:
        return "file_agent"

    @property
    def description(self) -> str:
        return "Manages Windows file system operations and generates/summarizes Word, Excel, PowerPoint, and PDF files."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "create_folder":
            path = params.get("path", "")
            res = self.file_mgr.create_folder(path)
            return {"status": "success" if res else "error", "path": path}

        elif action in ["create_file", "make_file", "new_file"]:
            path = params.get("path", "")
            content = params.get("content", "")
            return self.file_mgr.create_file(path, content)

        elif action in ["read_file", "open_file_text", "show_file"]:
            path = params.get("path", "")
            return self.file_mgr.read_file(path, max_chars=int(params.get("max_chars", 8000) or 8000))

        elif action in ["write_file", "save_file", "append_file"]:
            path = params.get("path", "")
            content = params.get("content", "")
            append = bool(params.get("append", action == "append_file"))
            return self.file_mgr.write_file(path, content, append=append)

        elif action in ["open_folder", "open_directory", "show_folder"]:
            path = params.get("path", "")
            return self.file_mgr.open_folder(path)

        elif action in ["copy_file", "copy"]:
            src = str(self.file_mgr.resolve_path(params.get("src", "")))
            dst = str(self.file_mgr.resolve_path(params.get("dst", "")))
            res = self.file_mgr.copy_file(src, dst)
            return {
                "status": "success" if res else "error",
                "src": src,
                "dst": dst,
                "message": "" if res else f"'{src}' copy nahi ho payi.",
            }

        elif action in ["move_file", "move"]:
            src = str(self.file_mgr.resolve_path(params.get("src", "")))
            dst = str(self.file_mgr.resolve_path(params.get("dst", "")))
            res = self.file_mgr.move_file(src, dst)
            return {
                "status": "success" if res else "error",
                "src": src,
                "dst": dst,
                "message": "" if res else f"'{src}' move nahi ho payi.",
            }

        elif action == "delete_file":
            path = str(self.file_mgr.resolve_path(params.get("path", "")))
            if not Path(path).exists():
                return {
                    "status": "not_found",
                    "path": path,
                    "message": f"'{path}' exist hi nahi karta, isliye kuch delete nahi kiya.",
                }
            res = self.file_mgr.delete_file(path)
            return {
                "status": "success" if res else "error",
                "path": path,
                "message": "" if res else f"'{path}' delete nahi ho payi.",
            }

        elif action == "rename_file":
            src = str(self.file_mgr.resolve_path(params.get("src", "")))
            new_name = params.get("new_name", "")
            if not Path(src).exists():
                return {
                    "status": "not_found",
                    "path": src,
                    "message": f"'{src}' exist hi nahi karta.",
                }
            res = self.file_mgr.rename_file(src, new_name)
            return {
                "status": "success" if res else "error",
                "src": src,
                "new_name": new_name,
            }

        elif action == "search_files":
            search_dir = params.get("dir", ".")
            resolved_dir = str(self.file_mgr.resolve_path(search_dir)) if search_dir != "." else "."
            pattern = params.get("pattern", "*")
            matches = self.file_mgr.search_files(resolved_dir, pattern)
            return {
                "status": "success",
                "dir": resolved_dir,
                "pattern": pattern,
                "count": len(matches),
                "matches": matches,
                "speech_reply": (
                    f"Ji Sir, {len(matches)} file mili."
                    if matches else "Sir, is pattern se koi file nahi mili."
                ),
            }

        elif action == "create_word_doc":
            path = params.get("path", "doc.docx")
            title = params.get("title", "Document")
            paragraphs = params.get("paragraphs", [])
            res = self.office.create_word_document(path, title, paragraphs)
            return {"status": "success" if res else "error", "path": path}

        elif action == "create_excel_sheet":
            path = params.get("path", "sheet.xlsx")
            headers = params.get("headers", [])
            rows = params.get("rows", [])
            res = self.office.create_excel_sheet(path, headers, rows)
            return {"status": "success" if res else "error", "path": path}

        elif action == "create_powerpoint":
            path = params.get("path", "presentation.pptx")
            slides = params.get("slides", [])
            res = self.office.create_powerpoint_presentation(path, slides)
            return {"status": "success" if res else "error", "path": path}

        elif action == "read_pdf":
            path = params.get("path", "")
            text = self.office.read_pdf(path)
            return {"status": "success", "text_snippet": text[:1000]}

        return {"status": "error", "message": f"Unknown file action: '{action}'"}
