"""JARVIS v4 Automation Package"""
from automation.system import SystemControl
from automation.input_control import InputControl
from automation.file_manager import FileManager
from automation.browser import PlaywrightBrowser
from automation.office import OfficeAutomation
from automation.email_client import EmailClient

__all__ = [
    "SystemControl", "InputControl", "FileManager", 
    "PlaywrightBrowser", "OfficeAutomation", "EmailClient"
]
