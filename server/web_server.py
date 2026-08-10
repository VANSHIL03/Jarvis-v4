"""
JARVIS v4 - Local Wi-Fi Mobile Web Application Server
Exposes a responsive mobile HUD web app on your local network (e.g. http://192.168.x.x:8000).
Allows full remote voice & text control, system telemetry monitoring, and code viewing from any mobile phone or tablet.
"""

import os
import json
import socket
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
import psutil

from utils.logger import logger

def get_local_ip() -> str:
    """Resolves local network Wi-Fi IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


HTML_MOBILE_APP = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>J.A.R.V.I.S. Mobile Command Center</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background-color: #060a12; color: #e0f7ff; min-height: 100vh; display: flex; flex-direction: column; }
        
        /* Header & Arc Reactor Glow */
        header { background: rgba(10, 18, 32, 0.9); border-bottom: 1px solid rgba(0, 210, 255, 0.3); padding: 15px; text-align: center; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(10px); }
        .hud-title { color: #00e5ff; font-size: 20px; font-weight: bold; letter-spacing: 2px; text-shadow: 0 0 10px rgba(0, 229, 255, 0.5); }
        .hud-sub { color: #6699bb; font-size: 11px; margin-top: 2px; font-family: monospace; }
        
        /* System Telemetry Cards */
        .telemetry-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 10px; background: rgba(5, 10, 20, 0.8); }
        .card { background: rgba(12, 22, 40, 0.8); border: 1px solid rgba(0, 180, 255, 0.2); border-radius: 8px; padding: 8px 4px; text-align: center; }
        .card-label { color: #6699bb; font-size: 9px; font-weight: bold; }
        .card-val { color: #00ffcc; font-size: 13px; font-weight: bold; margin-top: 2px; font-family: monospace; }
        
        /* Main Chat Feed */
        .chat-container { flex: 1; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 14px; border-radius: 10px; max-width: 85%; font-size: 13.5px; line-height: 1.4; word-wrap: break-word; }
        .msg-user { background: rgba(0, 120, 220, 0.3); border: 1px solid rgba(0, 180, 255, 0.4); color: #ffffff; align-self: flex-end; border-bottom-right-radius: 2px; }
        .msg-jarvis { background: rgba(10, 30, 50, 0.8); border: 1px solid rgba(0, 255, 170, 0.3); color: #d8f8ff; align-self: flex-start; border-bottom-left-radius: 2px; }
        .msg-sender { font-size: 10px; font-weight: bold; margin-bottom: 3px; display: block; }
        .msg-user .msg-sender { color: #00d2ff; }
        .msg-jarvis .msg-sender { color: #00ffaa; }
        
        /* Code Container */
        .code-box { background: #030710; border: 1px solid #00d2ff; border-radius: 6px; padding: 10px; margin-top: 6px; font-family: monospace; font-size: 11px; color: #a0f0ff; overflow-x: auto; white-space: pre-wrap; }
        
        /* Controls Footer */
        footer { background: rgba(8, 14, 26, 0.95); border-top: 1px solid rgba(0, 210, 255, 0.3); padding: 10px; display: flex; gap: 8px; position: sticky; bottom: 0; backdrop-filter: blur(10px); }
        input[type="text"] { flex: 1; background: rgba(15, 28, 50, 0.9); border: 1px solid rgba(0, 180, 255, 0.5); border-radius: 20px; padding: 10px 16px; color: #ffffff; font-size: 14px; outline: none; }
        input[type="text"]:focus { border-color: #00e5ff; box-shadow: 0 0 8px rgba(0, 229, 255, 0.4); }
        .btn { background: linear-gradient(135deg, #00b8e6, #0055ff); border: none; border-radius: 20px; color: #fff; font-weight: bold; padding: 0 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 13px; }
        .btn-mic { background: linear-gradient(135deg, #ff0055, #cc0000); width: 42px; height: 42px; border-radius: 50%; padding: 0; }
    </style>
</head>
<body>
    <header>
        <div class="hud-title">⚡ J.A.R.V.I.S. MOBILE</div>
        <div class="hud-sub">SYSTEM REMOTE CONTROLLER v4.0</div>
    </header>

    <div class="telemetry-row">
        <div class="card"><div class="card-label">CPU</div><div class="card-val" id="cpu-val">--%</div></div>
        <div class="card"><div class="card-label">VRAM</div><div class="card-val" id="vram-val">--%</div></div>
        <div class="card"><div class="card-label">RAM</div><div class="card-val" id="ram-val">--%</div></div>
        <div class="card"><div class="card-label">STATUS</div><div class="card-val" style="color:#00e5ff;">ONLINE</div></div>
    </div>

    <div class="chat-container" id="chat-feed">
        <div class="msg msg-jarvis">
            <span class="msg-sender">J.A.R.V.I.S.</span>
            Good day, Sir. Mobile Remote Command Link is active. How may I assist you today?
        </div>
    </div>

    <footer>
        <button class="btn btn-mic" id="mic-btn" onclick="toggleVoice()">🎙️</button>
        <input type="text" id="cmd-input" placeholder="Type command to JARVIS..." onkeypress="handleKey(event)">
        <button class="btn" onclick="sendCommand()">SEND</button>
    </footer>

    <script>
        const chatFeed = document.getElementById('chat-feed');
        const cmdInput = document.getElementById('cmd-input');
        let recognizing = false;
        let recognition = null;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                cmdInput.value = text;
                sendCommand();
            };

            recognition.onend = () => {
                recognizing = false;
                document.getElementById('mic-btn').style.background = 'linear-gradient(135deg, #ff0055, #cc0000)';
            };
        }

        function toggleVoice() {
            if (!recognition) {
                alert('Voice speech recognition not supported on this browser.');
                return;
            }
            if (recognizing) {
                recognition.stop();
            } else {
                recognition.start();
                recognizing = true;
                document.getElementById('mic-btn').style.background = 'linear-gradient(135deg, #00ffaa, #00b377)';
            }
        }

        function handleKey(e) {
            if (e.key === 'Enter') sendCommand();
        }

        async function sendCommand() {
            const text = cmdInput.value.trim();
            if (!text) return;

            appendMsg(text, 'user');
            cmdInput.value = '';

            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: text })
                });
                const data = await res.json();
                
                if (data.speech_reply) {
                    appendMsg(data.speech_reply, 'jarvis');
                }

                if (data.execution_results) {
                    data.execution_results.forEach(item => {
                        if (item.result && (item.result.code || item.result.explanation)) {
                            appendCode(item.result.code || item.result.explanation);
                        }
                    });
                }
            } catch (err) {
                appendMsg('Error connecting to JARVIS PC engine.', 'jarvis');
            }
        }

        function appendMsg(text, sender) {
            const div = document.createElement('div');
            div.className = `msg msg-${sender}`;
            div.innerHTML = `<span class="msg-sender">${sender === 'user' ? 'SIR' : 'J.A.R.V.I.S.'}</span>${text}`;
            chatFeed.appendChild(div);
            chatFeed.scrollTop = chatFeed.scrollHeight;
        }

        function appendCode(code) {
            const div = document.createElement('div');
            div.className = 'code-box';
            div.innerText = code;
            chatFeed.appendChild(div);
            chatFeed.scrollTop = chatFeed.scrollHeight;
        }

        async function updateTelemetry() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('cpu-val').innerText = `${Math.round(data.cpu_percent)}%`;
                document.getElementById('ram-val').innerText = `${Math.round(data.ram_percent)}%`;
            } catch(e) {}
        }
        setInterval(updateTelemetry, 2000);
    </script>
</body>
</html>
"""

class MobileWebHandler(BaseHTTPRequestHandler):
    planner_agent = None

    def log_message(self, format, *args):
        pass  # Suppress default HTTP request logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_MOBILE_APP.encode("utf-8"))

        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "cpu_percent": psutil.cpu_percent(),
                "ram_percent": psutil.virtual_memory().percent,
                "status": "ONLINE"
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/command":
            content_length = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_length)
            try:
                payload = json.loads(post_body.decode('utf-8'))
                user_prompt = payload.get("prompt", "")

                if self.planner_agent:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(self.planner_agent.process_user_request(user_prompt))
                    loop.close()
                else:
                    res = {
                        "speech_reply": "Ji Sir, engine ready hai lekin planner process loading mein hai.",
                        "execution_results": []
                    }

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res).encode("utf-8"))

            except Exception as e:
                logger.error(f"Mobile web POST error: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))


class MobileWebServer:
    def __init__(self, planner_agent=None, port: int = 8000):
        self.port = port
        self.local_ip = get_local_ip()
        self.planner_agent = planner_agent
        MobileWebHandler.planner_agent = planner_agent
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Launches Mobile Web Server in background daemon thread."""
        try:
            self.server = HTTPServer(("0.0.0.0", self.port), MobileWebHandler)
            self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self._thread.start()
            logger.info(f"⚡ JARVIS Mobile Web Remote is ONLINE at http://{self.local_ip}:{self.port}")
            print(f"\n=======================================================")
            print(f"📱 JARVIS MOBILE REMOTE CONNECTED:")
            print(f"👉 Open this link on your phone (Wi-Fi): http://{self.local_ip}:{self.port}")
            print(f"=======================================================\n")
        except Exception as e:
            logger.error(f"Failed to start Mobile Web Server: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            logger.info("Mobile Web Server stopped.")
