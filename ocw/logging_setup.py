import logging
import sys
from pathlib import Path


class ColourFormatter(logging.Formatter):
    _YELLOW = "\033[33m"
    _BLUE = "\033[34m"
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.WARNING:
            record = logging.makeLogRecord(record.__dict__)
            record.levelname = f"{self._YELLOW}WARNING{self._RESET}"
            if record.args:
                record.args = tuple(
                    f"{self._YELLOW}{a}{self._RESET}" for a in record.args
                )
        msg = super().format(record)
        msg = msg.replace("Parsing OLX:", f"{self._BLUE}Parsing OLX:{self._RESET}")
        msg = msg.replace("Parsing WP:", f"{self._BLUE}Parsing WP:{self._RESET}")
        return msg.replace("DOWNLOAD:", f"{self._BLUE}DOWNLOAD:{self._RESET}")


def setup_cli_logging(debug: bool, log_path: Path) -> None:
    """Attach stderr and file handlers to the root ocw logger."""
    log = logging.getLogger("ocw")
    log.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(ColourFormatter(fmt, datefmt=datefmt))
    log.addHandler(sh)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    log.addHandler(fh)