"""
JARVIS v4 - Executive Planner Agent (Orchestrator)
Parses user intent, performs silent chain-of-thought reasoning (<thought>), delegates sub-tasks to specialized sub-agents, enforces security rules, and synthesizes natural responses.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from config.prompts import PLANNER_AGENT_PROMPT
from ai.llm_client import LocalLLMClient
from memory.memory_manager import MemoryManager
from security.safety import SafetyManager
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

from automation.news_fetcher import NewsFetcher
from automation.reminder_manager import ReminderManager
from automation.shopping import ShoppingAutomation
from automation.food_delivery import FoodDeliveryAutomation
from automation.n8n_workflow_manager import N8nWorkflowManager

class PlannerAgent:
    def __init__(
        self,
        llm_client: LocalLLMClient,
        memory_manager: MemoryManager,
        safety_manager: SafetyManager,
        agents: Dict[str, Any]
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

    def _fast_path_match(self, user_input: str) -> tuple[bool, Dict[str, Any]]:
        """Fast-path resolution for instant OS, application & web site automation commands."""
        clean = re.sub(r"^(?:hey\s+jarvis|hi\s+jarvis|okay\s+jarvis|ok\s+jarvis|jarvis)\s*[,:\.\-]?\s*", "", user_input.lower().strip(), flags=re.I).strip()
        sir = self._get_user_salutation()

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
        if any(k in clean for k in ["bhejo", "send", "message", "msg", "whatsapp"]):
            target_text = re.sub(r"^(?:jarvis|jarvas|travis)\s*,?\s*", "", user_input, flags=re.I).strip()

            p_eng1 = re.search(r"(?:send\s+a?\s*|write\s+a?\s*)?(?:whatsapp\s+)?message\s+(?:to\s+)?([a-zA-Z0-9_\-\s]+?)\s+(?:on\s+whatsapp\s+|in\s+whatsapp\s+)?[\"\']?(.+?)[\"\']?$", target_text, re.IGNORECASE)
            p_eng2 = re.search(r"(?:send\s+a?\s*|write\s+a?\s*)?whatsapp\s+(?:message\s+)?(?:to\s+)?([a-zA-Z0-9_\-\s]+?)\s+(?:on\s+whatsapp\s+|in\s+whatsapp\s+)?[\"\']?(.+?)[\"\']?$", target_text, re.IGNORECASE)
            p_hing = re.search(r"(?:whatsapp\s+(?:kholo|open\s+karo)?\s*(?:aur|and)?\s*)?([a-zA-Z0-9_\-\s]+?)\s+(?:ko|par|pe)\s+(?:whatsapp\s+)?(?:pe\s+|par\s+)?(?:message\s+bhejo\s+|msg\s+bhejo\s+|message\s+|msg\s+|bhejo\s+)?[\"\']?(.+?)[\"\']?$", target_text, re.IGNORECASE)

            match = p_eng1 or p_eng2 or p_hing
            if match:
                contact = match.group(1).strip()
                msg = match.group(2).strip()

                for prefix in ["whatsapp kholo aur", "whatsapp kholo and", "whatsapp pe", "whatsapp par", "whatsapp p", "open whatsapp and", "send", "message"]:
                    if contact.lower().startswith(prefix):
                        contact = contact[len(prefix):].strip()

                contact = re.sub(r"\s+(?:on|in|via|through)\s+whatsapp$", "", contact, flags=re.I).strip()
                msg = re.sub(r"^(?:on|in|via|through)\s+whatsapp\s+", "", msg, flags=re.I).strip()
                msg = msg.strip('"').strip("'").strip()

                if contact and msg and len(contact) >= 2 and contact.lower() not in ["open", "kholo", "chalao"]:
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

        # System app launches (English & Hinglish: kholo / chalao / open karo)
        apps = ["chrome", "edge", "vscode", "notepad", "calculator", "calc", "paint", "cmd", "powershell", "settings", "file explorer", "downloads", "documents"]
        for app in apps:
            if clean == app or any(p in clean for p in [f"open {app}", f"{app} kholo", f"{app} chalao", f"{app} open karo", f"launch {app}"]):
                return True, {
                    "thought": f"Fast-path triggered: Launching {app}.",
                    "speech_reply": f"Ji Sir, {app.capitalize()} khol raha hoon.",
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
            detected_games = self.windows.sys_control.detect_installed_games()
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

            desktop_path = Path.home() / "Desktop" / folder_name
            desktop_path.mkdir(parents=True, exist_ok=True)
            return True, {
                "thought": f"Fast-path triggered: Explicit Desktop folder creation for '{folder_name}'.",
                "speech_reply": f"Ji {sir}, Desktop par '{folder_name}' naam se folder bana diya hai!",
                "delegations": [{"agent": "file_agent", "action": "create_folder", "params": {"folder_path": str(desktop_path)}}]
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
            "n8n", "workflow", "whatsapp", "whatsapp message", "send whatsapp",
            "github", "github push", "google drive", "gdrive", "upload to drive",
            "linkedin", "instagram", "youtube upload", "reddit", "excel", "powerpoint", "ppt",
            "google calendar", "calendar event", "grok", "grok ai", "xai", "ask grok",
            "gmail", "email", "emails", "mail", "read gmail", "check gmail", "read my gmail", "gmail padho",
            "read email", "check email", "inbox", "backup folder", "discord alert",
            "discord notification", "telegram message", "google sheets", "spreadsheet",
            "slack message", "notion add", "dropbox", "onedrive"
        ]
        if any(k in clean for k in n8n_keywords):
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

    async def process_user_request(self, user_input: str, session_id: str = "default") -> Dict[str, Any]:
        """Main entry point: processes user prompt, delegates to sub-agents, and produces response."""
        logger.info(f"Processing user input: '{user_input}'")

        # Check fast-path direct command matching
        is_fast, fast_result = self._fast_path_match(user_input)
        if is_fast:
            thought = fast_result["thought"]
            speech_reply = fast_result["speech_reply"]
            delegations = fast_result["delegations"]
            parsed_plan = {"thought": thought, "speech_reply": speech_reply, "delegations": delegations}
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
                system_prompt=PLANNER_AGENT_PROMPT,
                temperature=0.3
            )

            thought, cleaned_response = strip_thought_tags(raw_response)
            parsed_plan = parse_json_safely(cleaned_response)

        execution_results = []
        speech_reply = ""

        if parsed_plan and "delegations" in parsed_plan:
            thought = parsed_plan.get("thought", thought if 'thought' in locals() else "")
            speech_reply = parsed_plan.get("speech_reply", "")
            delegations = parsed_plan.get("delegations", [])

            # 4. Execute Sub-Agent Tasks
            for delegation in delegations:
                target_agent_name = delegation.get("agent", "").lower()
                action = delegation.get("action", "")
                params = delegation.get("params", {})

                logger.info(f"Delegating task to '{target_agent_name}' -> Action: '{action}'")

                # Safety Check Interceptor
                if not self.safety.check_and_confirm(action, params):
                    execution_results.append({
                        "agent": target_agent_name,
                        "action": action,
                        "status": "security_rejected",
                        "message": "User denied authorization for dangerous command."
                    })
                    continue

                # Ignore pseudo-agents generated by LLM (like speech_reply or none)
                if target_agent_name in ["speech_reply", "speech", "reply", "none", "llm", "user", "assistant", ""]:
                    continue

                if target_agent_name in self.sub_agents:
                    sub_agent = self.sub_agents[target_agent_name]
                    res = await sub_agent.execute_task(action, params)
                    if isinstance(res, dict) and res.get("speech_reply"):
                        speech_reply = res["speech_reply"]
                    execution_results.append({
                        "agent": target_agent_name,
                        "action": action,
                        "result": res
                    })
                else:
                    execution_results.append({
                        "agent": target_agent_name,
                        "status": "error",
                        "message": f"Sub-agent '{target_agent_name}' not found."
                    })

            # Check if any sub-task failed or got stuck, and ask the user for guidance
            failures = []
            for item in execution_results:
                status = item.get("status", "")
                res = item.get("result", {})
                if status == "security_rejected":
                    failures.append(f"Security interceptor blocked '{item.get('action')}'")
                elif status == "error":
                    failures.append(item.get("message", "Sub-agent error"))
                elif isinstance(res, dict) and res.get("success") is False:
                    failures.append(res.get("message", "Task execution failed"))

            if failures:
                error_summary = "; ".join(failures)
                thought = f"{thought}\n[System Feedback]: Task encountered an issue ({error_summary}). Asking user for clarification."
                speech_reply = f"Sir, I encountered an issue: {error_summary}. How would you like me to handle this?"

        else:
            # Direct natural speech answer if no JSON action requested
            speech_reply = cleaned_response if 'cleaned_response' in locals() else "I apologize, Sir. I am unsure how to complete that request. Could you please clarify?"

        # Clean speech_reply from any leftover JSON code blocks or raw formatting
        if speech_reply:
            speech_reply = re.sub(r"```(?:json)?[\s\S]*?```", "", speech_reply).strip()
            speech_reply = re.sub(r"[\{\}\[\]\\]", "", speech_reply).strip()
            speech_reply = speech_reply.strip('"').strip("'").strip()

        # 5. Record Turn into Memory
        self.memory.record_turn(session_id, "user", user_input)
        self.memory.record_turn(session_id, "assistant", speech_reply, thought=thought if 'thought' in locals() else "")

        return {
            "thought": thought if 'thought' in locals() else "",
            "speech_reply": speech_reply,
            "execution_results": execution_results
        }
