import csv
import html
import queue
import re
import sys
import tarfile
import threading
import zlib
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from tkinter import END, StringVar, Text, Tk, filedialog, ttk

ARCHIVE_SUFFIXES = (".tar.gz", ".mbz")
NAV_CLASS = "vc_btn3"
NAV_TEXTS = frozenset({"previous", "next", "vorige", "volgende"})
ANY_OCW_RE = re.compile(r"""[^\s"'<>]*(?<![A-Za-z0-9-])ocw\.tudelft\.nl(?![A-Za-z0-9-])[^\s"'<>]*""", re.IGNORECASE)
TEACHER_RE = re.compile(r"ocw\.tudelft\.nl/teachers(?:[/?#]|$)", re.IGNORECASE)
NON_RELATIVE_RE = re.compile(r"(?:[a-z][a-z0-9+.-]*:|//|#|@@PLUGINFILE@@)", re.IGNORECASE)
FULLNAME_RE = re.compile(r"<fullname>(.*?)</fullname>", re.DOTALL)
KIND_LABELS = {"nav": "Nav button", "teacher": "Teacher Profile", "other": "Other"}
DETAIL_LIMIT = 500
POLL_MS = 100
COLUMNS = (
    ("file", "File", 260),
    ("course", "Course", 260),
    ("pages", "Pages", 60),
    ("navpages", "Nav pages", 80),
    ("nav", "Nav buttons", 90),
    ("teacher", "Teacher Profiles", 110),
    ("other", "Other", 70),
    ("status", "Status", 160),
)


@dataclass
class Finding:
    member: str
    kind: str
    url: str


def _is_page(member: str) -> bool:
    return member.startswith("activities/page_") and member.endswith("/page.xml")


@dataclass
class ArchiveResult:
    name: str
    course: str = ""
    pages: int = 0
    findings: list[Finding] = field(default_factory=list)
    error: str = ""

    def count(self, kind: str) -> int:
        return sum(f.kind == kind for f in self.findings)

    @property
    def nav_pages(self) -> int:
        return len({f.member for f in self.findings if f.kind == "nav" and _is_page(f.member)})


class LinkParser(HTMLParser):
    """Collect `(href, classes, text)` for every anchor."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, list[str], str]] = []
        self._open: list | None = None

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "a":
            attrs = dict(attrs)
            self._open = [attrs.get("href") or "", (attrs.get("class") or "").split(), ""]

    def handle_data(self, data) -> None:
        if self._open:
            self._open[2] += data

    def handle_endtag(self, tag) -> None:
        if tag == "a" and self._open:
            self.links.append((self._open[0], self._open[1], self._open[2]))
            self._open = None


def _is_nav(classes: list[str], label: str) -> bool:
    return NAV_CLASS in classes and label.strip().lower() in NAV_TEXTS


def scan_text(member: str, text: str, result: ArchiveResult) -> None:
    if member == "course/course.xml":
        found = FULLNAME_RE.search(text)
        result.course = html.unescape(found.group(1)).strip() if found else ""
    result.pages += _is_page(member)
    unescaped = html.unescape(text)
    parser = LinkParser()
    parser.feed(unescaped)
    nav_hrefs = Counter(href for href, classes, label in parser.links if _is_nav(classes, label))
    for match in ANY_OCW_RE.finditer(unescaped):
        url = html.unescape(match.group(0))
        if nav_hrefs[url]:
            nav_hrefs[url] -= 1
            kind = "nav"
        elif TEACHER_RE.search(url):
            kind = "teacher"
        else:
            kind = "other"
        result.findings.append(Finding(member, kind, url))
    for href, classes, label in parser.links:
        href = href.strip()
        if not href or NON_RELATIVE_RE.match(href):
            continue
        if _is_nav(classes, label):
            kind = "nav"
        elif href.startswith("/teachers"):
            kind = "teacher"
        else:
            kind = "other"
        result.findings.append(Finding(member, kind, href))


def scan_archive(path: Path, stop: threading.Event, on_progress=lambda fraction: None) -> ArchiveResult:
    result = ArchiveResult(path.name)
    size = max(path.stat().st_size, 1)
    try:
        with path.open("rb") as raw, tarfile.open(fileobj=raw, mode="r|*") as tar:
            for member in tar:
                if stop.is_set():
                    result.error = "stopped"
                    break
                name = member.name.removeprefix("./")
                if member.isfile() and name.endswith(".xml"):
                    scan_text(name, tar.extractfile(member).read().decode("utf-8", "replace"), result)
                on_progress(raw.tell() / size)
    except (tarfile.TarError, EOFError, OSError, zlib.error) as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def find_archives(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.name.lower().endswith(ARCHIVE_SUFFIXES))


def write_csv(path: Path, results: list[ArchiveResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Archive", "Course", "Member", "Type", "Text"])
        for r in results:
            writer.writerows([r.name, r.course, f.member, KIND_LABELS[f.kind], f.url] for f in r.findings)


class App:
    def __init__(self, root: Tk, folder: Path) -> None:
        self.root = root
        self.folder = StringVar(value=str(folder))
        self.status = StringVar(value="Ready")
        self.events: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.results: dict[str, ArchiveResult] = {}
        root.title("OCW link scan")
        root.geometry("1100x640")
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Entry(top, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="Choose folder", command=self._choose).pack(side="left", padx=4)
        self.scan_button = ttk.Button(top, text="Scan", command=self._scan)
        self.scan_button.pack(side="left")
        self.stop_button = ttk.Button(top, text="Stop", command=self.stop.set, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        self.export_button = ttk.Button(top, text="Export CSV", command=self._export, state="disabled")
        self.export_button.pack(side="left")
        self.table = ttk.Treeview(self.root, columns=[c for c, _, _ in COLUMNS], show="headings", height=12)
        for column, heading, width in COLUMNS:
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor="w" if width > 100 else "e")
        self.table.pack(fill="both", expand=True, padx=8)
        self.table.bind("<<TreeviewSelect>>", self._show_detail)
        self.progress = ttk.Progressbar(self.root, maximum=1.0)
        self.progress.pack(fill="x", padx=8, pady=4)
        ttk.Label(self.root, textvariable=self.status).pack(fill="x", padx=8)
        self.detail = Text(self.root, height=12, wrap="none")
        self.detail.pack(fill="both", expand=True, padx=8, pady=8)

    def _choose(self) -> None:
        picked = filedialog.askdirectory(initialdir=self.folder.get())
        if picked:
            self.folder.set(picked)

    def _scan(self) -> None:
        folder = Path(self.folder.get())
        archives = find_archives(folder) if folder.is_dir() else []
        if not archives:
            self.status.set(f"No .tar.gz or .mbz files in {folder}")
            return
        self.table.delete(*self.table.get_children())
        self.results.clear()
        self.stop.clear()
        self.scan_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.export_button.config(state="disabled")
        threading.Thread(target=self._worker, args=(archives,), daemon=True).start()
        self.root.after(POLL_MS, self._poll)

    def _worker(self, archives: list[Path]) -> None:
        for index, path in enumerate(archives, 1):
            self.events.put(("start", path.name, index, len(archives)))
            result = scan_archive(path, self.stop, lambda f: self.events.put(("progress", f)))
            self.events.put(("done", result))
            if self.stop.is_set():
                break
        self.events.put(("finished",))

    def _poll(self) -> None:
        while not self.events.empty():
            event = self.events.get()
            if event[0] == "start":
                self.status.set(f"Scanning {event[1]} ({event[2]} of {event[3]})")
                self.progress["value"] = 0
            elif event[0] == "progress":
                self.progress["value"] = event[1]
            elif event[0] == "done":
                self._add_row(event[1])
            else:
                self._finish()
                return
        self.root.after(POLL_MS, self._poll)

    def _add_row(self, r: ArchiveResult) -> None:
        self.results[r.name] = r
        self.table.insert(
            "",
            END,
            iid=r.name,
            values=(
                r.name,
                r.course,
                r.pages,
                r.nav_pages,
                r.count("nav"),
                r.count("teacher"),
                r.count("other"),
                r.error or "ok",
            ),
        )

    def _finish(self) -> None:
        totals = Counter(f.kind for r in self.results.values() for f in r.findings)
        self.status.set(
            f"{len(self.results)} archives: {totals['nav']} Nav buttons, "
            f"{totals['teacher']} Teacher Profiles, {totals['other']} Other"
        )
        self.progress["value"] = 0
        self.scan_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.export_button.config(state="normal" if self.results else "disabled")

    def _show_detail(self, _event) -> None:
        self.detail.delete("1.0", END)
        selected = self.table.selection()
        if not selected:
            return
        findings = self.results[selected[0]].findings
        for f in findings[:DETAIL_LIMIT]:
            self.detail.insert(END, f"{KIND_LABELS[f.kind]:<16} {f.member}  {f.url}\n")
        if len(findings) > DETAIL_LIMIT:
            self.detail.insert(END, f"... {len(findings) - DETAIL_LIMIT} more, use Export CSV\n")

    def _export(self) -> None:
        target = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="link_scan.csv")
        if target:
            write_csv(Path(target), list(self.results.values()))
            self.status.set(f"Wrote {target}")


def main() -> None:
    root = Tk()
    App(root, Path(sys.argv[0]).resolve().parent)
    root.mainloop()


if __name__ == "__main__":
    main()
