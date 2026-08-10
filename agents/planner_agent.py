"""
JARVIS v4 - Executive Planner Agent (Orchestrator)
Parses user intent, performs silent chain-of-thought reasoning (<thought>), delegates sub-tasks to specialized sub-agents, enforces security rules, and synthesizes natural responses.
"""

import re
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

        # Code Generation fast-path (English & Hinglish)
        if "code" in clean.lower() and any(k in clean.lower() for k in ["write", "likh", "banao", "create", "generate", "give", "do", "script", "make"]):
            lang = "python"
            for l in ["java", "python", "cpp", "c++", "c#", "html", "css", "javascript", "js", "sql", "react", "unity"]:
                if l in clean.lower():
                    lang = l
                    break

            return True, {
                "thought": f"Fast-path triggered: Generating {lang} code and opening in Notepad.",
                "speech_reply": f"Ji Sir, aapka {lang.capitalize()} code generate karke Notepad me open kar raha hoon.",
                "delegations": [{"agent": "coding_agent", "action": "generate_code", "params": {"language": lang, "prompt": user_input}}]
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
        is_yt_mention = any(k in clean.lower() for k in yt_keywords)
        is_music_mention = any(k in clean.lower() for k in music_keywords)

        if is_yt_mention or (is_music_mention and any(k in clean.lower() for k in ["play", "chalao", "sunao", "search"])):
            term = clean
            term = re.sub(r"^(?:play|search|chalao|sunao|open|kholo|launch)\s+", "", term, flags=re.I).strip()
            term = re.sub(r"\s+(?:on|in|pe|par|p)\s+(?:youtube|you\s+tube|youtuve|yutube|utube).*$", "", term, flags=re.I).strip()
            term = re.sub(r"^(?:youtube|you\s+tube|youtuve|yutube|utube)\s+(?:pe|par|p)?\s*", "", term, flags=re.I).strip()
            term = re.sub(r"\s+(?:chalao|play\s+karo|search\s+karo|dhoondho|sunao)$", "", term, flags=re.I).strip()
            
            if not term or term.lower() in ["music", "song", "gana", "video", "youtube"]:
                term = "top trending music"

            return True, {
                "thought": f"Fast-path triggered: Playing '{term}' on YouTube.",
                "speech_reply": f"Ji {sir}, YouTube par {term} chala raha hoon.",
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
        if any(k in clean for k in ["bhejo", "send", "message", "msg"]):
            wa_msg_hinglish = re.search(
                r"(?:whatsapp\s+(?:kholo|open\s+karo)?\s*(?:aur|and)?\s*)?(.+?)\s+(?:ko|par|pe)\s+(?:message\s+bhejo\s+|msg\s+bhejo\s+|message\s+|bhejo\s+)?[\"\']?(.+?)[\"\']?$",
                clean,
                re.IGNORECASE
            )
            if wa_msg_hinglish:
                contact = wa_msg_hinglish.group(1).strip()
                msg = wa_msg_hinglish.group(2).strip()
                for prefix in ["whatsapp kholo aur", "whatsapp kholo and", "whatsapp pe", "whatsapp par", "whatsapp p", "open whatsapp and"]:
                    if contact.lower().startswith(prefix):
                        contact = contact[len(prefix):].strip()

                if contact and msg:
                    return True, {
                        "thought": f"Fast-path triggered: Sending WhatsApp message to '{contact}': '{msg}'.",
                        "speech_reply": f"Ji Sir, {contact} ko WhatsApp par '{msg}' message bhej raha hoon.",
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

        # Lock PC
        if any(k in clean for k in ["lock pc", "lock computer", "pc lock karo", "computer lock karo"]):
            return True, {
                "thought": "Fast-path triggered: Locking workstation.",
                "speech_reply": "Ji Sir, system lock kar raha hoon.",
                "delegations": [{"agent": "windows_agent", "action": "lock_pc", "params": {}}]
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

                if target_agent_name in self.sub_agents:
                    sub_agent = self.sub_agents[target_agent_name]
                    res = await sub_agent.execute_task(action, params)
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
