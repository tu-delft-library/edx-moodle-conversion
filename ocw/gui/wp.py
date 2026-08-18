import argparse
import shutil
import tempfile
from pathlib import Path
from tkinter import Tk, Toplevel, ttk
from tkinter.scrolledtext import ScrolledText

from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.gui.common import ConverterApp, _input_label
from ocw.utils import versioned_output_path
from ocw.wp_parser import WPCourse

WP_WINDOW_TITLE = "WordPress to Moodle Converter"


class App(ConverterApp):
    """Provide the GUI workflow for converting WordPress course sites."""

    WINDOW_TITLE = WP_WINDOW_TITLE

    def _ask_urls(self) -> str | None:
        """Open a modal dialog for one course home-page URL per line.

        Returns the entered text, or `None` when the dialog is cancelled.
        """
        dialog = Toplevel(self.root)
        dialog.title("WordPress course URLs")
        dialog.geometry("560x360")
        dialog.transient(self.root)
        dialog.grab_set()

        result: dict[str, str | None] = {"value": None}

        def on_ok() -> None:
            result["value"] = text_box.get("1.0", "end-1c")
            dialog.destroy()

        def on_cancel() -> None:
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side="right")
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(
            side="right", padx=(0, 8)
        )

        ttk.Label(dialog, text="Course home page URL(s), one per line:").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        text_box = ScrolledText(dialog, wrap="none")
        text_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        text_box.focus_set()

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.bind("<Escape>", lambda _e: on_cancel())
        dialog.bind("<Control-Return>", lambda _e: on_ok())
        dialog.wait_window()
        return result["value"]

    def _choose_input(self) -> None:
        """Collect course URLs from the dialog and populate the sidebar."""
        raw = self._ask_urls()
        self.input_paths = [line.strip() for line in (raw or "").splitlines() if line.strip()]
        if not self.input_paths:
            return
        summary = (
            _input_label(self.input_paths[0])
            if len(self.input_paths) == 1
            else f"{len(self.input_paths)} courses selected"
        )
        self.input_var.set(summary)
        self._populate_sidebar()

    def _convert_one(self, path: str) -> Path:
        """Scrape one WordPress course site and build its versioned MBZ archive.

        The temporary directory used for fetched external assets is removed after conversion.
        """
        fetch_tmp = None
        try:
            fetcher = None
            if self.fetch_external_assets.get():
                fetch_tmp = Path(tempfile.mkdtemp())
                fetcher = AssetFetcher(fetch_tmp)

            course = WPCourse(path, fetcher=fetcher)
            course.parse()
            name = _input_label(path)

            out = versioned_output_path(self.output_dir / f"{name}.mbz")
            MBZBuilder(
                course,
                sequential_sections=self.sequential_sections.get(),
                disable_custom_fields=not self.enable_custom_fields.get(),
            ).build(out)
            return out
        finally:
            if fetch_tmp:
                shutil.rmtree(fetch_tmp, ignore_errors=True)


def main() -> None:
    """Launch the WordPress conversion GUI.

    `--log-file` optionally mirrors application logs to a file for development and diagnosis.
    """
    ap = argparse.ArgumentParser(description="WordPress to Moodle Converter GUI")
    ap.add_argument(
        "--log-file",
        type=Path,
        nargs="?",
        const=Path("ocw.log"),
        default=None,
        help="dev/testing only: also write logs to this file (default: ocw.log)",
    )
    args = ap.parse_args()

    root = Tk()
    App(root, log_file=args.log_file)
    root.mainloop()


if __name__ == "__main__":
    main()
