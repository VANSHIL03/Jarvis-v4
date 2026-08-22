"""
JARVIS v4 - Document Tools

Section 18's document workflow: scan it, pull the text out, summarise it, turn a
scan into something editable, and write a PDF back. Bound to DocumentAgent, which
handles PDF, DOCX, TXT and image formats through one extraction path.

The three Office creators at the bottom stay bound to FileAgent, where the
python-docx / openpyxl / python-pptx code already lives. They are registered here
rather than in file_tools because a user asking for "a Word document about X" is
thinking about documents, not the filesystem -- and because the LLM picks tools by
reading these descriptions, so grouping them by intent makes it choose better.

Everything here is LOW_RISK: reading a document touches personal data and writing
one creates a file, both worth marking, neither worth interrupting the user over.
"""

from __future__ import annotations

from typing import List

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec

CATEGORY = "documents"

_DOC = ToolParam(
    "path", "string", required=True,
    description="Document to read: PDF, DOCX, TXT, PNG, JPG or JPEG.",
)
_DOC_ALIASES = {
    "file_path": "path",
    "document": "path",
    "doc": "path",
    "image_path": "path",
    "file": "path",
    "filename": "path",
    "name": "path",
}


DOCUMENT_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="scan_document",
        description="Read a document (PDF, DOCX, TXT or a scanned image) and report what is in it.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="document_agent",
        action="scan_document",
        parameters=(_DOC,),
        aliases=_DOC_ALIASES,
        confirm_template="Sir, '{path}' scan kar loon? Haan ya na bataiye.",
        legacy_actions=("scan", "read_document", "scan_pdf", "scan_file"),
    ),
    ToolSpec(
        name="extract_text",
        description="Extract the full plain text of a document, using OCR for scans and images.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="document_agent",
        action="extract_text",
        parameters=(_DOC,),
        aliases=_DOC_ALIASES,
        confirm_template="Sir, '{path}' se text nikal loon? Haan ya na bataiye.",
        legacy_actions=("get_text", "ocr_document", "read_pdf", "document_text"),
    ),
    ToolSpec(
        name="summarize_document",
        description="Summarise a document's key points, optionally saving the summary as a PDF.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="document_agent",
        action="summarize_document",
        parameters=(
            _DOC,
            ToolParam("prompt", "string", default="", description="Extra instructions for the summary."),
            ToolParam("save_to", "string", default="", description="Write the summary to this PDF path."),
        ),
        aliases={
            **_DOC_ALIASES,
            "user_prompt": "prompt", "instruction": "prompt", "question": "prompt",
            "output_path": "save_to", "output": "save_to", "save_as": "save_to",
        },
        confirm_template="Sir, '{path}' ka summary bana doon? Haan ya na bataiye.",
        legacy_actions=("summarise_document", "summarize", "summarize_pdf", "summarise"),
    ),
    ToolSpec(
        name="to_editable_text",
        description="Convert a scan or PDF into an editable Word document.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="document_agent",
        action="to_editable_text",
        parameters=(
            _DOC,
            ToolParam("save_to", "string", default="", description="Output .docx path (default: alongside the source)."),
        ),
        aliases={**_DOC_ALIASES, "output_path": "save_to", "output": "save_to", "save_as": "save_to"},
        confirm_template="Sir, '{path}' ko editable Word file bana doon? Haan ya na bataiye.",
        legacy_actions=("make_editable", "convert_to_word", "to_word", "editable"),
    ),
    ToolSpec(
        name="create_pdf",
        description="Write a PDF from given text, or convert another document into one.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="document_agent",
        action="create_pdf",
        parameters=(
            ToolParam("path", "string", required=True, description="Output PDF path."),
            ToolParam("title", "string", default="", description="Title printed at the top."),
            ToolParam("body", "string", default="", description="Body text of the PDF."),
            ToolParam("source", "string", default="", description="Existing document to convert instead."),
        ),
        aliases={
            "file_path": "path", "save_to": "path", "output_path": "path", "output": "path",
            "name": "path", "filename": "path",
            "content": "body", "text": "body", "message": "body",
            "heading": "title", "subject": "title",
            "from_document": "source", "document": "source", "input": "source",
        },
        confirm_template="Sir, '{path}' naam se PDF bana doon? Haan ya na bataiye.",
        legacy_actions=("make_pdf", "write_pdf", "save_as_pdf", "generate_pdf"),
    ),

    # ------------------------------------------------------- Office creators
    ToolSpec(
        name="create_word_doc",
        description="Create a Word (.docx) document with a title and paragraphs.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="create_word_doc",
        parameters=(
            ToolParam("path", "string", default=None, description="Output .docx path."),
            ToolParam("title", "string", default="Document", description="Document title."),
            ToolParam("paragraphs", "array", default=None, description="List of paragraph strings."),
        ),
        aliases={
            "file_path": "path", "save_to": "path", "name": "path", "filename": "path",
            "heading": "title", "content": "paragraphs", "body": "paragraphs", "lines": "paragraphs",
        },
        confirm_template="Sir, Word document bana doon? Haan ya na bataiye.",
        legacy_actions=("create_word", "make_word_doc", "new_word_doc", "create_docx"),
    ),
    ToolSpec(
        name="create_excel_sheet",
        description="Create an Excel (.xlsx) sheet with headers and rows.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="create_excel_sheet",
        parameters=(
            ToolParam("path", "string", default=None, description="Output .xlsx path."),
            ToolParam("headers", "array", default=None, description="Column headers."),
            ToolParam("rows", "array", default=None, description="Rows, each a list of cell values."),
        ),
        aliases={
            "file_path": "path", "save_to": "path", "name": "path", "filename": "path",
            "columns": "headers", "data": "rows", "records": "rows",
        },
        confirm_template="Sir, Excel sheet bana doon? Haan ya na bataiye.",
        legacy_actions=("create_excel", "make_excel", "new_spreadsheet", "create_xlsx"),
    ),
    ToolSpec(
        name="create_powerpoint",
        description="Create a PowerPoint (.pptx) deck from a list of slides.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="file_agent",
        action="create_powerpoint",
        parameters=(
            ToolParam("path", "string", default=None, description="Output .pptx path."),
            ToolParam("slides", "array", default=None, description="Slides, each {title, bullets}."),
        ),
        aliases={
            "file_path": "path", "save_to": "path", "name": "path", "filename": "path",
            "content": "slides", "decks": "slides", "pages": "slides",
        },
        confirm_template="Sir, presentation bana doon? Haan ya na bataiye.",
        legacy_actions=("create_ppt", "make_presentation", "new_presentation", "create_pptx"),
    ),
]

__all__ = ["DOCUMENT_TOOLS"]
