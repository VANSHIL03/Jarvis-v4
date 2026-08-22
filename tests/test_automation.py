"""
JARVIS v4 Unit Tests - System & Office Automation Subsystem
"""

import pytest
import os
import tempfile
from pathlib import Path
from automation.file_manager import FileManager
from automation.office import OfficeAutomation

def test_file_manager():
    fm = FileManager()
    with tempfile.TemporaryDirectory() as tmp_dir:
        folder_path = os.path.join(tmp_dir, "test_folder")
        assert fm.create_folder(folder_path) is True
        assert os.path.exists(folder_path) is True

        file_path = os.path.join(folder_path, "sample.txt")
        with open(file_path, "w") as f:
            f.write("Hello JARVIS")

        matches = fm.search_files(folder_path, "*.txt")
        assert len(matches) == 1

def test_office_automation():
    office = OfficeAutomation()
    with tempfile.TemporaryDirectory() as tmp_dir:
        docx_path = os.path.join(tmp_dir, "test.docx")
        assert office.create_word_document(docx_path, "Title", ["Paragraph 1"]) is True
        assert os.path.exists(docx_path) is True

        xlsx_path = os.path.join(tmp_dir, "test.xlsx")
        assert office.create_excel_sheet(xlsx_path, ["Col1", "Col2"], [["A", 1]]) is True
        assert os.path.exists(xlsx_path) is True
