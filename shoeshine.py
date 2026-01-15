#!/usr/bin/env python3
"""
Shoeshine CLI - All-in-one launcher and management tool.

Commands:
    python shoeshine.py run         - Start the API server
    python shoeshine.py diag        - Run system diagnostics
    python shoeshine.py check       - Check dependencies and services
    python shoeshine.py start-ollama - Start Ollama service
    python shoeshine.py pull MODEL  - Pull a model from Ollama
    python shoeshine.py test        - Run test suite
    python shoeshine.py monitor     - Monitor resource usage
"""

import os
import sys
import time
import argparse
import subprocess
import signal
from typing import Optional, List


def print_header():
    print("=" * 60)
    print("  SHOESHINE - Document Scanning Layer for Local LLMs")
    print("=" * 60)
    print()


def run_diagnostics():
    """Run and display system diagnostics."""
    print_header()
    print("Running system diagnostics...\n")

    from system_info import print_diagnostics


def check_dependencies():
    """Check dependencies and services."""
    print_header()
    print("Checking dependencies and services...\n")

    from system_info import check_dependencies, detect_llm_frameworks, get_hardware_info

    print("Dependencies:")
    deps = check_dependencies()
    all_good = True
    for name, info in deps.items():
        if info.get("installed"):
            version = info.get("version", "")
            cuda = " (CUDA)" if info.get("cuda") else ""
            print(f"  [OK] {name}: {version}{cuda}")
        else:
            print(f"  [MISSING] {name}: NOT INSTALLED")
            if info.get("install_cmd"):
                print(f"    Run: {info['install_cmd']}")
            all_good = False

    print("\nLLM Frameworks:")
    frameworks = detect_llm_frameworks()
    for fw in frameworks:
        status = "Running" if fw.running else "Not running"
        if fw.running and fw.models:
            status += f" ({len(fw.models)} models)"
        print(f"  {fw.name.upper()}: {status}")

    hw = get_hardware_info()
    print(f"\nHardware:")
    print(f"  CPU: {hw.cpu.brand} ({hw.cpu.cores} cores, {hw.cpu.threads} threads)")
    print(f"  Memory: {hw.memory.total_gb:.1f}GB")
    if hw.gpus:
        for gpu in hw.gpus:
            vram = f"{gpu.vram_gb:.1f}GB" if gpu.vram_gb else "Unknown"
            print(f"  GPU: {gpu.name} ({vram})")
    else:
        print("  GPU: None detected (CPU-only mode)")

    if all_good:
        print("\n[OK] All dependencies are satisfied!")
    else:
        print("\n[MISSING] Some dependencies are missing. Install them above.")


def start_ollama():
    """Start Ollama service."""
    print_header()
    print("Starting Ollama...\n")

    try:
        import httpx

        with httpx.Client(timeout=2) as client:
            response = client.get("http://localhost:11434/api/version")
            if response.status_code == 200:
                print("Ollama is already running at http://localhost:11434")
                return
    except:
        pass

    print("Attempting to start Ollama...")

    if sys.platform == "darwin":
        try:
            subprocess.run(["ollama", "serve"], check=True)
            print("Ollama started (macOS)")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("Ollama not found. Install from https://ollama.com")

    elif sys.platform == "linux":
        try:
            result = subprocess.run(["which", "ollama"], capture_output=True)
            if result.returncode != 0:
                print(
                    "Ollama not found. Install with: curl -fsSL https://ollama.ai/install.sh | sh"
                )
                return

            subprocess.run(["ollama", "serve"], check=True)
            print("Ollama started (Linux)")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("Failed to start Ollama")

    elif sys.platform == "win32":
        try:
            result = subprocess.run(
                ["where", "ollama"], capture_output=True, shell=True
            )
            if result.returncode != 0:
                print("Ollama not found. Install from https://ollama.com")
                return

            subprocess.Popen(["ollama", "serve"], shell=True)
            print("Ollama started (Windows)")
            print("Note: Ollama should now be running in the background")
        except Exception as e:
            print(f"Failed to start Ollama: {e}")


def pull_model(model: str):
    """Pull a model from Ollama."""
    print_header()
    print(f"Pulling model: {model}\n")

    if sys.platform == "win32":
        result = subprocess.run(
            ["ollama", "pull", model], shell=True, capture_output=True, text=True
        )
    else:
        result = subprocess.run(
            ["ollama", "pull", model], capture_output=True, text=True
        )

    if result.returncode == 0:
        print(f"✓ Successfully pulled {model}")
    else:
        print(f"✗ Failed to pull {model}")
        if result.stderr:
            print(f"Error: {result.stderr}")


def run_server():
    """Start the Shoeshine API server."""
    print_header()
    print("Starting Shoeshine API server...\n")

    config_env = {
        "SHOESHINE_HOST": "0.0.0.0",
        "SHOESHINE_PORT": "8000",
    }

    env = os.environ.copy()
    for key, value in config_env.items():
        env[key] = value

    cmd = [sys.executable, "api_server.py"]

    print(f"Running: {' '.join(cmd)}")
    print(f"API will be available at http://localhost:8000")
    print(f"Documentation at http://localhost:8000/docs")
    print()

    if sys.platform == "win32":
        subprocess.run(cmd, env=env, shell=True)
    else:
        subprocess.run(cmd, env=env)


def run_tests():
    """Run the test suite."""
    print_header()
    print("Running tests...\n")

    cmd = [sys.executable, "-m", "pytest", "tests/test_local_only.py", "-v"]

    if sys.platform == "win32":
        subprocess.run(cmd, shell=True)
    else:
        subprocess.run(cmd)


def monitor_resources(interval: int = 2):
    """Monitor resource usage in real-time."""
    print_header()
    print("Monitoring resource usage (Ctrl+C to stop)...\n")

    try:
        import psutil
        import torch

        has_psutil = True
        has_torch = True
    except ImportError:
        has_psutil = False
        has_torch = False
        print("Note: Install psutil and torch for full monitoring")
        print()

    try:
        while True:
            import datetime

            now = datetime.datetime.now().strftime("%H:%M:%S")

            if has_psutil:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                mem_percent = mem.percent
            else:
                cpu = 0
                mem_percent = 0

            gpu_info = ""
            if has_torch:
                try:
                    import torch

                    if torch.cuda.is_available():
                        mem_used = torch.cuda.memory_allocated(0) / 1024**3
                        mem_total = (
                            torch.cuda.get_device_properties(0).total_memory / 1024**3
                        )
                        gpu_info = f" | GPU: {mem_used:.1f}/{mem_total:.1f}GB"
                except:
                    pass

            cpu_bar = "#" * int(cpu / 5) + "-" * (20 - int(cpu / 5))
            mem_bar = "#" * int(mem_percent / 5) + "-" * (20 - int(mem_percent / 5))

            print(
                f"[{now}] CPU: {cpu:5.1f}% [{cpu_bar}] | "
                f"RAM: {mem_percent:5.1f}% [{mem_bar}]{gpu_info}"
            )

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")


def main():
    parser = argparse.ArgumentParser(
        description="Shoeshine CLI - All-in-one management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python shoeshine.py run         Start the API server
  python shoeshine.py diag        Run system diagnostics
  python shoeshine.py check       Check dependencies and services
  python shoeshine.py start-ollama Start Ollama service
  python shoeshine.py pull llama3 Pull a model
  python shoeshine.py test        Run test suite
  python shoeshine.py monitor     Monitor resources
        """,
    )

    parser.add_argument(
        "command",
        choices=["run", "diag", "check", "start-ollama", "pull", "test", "monitor"],
        help="Command to run",
    )

    parser.add_argument(
        "model", nargs="?", default="llama3", help="Model name for 'pull' command"
    )

    parser.add_argument(
        "-i", "--interval", type=int, default=2, help="Monitoring interval in seconds"
    )

    args = parser.parse_args()

    if args.command == "diag":
        run_diagnostics()
    elif args.command == "check":
        check_dependencies()
    elif args.command == "start-ollama":
        start_ollama()
    elif args.command == "pull":
        pull_model(args.model)
    elif args.command == "run":
        run_server()
    elif args.command == "test":
        run_tests()
    elif args.command == "monitor":
        monitor_resources(args.interval)


if __name__ == "__main__":
    main()
