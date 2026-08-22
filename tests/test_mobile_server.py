import pytest
import requests
from server.web_server import get_local_ip, MobileWebServer

def test_local_ip_resolution():
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0

def test_mobile_web_server_startup():
    server = MobileWebServer(planner_agent=None, port=8999)
    server.start()
    try:
        res = requests.get("http://127.0.0.1:8999/")
        assert res.status_code == 200
        assert "J.A.R.V.I.S. MOBILE" in res.text

        status_res = requests.get("http://127.0.0.1:8999/api/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert "cpu_percent" in data
        assert "ram_percent" in data
    finally:
        server.stop()
