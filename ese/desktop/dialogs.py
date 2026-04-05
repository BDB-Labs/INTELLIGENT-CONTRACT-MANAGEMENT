from __future__ import annotations

from pathlib import Path
from typing import Sequence


class DesktopPathDialogAPI:
    def __init__(self) -> None:
        self.window = None

    def attach(self, window) -> None:  # noqa: ANN001
        self.window = window

    def choose_path(
        self,
        kind: str,
        directory: str = "",
        allow_multiple: bool = False,
        save_filename: str = "",
        file_types: Sequence[str] | None = None,
    ) -> str | list[str] | None:
        if self.window is None:
            raise RuntimeError("Desktop dialog API is not attached to a window.")

        import webview

        dialog_kind = {
            "open-file": webview.FileDialog.OPEN,
            "directory": webview.FileDialog.FOLDER,
            "save-file": webview.FileDialog.SAVE,
        }.get(kind)
        if dialog_kind is None:
            raise ValueError(f"Unsupported dialog kind: {kind}")

        start_dir = directory.strip()
        if start_dir:
            resolved = Path(start_dir).expanduser()
            if resolved.exists():
                start_dir = str(resolved.resolve())
            else:
                start_dir = str(resolved.parent.resolve()) if resolved.parent.exists() else ""

        selected = self.window.create_file_dialog(
            dialog_type=dialog_kind,
            directory=start_dir,
            allow_multiple=allow_multiple,
            save_filename=save_filename,
            file_types=tuple(file_types or ()),
        )
        if not selected:
            return None

        paths = [str(Path(item).expanduser().resolve()) for item in selected]
        if allow_multiple:
            return paths
        return paths[0]
