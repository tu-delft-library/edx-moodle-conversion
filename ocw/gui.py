import logging
import os
import queue
import re
import shutil
import sys
import tarfile
import tempfile
import threading
import traceback
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from ocw.converter import MBZBuilder
from ocw.parser import Course
from ocw.utils import run_hybrid_checks

if sys.platform.startswith("linux"):
    os.environ.setdefault("TK_USE_PORTAL", "1")

_LOG_LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}) \[(\w+)\] (.*)$")


class _QueueLogHandler(logging.Handler):
    """Routes ocw.* log records into the GUI's log queue for display."""

    def __init__(self, log_callback) -> None:
        super().__init__()
        self._log_callback = log_callback
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
            )
        )

    def emit(self, record: logging.LogRecord) -> None:
        self._log_callback(self.format(record))


class App:
    def __init__(self, root: Tk) -> None:
        """Set up state vars and build the window."""
        self.root = root
        root.title("OLX to Moodle Converter")
        root.geometry("640x420")

        self.mode = StringVar(value="files")
        self.sequential_sections = BooleanVar(value=False)
        self.enable_custom_fields = BooleanVar(value=True)
        self.debug = BooleanVar(value=False)
        self.input_paths: list[Path] = []
        self.input_var = StringVar(value="")
        self.output_dir = Path.cwd()
        self.output_var = StringVar(value=str(self.output_dir))
        self._log_queue: queue.Queue[str] = queue.Queue()

        self._build_widgets()
        self._setup_logging()
        self.root.after(100, self._drain_log_queue)

    def _setup_logging(self) -> None:
        """Route the ocw logger hierarchy (parser/converter) into the log box."""
        log = logging.getLogger("ocw")
        log.setLevel(logging.INFO)
        log.addHandler(_QueueLogHandler(self._log))

    def _build_widgets(self) -> None:
        """Lay out mode/input/output/convert widgets and the log box."""
        pad = {"padx": 8, "pady": 4}

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

        input_frame = ttk.Frame(self.root)
        input_frame.pack(fill="x", **pad)
        ttk.Button(
            input_frame, text="Choose input...", command=self._choose_input
        ).pack(side="left")
        ttk.Label(input_frame, textvariable=self.input_var).pack(side="left", padx=8)

        output_frame = ttk.Frame(self.root)
        output_frame.pack(fill="x", **pad)
        ttk.Button(
            output_frame, text="Choose output directory...", command=self._choose_output
        ).pack(side="left")
        ttk.Label(output_frame, textvariable=self.output_var).pack(side="left", padx=8)

        ttk.Checkbutton(
            self.root,
            text="Flatten sub-sections (one section per sequential)",
            variable=self.sequential_sections,
        ).pack(anchor="w", **pad)

        ttk.Checkbutton(
            self.root,
            text="Enable Edusources custom fields",
            variable=self.enable_custom_fields,
        ).pack(anchor="w", **pad)

        ttk.Checkbutton(
            self.root,
            text="Debug logging",
            variable=self.debug,
        ).pack(anchor="w", **pad)

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", **pad)
        self.convert_button = ttk.Button(
            button_frame, text="Convert", command=self._start_convert
        )
        self.convert_button.pack(side="left", fill="x", expand=True)
        ttk.Button(button_frame, text="Done", command=self.root.destroy).pack(
            side="left", fill="x", expand=True
        )

        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(progress_frame, text="")
        self.progress_label.pack(side="left", padx=8)

        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_box = ScrolledText(log_frame, state="disabled", height=14)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_configure("green", foreground="#2e7d32")
        self.log_box.tag_configure("red", foreground="#c62828")
        self.log_box.tag_configure("yellow", foreground="#f9a825")
        self.log_box.tag_configure("black", foreground="black")
        self.log_box.tag_configure("gray", foreground="gray")

        copy_frame = ttk.Frame(self.root)
        copy_frame.pack(fill="x", **pad)
        ttk.Button(copy_frame, text="Copy log", command=self._copy_log).pack(side="right")

    def _reset_input(self) -> None:
        """Clear the chosen input paths when the mode switches."""
        self.input_paths = []
        self.input_var.set("")

    def _choose_input(self) -> None:
        """Prompt for one or more .tar.gz files, or a folder to glob them from."""
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
            self.input_paths[0].name
            if len(self.input_paths) == 1
            else f"{len(self.input_paths)} files selected"
        )
        self.input_var.set(summary)

    def _choose_output(self) -> None:
        """Prompt for the output directory the .mbz file(s) get written to."""
        path = filedialog.askdirectory()
        if path:
            self.output_dir = Path(path)
            self.output_var.set(path)

    def _log(self, message: str) -> None:
        """Queue a message for the log box (safe to call from a worker thread)."""
        self._log_queue.put(message)

    def _copy_log(self) -> None:
        """Copy the full log box contents to the clipboard."""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_box.get("1.0", "end-1c"))

    def _start_convert(self) -> None:
        """Validate selections and kick off the background conversion thread."""
        if not self.input_paths or not self.output_dir:
            self._log("Pick an input and an output directory first.")
            return
        logging.getLogger("ocw").setLevel(
            logging.DEBUG if self.debug.get() else logging.INFO
        )
        total = len(self.input_paths)
        self.progress["maximum"] = total
        self.progress["value"] = 0
        self.progress_label.config(text=f"0 / {total} courses")
        self.convert_button.state(["disabled"])
        threading.Thread(target=self._convert_worker, daemon=True).start()

    def _advance_progress(self) -> None:
        """Bump the progress bar by one completed course (queued onto the main
        thread via root.after — ttk widgets aren't thread-safe to touch directly
        from the worker thread)."""
        self.progress["value"] += 1
        self.progress_label.config(
            text=f"{int(self.progress['value'])} / {int(self.progress['maximum'])} courses"
        )

    def _convert_worker(self) -> None:
        """Run on a background thread: convert each course, isolating failures."""
        for course_path in self.input_paths:
            try:
                out = self._convert_one(course_path)
                self._log(f"OK: {course_path.name} -> {out.name}")
            except Exception:
                self._log(f"FAILED: {course_path.name}\n{traceback.format_exc()}")
            self.root.after(0, self._advance_progress)
            self._log("")  # blank line between files — keeps bulk-mode output readable

        self._log("Done.")
        self.root.after(0, lambda: self.convert_button.state(["!disabled"]))

    def _convert_one(self, path: Path) -> Path:
        """Parse and build a single course, extracting the .tar.gz first if needed."""
        tmp = None
        try:
            olx_path = path
            if path.suffix == ".gz":
                tmp = Path(tempfile.mkdtemp())
                with tarfile.open(path) as tar:
                    tar.extractall(tmp)
                olx_path = next(p for p in tmp.iterdir() if p.is_dir())

            course = Course(olx_path)
            course.parse()
            name = (
                path.name.removesuffix(".tar.gz") if path.suffix == ".gz" else path.stem
            )
            out = self.output_dir / f"{name}.mbz"
            MBZBuilder(
                course,
                sequential_sections=self.sequential_sections.get(),
                disable_custom_fields=not self.enable_custom_fields.get(),
            ).build(out)
            run_hybrid_checks(olx_path, out)
            return out
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def _drain_log_queue(self) -> None:
        """Poll the log queue on the main thread and append to the log box."""
        while not self._log_queue.empty():
            message = self._log_queue.get()
            self.log_box.configure(state="normal")
            self._insert_log_line(message)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(100, self._drain_log_queue)

    def _insert_log_line(self, message: str) -> None:
        """Colour a queued line: OK green, FAILED/ERROR red, WARNING yellow,
        message text black, timestamp/level decorations gray."""
        match = _LOG_LINE_RE.match(message)
        if match:
            ts, level, body = match.groups()
            level_tag = (
                "yellow"
                if level == "WARNING"
                else "red"
                if level in ("ERROR", "CRITICAL")
                else "gray"
            )
            self.log_box.insert("end", f"{ts} [", "gray")
            self.log_box.insert("end", level, level_tag)
            self.log_box.insert("end", "] ", "gray")
            self.log_box.insert("end", body + "\n", "black")
            return
        if message.startswith("OK:"):
            self.log_box.insert("end", message + "\n", "green")
        elif message.startswith("FAILED:"):
            self.log_box.insert("end", message + "\n", "red")
        else:
            self.log_box.insert("end", message + "\n", "black")


def main() -> None:
    """Entry point: create the root window and start the tkinter mainloop."""
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
