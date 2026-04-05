from __future__ import annotations

from dataclasses import dataclass

from ese.platform import get_surface_spec as _get_surface_spec
from ese.platform.catalog import SurfaceSpec


DesktopSurfaceSpec = SurfaceSpec
get_surface_spec = _get_surface_spec


@dataclass(frozen=True)
class DesktopLaunchConfig:
    artifacts_dir: str = "artifacts"
    host: str = "127.0.0.1"
    port: int = 0
    config_path: str | None = None
    surface: str = "icm-workbench"
    window_title: str | None = None
    width: int = 1500
    height: int = 980
    min_width: int = 1180
    min_height: int = 760
    debug: bool = False
    browser_fallback: bool = True
