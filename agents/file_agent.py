"""
JARVIS v4 - File Operations & Office Document Agent
"""

from typing import Dict, Any
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

        elif action == "delete_file":
            path = params.get("path", "")
            res = self.file_mgr.delete_file(path)
            return {"status": "success" if res else "error", "path": path}

        elif action == "rename_file":
            src = params.get("src", "")
            new_name = params.get("new_name", "")
            res = self.file_mgr.rename_file(src, new_name)
            return {"status": "success" if res else "error"}

        elif action == "search_files":
            search_dir = params.get("dir", ".")
            pattern = params.get("pattern", "*")
            matches = self.file_mgr.search_files(search_dir, pattern)
            return {"status": "success", "matches": matches}

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
