from __future__ import annotations

import argparse
import time
import webbrowser

from ese.dashboard import serve_dashboard
from ese.desktop.branding import render_splash_html
from ese.desktop.config import DesktopLaunchConfig, get_surface_spec
from ese.desktop.runtime import SubprocessDashboardRuntime


def launch_desktop_app(config: DesktopLaunchConfig | None = None) -> None:
    launch_config = config or DesktopLaunchConfig()
    runtime = SubprocessDashboardRuntime(launch_config)
    surface = get_surface_spec(launch_config.surface)

    try:
        url = runtime.start()
        try:
            import webview
        except ModuleNotFoundError:
            if not launch_config.browser_fallback:
                raise RuntimeError(
                    "pywebview is not installed and browser fallback is disabled."
                ) from None
            webbrowser.open(url)
            while runtime.process is not None and runtime.process.poll() is None:
                time.sleep(0.5)
            return

        window = webview.create_window(
            launch_config.window_title,
            html=render_splash_html(surface),
            width=launch_config.width,
            height=launch_config.height,
            min_size=(launch_config.min_width, launch_config.min_height),
            text_select=True,
            background_color="#08111c",
        )

        def _load_surface(target_window):  # noqa: ANN001
            target_window.load_url(url)

        webview.start(_load_surface, window, debug=launch_config.debug)
    finally:
        runtime.stop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the ESE desktop shell.")
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run only the dashboard server. Used by the desktop shell launcher.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Artifacts directory used by the dashboard surface.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard host.")
    parser.add_argument("--port", default=0, type=int, help="Dashboard port.")
    parser.add_argument(
        "--config",
        default=None,
        help="Optional config path to prefill the dashboard.",
    )
    parser.add_argument(
        "--surface",
        default="ese-dashboard",
        help="Desktop surface key to launch.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable desktop shell debug mode.",
    )
    parser.add_argument(
        "--no-browser-fallback",
        action="store_true",
        help="Disable opening the system browser when pywebview is unavailable.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.server:
        serve_dashboard(
            artifacts_dir=args.artifacts_dir,
            host=args.host,
            port=args.port,
            open_browser=False,
            config_path=args.config,
        )
        return

    launch_desktop_app(
        DesktopLaunchConfig(
            artifacts_dir=args.artifacts_dir,
            host=args.host,
            port=args.port,
            config_path=args.config,
            surface=args.surface,
            debug=args.debug,
            browser_fallback=not args.no_browser_fallback,
        )
    )


if __name__ == "__main__":
    main()
