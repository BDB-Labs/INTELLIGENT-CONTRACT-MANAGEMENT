from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceSpec:
    key: str
    title: str
    subtitle: str
    headline: str
    supporting_copy: str
    route_path: str = "/"
    server_mode: str = "ese-dashboard"
    runtime_slug: str = "surface-runtime"
    window_title: str | None = None
    accent_start: str = "#78ffd6"
    accent_end: str = "#007cf0"
    glow: str = "rgba(120, 255, 214, 0.30)"


@dataclass(frozen=True)
class PlatformTarget:
    key: str
    label: str
    category: str
    status: str
    summary: str
    delivery_model: str


SURFACES: dict[str, SurfaceSpec] = {
    "icm-workbench": SurfaceSpec(
        key="icm-workbench",
        title="Operator Workbench",
        subtitle="Construction contract review, commitment, and monitoring",
        headline="Intelligent Contract Management",
        supporting_copy=(
            "A contract-specific operating surface for bid review, negotiation "
            "posture, obligations, and field monitoring. Powered by Ensemble "
            "Systems Engineering."
        ),
        route_path="/workbench",
        server_mode="contract-intelligence-api",
        runtime_slug="intelligent-contract-management",
        window_title="Intelligent Contract Management",
        accent_start="#b8d896",
        accent_end="#c56a2d",
        glow="rgba(197, 106, 45, 0.28)",
    ),
    "ese-dashboard": SurfaceSpec(
        key="ese-dashboard",
        title="Run Studio",
        subtitle="Task orchestration, review loops, and artifact intelligence",
        headline="ESE Control Center",
        supporting_copy=(
            "A native control surface for the ensemble runtime. Today it opens "
            "the ESE dashboard and command center; the same contract can support "
            "future contract-intelligence, Windows desktop, and SaaS surfaces."
        ),
        server_mode="ese-dashboard",
        runtime_slug="ese-control-center",
        window_title="ESE Control Center",
    ),
}


PLATFORM_TARGETS: dict[str, PlatformTarget] = {
    "macos-desktop": PlatformTarget(
        key="macos-desktop",
        label="macOS Desktop",
        category="desktop",
        status="active",
        summary="Native webview shell, packaged app bundle, and DMG distribution.",
        delivery_model="pywebview + PyInstaller + DMG",
    ),
    "windows-desktop": PlatformTarget(
        key="windows-desktop",
        label="Windows Desktop",
        category="desktop",
        status="planned",
        summary="Future native desktop distribution reusing the same surface registry and local runtime contract.",
        delivery_model="shared shell contract, Windows packaging pending",
    ),
    "saas-web": PlatformTarget(
        key="saas-web",
        label="SaaS Web",
        category="web",
        status="planned",
        summary="Hosted control center that can reuse surface metadata and service contracts while swapping the local launcher.",
        delivery_model="web app over shared APIs and artifacts",
    ),
}


def get_surface_spec(surface_key: str) -> SurfaceSpec:
    return SURFACES.get(surface_key, SURFACES["icm-workbench"])


def list_surface_specs() -> list[SurfaceSpec]:
    return list(SURFACES.values())


def get_platform_target(target_key: str) -> PlatformTarget:
    return PLATFORM_TARGETS[target_key]


def list_platform_targets() -> list[PlatformTarget]:
    return list(PLATFORM_TARGETS.values())
