"""
System Information Module for Shoeshine.

Provides:
- Hardware detection (CPU, RAM, GPU)
- Resource monitoring (current usage)
- LLM framework detection (Ollama, vLLM, LM Studio)
- Performance recommendations based on hardware
"""

import os
import sys
import time
import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class CPUInfo:
    """CPU information."""

    cores: int
    threads: int
    frequency_mhz: Optional[float]
    brand: str
    usage_percent: float = 0.0


@dataclass
class MemoryInfo:
    """Memory information."""

    total_gb: float
    available_gb: float
    used_percent: float


@dataclass
class GPUInfo:
    """GPU information."""

    name: str
    vram_gb: Optional[float]
    compute_cap: Optional[str]
    cuda_available: bool
    usage_percent: float = 0.0
    memory_used_gb: float = 0.0


@dataclass
class HardwareInfo:
    """Complete hardware information."""

    cpu: CPUInfo
    memory: MemoryInfo
    gpus: List[GPUInfo] = field(default_factory=list)
    platform: str = ""
    python_version: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class LLMFramework:
    """Detected LLM framework."""

    name: str
    installed: bool
    running: bool
    url: Optional[str]
    models: List[str] = field(default_factory=list)
    error: Optional[str] = None


def get_cpu_info() -> CPUInfo:
    """Get CPU information."""
    cores = threads = 0
    frequency = None
    brand = "Unknown"

    if sys.platform == "win32":
        try:
            import psutil

            cores = psutil.cpu_count(logical=False)
            threads = psutil.cpu_count(logical=True)
            frequency = psutil.cpu_freq().current if psutil.cpu_freq() else None
        except:
            pass
        brand = "Windows CPU"
    elif sys.platform == "linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line or "Model" in line:
                        brand = line.split(":")[1].strip()
                        break
                    if "cpu MHz" in line:
                        frequency = float(line.split(":")[1].strip())
            cores = os.cpu_count() or 4
            threads = cores
        except:
            pass
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
            )
            brand = result.stdout.strip()
            cores = int(
                subprocess.run(
                    ["sysctl", "-n", "hw.physicalcpu"], capture_output=True, text=True
                ).stdout.strip()
            )
            threads = int(
                subprocess.run(
                    ["sysctl", "-n", "hw.logicalcpu"], capture_output=True, text=True
                ).stdout.strip()
            )
        except:
            pass

    try:
        import psutil

        usage = psutil.cpu_percent()
    except:
        usage = 0.0

    return CPUInfo(
        cores=cores,
        threads=threads,
        frequency_mhz=frequency,
        brand=brand,
        usage_percent=usage,
    )


def get_memory_info() -> MemoryInfo:
    """Get memory information."""
    try:
        import psutil

        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)
        available_gb = mem.available / (1024**3)
        return MemoryInfo(
            total_gb=round(total_gb, 2),
            available_gb=round(available_gb, 2),
            used_percent=mem.percent,
        )
    except:
        return MemoryInfo(total_gb=0, available_gb=0, used_percent=0)


def get_gpu_info() -> List[GPUInfo]:
    """Get GPU information."""
    gpus = []

    try:
        import torch

        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                vram = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                compute_cap = f"{torch.cuda.get_device_capability(i)[0]}.{torch.cuda.get_device_capability(i)[1]}"
                try:
                    usage = (
                        torch.cuda.memory_allocated(i)
                        / torch.cuda.get_device_properties(i).total_memory
                        * 100
                    )
                except:
                    usage = 0.0
                gpus.append(
                    GPUInfo(
                        name=name,
                        vram_gb=round(vram, 2),
                        compute_cap=compute_cap,
                        cuda_available=True,
                        usage_percent=usage,
                        memory_used_gb=round(vram * usage / 100, 2),
                    )
                )
    except ImportError:
        pass

    if not gpus:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,m Utilization.gpu,memory.used",
                    "--format=csv,noheader,n",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        name = parts[0]
                        vram_gb = (
                            float(parts[1].replace(" MiB", "").replace("GB", "")) / 1024
                            if "MiB" in parts[1]
                            else float(parts[1].replace("GB", ""))
                        )
                        usage = float(parts[2].replace("%", ""))
                        mem_used = (
                            float(parts[3].replace(" MiB", "").replace("GB", "")) / 1024
                            if "MiB" in parts[3]
                            else float(parts[3].replace("GB", ""))
                        )
                        gpus.append(
                            GPUInfo(
                                name=name,
                                vram_gb=round(vram_gb, 2),
                                compute_cap=None,
                                cuda_available=True,
                                usage_percent=usage,
                                memory_used_gb=round(mem_used, 2),
                            )
                        )
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

    if not gpus:
        try:
            result = subprocess.run(
                ["rocm-smi", "--json"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for gpu_id, info in data.get("devices", {}).items():
                    gpus.append(
                        GPUInfo(
                            name=info.get("Card Name", "AMD GPU"),
                            vram_gb=None,
                            compute_cap=None,
                            cuda_available=False,
                            usage_percent=info.get("GPU use (%)", 0),
                        )
                    )
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    return gpus


def get_hardware_info() -> HardwareInfo:
    """Get complete hardware information."""
    cpu = get_cpu_info()
    memory = get_memory_info()
    gpus = get_gpu_info()

    platform_map = {"win32": "Windows", "linux": "Linux", "darwin": "macOS"}

    return HardwareInfo(
        cpu=cpu,
        memory=memory,
        gpus=gpus,
        platform=platform_map.get(sys.platform, sys.platform),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )


def get_resource_usage() -> Dict[str, Any]:
    """Get current resource usage."""
    usage = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cpu_percent": 0,
        "memory_percent": 0,
        "gpu_percent": [],
    }

    try:
        import psutil

        usage["cpu_percent"] = psutil.cpu_percent(interval=1)
        usage["memory_percent"] = psutil.virtual_memory().percent
    except ImportError:
        pass

    try:
        import torch

        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                mem_used = torch.cuda.memory_allocated(i)
                mem_total = torch.cuda.get_device_properties(i).total_memory
                usage["gpu_percent"].append(
                    {
                        "device": i,
                        "memory_percent": round(mem_used / mem_total * 100, 2),
                        "memory_used_mb": round(mem_used / 1024**2, 2),
                    }
                )
    except ImportError:
        pass

    return usage


def detect_llm_frameworks() -> List[LLMFramework]:
    """Detect installed and running LLM frameworks."""
    frameworks = []

    ollama = detect_ollama()
    frameworks.append(ollama)

    vllm = detect_vllm()
    frameworks.append(vllm)

    lmstudio = detect_lmstudio()
    frameworks.append(lmstudio)

    return frameworks


def detect_ollama() -> LLMFramework:
    """Detect Ollama installation and status."""
    urls = [
        os.getenv("SHOESHINE_OLLAMA_URL", "http://localhost:11434"),
        "http://localhost:11434",
        "http://127.0.0.1:11434",
    ]

    running = False
    models = []
    error = None

    for url in urls:
        try:
            import httpx

            with httpx.Client(timeout=5) as client:
                response = client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    running = True
                    models = [m["name"] for m in response.json().get("models", [])]
                    break
        except Exception:
            continue

    return LLMFramework(
        name="ollama",
        installed=True,
        running=running,
        url=urls[0] if running else None,
        models=models,
        error=error,
    )


def detect_vllm() -> LLMFramework:
    """Detect vLLM installation and status."""
    urls = ["http://localhost:8000", "http://127.0.0.1:8000"]

    running = False
    models = []
    error = None

    for url in urls:
        try:
            import httpx

            with httpx.Client(timeout=5) as client:
                response = client.get(f"{url}/v1/models")
                if response.status_code == 200:
                    running = True
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]
                    break
        except Exception:
            continue

    return LLMFramework(
        name="vllm",
        installed=True,
        running=running,
        url=urls[0] if running else None,
        models=models,
        error=error,
    )


def detect_lmstudio() -> LLMFramework:
    """Detect LM Studio installation and status."""
    urls = ["http://localhost:1234", "http://127.0.0.1:1234"]

    running = False
    models = []
    error = None

    for url in urls:
        try:
            import httpx

            with httpx.Client(timeout=5) as client:
                response = client.get(f"{url}/v1/models")
                if response.status_code == 200:
                    running = True
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]
                    break
        except Exception:
            continue

    return LLMFramework(
        name="lmstudio",
        installed=True,
        running=running,
        url=urls[0] if running else None,
        models=models,
        error=error,
    )


def check_dependencies() -> Dict[str, Dict[str, Any]]:
    """Check if required dependencies are installed."""
    deps = {}

    dep_checks = [
        ("easyocr", "EasyOCR", "pip install easyocr"),
        ("torch", "PyTorch", "pip install torch"),
        ("transformers", "Transformers", "pip install transformers"),
        ("onnxruntime", "ONNX Runtime", "pip install onnxruntime"),
    ]

    for module, name, install_cmd in dep_checks:
        try:
            __import__(module)
            deps[name.lower()] = {"installed": True, "version": None}
        except ImportError:
            deps[name.lower()] = {"installed": False, "install_cmd": install_cmd}

    try:
        import easyocr

        deps["easyocr"]["version"] = getattr(easyocr, "__version__", "unknown")
    except:
        pass

    try:
        import torch

        deps["torch"]["version"] = torch.__version__
        deps["torch"]["cuda"] = torch.cuda.is_available()
    except:
        pass

    return deps


def get_performance_recommendations(hw: HardwareInfo) -> Dict[str, Any]:
    """Generate performance recommendations based on hardware."""
    recs = {
        "ocr_engine": "easyocr",
        "batch_size": 1,
        "llm_recommendation": "ollama",
        "warnings": [],
    }

    if not hw.gpus:
        recs["warnings"].append("No GPU detected - OCR will use CPU (slower)")
        if hw.memory.total_gb < 8:
            recs["warnings"].append("Less than 8GB RAM - consider reducing batch size")
    else:
        recs["ocr_engine"] = "easyocr"
        for gpu in hw.gpus:
            if gpu.vram_gb and gpu.vram_gb >= 4:
                recs["batch_size"] = 4
            elif gpu.vram_gb and gpu.vram_gb >= 2:
                recs["batch_size"] = 2

    if hw.cpu.cores < 4:
        recs["warnings"].append("Less than 4 CPU cores - performance may be limited")

    if hw.memory.total_gb < 4:
        recs["llm_recommendation"] = "ollama (small models only)"
        recs["warnings"].append("Less than 4GB RAM - use small LLM models")

    return recs


def run_diagnostics() -> Dict[str, Any]:
    """Run complete system diagnostics."""
    hw = get_hardware_info()
    frameworks = detect_llm_frameworks()
    deps = check_dependencies()
    usage = get_resource_usage()
    recs = get_performance_recommendations(hw)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hardware": {
            "platform": hw.platform,
            "python": hw.python_version,
            "cpu": {
                "cores": hw.cpu.cores,
                "threads": hw.cpu.threads,
                "brand": hw.cpu.brand,
                "usage_percent": hw.cpu.usage_percent,
            },
            "memory": {
                "total_gb": hw.memory.total_gb,
                "available_gb": hw.memory.available_gb,
                "used_percent": hw.memory.used_percent,
            },
            "gpus": [
                {
                    "name": g.name,
                    "vram_gb": g.vram_gb,
                    "cuda": g.cuda_available,
                    "usage_percent": g.usage_percent,
                }
                for g in hw.gpus
            ],
        },
        "frameworks": [
            {
                "name": f.name,
                "installed": f.installed,
                "running": f.running,
                "url": f.url,
                "models": f.models,
                "error": f.error,
            }
            for f in frameworks
        ],
        "dependencies": deps,
        "resource_usage": usage,
        "recommendations": recs,
    }


def print_diagnostics():
    """Print formatted diagnostics to console."""
    diag = run_diagnostics()

    print("=" * 60)
    print("SHOESHINE SYSTEM DIAGNOSTICS")
    print("=" * 60)

    hw = diag["hardware"]
    print(f"\nHardware:")
    print(f"  Platform: {hw['platform']} (Python {hw['python']})")
    print(f"  CPU: {hw['cpu']['brand']}")
    print(f"    Cores: {hw['cpu']['cores']}, Threads: {hw['cpu']['threads']}")
    print(f"    Usage: {hw['cpu']['usage_percent']:.1f}%")
    print(
        f"  Memory: {hw['memory']['total_gb']:.1f}GB total, {hw['memory']['available_gb']:.1f}GB available"
    )
    print(f"    Usage: {hw['memory']['used_percent']:.1f}%")

    if hw["gpus"]:
        print(f"  GPUs:")
        for gpu in hw["gpus"]:
            vram = f"{gpu['vram_gb']:.1f}GB" if gpu["vram_gb"] else "Unknown"
            print(f"    {gpu['name']} ({vram}, CUDA: {gpu['cuda']})")
            print(f"    Usage: {gpu['usage_percent']:.1f}%")

    print(f"\nLLM Frameworks:")
    for fw in diag["frameworks"]:
        status = "✓ Running" if fw["running"] else "✗ Not running"
        if fw["models"]:
            status += f" ({len(fw['models'])} models)"
        print(f"  {fw['name'].upper()}: {status}")
        if fw["url"]:
            print(f"    URL: {fw['url']}")

    print(f"\nDependencies:")
    for name, info in diag["dependencies"].items():
        if info.get("installed"):
            version = info.get("version", "")
            cuda = f" (CUDA)" if info.get("cuda") else ""
            print(f"  {name}: ✓ {version}{cuda}")
        else:
            print(f"  {name}: ✗ {info.get('install_cmd', 'install manually')}")

    print(f"\nRecommendations:")
    for warning in diag["recommendations"]["warnings"]:
        print(f"  ⚠ {warning}")
    print(f"  Recommended OCR: {diag['recommendations']['ocr_engine']}")
    print(f"  Recommended LLM: {diag['recommendations']['llm_recommendation']}")

    print("=" * 60)


if __name__ == "__main__":
    print_diagnostics()
