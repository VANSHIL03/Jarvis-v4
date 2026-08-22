import pytest
from automation.vscode_control import VSCodeControl

def test_vscode_project_creation(tmp_path):
    vscode = VSCodeControl()
    res = vscode.create_project_and_code(
        folder_name="TestWebApp",
        target_dir=str(tmp_path),
        language="html",
        code_content="<h1>JARVIS WebApp</h1>"
    )

    assert res["status"] == "success"
    assert res["folder_name"] == "TestWebApp"
    assert (tmp_path / "TestWebApp" / "index.html").exists()
    with open(tmp_path / "TestWebApp" / "index.html", "r") as f:
        assert "JARVIS WebApp" in f.read()
