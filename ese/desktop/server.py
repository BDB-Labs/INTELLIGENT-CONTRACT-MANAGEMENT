from __future__ import annotations

from ese.dashboard import serve_dashboard
from ese.desktop.config import DesktopLaunchConfig, get_surface_spec


def serve_desktop_surface(config: DesktopLaunchConfig) -> None:
    surface = get_surface_spec(config.surface)

    if surface.server_mode == "ese-dashboard":
        serve_dashboard(
            artifacts_dir=config.artifacts_dir,
            host=config.host,
            port=config.port,
            open_browser=False,
            config_path=config.config_path,
        )
        return

    if surface.server_mode == "contract-intelligence-api":
        from apps.contract_intelligence.api.app import serve_contract_intelligence_api

        serve_contract_intelligence_api(host=config.host, port=config.port)
        return

    raise ValueError(
        f"Unsupported desktop surface server mode '{surface.server_mode}' for '{surface.key}'."
    )
