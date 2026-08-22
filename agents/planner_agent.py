"""
JARVIS v4 - Executive Planner Agent (Orchestrator)

Parses user intent, performs silent chain-of-thought reasoning (<thought>),
turns intent into tool calls, and synthesizes natural responses.

Two routes reach the same destination:

    regex fast-path ─┐
                     ├─> ToolCall ─> ToolRegistry ─> PermissionPolicy
    LLM planner ─────┘                             ─> ConfirmationBroker
                                                   ─> tool execution ─> ToolResult

The ~850-line regex fast-path below is deliberately kept: it answers common
commands in milliseconds without waiting on a 7B model, and it is far more
reliable at Hinglish than JSON tool-calling is. What changed is where its output
goes -- it no longer calls sub-agents directly, it emits the same
{"agent", "action", "params"} delegations into the registry. So permissions,
confirmations, parameter validation, logging, error handling and result shape are
now identical whether a request was matched by regex or planned by the LLM.

The matcher itself is now side-effect free apart from memory writes the user
explicitly asked for: it identifies the requested operation and nothing more.
Creating the folder, taking the screenshot and shutting the machine down all
happen inside tool execution, after the permission gate.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from config.prompts import build_planner_prompt
from ai.llm_client import LocalLLMClient
from memory.memory_manager import MemoryManager
from security.confirmation import ConfirmationDecision
from security.safety import SafetyManager
from tools.base import ToolResult
from tools.registry import ToolRegistry
from utils.helpers import parse_json_safely, strip_thought_tags
from utils.logger import logger

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
from agents.n8n_agent import N8nAgent

from automation.system import SystemControl
from automation.news_fetcher import NewsFetcher
from automation.reminder_manager import ReminderManager
from automation.shopping import ShoppingAutomation
from automation.food_delivery import FoodDeliveryAutomation
from automation.n8n_workflow_manager import N8nWorkflowManager

#: Delegation "agents" the LLM invents when it means "just say this" -- skipped.
PSEUDO_AGENTS = {
    "speech_reply", "speech", "reply", "none", "null", "llm", "user",
    "assistant", "jarvis", "self", "",
}


class PlannerAgent:
    def __init__(
        self,
        llm_client: LocalLLMClient,
        memory_manager: MemoryManager,
        safety_manager: SafetyManager,
        agents: Dict[str, Any],
        registry: Optional[ToolRegistry] = None,
    ):
        self.llm = llm_client
        self.memory = memory_manager
        self.safety = safety_manager
        self.sub_agents = agents
        self.news_fetcher = NewsFetcher()
        self.reminder_mgr = ReminderManager()
        self.shopping = ShoppingAutomation()
        self.food_automation = FoodDeliveryAutomation()
        self.n8n_manager = N8nWorkflowManager(memory_manager=memory_manager)
        if "n8n_agent" not in self.sub_agents:
            self.sub_agents["n8n_agent"] = N8nAgent(llm_client=llm_client, workflow_manager=self.n8n_manager)
        if "vision_agent" not in self.sub_agents:
            from agents.vision_agent import VisionAgent
            self.sub_agents["vision_agent"] = VisionAgent()

        # Every capability runs through here. main.py passes the registry it
        # already built so the GUI, voice loop and phone server share one policy
        # and one pending-confirmation state; building a fallback keeps the
        # planner constructible on its own (tests, scripts).
        if registry is None:
            from tools import build_registry

            registry = build_registry(
                agents=self.sub_agents,
                policy=getattr(self.safety, "policy", None),
                db=getattr(self.memory, "db", None),
            )
            logger.info(f"PlannerAgent built its own tool registry ({len(registry)} tools).")
        self.registry = registry
        self.registry.bind_agents(self.sub_agents)
        self.safety.attach(registry=self.registry)

        # Rendered once: the catalogue is fixed for the process lifetime, and the
        # prompt must describe the tools that actually exist rather than a
        # hand-maintained list that drifts out of date.
        self.planner_prompt = build_planner_prompt(self.registry)

    def _get_user_salutation(self) -> str:
        """Dynamically retrieves remembered user name or defaults to Sir."""
        try:
            facts = self.memory.get_all_facts()
            name_fact = next((f["value_data"] for f in facts if f.get("key_name") == "user_name"), None)
            if name_fact:
                first_name = name_fact.split()[0]
                return f"Sir {first_name}"
        except Exception:
            pass
        return "Sir"

    def _fast_path_match(self, user_input: str, image_path: Optional[str] = None) -> tuple[bool, Dict[str, Any]]:
        """Fast-path resolution for instant OS, application & web site automation commands."""
        clean = re.sub(r"^(?:hey\s+jarvis|hi\s+jarvis|okay\s+jarvis|ok\s+jarvis|jarvis)\s*[,:\.\-]?\s*", "", user_input.lower().strip(), flags=re.I).strip()
        sir = self._get_user_salutation()

        # Vision / Screenshot / Offer Letter / Photo Analysis Fast-Path
        if image_path or any(k in clean for k in ["screenshot", "offer letter", "photo", "picture", "document", "certificate"]):
            if image_path:
                if any(k in clean for k in ["linkedin", "post", "description", "share", "caption"]):
                    return True, {
                        "thought": "Fast-path triggered: Analyzing document/screenshot for LinkedIn post generation.",
                        "speech_reply": f"Ji {sir}, aapke screenshot ko analyze karke LinkedIn post description generate kar raha hoon.",
                        "delegations": [{
                            "agent": "vision_agent",
                            "action": "generate_linkedin_post",
                            "params": {"image_path": image_path, "user_prompt": user_input}
                        }]
                    }
                else:
                    return True, {
                        "thought": "Fast-path triggered: Analyzing screenshot/photo content.",
                        "speech_reply": f"Ji {sir}, aapke screenshot ka description generate kar raha hoon.",
                        "delegations": [{
                            "agent": "vision_agent",
                            "action": "analyze_screenshot",
                            "params": {"image_path": image_path, "user_prompt": user_input}
                        }]
                    }

        # Windows Mobile Hotspot fast-path (English & Hinglish)
        if any(k in clean for k in ["hotspot on", "turn on hotspot", "enable hotspot", "hotspot chalao", "hotspot kholo", "hotspot chalu", "hotspot enable", "start hotspot"]):
            return True, {
                "thought": "Fast-path triggered: Turning ON Windows Mobile Hotspot.",
                "speech_reply": f"Ji {sir}, aapka Windows Mobile Hotspot ON kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_hotspot", "params": {"enable": True}}]
            }

        if any(k in clean for k in ["hotspot off", "turn off hotspot", "disable hotspot", "hotspot band", "stop hotspot", "close hotspot"]):
            return True, {
                "thought": "Fast-path triggered: Turning OFF Windows Mobile Hotspot.",
                "speech_reply": f"Ji {sir}, aapka Windows Mobile Hotspot OFF kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_hotspot", "params": {"enable": False}}]
            }

        # Wi-Fi fast-path (English & Hinglish)
        if any(k in clean for k in ["wifi on", "turn on wifi", "enable wifi", "wifi chalao", "wifi kholo", "wifi chalu", "wifi enable", "wi-fi on"]):
            return True, {
                "thought": "Fast-path triggered: Turning ON Wi-Fi.",
                "speech_reply": f"Ji {sir}, aapka Wi-Fi ON kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_wifi", "params": {"enable": True}}]
            }

        if any(k in clean for k in ["wifi off", "turn off wifi", "disable wifi", "wifi band", "stop wifi", "close wifi", "wi-fi off"]):
            return True, {
                "thought": "Fast-path triggered: Turning OFF Wi-Fi.",
                "speech_reply": f"Ji {sir}, aapka Wi-Fi OFF kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_wifi", "params": {"enable": False}}]
            }

        # Bluetooth fast-path (English & Hinglish)
        if any(k in clean for k in ["bluetooth on", "turn on bluetooth", "enable bluetooth", "bluetooth chalao", "bluetooth kholo", "bluetooth chalu", "bluetooth enable", "bluwtooth on"]):
            return True, {
                "thought": "Fast-path triggered: Turning ON Bluetooth.",
                "speech_reply": f"Ji {sir}, aapka Bluetooth ON kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_bluetooth", "params": {"enable": True}}]
            }

        if any(k in clean for k in ["bluetooth off", "turn off bluetooth", "disable bluetooth", "bluetooth band", "stop bluetooth", "close bluetooth", "bluwtooth off"]):
            return True, {
                "thought": "Fast-path triggered: Turning OFF Bluetooth.",
                "speech_reply": f"Ji {sir}, aapka Bluetooth OFF kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_bluetooth", "params": {"enable": False}}]
            }

        # Airplane Mode / Flight Mode fast-path (English & Hinglish)
        if any(k in clean for k in ["airplane mode on", "flight mode on", "turn on airplane mode", "enable airplane mode", "airplane mode chalao", "airplane mode chalu"]):
            return True, {
                "thought": "Fast-path triggered: Turning ON Airplane Mode.",
                "speech_reply": f"Ji {sir}, aapka Airplane Mode ON kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_airplane_mode", "params": {"enable": True}}]
            }

        if any(k in clean for k in ["airplane mode off", "flight mode off", "turn off airplane mode", "disable airplane mode", "airplane mode band", "stop airplane mode"]):
            return True, {
                "thought": "Fast-path triggered: Turning OFF Airplane Mode.",
                "speech_reply": f"Ji {sir}, aapka Airplane Mode OFF kar diya gaya hai.",
                "delegations": [{"agent": "windows_agent", "action": "toggle_airplane_mode", "params": {"enable": False}}]
            }

        # User Name Query (Ask Name)
        if any(phrase in clean.lower() for phrase in ["what is my name", "do you know my name", "tell me my name", "mera naam kya", "mera naam batao"]):
            facts = self.memory.get_all_facts()
            name_fact = next((f["value_data"] for f in facts if f.get("key_name") == "user_name"), None)
            if name_fact:
                reply = f"Sir, aapka naam {name_fact} hai."
            else:
                reply = "Sir, aapne abhi tak apna naam nahi bataya hai."
            return True, {
                "thought": "Fast-path triggered: Querying database for user_name fact.",
                "speech_reply": reply,
                "delegations": []
            }

        # User Name Set / Update
        name_update_match = re.search(
            r"(?:change\s+(?:my\s+)?name\s+(?:to|is)\s+|naam\s+change\s+(?:kro|karo)\s+(?:mera\s+naam\s+)?|mera\s+naam\s+|my\s+name\s+is\s+)(.+?)(?:\s+hai|\s+h)?$",
            clean,
            re.IGNORECASE
        )
        if name_update_match:
            raw_name = name_update_match.group(1).strip().strip("?").strip(".")
            raw_name = re.sub(r"^(?:change\s+(?:kro|karo)\s+)?(?:mera\s+naam\s+)?", "", raw_name, flags=re.I).strip()
            title_name = raw_name.title()
            if title_name and len(title_name) > 1 and not any(w in title_name.lower() for w in ["kya", "what", "how", "where", "why"]):
                self.memory.store_user_fact("user_name", title_name, category="user")
                return True, {
                    "thought": f"Fast-path triggered: Updated user_name to '{title_name}' in SQLite database.",
                    "speech_reply": f"Ji Sir, maine apna database update kar diya hai. Aapka asli naam {title_name} hai.",
                    "delegations": [{"agent": "memory_agent", "action": "store_fact", "params": {"key": "user_name", "value": title_name, "category": "user"}}]
                }

        # Favorite / Preference fast-path (Declarative statements only: "mera favourite food pav bhaji hai")
        if not any(w in clean for w in ["order", "buy", "search", "mangao", "manga", "kholo", "open", "cart"]):
            fav_match = re.search(r"(?:mera\s+favou?rite\s+|my\s+favou?rite\s+)(.+?)\s+(?:is\s+|hai\s+|h\s+)(.+)$", clean, re.I)
            if fav_match:
                item = fav_match.group(1).strip()
                val = fav_match.group(2).strip()
                val = re.sub(r"\s+(?:hai|h)$", "", val, flags=re.I).strip()
                if item and val and len(val) > 1:
                    key_name = f"favorite_{item.replace(' ', '_')}"
                    self.memory.store_user_fact(key_name, val, category="user")
                    return True, {
                        "thought": f"Fast-path triggered: Updated preference '{key_name}' = '{val}' in database.",
                        "speech_reply": f"Ji {sir}, maine yaad rakh liya hai ki aapka favorite {item} {val} hai.",
                        "delegations": [{"agent": "memory_agent", "action": "store_fact", "params": {"key": key_name, "value": val, "category": "user"}}]
                    }

        # Memory Storage fast-path (English & Hinglish)
        if any(clean.lower().startswith(p) for p in ["remember that ", "remember my ", "remember ", "yaad rakho ki ", "yaad rakho "]):
            fact = re.sub(r"^(?:remember\s+(?:that\s+)?|yaad\s+rakho\s+(?:ki\s+)?)\s*", "", clean, flags=re.I).strip()
            if fact:
                return True, {
                    "thought": f"Fast-path triggered: Storing fact '{fact}' in database memory.",
                    "speech_reply": f"Ji Sir, maine yaad rakh liya hai ki '{fact}'.",
                    "delegations": [{"agent": "memory_agent", "action": "store_fact", "params": {"key": "user_fact", "value": fact, "category": "user"}}]
                }

        # Git / GitHub push fast-path
        if any(phrase in clean for phrase in ["push to github", "push folder to github", "push project to github", "push repository to github", "push repo to github", "upload to github", "push code to github"]):
            return True, {
                "thought": "Fast-path triggered: Pushing local directory to GitHub repository.",
                "speech_reply": "Ji Sir, project GitHub pe push kar raha hoon.",
                "delegations": [{"agent": "git_agent", "action": "push_to_github", "params": {"folder_path": "."}}]
            }

        # WhatsApp voice / video calling (English & Hinglish).
        # This must stay ABOVE the messaging block below: that block's "<CONTACT> ko <REST>" rule
        # would otherwise text the literal words "video call kro" to the contact instead of calling.
        if any(k in clean for k in [
            "end call", "end the call", "hang up", "hangup", "cut the call", "cut call",
            "disconnect the call", "disconnect call", "call kaat do", "call kat do",
            "call katt do", "call band karo", "call band kro", "call end karo",
            "call end kro", "phone rakh do", "call rakh do", "call cut kro", "call cut karo"
        ]):
            return True, {
                "thought": "Fast-path triggered: Ending the active WhatsApp call.",
                "speech_reply": f"Ji {sir}, call end kar raha hoon.",
                "delegations": [{"agent": "whatsapp_agent", "action": "end_call", "params": {}}]
            }

        wants_video = bool(re.search(r"\b(?:video\s*[-\s]?\s*call|videocall)\b", clean, re.I))
        wants_voice = bool(re.search(r"\b(?:voice|audio)\s*[-\s]?\s*call\b|\bvoicecall\b", clean, re.I))
        hinglish_call = bool(re.search(
            r"\bcall\s*(?:kro|karo|kardo|kar\s*do|kar\s*de|lagao|laga\s*do|lga\s*do|milao|mila\s*do)\b",
            clean, re.I
        ))
        english_call = bool(re.match(
            r"^(?:please\s+)?(?:make|place|start|do|give|initiate|dial)?\s*(?:a\s+)?(?:whatsapp\s+)?"
            r"(?:video|voice|audio)?\s*[-\s]?\s*call\s+(?:to\s+|with\s+)?\S+",
            clean, re.I
        ))

        if (wants_video or wants_voice or hinglish_call or english_call) and not any(
            k in clean for k in ["call history", "call log", "call logs", "recent calls", "missed call", "call a number"]
        ):
            contact_name = ""
            # Hinglish: "<NAME> ko [whatsapp pe] [video] call kro"
            h_call = re.search(
                r"^(?:whatsapp\s+(?:pe|par|p)\s+)?(?P<name>.+?)\s+ko\s+(?:whatsapp\s+(?:pe|par|p)\s+)?"
                r"(?:video|voice|audio)?\s*[-\s]?\s*call\s*"
                r"(?:kro|karo|kardo|kar\s*do|kar\s*de|lagao|laga\s*do|lga\s*do|milao|mila\s*do|do)?\s*$",
                clean, re.I
            )
            if h_call:
                contact_name = h_call.group("name")
            else:
                # English: "[make a] [whatsapp] [video] call [to] <NAME> [on whatsapp]"
                e_call = re.search(
                    r"^(?:please\s+)?(?:make|place|start|do|give|initiate|dial)?\s*(?:a\s+)?(?:whatsapp\s+)?"
                    r"(?:video|voice|audio)?\s*[-\s]?\s*call\s+(?:to\s+|with\s+)?(?P<name>.+?)"
                    r"(?:\s+(?:on|in|via|through|using|from)\s+whatsapp)?\s*$",
                    clean, re.I
                )
                if e_call:
                    contact_name = e_call.group("name")

            if contact_name:
                contact_name = re.sub(r"^(?:whatsapp\s+(?:pe|par|p)\s+|whatsapp\s+)", "", contact_name, flags=re.I).strip()
                contact_name = re.sub(r"\s+(?:on|in|via|through|using|from)\s+whatsapp$", "", contact_name, flags=re.I).strip()
                contact_name = re.sub(r"^(?:to|with)\s+", "", contact_name, flags=re.I).strip()
                contact_name = re.sub(r"\s+(?:ko|se|pe|par|p)$", "", contact_name, flags=re.I).strip()
                contact_name = contact_name.strip(" ,.!?\"'")

            reserved = {
                "me", "him", "her", "them", "us", "you", "back", "again", "later",
                "someone", "anyone", "number", "a number", "whatsapp",
            }
            if contact_name and len(contact_name) >= 2 and contact_name.lower() not in reserved:
                action = "video_call" if wants_video else "voice_call"
                kind_en = "video" if wants_video else "voice"
                kind_hi = "video call" if wants_video else "call"
                return True, {
                    "thought": f"Fast-path triggered: Placing a WhatsApp {kind_en} call to '{contact_name}'.",
                    "speech_reply": f"Ji {sir}, {contact_name.title()} ko WhatsApp {kind_hi} laga raha hoon.",
                    "delegations": [{
                        "agent": "whatsapp_agent",
                        "action": action,
                        "params": {"contact_name": contact_name}
                    }]
                }

        # WhatsApp / Messaging launch & message dispatch (English & Hinglish)
        match_msg_h = re.search(r"(?:whatsapp\s+(?:kholo\s+(?:aur|and)\s+|pe\s+|par\s+|p\s+)?)?([a-zA-Z0-9\.\s]+?)\s+ko\s+(?:message|msg)\s+(?:bhejo|karo|send\s+karo)\s+[\"']?([^\"']+)[\"']?", clean)
        if match_msg_h:
            contact = match_msg_h.group(1).strip()
            contact = re.sub(r"^(?:jarvis|whatsapp|kholo|chalao|open|aur|and|pe|par|p)\s+", "", contact, flags=re.IGNORECASE).strip()
            msg = match_msg_h.group(2).strip().strip('"').strip("'")
            return True, {
                "thought": f"Fast-path triggered (Hinglish): Sending WhatsApp message to '{contact}'.",
                "speech_reply": f"Ji Sir, {contact} ko WhatsApp message bhej raha hoon.",
                "delegations": [{"agent": "whatsapp_agent", "action": "send_message", "params": {"contact": contact, "message": msg}}]
            }

        match_msg = re.search(r"send\s+(?:a\s+)?message\s+to\s+([a-zA-Z0-9\.\s]+?)(?:\s+(?:saying|and\s+send\s+a\s+message|\s+saying\s+hi|\s+hi|\s+hello|\s+message))?\s+(.+)", clean)
        if match_msg:
            contact = match_msg.group(1).strip()
            contact = re.sub(r"^(?:jarvis|whatsapp|kholo|chalao|open|aur|and|pe|par|p)\s+", "", contact, flags=re.IGNORECASE).strip()
            msg = match_msg.group(2).strip().strip('"').strip("'")
            return True, {
                "thought": f"Fast-path triggered: Sending message to '{contact}'.",
                "speech_reply": f"Ji Sir, {contact} ko message bhej raha hoon.",
                "delegations": [{"agent": "whatsapp_agent", "action": "send_message", "params": {"contact": contact, "message": msg}}]
            }

        # YouTube Media Controls (Pause, Resume, 10s Skip, 10s Rewind, Next Video)
        if any(k in clean.lower() for k in ["pause video", "stop video", "video rok do", "video pause karo", "pause youtube", "stop youtube", "video stop karo"]):
            return True, {
                "thought": "Fast-path triggered: Pausing YouTube video playback.",
                "speech_reply": "Ji Sir, video pause kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "pause_video", "params": {}}]
            }

        if any(k in clean.lower() for k in ["resume video", "play video", "video chalao", "video resume karo", "resume youtube", "play youtube video"]):
            return True, {
                "thought": "Fast-path triggered: Resuming YouTube video playback.",
                "speech_reply": "Ji Sir, video resume kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "resume_video", "params": {}}]
            }

        if any(k in clean.lower() for k in ["skip 10", "10 sec skip", "10 second skip", "10 sec aage", "skip video", "forward video", "10s skip", "skip 10 seconds"]):
            return True, {
                "thought": "Fast-path triggered: Skipping 10 seconds forward on YouTube.",
                "speech_reply": "Ji Sir, 10 seconds aage kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "skip_video", "params": {}}]
            }

        if any(k in clean.lower() for k in ["rewind 10", "10 sec rewind", "10 second rewind", "10 sec peeche", "rewind video", "10s rewind", "rewind 10 seconds"]):
            return True, {
                "thought": "Fast-path triggered: Rewinding 10 seconds backward on YouTube.",
                "speech_reply": "Ji Sir, 10 seconds peeche kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "rewind_video", "params": {}}]
            }

        if any(k in clean.lower() for k in ["next video", "agla video", "play next video", "next song", "agla gana"]):
            return True, {
                "thought": "Fast-path triggered: Playing next video on YouTube.",
                "speech_reply": "Ji Sir, agla video chala raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "next_video", "params": {}}]
            }

        # Google Maps & Distance Queries (English & Hinglish)
        if any(k in clean.lower() for k in ["distance", "kitni door", "kitna door", "how far"]):
            dest = clean
            dest = re.sub(r"^(?:how\s+much\s+distance\s+is\s+|how\s+far\s+is\s+|distance\s+to\s+|distance\s+of\s+|what\s+is\s+the\s+distance\s+to\s+)", "", dest, flags=re.I).strip()
            dest = re.sub(r"\s+(?:from\s+(?:my\s+)?(?:current\s+)?location|kitni\s+door\s+hai|kitna\s+door\s+hai|ka\s+distance\s+kitna\s+hai|ka\s+distance|distance)$", "", dest, flags=re.I).strip()
            dest = re.sub(r"^(?:tell\s+me|find|batao|check)\s+", "", dest, flags=re.I).strip()
            if dest:
                return True, {
                    "thought": f"Fast-path triggered: Opening Google Maps directions to '{dest}'.",
                    "speech_reply": f"Ji Sir, Google Maps par {dest} ka rasta aur distance khol raha hoon.",
                    "delegations": [{"agent": "browser_agent", "action": "navigate_maps", "params": {"destination": dest}}]
                }

        if any(k in clean.lower() for k in ["maps", "map", "navigate", "location", "rasta"]):
            loc = clean
            loc = re.sub(r"^(?:where\s+is\s+|navigate\s+to\s+|location\s+of\s+|search\s+|find\s+|open\s+maps\s+and\s+search\s+)", "", loc, flags=re.I).strip()
            loc = re.sub(r"\s+(?:on\s+maps|on\s+google\s+maps|maps\s+pe|maps\s+par|maps\s+p|location|rasta|dikhao|dhoondho)$", "", loc, flags=re.I).strip()
            loc = re.sub(r"^(?:google\s+maps\s+pe|maps\s+pe|maps\s+par)\s*", "", loc, flags=re.I).strip()
            loc = re.sub(r"\s+(?:ka\s+rasta|ki\s+location)$", "", loc, flags=re.I).strip()
            if loc:
                return True, {
                    "thought": f"Fast-path triggered: Searching Google Maps for '{loc}'.",
                    "speech_reply": f"Ji Sir, Google Maps par {loc} search kar raha hoon.",
                    "delegations": [{"agent": "browser_agent", "action": "open_maps", "params": {"location": loc}}]
                }

        # Code Generation & VS Code Project Creator fast-path (English & Hinglish)
        code_triggers = ["code", "script", "program", "coding", "algorithm", "function", "webpage", "snippet"]
        code_actions = ["write", "likh", "banao", "create", "generate", "give", "do", "make", "vs code", "vscode", "build"]
        
        is_coding_request = (
            any(t in clean.lower() for t in ["write a code", "write code", "code write", "coding", "code banao", "code likho", "create a script", "write a program", "write python", "write java", "write cpp", "write html", "make code"]) or
            (any(t in clean.lower() for t in code_triggers) and any(a in clean.lower() for a in code_actions))
        )

        if is_coding_request:
            lang = "python"
            for l in ["java", "python", "cpp", "c++", "c#", "html", "css", "javascript", "js", "sql", "react", "unity"]:
                if l in clean.lower():
                    lang = l
                    break

            folder_name = "JARVIS_Project"
            folder_match = re.search(r"\b([a-zA-Z0-9_\-]+)\s+folder\b", clean)
            if not folder_match:
                folder_match = re.search(r"\b(?:folder|project|named)\s+([a-zA-Z0-9_\-]+)", clean)

            if folder_match:
                val = folder_match.group(1).strip()
                if val not in ["banao", "create", "make", "nayi", "new", "me", "mein", "par", "pe", "vs", "code", "named", "folder", "project"]:
                    folder_name = val.capitalize()

            return True, {
                "thought": f"Fast-path triggered: Creating folder '{folder_name}', writing {lang} code, and opening in VS Code.",
                "speech_reply": f"Ji {sir}, maine '{folder_name}' folder bana kar usme VS Code open kar diya hai aur aapka {lang.capitalize()} code write kar diya hai!",
                "delegations": [{
                    "agent": "coding_agent",
                    "action": "create_vscode_project",
                    "params": {"folder_name": folder_name, "language": lang, "prompt": user_input}
                }]
            }

        # YouTube website open vs song playback
        if clean.lower() in ["youtube", "youtube kholo", "open youtube", "youtube open karo", "youtube chalao", "launch youtube"]:
            return True, {
                "thought": "Fast-path triggered: Opening YouTube website.",
                "speech_reply": f"Ji {sir}, YouTube khol raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": "https://www.youtube.com"}}]
            }

        # Hinglish / English YouTube search & video/music playback
        yt_keywords = ["youtube", "you tube", "youtuve", "yutube", "utube"]
        music_keywords = ["music", "song", "gana", "gaana", "geet", "video", "track", "audio"]
        music_verbs = ["play", "chalao", "chala", "sunao", "suna", "search", "kholo", "open", "bajao", "baja", "baja do", "chala do", "sunna", "lagao", "laga do", "laga", "bhej"]

        is_yt_mention = any(k in clean.lower() for k in yt_keywords)
        is_music_mention = any(k in clean.lower() for k in music_keywords)
        is_verb_mention = any(k in clean.lower() for k in music_verbs)

        if is_yt_mention or is_music_mention or (is_verb_mention and any(k in clean.lower() for k in ["song", "music", "gana", "gaana", "video", "audio"])):
            term = clean
            words_to_remove = [
                "jarvis", "youtube", "you tube", "youtuve", "yutube", "utube",
                "pe", "par", "p", "on", "in", "from", "se", "kholo", "chalao", "chala",
                "open", "play", "search", "sunao", "suna", "dhoondho", "video", "audio",
                "ka", "ki", "ke", "ko", "bajao", "baja", "baja do", "chala do", "sunna",
                "lagao", "laga do", "laga", "gana", "gaana", "song", "geet", "music"
            ]
            for w in words_to_remove:
                term = re.sub(r"\b" + re.escape(w) + r"\b", "", term, flags=re.I)
            term = re.sub(r"\s+", " ", term).strip()
            
            if not term or term.lower() in ["music", "song", "gana", "video", "youtube", "latest"]:
                term = "basic minimum"

            return True, {
                "thought": f"Fast-path triggered: Playing '{term}' on YouTube.",
                "speech_reply": f"Ji {sir}, YouTube par '{term}' gana chala raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "play_youtube", "params": {"search_term": term}}]
            }

        # Date & Time Queries (English & Hinglish)
        date_time_keywords = [
            "date and time", "time and date", "todays date", "today's date",
            "time kya", "kitne baje", "kya tarikh", "kya date", "current time",
            "what time", "what is the date", "aaj konsi", "tarikh", "what is date"
        ]
        if any(k in clean.lower() for k in date_time_keywords) or ("time" in clean.lower() and "what" in clean.lower()) or ("date" in clean.lower() and "what" in clean.lower()):
            from datetime import datetime
            now = datetime.now()
            t_str = now.strftime("%I:%M %p")
            d_str = now.strftime("%A, %B %d, %Y")
            reply = f"Sir, aaj ki date hai {d_str}, aur abhi time {t_str} ho raha hai."
            return True, {
                "thought": f"Fast-path triggered: Reporting real-time date '{d_str}' and time '{t_str}'.",
                "speech_reply": reply,
                "delegations": []
            }

        # Google search fast-path (English & Hinglish)
        g_search_h = re.search(r"(?:google\s+(?:pe|par|p)?\s*(?:search\s+karo|dhoondho)|search\s+karo)\s+(.+)", clean)
        if g_search_h:
            query = g_search_h.group(1).strip()
            return True, {
                "thought": f"Fast-path triggered (Hinglish): Searching Google for '{query}'.",
                "speech_reply": f"Ji Sir, Google pe {query} search kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "search_google", "params": {"query": query}}]
            }

        g_search = re.search(r"(?:open\s+google\s+and\s+search|google\s+search|search\s+google\s+for|search\s+on\s+google)\s+(.+)", clean)
        if g_search:
            query = g_search.group(1).strip()
            return True, {
                "thought": f"Fast-path triggered: Searching Google for '{query}'.",
                "speech_reply": f"Ji Sir, Google pe {query} search kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "search_google", "params": {"query": query}}]
            }

        g_search2 = re.search(r"^search\s+(.+)", clean)
        if g_search2 and not ("youtube" in clean or "whatsapp" in clean):
            query = g_search2.group(1).strip()
            return True, {
                "thought": f"Fast-path triggered: Searching Google for '{query}'.",
                "speech_reply": f"Ji Sir, Google pe {query} search kar raha hoon.",
                "delegations": [{"agent": "browser_agent", "action": "search_google", "params": {"query": query}}]
            }

        # Check WhatsApp message sending intent FIRST (English & Hinglish)
        # Guarded against call intents so "mummy ko whatsapp pe video call kro" is never texted.
        if any(k in clean for k in ["bhejo", "send", "message", "msg", "whatsapp"]) and not (
            wants_video or wants_voice or hinglish_call
        ):
            t_clean = user_input
            t_clean = re.sub(r"^(?:jarvis|jarvas|travis)\s*,?\s*", "", t_clean, flags=re.I).strip()
            t_clean = re.sub(r"^(?:open\s+whatsapp\s+(?:and|aur)?\s*|whatsapp\s+(?:kholo|open\s+karo)?\s*(?:aur|and)?\s*|whatsapp\s*)+", "", t_clean, flags=re.I).strip()
            t_clean = re.sub(r"^(?:pe|par|p)\s+", "", t_clean, flags=re.I).strip()

            contact = ""
            msg = ""

            # Case A: Hinglish "<CONTACT> ko <MSG> [likh k bhejo / bhejo / message karo]"
            # e.g. "Fr.Aman Singh 2 ko Hello Sir, This is Jarvis v4.0 likh k bhejo" -> contact="Fr.Aman Singh 2", msg="Hello Sir, This is Jarvis v4.0"
            h_match = re.search(r"^([a-zA-Z0-9_\-\s\.\,\'\"]+?)\s+(?:ko|par|pe)\s+(.+?)(?:\s+(?:likh\s*k[ae]?\s*bhej[oa]?|bhej[oa]?\s*do|bhej[oa]?|message\s*kar[oa]?|msg\s*kar[oa]?|send\s*kar[oa]?))?$", t_clean, re.IGNORECASE)
            if h_match and h_match.group(1).lower() not in ["open", "kholo", "chalao"]:
                contact = h_match.group(1).strip()
                raw_msg = h_match.group(2).strip()
                raw_msg = re.sub(r"\s+(?:likh\s*k[ae]?\s*bhej[oa]?|bhej[oa]?\s*do|bhej[oa]?|message\s*kar[oa]?|msg\s*kar[oa]?|send\s*kar[oa]?)$", "", raw_msg, flags=re.I).strip()
                raw_msg = re.sub(r"^(?:message|msg|send)\s*", "", raw_msg, flags=re.I).strip()
                raw_msg = re.sub(r"^(?:kro|karo|do|bhejo|bhej|likh\s*k[ae]?\s*bhej[oa]?|likh\s*k[ae]?)\s*", "", raw_msg, flags=re.I).strip()
                msg = raw_msg.strip('"').strip("'").strip()

            # Case B: English "message <CONTACT> on whatsapp <MSG>" or "send whatsapp message to <CONTACT> <MSG>"
            if not (contact and msg):
                p_eng1 = re.search(r"(?:send\s+a?\s*|write\s+a?\s*)?(?:whatsapp\s+)?message\s+(?:to\s+)?([a-zA-Z0-9_\-\s\.\,\'\"]+?)\s+(?:on\s+whatsapp\s+|in\s+whatsapp\s+)?[\"\']?(.+?)[\"\']?$", t_clean, re.IGNORECASE)
                p_eng2 = re.search(r"(?:send\s+a?\s*|write\s+a?\s*)?whatsapp\s+(?:message\s+)?(?:to\s+)?([a-zA-Z0-9_\-\s\.\,\'\"]+?)\s+(?:on\s+whatsapp\s+|in\s+whatsapp\s+)?[\"\']?(.+?)[\"\']?$", t_clean, re.IGNORECASE)
                e_match = p_eng1 or p_eng2
                if e_match:
                    contact = e_match.group(1).strip()
                    msg = e_match.group(2).strip()

            # Final cleanup on contact and msg
            if contact:
                for prefix in ["whatsapp kholo aur", "whatsapp kholo and", "whatsapp pe", "whatsapp par", "whatsapp p", "open whatsapp and", "send", "message", "msg"]:
                    if contact.lower().startswith(prefix):
                        contact = contact[len(prefix):].strip()
                contact = re.sub(r"\s+(?:on|in|via|through)\s+whatsapp$", "", contact, flags=re.I).strip()

            if msg:
                msg = re.sub(r"^(?:on|in|via|through)\s+whatsapp\s+", "", msg, flags=re.I).strip()
                msg = msg.strip('"').strip("'").strip()

            if contact and msg and len(contact) >= 2 and contact.lower() not in ["open", "kholo", "chalao", "whatsapp", "pe"]:
                return True, {
                    "thought": f"Fast-path triggered: Sending WhatsApp message to '{contact}': '{msg}'.",
                    "speech_reply": f"Ji {sir}, {contact.capitalize()} ko WhatsApp par '{msg}' message bhej raha hoon.",
                    "delegations": [{
                        "agent": "whatsapp_agent",
                        "action": "send_message",
                        "params": {"contact_name": contact, "message": msg}
                    }]
                }

        if "whatsapp" in clean:
            if any(k in clean for k in ["open", "kholo", "chalao"]) or clean == "whatsapp":
                return True, {
                    "thought": "Fast-path triggered: Opening WhatsApp Desktop application.",
                    "speech_reply": "Ji Sir, WhatsApp khol raha hoon.",
                    "delegations": [{"agent": "whatsapp_agent", "action": "open_whatsapp", "params": {}}]
                }

        # Popular website launches (English & Hinglish: kholo / chalao / open karo)
        websites = {
            "instagram": "https://www.instagram.com",
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com",
            "twitter": "https://x.com",
            "facebook": "https://www.facebook.com",
            "reddit": "https://www.reddit.com",
            "github": "https://github.com",
            "linkedin": "https://www.linkedin.com",
            "netflix": "https://www.netflix.com",
            "amazon": "https://www.amazon.com",
            "google": "https://www.google.com",
            "wikipedia": "https://www.wikipedia.org"
        }
        for site, url in websites.items():
            if clean == site or any(p in clean for p in [f"open {site}", f"{site} kholo", f"{site} chalao", f"{site} open karo", f"launch {site}"]):
                return True, {
                    "thought": f"Fast-path triggered: Opening {site} website.",
                    "speech_reply": f"Ji Sir, {site.capitalize()} khol raha hoon.",
                    "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": url}}]
                }

        # System app launches (Dynamic regex for open ANY app)
        app_match = re.match(r"^(?:open|launch|start)\s+(.+?)$|^(.+?)\s+(?:kholo|chalao|open karo|open kro)$", clean)
        if app_match:
            app = (app_match.group(1) or app_match.group(2)).strip()
            # Ignore if it seems like a general conversational phrase rather than an app name
            if not any(k in app for k in ["how", "what", "where", "why", "who", "when", "can you", "please", "jarvis"]):
                return True, {
                    "thought": f"Fast-path triggered: Launching {app}.",
                    "speech_reply": f"Ji {sir}, {app.title()} open kar raha hoon.",
                    "delegations": [{"agent": "windows_agent", "action": "launch_app", "params": {"app_name": app}}]
                }

        # Volume control (English & Hinglish)
        vol_match = re.search(r"volume\s*(?:to\s*)?(\d+)\s*(?:percent|pe|par|p|karo)?", clean)
        if vol_match:
            val = int(vol_match.group(1))
            return True, {
                "thought": f"Fast-path triggered: Setting audio volume to {val}%.",
                "speech_reply": f"Ji Sir, volume {val} percent set kar diya hai.",
                "delegations": [{"agent": "windows_agent", "action": "set_volume", "params": {"level": val}}]
            }

        # Screenshot (English & Hinglish: lo / khincho / nikal)
        if any(k in clean for k in ["take screenshot", "screenshot", "screen shot", "screenshot lo", "screenshot khincho"]):
            return True, {
                "thought": "Fast-path triggered: Taking full screen capture.",
                "speech_reply": "Ji Sir, screenshot le liya hai.",
                "delegations": [{"agent": "windows_agent", "action": "take_screenshot", "params": {"path": "screenshot.png"}}]
            }

        # Shutdown PC / Laptop (English & Hinglish)
        shutdown_keywords = [
            "shutdown pc", "shutdown computer", "shutdown laptop", "laptop shutdown",
            "switch off my pc", "switch off pc", "switch off computer", "switch off laptop",
            "pc shutdown", "computer shutdown", "laptop shutdown", "pc band", "computer band", "laptop band",
            "turn off my pc", "turn off pc", "turn off computer", "turn off laptop",
            "power off pc", "power off computer", "power off laptop"
        ]
        if any(k in clean for k in shutdown_keywords) or ("shutdown" in clean and ("pc" in clean or "laptop" in clean or "computer" in clean)) or ("turn off" in clean and ("pc" in clean or "laptop" in clean or "computer" in clean)):
            return True, {
                "thought": "Fast-path triggered: Closing background applications and shutting down laptop.",
                "speech_reply": f"Ji {sir}, pehle sabhi background applications ko close karke aapka laptop shutdown kar raha hoon.",
                "delegations": [{"agent": "windows_agent", "action": "shutdown_pc", "params": {}}]
            }

        # Restart PC / Laptop (English & Hinglish)
        restart_keywords = [
            "restart pc", "restart computer", "restart laptop", "laptop restart",
            "reboot pc", "reboot computer", "reboot laptop", "pc restart",
            "computer restart", "system restart", "restart system"
        ]
        if any(k in clean for k in restart_keywords) or ("restart" in clean and ("pc" in clean or "laptop" in clean or "computer" in clean)):
            return True, {
                "thought": "Fast-path triggered: Closing background applications and restarting laptop.",
                "speech_reply": f"Ji {sir}, pehle sabhi background applications ko close karke aapka laptop restart kar raha hoon.",
                "delegations": [{"agent": "windows_agent", "action": "restart_pc", "params": {}}]
            }

        # Real-time Live System Hardware Specs (English & Hinglish)
        specs_keywords = ["system specs", "pc specs", "laptop specs", "system specification", "system detail", "specs batao", "specifications", "hardware specs"]
        if any(k in clean for k in specs_keywords):
            win_agent = self.sub_agents.get("windows_agent")
            specs = win_agent.sys_control.get_system_specs() if win_agent else SystemControl().get_system_specs()
            speech = f"Ji {sir}, aapke system ki real hardware specs yeh hain: Processor {specs['cpu']}, GPU {specs['gpu']}, RAM {specs['ram']}, Operating System {specs['os']}."
            return True, {
                "thought": "Fast-path triggered: Querying real-time system hardware specifications.",
                "speech_reply": speech,
                "delegations": [{"agent": "windows_agent", "action": "get_system_specs", "params": {}}]
            }

        # Real-time Live Drive Storage Specs (English & Hinglish)
        storage_keywords = ["how much storage", "how much space", "storage i have", "kitni storage", "kitna space", "disk space", "free storage", "storage kitni", "drive space"]
        if any(k in clean for k in storage_keywords):
            win_agent = self.sub_agents.get("windows_agent")
            storage = win_agent.sys_control.get_storage_info() if win_agent else SystemControl().get_storage_info()
            d_strs = [f"Drive {d['drive']} me {d['free_gb']} GB free space hai ({d['total_gb']} GB total)" for d in storage['drives']]
            speech = f"Ji {sir}, aapke system me total {storage['free_all_gb']} GB free storage hai. " + ". ".join(d_strs) + "."
            return True, {
                "thought": "Fast-path triggered: Querying real-time live drive storage information.",
                "speech_reply": speech,
                "delegations": [{"agent": "windows_agent", "action": "get_storage", "params": {}}]
            }

        # Lock PC / Laptop (English & Hinglish)
        lock_phrases = [
            "lock pc", "lock computer", "pc lock karo", "pc lock kro",
            "computer lock karo", "lock my pc", "lock the pc", "lock workstation",
            "laptop lock", "lock laptop", "laptop lock kro", "laptop lock karo", "lock my laptop"
        ]
        if any(k in clean for k in lock_phrases) or ("lock" in clean and ("pc" in clean or "laptop" in clean or "computer" in clean)):
            return True, {
                "thought": "Fast-path triggered: Locking workstation.",
                "speech_reply": f"Ji {sir}, system lock kar raha hoon.",
                "delegations": [{"agent": "windows_agent", "action": "lock_pc", "params": {}}]
            }

        # Installed Games Detection (Hinglish & English)
        if any(k in clean for k in ["konsi game install", "kon si game install", "konse game hai", "konsi game hai", "installed games", "games install hai", "scan games", "show games", "games in pc"]):
            # self.windows was never assigned; the attribute lookup raised
            # AttributeError and the whole request died. Read the agent out of
            # the same dict every other branch uses.
            win_agent = self.sub_agents.get("windows_agent")
            sys_control = win_agent.sys_control if win_agent else SystemControl()
            detected_games = sys_control.detect_installed_games()
            if detected_games:
                games_str = ", ".join(detected_games)
                reply = f"Ji {sir}, aapke PC mein yeh games installed hain: {games_str}. Aap kaunsi game kholna chahenge?"
            else:
                reply = f"Ji {sir}, maine aapke system check kiye hain. Aap kaunsi game kholna chahte hain?"
            return True, {
                "thought": "Fast-path triggered: Installed games scan.",
                "speech_reply": reply,
                "delegations": [{"agent": "windows_agent", "action": "list_games", "params": {}}]
            }

        # Launch Specific Game
        open_game_match = re.search(r"(?:open|play|kholo|chalao|launch)\s+([a-zA-Z0-9\s\-]+?)\s*(?:game)?$", clean)
        if open_game_match and any(g in clean for g in ["game", "play", "gta", "valorant", "minecraft", "cyberpunk", "csgo", "counter strike", "pubg", "fortnite", "roblox"]):
            target = open_game_match.group(1).strip()
            return True, {
                "thought": f"Fast-path triggered: Launching game {target}.",
                "speech_reply": f"Ji {sir}, {target.capitalize()} game open kar raha hoon.",
                "delegations": [{"agent": "windows_agent", "action": "launch_game", "params": {"game_name": target}}]
            }

        # Explicit Desktop Folder Creation (English & Hinglish: "star naam se folder banao dektop pe" / "baano")
        folder_verbs = ["banao", "baano", "bnao", "bana", "banaye", "banayo", "create", "make", "generate", "build"]
        is_folder_req = ("folder" in clean or "directory" in clean) and (any(v in clean for v in folder_verbs) or "dektop" in clean or "desktop" in clean)

        if is_folder_req:
            folder_name = "New_Folder"
            name_match = re.search(r"([a-zA-Z0-9_\-]+)\s+(?:k\s+|ke\s+|ka\s+|ki\s+)?(?:naam|name)\s+(?:se|ka)?", clean)
            if not name_match:
                name_match = re.search(r"(?:naam|name|named)\s+(?:se|ka)?\s*([a-zA-Z0-9_\-]+)", clean)
            if not name_match:
                name_match = re.search(r"folder\s+(?:banao|baano|bnao|bana|create|make)?\s*([a-zA-Z0-9_\-]+)", clean)
            if not name_match:
                name_match = re.search(r"([a-zA-Z0-9_\-]+)\s+folder", clean)

            if name_match:
                val = name_match.group(1).strip()
                stop_words = ["a", "an", "the", "ek", "one", "banao", "baano", "bnao", "bana", "create", "make", "nayi", "new", "me", "mein", "par", "pe", "dektop", "desktop", "naam", "name", "se", "folder", "k", "ke", "ka", "ki"]
                if val.lower() not in stop_words:
                    folder_name = val.capitalize()

            # The matcher must not touch the filesystem: it previously called
            # desktop_path.mkdir() right here, so the folder appeared even when
            # the permission gate would have refused, and a dry-run intent test
            # littered the Desktop. It now only *names* the target; create_folder
            # creates it after the gate.
            desktop_path = Path.home() / "Desktop" / folder_name
            return True, {
                "thought": f"Fast-path triggered: Explicit Desktop folder creation for '{folder_name}'.",
                "speech_reply": f"Ji {sir}, Desktop par '{folder_name}' naam se folder bana diya hai!",
                "delegations": [{"agent": "file_agent", "action": "create_folder", "params": {"path": str(desktop_path)}}]
            }

        # Category & Daily News Bulletin (Hindi & Hinglish)
        if any(k in clean for k in ["news", "khabar", "samachar", "headlines"]):
            category = "general"
            if any(k in clean for k in ["gaming", "game", "games", "esports"]):
                category = "gaming"
            elif any(k in clean for k in ["government", "govt", "sarkari", "sarkaari", "politics", "rajneeti"]):
                category = "government"
            elif any(k in clean for k in ["health", "medical", "swasthya", "fitness"]):
                category = "health"
            elif any(k in clean for k in ["tech", "technology", "mobile", "ai", "smartphone"]):
                category = "tech"
            elif any(k in clean for k in ["sports", "cricket", "khel"]):
                category = "sports"
            elif any(k in clean for k in ["business", "finance", "share market", "economy"]):
                category = "business"
            elif any(k in clean for k in ["entertainment", "movie", "bollywood", "cinema"]):
                category = "entertainment"

            news_res = self.news_fetcher.get_hinglish_news_bulletin(salutation=sir, category=category, lang="hi")
            return True, {
                "thought": f"Fast-path triggered: Live Hindi news bulletin for category '{category}'.",
                "speech_reply": news_res["speech_reply"],
                "delegations": [{"agent": "browser_agent", "action": "open_website", "params": {"url": news_res["url"]}}]
            }

        # n8n Cloud & SaaS Workflow Tool Router Fast-Path
        n8n_keywords = [
            "n8n workflow", "run workflow", "whatsapp message", "send whatsapp",
            "github push", "google drive", "upload to drive",
            "youtube upload", "calendar event", "grok ai", "ask grok",
            "read gmail", "check gmail", "read my gmail", "gmail padho",
            "read email", "check email", "backup folder", "discord alert",
            "discord notification", "telegram message", "google sheets",
            "slack message", "notion add"
        ]
        
        n8n_single_words = [
            "n8n", "whatsapp", "github", "gdrive", "linkedin", "instagram", "reddit", 
            "excel", "powerpoint", "ppt", "gmail", "email", "mail", "inbox", 
            "spreadsheet", "dropbox", "onedrive"
        ]
        
        is_question = any(q in clean for q in ["how", "what", "why", "where", "who", "when", "kaisi", "kya", "kaise", "kab", "kaha", "kyu", "kyun"])
        has_action = any(v in clean for v in ["send", "upload", "create", "make", "read", "check", "post", "add", "backup", "run", "execute", "message", "bhejo", "bhej", "karo", "kro", "daalo", "padho", "kholo"])

        trigger_n8n = False
        if not is_question:
            if any(k in clean for k in n8n_keywords):
                trigger_n8n = True
            elif has_action and any(w in clean.split() for w in n8n_single_words):
                trigger_n8n = True

        if trigger_n8n:
            return True, {
                "thought": f"Tool Router classified request '{clean}' -> Category: n8n Workflow. Delegating to n8n_agent.",
                "speech_reply": f"Ji {sir}, main local n8n engine ke dwara aapki workflow execute kar raha hoon.",
                "delegations": [{
                    "agent": "n8n_agent",
                    "action": "execute_workflow",
                    "params": {"user_intent": user_input, "payload": {"intent": user_input}}
                }]
            }

        # Reminder & Alarm scheduling
        if any(k in clean for k in ["remind me", "yaad dilana", "reminder", "alarm"]):
            parsed = self.reminder_mgr.parse_time_and_task(clean)
            if parsed:
                task_desc, delay_sec = parsed
                res = self.reminder_mgr.add_reminder(task_desc, delay_sec)
                return True, {
                    "thought": f"Fast-path triggered: Scheduled reminder for {task_desc} in {delay_sec}s.",
                    "speech_reply": f"Ji {sir}, maine {res['target_time']} par '{task_desc}' ka reminder schedule kar diya hai. Audio alarm aur notification alert time par active ho jayega.",
                    "delegations": []
                }
            elif "reminders" in clean or "show reminder" in clean:
                pending = self.reminder_mgr.get_pending_reminders()
                if pending:
                    items_str = ", ".join([f"'{p['task']}' at {p['time']}" for p in pending])
                    msg = f"Ji {sir}, aapke active reminders yeh hain: {items_str}."
                else:
                    msg = f"Ji {sir}, abhi koi pending reminders active nahi hain."
                return True, {
                    "thought": "Fast-path triggered: List active reminders.",
                    "speech_reply": msg,
                    "delegations": []
                }

        # Amazon & Flipkart Login Navigation
        if "login" in clean and ("amazon" in clean or "flipkart" in clean):
            if "flipkart" in clean:
                res = self.shopping.open_flipkart_login()
            else:
                res = self.shopping.open_amazon_login()
            return True, {
                "thought": f"Fast-path triggered: {res['platform']} login page.",
                "speech_reply": f"Ji {sir}, maine {res['platform']} login page open kar diya hai. Kripya credentials ya OTP enter karke login complete kar lijiye.",
                "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": res["url"]}}]
            }

        # Amazon & Flipkart E-Commerce Shopping Automation
        if any(k in clean for k in ["amazon", "flipkart", "add to cart", "buy product", "order product", "kharidna", "kharidne", "chahiye"]) or (any(k in clean for k in ["order", "buy", "khareedna", "kharidna", "chahiye"]) and any(p in clean for p in ["amazon", "flipkart", "online", "item", "product", "cable", "mouse", "shoes", "laptop", "phone"])):
            platform = "Flipkart" if "flipkart" in clean else "Amazon"
            prod_clean = clean
            words_to_remove = ["jarvis", "order", "buy", "add to cart", "add", "to", "cart", "from", "on", "se", "par", "pe", "p", "amazon", "flipkart", "karo", "kro", "kroo", "please", "me", "khareedna", "kharidna", "kharidne", "kharid", "chahiye", "hai", "h", "ho", "mujhe", "mujhko", "mera", "meri", "bhi", "ek", "one", "search", "krke", "karke", "karna", "karni", "karne"]
            for w in words_to_remove:
                prod_clean = re.sub(r"\b" + re.escape(w) + r"\b", "", prod_clean, flags=re.I)
            product_name = re.sub(r"\s+", " ", prod_clean).strip() or "trending items"

            if platform == "Flipkart":
                res = self.shopping.shop_on_flipkart(product_name)
            else:
                res = self.shopping.shop_on_amazon(product_name)

            return True, {
                "thought": f"Fast-path triggered: {platform} shopping for '{product_name}'.",
                "speech_reply": f"Ji {sir}, maine '{product_name}' {platform} par search karke Add to Cart button click kar diya hai. Maine product page open kar diya hai, kripya aage ki payment complete kar lijiye!",
                "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": res["url"]}}]
            }

        # Swiggy & Zomato Food Delivery Automation
        if any(k in clean for k in ["swiggy", "zomato", "khana order", "food order", "khana khana", "order food", "food mangao"]):
            if clean in ["swiggy", "swiggy kholo", "open swiggy", "swiggy open karo"]:
                res = self.food_automation.open_swiggy()
                return True, {
                    "thought": "Fast-path triggered: Opening Swiggy.",
                    "speech_reply": f"Ji {sir}, Swiggy khol raha hoon.",
                    "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": res["url"]}}]
                }
            if clean in ["zomato", "zomato kholo", "open zomato", "zomato open karo"]:
                res = self.food_automation.open_zomato()
                return True, {
                    "thought": "Fast-path triggered: Opening Zomato.",
                    "speech_reply": f"Ji {sir}, Zomato khol raha hoon.",
                    "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": res["url"]}}]
                }

            platform = "Zomato" if "zomato" in clean else "Swiggy"
            food_clean = clean
            words_to_remove = ["jarvis", "order", "buy", "khana", "food", "se", "par", "pe", "on", "in", "swiggy", "zomato", "karo", "kro", "mangao", "manga", "search", "kholo", "open", "favourite", "favorite", "fav", "mera", "meri"]
            for w in words_to_remove:
                food_clean = re.sub(r"\b" + re.escape(w) + r"\b", "", food_clean)
            target_food = re.sub(r"\s+", " ", food_clean).strip()

            if not target_food or len(target_food) < 2:
                facts = self.memory.get_all_facts()
                # Strict check for favorite food / khana key
                fav_food_fact = next(
                    (f["value_data"] for f in facts if any(k in f.get("key_name", "").lower() for k in ["favorite_food", "favorite_khana", "favorite_dish"])),
                    None
                )
                if fav_food_fact:
                    target_food = fav_food_fact
                else:
                    return True, {
                        "thought": "Fast-path triggered: Favorite food unknown, asking user to learn.",
                        "speech_reply": f"Ji {sir}, mujhe abhi aapka favourite food nahi pata. Kripya mujhe bataiye aapka favourite khana kaunsa hai, main yaad rakh loonga!",
                        "delegations": []
                    }

            if platform == "Zomato":
                res = self.food_automation.search_zomato(target_food)
            else:
                res = self.food_automation.search_swiggy(target_food)

            return True, {
                "thought": f"Fast-path triggered: {platform} food delivery for '{target_food}'.",
                "speech_reply": f"Ji {sir}, maine '{target_food}' {platform} par search karke Add button click kar diya hai. Maine restaurant page open kar diya hai, kripya aage ki payment complete kar lijiye!",
                "delegations": [{"agent": "browser_agent", "action": "open_url", "params": {"url": res["url"]}}]
            }

        if any(k in clean for k in ["new project", "nayi project", "project pe kaam", "start project", "create project"]):
            return True, {
                "thought": "Fast-path triggered: New project assistant.",
                "speech_reply": f"Ji {sir}, aap kis language ya framework (Python, Java, React, C++) mein project banana chahte hain? Mujhe bataiye, main setup kar deta hoon!",
                "delegations": []
            }

        return False, {}

    # ------------------------------------------------------------------------
    # Execution: the single path shared by the fast-path and the LLM planner
    # ------------------------------------------------------------------------
    @staticmethod
    def _result_entry(result: ToolResult, agent: str, action: str) -> Dict[str, Any]:
        """
        One execution_results row.

        Keeps the historical {"agent", "action", "result"} shape the GUI and the
        phone UI read, and adds the authoritative ToolResult fields on top.
        """
        entry = result.to_dict()
        entry["agent"] = agent
        entry["action"] = action
        return entry

    async def _execute_delegations(
        self,
        delegations: List[Dict[str, Any]],
        session_id: str,
        user_input: str,
        speech_reply: str,
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """
        Runs a plan's delegations through the tool registry.

        Returns (execution_results, speech_reply, gated). ``gated`` is True when
        a tool needed confirmation: the question becomes the spoken reply,
        nothing further is executed, and the held action waits for "haan"/"nahi".
        """
        execution_results: List[Dict[str, Any]] = []

        for delegation in delegations or []:
            agent_name = str(delegation.get("agent", "") or "").strip().lower()
            action = str(delegation.get("action", "") or "").strip()
            params = delegation.get("params", {}) or {}

            # "agent": "speech_reply" means the model just wanted to talk.
            if agent_name in PSEUDO_AGENTS and not action:
                continue

            spec = self.registry.get(action) or self.registry.resolve_legacy(agent_name, action)
            if spec is None:
                if agent_name in PSEUDO_AGENTS:
                    continue
                logger.warning(f"No tool for delegation {agent_name}/{action}; skipping.")
                execution_results.append(self._result_entry(
                    ToolResult(
                        ok=False,
                        tool=action or agent_name,
                        message=f"Sir, '{action or agent_name}' ke liye koi tool available nahi hai.",
                    ),
                    agent_name, action,
                ))
                continue

            logger.info(f"Delegation {agent_name}/{action} -> tool '{spec.name}'")

            # The registry applies the permission gate itself: a tool that needs
            # confirmation and is called without confirmed=True comes back
            # blocked, having executed nothing.
            result = await self.registry.execute(spec, params, confirmed=False)

            if result.awaiting_confirmation:
                pending = self.safety.hold_for_confirmation(
                    result,
                    session_id=session_id,
                    original_input=user_input,
                    on_confirm_reply=speech_reply,
                )
                execution_results.append(self._result_entry(result, agent_name, action))
                logger.info(
                    f"Holding '{pending.tool}' for confirmation; "
                    f"{len(delegations) - len(execution_results)} later delegation(s) not attempted."
                )
                return execution_results, pending.question, True

            if result.speech_reply:
                speech_reply = result.speech_reply
            execution_results.append(self._result_entry(result, agent_name, action))

        return execution_results, speech_reply, False

    async def _handle_confirmation_reply(
        self, user_input: str, session_id: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Interprets an utterance while an action is held for approval.

        Returns (handled, response). ``handled`` is False for a reply that is
        neither yes nor no -- the pending action is dropped without running and
        the caller processes the input as a brand-new request.
        """
        decision, pending = self.safety.resolve_reply(user_input, session_id)

        if decision is ConfirmationDecision.NONE or pending is None:
            return False, {}

        if decision is ConfirmationDecision.UNRELATED:
            logger.info(f"'{pending.tool}' dropped unexecuted; input is a new request.")
            return False, {}

        if decision is ConfirmationDecision.EXPIRED:
            reply = self.safety.expiry_reply(pending)
            return True, self._finalize(
                session_id, user_input, reply,
                thought=f"Confirmation for '{pending.tool}' expired; nothing executed.",
                execution_results=[],
            )

        if decision is ConfirmationDecision.DENY:
            reply = self.safety.cancellation_reply(pending)
            return True, self._finalize(
                session_id, user_input, reply,
                thought=f"User declined '{pending.tool}'; nothing executed.",
                execution_results=[],
            )

        # AFFIRM -- and only now does the held action actually run.
        logger.info(f"Confirmed '{pending.tool}'; executing with confirmed=True.")
        result = await self.registry.execute(pending.tool, pending.params, confirmed=True)
        spec = self.registry.get(pending.tool)
        entry = self._result_entry(
            result,
            getattr(spec, "agent", "") or "",
            getattr(spec, "action", "") or pending.tool,
        )

        if result.speech_reply:
            reply = result.speech_reply
        elif result.ok:
            reply = pending.on_confirm_reply or "Ji Sir, ho gaya."
        else:
            reply = result.message or f"Sir, '{pending.tool}' complete nahi ho paya."

        return True, self._finalize(
            session_id, user_input, reply,
            thought=f"User confirmed '{pending.tool}'; executed after approval.",
            execution_results=[entry],
        )

    def _finalize(
        self,
        session_id: str,
        user_input: str,
        speech_reply: str,
        thought: str,
        execution_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Cleans the spoken reply, records the turn, and shapes the response."""
        if speech_reply:
            speech_reply = re.sub(r"```(?:json)?[\s\S]*?```", "", speech_reply).strip()
            speech_reply = re.sub(r"[\{\}\[\]\\]", "", speech_reply).strip()
            speech_reply = speech_reply.strip('"').strip("'").strip()

        self.memory.record_turn(session_id, "user", user_input)
        self.memory.record_turn(session_id, "assistant", speech_reply, thought=thought)

        return {
            "thought": thought,
            "speech_reply": speech_reply,
            "execution_results": execution_results,
        }

    async def process_user_request(self, user_input: str, session_id: str = "default", image_path: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point: turns a prompt into tool calls and a spoken reply."""
        logger.info(f"Processing user input: '{user_input}' (Image: {image_path})")

        # 0. A held action outranks everything: "haan" must approve the shutdown,
        #    not be re-parsed as a fresh command. include_expired=True because a
        #    late answer still deserves a straight answer -- the broker decides
        #    whether the window had closed, and an utterance that was not an
        #    answer at all falls through to normal handling below.
        if self.safety.has_pending(session_id, include_expired=True):
            handled, response = await self._handle_confirmation_reply(user_input, session_id)
            if handled:
                return response

        thought = ""
        cleaned_response = ""

        # Check fast-path direct command matching
        is_fast, fast_result = self._fast_path_match(user_input, image_path=image_path)
        if is_fast:
            thought = fast_result["thought"]
            parsed_plan = {
                "thought": thought,
                "speech_reply": fast_result["speech_reply"],
                "delegations": fast_result["delegations"],
            }
        else:
            # 1. Retrieve RAG memory & user facts
            all_facts = self.memory.get_all_facts()
            facts_str = "\n".join([f"- {f['key_name']}: {f['value_data']}" for f in all_facts]) if all_facts else "None"
            relevant_memories = self.memory.retrieve_relevant_memory(user_input, top_k=3)
            dialogue_history = self.memory.get_dialogue_context(session_id=session_id, turns=4)

            # 2. Build LLM Planner Prompt
            context_str = "\n".join([f"- {m}" for m in relevant_memories]) if relevant_memories else "None"
            history_str = "\n".join([f"{turn['role']}: {turn['content']}" for turn in dialogue_history])

            full_prompt = f"""
Known Stored Facts & User Preferences:
{facts_str}

System Context & Retrieved Memory:
{context_str}

Recent Conversation History:
{history_str}

User Request: "{user_input}"
"""

            # 3. Call Local LLM for CoT Planning & Delegation Schema
            raw_response = await self.llm.generate_response(
                prompt=full_prompt,
                system_prompt=self.planner_prompt,
                temperature=0.3
            )

            thought, cleaned_response = strip_thought_tags(raw_response)
            parsed_plan = parse_json_safely(cleaned_response)

        execution_results: List[Dict[str, Any]] = []

        if parsed_plan and "delegations" in parsed_plan:
            thought = parsed_plan.get("thought", thought)
            speech_reply = parsed_plan.get("speech_reply", "")

            # 4. Execute through the registry (permissions, confirmation, results)
            execution_results, speech_reply, gated = await self._execute_delegations(
                parsed_plan.get("delegations", []),
                session_id=session_id,
                user_input=user_input,
                speech_reply=speech_reply,
            )

            if gated:
                # Nothing ran. Ask, and say nothing that implies it already did.
                return self._finalize(
                    session_id, user_input, speech_reply,
                    thought=f"{thought}\n[Safety]: Awaiting user confirmation; nothing executed.",
                    execution_results=execution_results,
                )

            # 5. Report failures honestly. This loop used to read res["success"],
            #    a key the sub-agents never set -- so {"status": "error"} was
            #    announced as a success. ToolResult.ok is now authoritative.
            failures = [
                item.get("message") or f"'{item.get('tool')}' failed"
                for item in execution_results
                if not item.get("ok") and not item.get("awaiting_confirmation")
            ]

            if failures:
                error_summary = "; ".join(failures)
                thought = f"{thought}\n[System Feedback]: Task encountered an issue ({error_summary})."
                speech_reply = f"Sir, ek problem aa gayi: {error_summary} Aap kaise handle karna chahenge?"
        else:
            # Direct natural speech answer if no JSON action requested
            speech_reply = cleaned_response or (
                "I apologize, Sir. I am unsure how to complete that request. "
                "Could you please clarify?"
            )

        return self._finalize(
            session_id, user_input, speech_reply, thought, execution_results
        )
