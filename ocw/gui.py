import os
import queue
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

if sys.platform.startswith("linux"):
    os.environ.setdefault("TK_USE_PORTAL", "1")


class App:
    def __init__(self, root: Tk) -> None:
        """Set up state vars and build the window."""
        self.root = root
        root.title("OLX to Moodle Converter")
        root.geometry("640x420")

        self.mode = StringVar(value="files")
        self.sequential_sections = BooleanVar(value=False)
        self.input_paths: list[Path] = []
        self.input_var = StringVar(value="")
        self.output_dir = Path.cwd()
        self.output_var = StringVar(value=str(self.output_dir))
        self._log_queue: queue.Queue[str] = queue.Queue()

        self._build_widgets()
        self.root.after(100, self._drain_log_queue)

    def _build_widgets(self) -> None:
        """Lay out mode/input/output/convert widgets and the log box."""
        pad = {"padx": 8, "pady": 4}

        mode_frame = ttk.Frame(self.root)
        mode_frame.pack(fill="x", **pad)
        ttk.Radiobutton(
            mode_frame, text="Files (.tar.gz)", variable=self.mode, value="files",
            command=self._reset_input,
        ).pack(side="left")
        ttk.Radiobutton(
            mode_frame, text="Folder (all .tar.gz inside)", variable=self.mode, value="folder",
            command=self._reset_input,
        ).pack(side="left")

        input_frame = ttk.Frame(self.root)
        input_frame.pack(fill="x", **pad)
        ttk.Button(input_frame, text="Choose input...", command=self._choose_input).pack(side="left")
        ttk.Label(input_frame, textvariable=self.input_var).pack(side="left", padx=8)

        output_frame = ttk.Frame(self.root)
        output_frame.pack(fill="x", **pad)
        ttk.Button(output_frame, text="Choose output directory...", command=self._choose_output).pack(side="left")
        ttk.Label(output_frame, textvariable=self.output_var).pack(side="left", padx=8)

        ttk.Checkbutton(
            self.root, text="Sequential sections (one section per sequential)",
            variable=self.sequential_sections,
        ).pack(anchor="w", **pad)

        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill="x", **pad)
        self.convert_button = ttk.Button(button_frame, text="Convert", command=self._start_convert)
        self.convert_button.pack(side="left", fill="x", expand=True)
        ttk.Button(button_frame, text="Done", command=self.root.destroy).pack(side="left", fill="x", expand=True)

        self.log_box = ScrolledText(self.root, state="disabled", height=14)
        self.log_box.pack(fill="both", expand=True, **pad)

    def _reset_input(self) -> None:
        """Clear the chosen input paths when the mode switches."""
        self.input_paths = []
        self.input_var.set("")

    def _choose_input(self) -> None:
        """Prompt for one or more .tar.gz files, or a folder to glob them from."""
        if self.mode.get() == "files":
            paths = filedialog.askopenfilenames(filetypes=[("OLX archive", "*.tar.gz"), ("All files", "*.*")])
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

    def _start_convert(self) -> None:
        """Validate selections and kick off the background conversion thread."""
        if not self.input_paths or not self.output_dir:
            self._log("Pick an input and an output directory first.")
            return
        self.convert_button.state(["disabled"])
        threading.Thread(target=self._convert_worker, daemon=True).start()

    def _convert_worker(self) -> None:
        """Run on a background thread: convert each course, isolating failures."""
        for course_path in self.input_paths:
            try:
                out = self._convert_one(course_path)
                self._log(f"OK: {course_path.name} -> {out.name}")
            except Exception:
                self._log(f"FAILED: {course_path.name}\n{traceback.format_exc()}")

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
            name = path.name.removesuffix(".tar.gz") if path.suffix == ".gz" else path.stem
            out = self.output_dir / f"{name}.mbz"
            MBZBuilder(course, sequential_sections=self.sequential_sections.get()).build(out)
            return out
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def _drain_log_queue(self) -> None:
        """Poll the log queue on the main thread and append to the log box."""
        while not self._log_queue.empty():
            message = self._log_queue.get()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(100, self._drain_log_queue)


def main() -> None:
    """Entry point: create the root window and start the tkinter mainloop."""
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
