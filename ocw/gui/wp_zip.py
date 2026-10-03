import argparse
import logging
import shutil
import tempfile
from pathlib import Path
from tkinter import Tk

from ocw.converter.zip_builder import ZipBuilder
from ocw.fetcher import AssetFetcher
from ocw.gui.common import _input_label
from ocw.gui.wp import App as WPApp
from ocw.parser.wp import WPCourse
from ocw.utils import versioned_output_path
from ocw.zip_checks import log_zip_checks

ZIP_WINDOW_TITLE = "WordPress to Zip Converter"


class App(WPApp):
    """Provide the GUI workflow for backing up WordPress course sites as zip archives."""

    WINDOW_TITLE = ZIP_WINDOW_TITLE
    MBZ_OPTIONS = False

    def _build_source_widgets(self, pad: dict) -> None:
        """Drop the WordPress MBZ-only license footer checkbox, the zip keeps no footer."""

    def _convert_one(self, path: str) -> Path:
        """Scrape one WordPress course site and build its versioned zip archive.

        The temporary directory used for fetched external assets is removed after conversion.
        """
        fetch_tmp = None
        try:
            fetcher = None
            if self.fetch_external_assets.get():
                fetch_tmp = Path(tempfile.mkdtemp())
                fetcher = AssetFetcher(fetch_tmp)

            course = WPCourse(path, fetcher=fetcher, keep_all_content=True)
            course.parse()
            name = _input_label(path)

            out = versioned_output_path(self.output_dir / f"{name}.zip")
            ZipBuilder(course).build(out)
            log_zip_checks(course, out, logging.getLogger("ocw.zip_checks"))
            return out
        finally:
            if fetch_tmp:
                shutil.rmtree(fetch_tmp, ignore_errors=True)


def main() -> None:
    """Launch the WordPress zip backup GUI.

    `--log-file` optionally mirrors application logs to a file for development and diagnosis.
    """
    ap = argparse.ArgumentParser(description="WordPress to Zip Converter GUI")
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
