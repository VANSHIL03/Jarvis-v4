"""
JARVIS v4 - System Hardware Telemetry Monitor
Monitors CPU, RAM, GPU VRAM, and System Temperature for Windows 11 / RTX GPU platform.
"""

import psutil
import subprocess
from typing import Dict, Any
from utils.logger import logger

class SystemMonitor:
    def __init__(self):
        self._nvml_available = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self.pynvml = pynvml
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._nvml_available = True
            logger.info("NVML initialized successfully for GPU monitoring.")
        except Exception as e:
            logger.warning(f"NVML GPU monitoring unavailable ({e}). Falling back to nvidia-smi / psutil.")

    def get_cpu_usage(self) -> float:
        """Returns CPU usage percentage."""
        return psutil.cpu_percent(interval=None)

    def get_ram_usage(self) -> Dict[str, Any]:
        """Returns RAM usage stats in GB and percentage."""
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "used_gb": round(mem.used / (1024 ** 3), 2),
            "percent": mem.percent
        }

    def get_gpu_stats(self) -> Dict[str, Any]:
        """Returns GPU VRAM usage and temperature."""
        if self._nvml_available:
            try:
                info = self.pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                temp = self.pynvml.nvmlDeviceGetTemperature(
                    self.handle, self.pynvml.NVML_TEMPERATURE_GPU
                )
                return {
                    "vram_total_mb": round(info.total / (1024 ** 2), 2),
                    "vram_used_mb": round(info.used / (1024 ** 2), 2),
                    "vram_percent": round((info.used / info.total) * 100, 1),
                    "temperature_c": temp
                }
            except Exception as e:
                logger.error(f"Error fetching GPU stats via NVML: {e}")

        # Fallback using nvidia-smi
        try:
            cmd = "nvidia-smi --query-gpu=memory.total,memory.used,temperature.gpu --format=csv,noheader,nounits"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            total, used, temp = map(float, output.split(','))
            return {
                "vram_total_mb": total,
                "vram_used_mb": used,
                "vram_percent": round((used / total) * 100, 1),
                "temperature_c": int(temp)
            }
        except Exception:
            return {
                "vram_total_mb": 6144.0,
                "vram_used_mb": 0.0,
                "vram_percent": 0.0,
                "temperature_c": 0
            }

    def get_full_telemetry(self) -> Dict[str, Any]:
        """Collects complete hardware telemetry payload."""
        ram = self.get_ram_usage()
        gpu = self.get_gpu_stats()
        return {
            "cpu_percent": self.get_cpu_usage(),
            "ram_percent": ram["percent"],
            "ram_used_gb": ram["used_gb"],
            "ram_total_gb": ram["total_gb"],
            "gpu_vram_percent": gpu["vram_percent"],
            "gpu_vram_used_mb": gpu["vram_used_mb"],
            "gpu_vram_total_mb": gpu["vram_total_mb"],
            "gpu_temp_c": gpu["temperature_c"]
        }
