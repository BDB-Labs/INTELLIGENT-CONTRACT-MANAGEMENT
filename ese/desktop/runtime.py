from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from ese.desktop.config import DesktopLaunchConfig, get_surface_spec


@dataclass(frozen=True)
class RuntimePaths:
    log_dir: Path
    stdout_log: Path
    stderr_log: Path


def build_server_command(config: DesktopLaunchConfig) -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "--server",
            "--artifacts-dir",
            config.artifacts_dir,
            "--host",
            config.host,
            "--port",
            str(config.port),
            *(["--config", config.config_path] if config.config_path else []),
        ]

    return [
        sys.executable,
        "-m",
        "ese.desktop.app",
        "--server",
        "--artifacts-dir",
        config.artifacts_dir,
        "--host",
        config.host,
        "--port",
        str(config.port),
        *(["--config", config.config_path] if config.config_path else []),
    ]


def runtime_paths(app_name: str = "ese-control-center") -> RuntimePaths:
    root = Path.home() / "Library" / "Logs" / app_name
    root.mkdir(parents=True, exist_ok=True)
    return RuntimePaths(
        log_dir=root,
        stdout_log=root / "dashboard-stdout.log",
        stderr_log=root / "dashboard-stderr.log",
    )


def allocate_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class SubprocessDashboardRuntime:
    def __init__(self, config: DesktopLaunchConfig) -> None:
        bound_port = config.port or allocate_local_port()
        self.config = DesktopLaunchConfig(
            artifacts_dir=config.artifacts_dir,
            host=config.host,
            port=bound_port,
            config_path=config.config_path,
            surface=config.surface,
            window_title=config.window_title,
            width=config.width,
            height=config.height,
            min_width=config.min_width,
            min_height=config.min_height,
            debug=config.debug,
            browser_fallback=config.browser_fallback,
        )
        self.surface = get_surface_spec(config.surface)
        self.process: subprocess.Popen[str] | None = None
        self.paths = runtime_paths()

    @property
    def bound_port(self) -> int:
        return self.config.port

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.bound_port}{self.surface.route_path}"

    def start(self) -> str:
        if self.process is not None and self.process.poll() is None:
            return self.url

        command = build_server_command(self.config)
        stdout_handle = self.paths.stdout_log.open("w", encoding="utf-8")
        stderr_handle = self.paths.stderr_log.open("w", encoding="utf-8")
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        self.process = subprocess.Popen(
            command,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            env=env,
        )
        self.wait_until_ready()
        return self.url

    def wait_until_ready(self, *, timeout: float = 25.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(
                    "Desktop dashboard runtime exited before it became ready. "
                    f"See logs in {self.paths.log_dir}."
                )
            try:
                with urlopen(self.url, timeout=1.0) as response:  # noqa: S310
                    if response.status < 500:
                        return
            except URLError:
                time.sleep(0.2)
                continue
        raise TimeoutError(
            "Timed out waiting for the desktop dashboard runtime to become ready. "
            f"See logs in {self.paths.log_dir}."
        )

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
