"""
Fast-path routing test for "Desktop pe folder banao".

Two things this pins, both of which regressed once:

  * the misspelling "dekstop" still matches -- it is what actually gets said, and
    what the speech-to-text actually returns;
  * the delegation carries ``path``, the name create_folder declares. The router
    used to emit ``folder_path``, which the tool did not accept, so the folder
    name was dropped and the file agent received a create call with no target.
    The registry still aliases folder_path -> path for LLM-authored plans (see
    tests/test_tool_registry.py), but the fast-path emits the canonical name.
"""

from unittest.mock import MagicMock

from agents.planner_agent import PlannerAgent


def test_planner_desktop_folder_fast_path():
    planner = PlannerAgent(MagicMock(), MagicMock(), MagicMock(), {})

    is_fp, result = planner._fast_path_match("dekstop pe ek folder banao notes k naam se")
    assert is_fp is True

    delegation = result["delegations"][0]
    assert delegation["action"] == "create_folder"
    assert "Notes" in delegation["params"]["path"]
    assert "folder_path" not in delegation["params"]


def test_intent_matching_does_not_create_the_folder(tmp_path, monkeypatch):
    """
    The matcher names the target; it must not create it.

    It used to call desktop_path.mkdir() inline, so the folder appeared even when
    the permission gate would have refused -- and merely *asking* what a phrase
    would do littered the real Desktop.
    """
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    (tmp_path / "Desktop").mkdir()

    planner = PlannerAgent(MagicMock(), MagicMock(), MagicMock(), {})
    is_fp, result = planner._fast_path_match("desktop pe ek folder banao notes k naam se")

    assert is_fp is True
    target = result["delegations"][0]["params"]["path"]
    assert "Notes" in target
    assert list((tmp_path / "Desktop").iterdir()) == [], "the matcher touched the filesystem"
