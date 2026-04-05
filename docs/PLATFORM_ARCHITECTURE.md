# Platform Architecture

## Current posture

The repository now treats the UI as a shared control surface, not just a browser page.

There are three layers:

1. `ese` core
   - CLI commands
   - pipeline execution
   - report and artifact logic

2. shared surface catalog
   - `ese/platform/catalog.py`
   - declares reusable surface metadata and delivery targets
   - keeps macOS, Windows, and SaaS from diverging at the product-definition level

3. platform launchers
   - `ese/desktop/*` for local desktop shells
   - `packaging/macos/*` for native macOS distribution
   - future `packaging/windows/*` and hosted web surfaces should reuse the same surface catalog and backend contracts

## Design rules

- Keep business logic in `ese`, not in packaging scripts.
- Keep surface metadata generic so the same surface can be launched by desktop or hosted runtimes.
- Let platform launchers own windowing, packaging, and local process lifecycle.
- Prefer shared HTTP or service contracts over platform-specific branching in the core logic.

## macOS

macOS is the first fully implemented desktop target.

- Launcher entry: `ese.desktop.app`
- Local runtime: `ese.desktop.runtime.SubprocessDashboardRuntime`
- Branding and splash: `ese.desktop.branding`
- Packaging path: `scripts/build_macos_desktop.sh`

The desktop shell launches a child process for the dashboard server and loads it into a native webview. That separation is intentional: it keeps the control surface portable while letting packaging remain platform-specific.

## Windows

Windows should reuse:

- `ese/platform/catalog.py`
- the dashboard/server contracts
- the desktop runtime lifecycle pattern

Windows-specific work should live under `packaging/windows/` and only replace:

- installer format
- app bundle metadata
- native shell and signing details

## SaaS

The SaaS target should reuse:

- the surface catalog
- report and artifact APIs
- command coverage model from the control center

The hosted variant should replace:

- local process launch
- filesystem assumptions
- local artifact browsing with authenticated service-backed storage

## UI parity

The control center currently covers:

- task runs
- config-backed runs
- PR review
- rerun from role
- report viewing
- artifact viewing
- export
- feedback
- doctor validation
- command, pack, role, surface, and platform catalogs

The remaining large CLI gap is the interactive `init` wizard. When that moves into the UI, it should be implemented as a guided setup flow against shared config-generation functions, not a second independent wizard.
