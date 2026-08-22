"""
J.A.R.V.I.S. v4 - Advanced Windows Desktop AI Assistant Entry Point
Main application orchestrator launching PySide6 Arc Reactor HUD, local LLM clients,
multi-agent system, STT/TTS services, and background monitors.
"""

import sys
import os

# Register NVIDIA CUDA 12 DLL paths on Windows PATH before importing CUDA modules
for dll_dir in [
    os.path.expanduser(r"~\AppData\Roaming\Python\Python314\site-packages\nvidia\cublas\bin"),
    os.path.expanduser(r"~\AppData\Roaming\Python\Python314\site-packages\nvidia\cudnn\bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cudnn", "bin")
]:
    if os.path.exists(dll_dir):
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(dll_dir)
            except Exception:
                pass
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

import threading
import asyncio
from PySide6.QtWidgets import QApplication

from config.settings import settings
from utils.logger import logger
from memory.memory_manager import MemoryManager
from security.confirmation import ConfirmationBroker
from security.permissions import PermissionPolicy
from security.safety import SafetyManager
from tools import build_registry
from ai.llm_client import LocalLLMClient
from speech.stt import SpeechToText
from speech.tts import TextToSpeech
from vision.analyzer import VisionAnalyzer

from automation.system import SystemControl
from automation.input_control import InputControl
from automation.file_manager import FileManager
from automation.browser import PlaywrightBrowser
from automation.office import OfficeAutomation
from automation.email_client import EmailClient
from automation.git_control import GitControl

from plugins.plugin_manager import PluginManager
from plugins.whatsapp_plugin import WhatsAppPlugin
from plugins.steam_plugin import SteamPlugin
from plugins.unity_plugin import UnityPlugin

from agents.memory_agent import MemoryAgent
from agents.coding_agent import CodingAgent
from agents.browser_agent import BrowserAgent
from agents.windows_agent import WindowsAgent
from agents.whatsapp_agent import WhatsAppAgent
from agents.vision_agent import VisionAgent
from agents.email_agent import EmailAgent
from agents.file_agent import FileAgent
from agents.gaming_agent import GamingAgent
from agents.git_agent import GitAgent
from agents.document_agent import DocumentAgent
from agents.planner_agent import PlannerAgent

from ui.main_window import JarvisMainWindow


def main():
    logger.info("Initializing J.A.R.V.I.S. v4 Production Environment...")

    # 1. PySide6 Qt Application Instance
    app = QApplication(sys.argv)

    # 2. Core Infrastructure & Security
    #
    # The policy, the broker and the registry are built here and shared by every
    # front-end. That sharing is the point: the GUI, the voice loop and the phone
    # all consult one PermissionPolicy and hold their pending confirmations in one
    # ConfirmationBroker, so answering "haan" on the phone satisfies a question
    # that was asked out loud.
    memory_manager = MemoryManager()
    permission_policy = PermissionPolicy()
    confirmation_broker = ConfirmationBroker()
    safety_manager = SafetyManager(
        policy=permission_policy,
        broker=confirmation_broker,
    )
    llm_client = LocalLLMClient()
    stt_engine = SpeechToText()
    tts_engine = TextToSpeech()
    vision_analyzer = VisionAnalyzer()

    # 3. Automation Modules
    sys_control = SystemControl()
    input_control = InputControl()
    file_manager = FileManager()
    browser_auto = PlaywrightBrowser()
    office_auto = OfficeAutomation()
    email_client = EmailClient()
    git_control = GitControl()

    # 4. Plugins
    plugin_manager = PluginManager()
    whatsapp_plugin = plugin_manager.plugins.get("whatsapp", WhatsAppPlugin())
    steam_plugin = plugin_manager.plugins.get("steam", SteamPlugin())
    unity_plugin = plugin_manager.plugins.get("unity", UnityPlugin())

    # 5. Specialized Sub-Agents
    from agents.n8n_agent import N8nAgent
    from automation.n8n_workflow_manager import N8nWorkflowManager
    n8n_manager = N8nWorkflowManager(memory_manager=memory_manager)

    sub_agents = {
        "memory_agent": MemoryAgent(memory_manager),
        "coding_agent": CodingAgent(llm_client),
        "browser_agent": BrowserAgent(browser_auto),
        "windows_agent": WindowsAgent(sys_control, input_control),
        "whatsapp_agent": WhatsAppAgent(whatsapp_plugin),
        "vision_agent": VisionAgent(vision_analyzer),
        "email_agent": EmailAgent(email_client),
        "file_agent": FileAgent(file_manager, office_auto),
        "gaming_agent": GamingAgent(steam_plugin, unity_plugin),
        "git_agent": GitAgent(git_control),
        "n8n_agent": N8nAgent(llm_client, n8n_manager),
        "document_agent": DocumentAgent(
            llm_client=llm_client,
            office_auto=office_auto,
            vision_analyzer=vision_analyzer,
            file_manager=file_manager,
        ),
    }

    # 6. Controlled Tool Registry
    #
    # Section 19: the LLM never gets a shell. It picks a name out of this
    # catalogue, the registry validates the parameters against the tool's schema,
    # the policy decides whether the call needs approval, and only then does the
    # sub-agent run. Every execution path -- regex fast-path, LLM plan, GUI button
    # and phone -- goes through here, so none of them can skip the gate.
    tool_registry = build_registry(
        agents=sub_agents,
        policy=permission_policy,
        db=getattr(memory_manager, "db", None),
    )
    safety_manager.attach(registry=tool_registry, broker=confirmation_broker)
    logger.info(
        f"Tool registry ready: {len(tool_registry)} tools across "
        f"{len(sub_agents)} sub-agents."
    )

    # 7. Executive Planner Agent
    planner_agent = PlannerAgent(
        llm_client=llm_client,
        memory_manager=memory_manager,
        safety_manager=safety_manager,
        agents=sub_agents,
        registry=tool_registry
    )

    # 8. Local Wi-Fi Mobile Remote Server
    from server.web_server import MobileWebServer
    mobile_server = MobileWebServer(planner_agent=planner_agent, port=8000)
    mobile_server.start()

    # 9. Main Arc Reactor HUD Dashboard Window
    main_window = JarvisMainWindow(
        planner_agent=planner_agent,
        tts_engine=tts_engine,
        stt_engine=stt_engine
    )
    main_window.show()

    logger.info("J.A.R.V.I.S. v4 fully operational. Launching PySide6 Event Loop.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
