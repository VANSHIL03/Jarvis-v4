import pytest
from PySide6.QtWidgets import QApplication
from ui.components.stark_hud_widget import StarkHudWidget

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_stark_hud_telemetry(qapp):
    hud = StarkHudWidget()
    hud.update_telemetry({
        "cpu_percent": 35.0,
        "ram_percent": 60.0,
        "gpu_vram_percent": 40.0,
        "gpu_temp_c": 45.0
    })
    assert hud.cpu_percent == 35.0
    assert hud.ram_percent == 60.0
    assert hud.vram_percent == 40.0
