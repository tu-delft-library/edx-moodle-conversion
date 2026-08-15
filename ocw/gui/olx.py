import argparse
import logging
import shutil
import tarfile
import tempfile
from pathlib import Path
from tkinter import StringVar, Tk, filedialog, ttk

from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.gui.common import ConverterApp, _input_label
from ocw.hybrid_checks import log_hybrid_checks
from ocw.parser import Course
from ocw.utils import versioned_output_path


class App(ConverterApp):
    WINDOW_TITLE = "OLX to Moodle Converter"

    def __init__(self, root: Tk, log_file: Path | None = None) -> None:
        self.mode = StringVar(value="files")
        super().__init__(root, log_file)

    def _build_source_widgets(self, pad: dict) -> None:
        mode_frame = ttk.Frame(self.root)
        mode_frame.pack(fill="x", **pad)
        ttk.Radiobutton(
            mode_frame,
            text="Files (.tar.gz)",
            variable=self.mode,
            value="files",
            command=self._reset_input,
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frame,
            text="Folder (all .tar.gz inside)",
            variable=self.mode,
            value="folder",
            command=self._reset_input,
        ).pack(side="left")

    def _choose_input(self) -> None:
        if self.mode.get() == "files":
            paths = filedialog.askopenfilenames(
                filetypes=[("OLX archive", "*.tar.gz"), ("All files", "*.*")]
            )
            self.input_paths = [Path(p) for p in paths]
        else:
            folder = filedialog.askdirectory()
            self.input_paths = sorted(Path(folder).glob("*.tar.gz")) if folder else []

        if not self.input_paths:
            return
        summary = (
            _input_label(self.input_paths[0])
            if len(self.input_paths) == 1
            else f"{len(self.input_paths)} courses selected"
        )
        self.input_var.set(summary)
        self._populate_sidebar()

    def _convert_one(self, path: Path) -> Path:
        tmp = None
        fetch_tmp = None
        try:
            fetcher = None
            if self.fetch_external_assets.get():
                fetch_tmp = Path(tempfile.mkdtemp())
                fetcher = AssetFetcher(fetch_tmp)

            olx_path = path
            if path.suffix == ".gz":
                tmp = Path(tempfile.mkdtemp())
                with tarfile.open(path) as tar:
                    tar.extractall(tmp)
                olx_path = next(p for p in tmp.iterdir() if p.is_dir())
            course = Course(olx_path, fetcher=fetcher)
            course.parse()
            name = path.name.removesuffix(".tar.gz") if path.suffix == ".gz" else path.stem

            out = versioned_output_path(self.output_dir / f"{name}.mbz")
            MBZBuilder(
                course,
                sequential_sections=self.sequential_sections.get(),
                disable_custom_fields=not self.enable_custom_fields.get(),
            ).build(out)
            log_hybrid_checks(olx_path, out, logging.getLogger("ocw"))
            return out
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
            if fetch_tmp:
                shutil.rmtree(fetch_tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="OLX to Moodle Converter GUI")
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
