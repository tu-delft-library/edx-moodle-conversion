import logging
import os
import queue
import re
import sys
import threading
import traceback
from pathlib import Path
from typing import Any
from tkinter import BooleanVar, StringVar, Tk, filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from ocw._version import __version__

if sys.platform.startswith("linux"):
    os.environ.setdefault("TK_USE_PORTAL", "1")

_LOG_LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}) \[(\w+)\] (.*)$")


def _input_label(path: Path | str) -> str:
    """Short display name for an input entry, whether it's a local file or a URL."""
    return path.name if isinstance(path, Path) else path.rstrip("/").rsplit("/", 1)[-1]


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


class ConverterApp:
    """Provide the shared GUI workflow for converting one or more course sources.

    The Tk main thread owns all widgets. Conversion runs on a worker thread, which communicates
    log lines, course markers, and status changes through `_log_queue`. Subclasses supply
    source-specific input selection and conversion.
    """

    WINDOW_TITLE = "OCW Converter"

    def __init__(self, root: Tk, log_file: Path | None = None) -> None:
        self.root = root
        root.title(f"{self.WINDOW_TITLE} ({__version__})")
        root.geometry("860x460")

        self.sequential_sections = BooleanVar(value=False)
        self.enable_custom_fields = BooleanVar(value=False)
        self.debug = BooleanVar(value=False)
        self.fetch_external_assets = BooleanVar(value=True)
        self.input_paths: list[Path | str] = []
        self.input_var = StringVar(value="")
        self.output_dir = Path.cwd()
        self.output_var = StringVar(value=str(self.output_dir))
        self._log_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._pending_mark: str | None = None

        self._build_widgets()
        self._setup_logging(log_file)
        self.root.after(100, self._drain_log_queue)

    def _setup_logging(self, log_file: Path | None) -> None:
        """Route `ocw` log records to the GUI queue and, optionally, to `log_file`."""
        log = logging.getLogger("ocw")
        log.setLevel(logging.INFO)
        log.addHandler(_QueueLogHandler(self._log))
        if log_file is not None:
            fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
                )
            )
            log.addHandler(fh)

    def _block_log_edit(self, event) -> str | None:
        """Allow selection, navigation, and copy shortcuts in the log while blocking text edits."""
        if event.state & 0x4 or event.keysym in (
            "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Tab",
        ):
            return None
        return "break"

    def _build_source_widgets(self, pad: dict) -> None:
        """Add source-specific controls above the shared input and output controls.

        The base implementation adds none.
        """

    def _build_widgets(self) -> None:
        """Construct the shared controls, progress display, conversion log, and course sidebar."""
        pad = {"padx": 8, "pady": 4}

        self._build_source_widgets(pad)

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

        ttk.Checkbutton(
            self.root,
            text="Fetch PDFs still hosted on edX",
            variable=self.fetch_external_assets,
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

        content_frame = ttk.Frame(self.root)
        content_frame.pack(fill="both", expand=True, **pad)

        log_frame = ttk.Frame(content_frame)
        log_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.log_box = ScrolledText(log_frame, height=14)
        self.log_box.bind("<Key>", self._block_log_edit)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_configure("green", foreground="#2e7d32")
        self.log_box.tag_configure("red", foreground="#c62828")
        self.log_box.tag_configure("yellow", foreground="#f9a825")
        self.log_box.tag_configure("black", foreground="black")
        self.log_box.tag_configure("gray", foreground="gray")
        self.log_box.tag_configure("blue", foreground="#1565c0")

        sidebar_frame = ttk.Frame(content_frame, width=180)
        sidebar_frame.pack(side="right", fill="y")
        sidebar_frame.pack_propagate(False)
        self.sidebar = ttk.Treeview(
            sidebar_frame, columns=("status",), show="tree headings", height=14
        )
        self.sidebar.heading("#0", text="Course")
        self.sidebar.heading("status", text="Status")
        self.sidebar.column("status", width=70, anchor="center")
        self.sidebar.pack(fill="both", expand=True)
        self.sidebar.tag_configure("pending", foreground="gray")
        self.sidebar.tag_configure("ok", foreground="#2e7d32")
        self.sidebar.tag_configure("failed", foreground="#c62828")
        self.sidebar.bind("<<TreeviewSelect>>", self._jump_to_course)

        copy_frame = ttk.Frame(self.root)
        copy_frame.pack(fill="x", **pad)
        ttk.Button(copy_frame, text="Copy log", command=self._copy_log).pack(side="right")

    def _reset_input(self) -> None:
        """Clear the current source selection before a subclass records a new one."""
        self.input_paths = []
        self.input_var.set("")

    def _choose_input(self) -> None:
        """Select source input and update `input_paths` and its displayed summary."""
        raise NotImplementedError

    def _choose_output(self) -> None:
        """Select an output directory and retain the existing directory when cancelled."""
        path = filedialog.askdirectory()
        if path:
            self.output_dir = Path(path)
            self.output_var.set(path)

    def _log(self, message: str) -> None:
        """Queue one unformatted message for insertion into the GUI log."""
        self._log_queue.put(("log", message))

    def _mark_course(self, key: str) -> None:
        """Queue a marker for the next log line of the course identified by `key`."""
        self._log_queue.put(("mark", key))

    def _set_course_status(self, key: str, status: str) -> None:
        """Queue a sidebar status update for the course identified by `key`."""
        self._log_queue.put(("status", (key, status)))

    def _populate_sidebar(self) -> None:
        """Rebuild the sidebar from `input_paths`, resetting every course to Pending.

        Row IDs use the same `course_<index>` keys as the log markers.
        """
        self.sidebar.delete(*self.sidebar.get_children())
        for idx, path in enumerate(self.input_paths):
            self.sidebar.insert(
                "",
                "end",
                iid=f"course_{idx}",
                text=_input_label(path),
                values=("Pending",),
                tags=("pending",),
            )

    def _copy_log(self) -> None:
        """Copy the complete rendered conversion log to the system clipboard."""
        text = self.log_box.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _start_convert(self) -> None:
        """Validate the selection, reset conversion state, and start the worker thread."""
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
        self._populate_sidebar()

        self.convert_button.state(["disabled"])
        threading.Thread(target=self._convert_worker, daemon=True).start()

    def _advance_progress(self) -> None:
        """Advance the completed-course counter on the Tk main thread."""
        self.progress["value"] += 1
        self.progress_label.config(
            text=f"{int(self.progress['value'])} / {int(self.progress['maximum'])} courses"
        )

    def _convert_worker(self) -> None:
        """Convert every queued source independently and report its result.

        Failures are logged per course so the remaining batch continues. Tk updates are scheduled
        through the queue or `root.after()`.
        """
        for idx, course_path in enumerate(self.input_paths):
            key = f"course_{idx}"
            self._mark_course(key)
            try:
                out = self._convert_one(course_path)
                self._log(f"OK: {_input_label(course_path)} -> {out.name}")
                self._set_course_status(key, "OK")
            except Exception:
                self._log(f"FAILED: {_input_label(course_path)}\n{traceback.format_exc()}")
                self._set_course_status(key, "Failed")
            self.root.after(0, self._advance_progress)
            self._log("")
        self._log("Done.")
        self.root.after(0, lambda: self.convert_button.state(["!disabled"]))

    def _convert_one(self, path: Path | str) -> Path:
        """Convert one source at `path` and return the generated MBZ path."""
        raise NotImplementedError

    def _drain_log_queue(self) -> None:
        """Apply queued worker events to Tk widgets in first-in, first-out order.

        A course marker is placed immediately before its first queued log line, keeping sidebar
        navigation aligned with the corresponding conversion block.
        """
        while not self._log_queue.empty():
            kind, payload = self._log_queue.get()
            if kind == "log":
                start = self.log_box.index("end-1c")
                self._insert_log_line(payload)
                self.log_box.see("end")
                if self._pending_mark is not None:
                    self.log_box.mark_set(self._pending_mark, start)
                    self.log_box.mark_gravity(self._pending_mark, "left")
                    self._pending_mark = None
            elif kind == "mark":
                self._pending_mark = payload
            elif kind == "status":
                key, status = payload
                self._update_sidebar_status(key, status)
        self.root.after(100, self._drain_log_queue)

    def _update_sidebar_status(self, key: str, status: str) -> None:
        """Render a course status in the sidebar using its matching colour tag."""
        tag = {"OK": "ok", "Failed": "failed"}.get(status, "pending")
        self.sidebar.item(key, values=(status,), tags=(tag,))

    def _jump_to_course(self, _event) -> None:
        """Scroll the log to the block marked for the selected sidebar course."""
        selection = self.sidebar.selection()
        if not selection:
            return
        key = selection[0]
        if key in self.log_box.mark_names():
            self.log_box.yview(key)

    def _insert_log_line(self, message: str) -> None:
        """Append one message to the log using colours for timestamps, levels, and outcomes.

        Structured logger output is split into timestamp, level, and body. Plain status messages
        use their `OK:` or `FAILED:` prefix.
        """
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
            if body.startswith("DOWNLOAD:"):
                self.log_box.insert("end", "DOWNLOAD:", "blue")
                self.log_box.insert("end", body.removeprefix("DOWNLOAD:") + "\n", "black")
            else:
                self.log_box.insert("end", body + "\n", "black")
            return
        if message.startswith("OK:"):
            self.log_box.insert("end", message + "\n", "green")
        elif message.startswith("FAILED:"):
            self.log_box.insert("end", message + "\n", "red")
        else:
            self.log_box.insert("end", message + "\n", "black")
