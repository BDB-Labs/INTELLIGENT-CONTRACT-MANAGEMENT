from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

desktop_app = importlib.import_module("ese.desktop.app")
desktop_branding = importlib.import_module("ese.desktop.branding")
desktop_config = importlib.import_module("ese.desktop.config")
desktop_runtime = importlib.import_module("ese.desktop.runtime")
platform_catalog = importlib.import_module("ese.platform.catalog")
dashboard_module = importlib.import_module("ese.dashboard")

DesktopLaunchConfig = desktop_config.DesktopLaunchConfig
get_surface_spec = desktop_config.get_surface_spec
render_splash_html = desktop_branding.render_splash_html
build_server_command = desktop_runtime.build_server_command
SubprocessDashboardRuntime = desktop_runtime.SubprocessDashboardRuntime
list_platform_targets = platform_catalog.list_platform_targets
list_surface_specs = platform_catalog.list_surface_specs
catalog_payload = dashboard_module._catalog_payload
config_preview_payload = dashboard_module._config_preview_payload
save_config_payload = dashboard_module._save_config_payload


def test_surface_registry_falls_back_to_dashboard_surface() -> None:
    surface = get_surface_spec("unknown-surface")

    assert surface.key == "ese-dashboard"
    assert surface.title == "Run Studio"


def test_render_splash_html_includes_brand_copy() -> None:
    surface = get_surface_spec("ese-dashboard")
    html = render_splash_html(surface)

    assert "ESE Control Center" in html
    assert "macOS-first, multi-platform-ready" in html
    assert surface.subtitle in html


def test_build_server_command_uses_module_entrypoint_in_dev_mode() -> None:
    command = build_server_command(
        DesktopLaunchConfig(
            artifacts_dir="artifacts",
            host="127.0.0.1",
            port=9001,
            config_path="ese.config.yaml",
        )
    )

    assert command[:3] == [sys.executable, "-m", "ese.desktop.app"]
    assert "--server" in command
    assert "9001" in command
    assert "ese.config.yaml" in command


def test_subprocess_runtime_allocates_local_port_when_unspecified() -> None:
    runtime = SubprocessDashboardRuntime(DesktopLaunchConfig(port=0))

    assert runtime.bound_port > 0
    assert runtime.url.startswith("http://127.0.0.1:")


def test_platform_catalog_includes_future_targets() -> None:
    targets = {item.key for item in list_platform_targets()}

    assert "macos-desktop" in targets
    assert "windows-desktop" in targets
    assert "saas-web" in targets


def test_catalog_payload_exposes_commands_and_surfaces() -> None:
    payload = catalog_payload()

    command_names = {item["command"] for item in payload["commands"]}
    surface_names = {item.key for item in list_surface_specs()}

    assert "doctor" in command_names
    assert "platforms" in command_names
    assert "ese-dashboard" in surface_names
    assert payload["platforms"]


def test_task_config_preview_payload_exposes_yaml_and_cli_equivalent() -> None:
    payload = config_preview_payload(
        {
            "workflow": "task",
            "scope": "Review a staged release checklist",
            "template_key": "release-readiness",
            "provider": "openai",
            "execution_mode": "demo",
            "artifacts_dir": "artifacts",
        },
        root_artifacts_dir="artifacts",
    )

    assert payload["workflow"] == "task"
    assert "ese task" in payload["command_preview"]
    assert "template_key: release-readiness" in payload["config_yaml"]


def test_save_config_payload_writes_generated_config(tmp_path: Path) -> None:
    target = tmp_path / "preview.config.yaml"

    payload = save_config_payload(
        {
            "workflow": "task",
            "scope": "Review a staged release checklist",
            "template_key": "feature-delivery",
            "provider": "openai",
            "execution_mode": "demo",
            "artifacts_dir": "artifacts",
            "config_path": str(target),
        },
        root_artifacts_dir="artifacts",
    )

    assert payload["config_path"] == str(target)
    assert target.exists()
    assert "feature-delivery" in target.read_text(encoding="utf-8")
