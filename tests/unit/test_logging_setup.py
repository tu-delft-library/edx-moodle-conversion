import logging

import pytest

from ocw.logging_setup import ColourFormatter, setup_cli_logging


@pytest.fixture(autouse=True)
def _reset_ocw_logger():
    log = logging.getLogger("ocw")
    yield
    log.handlers.clear()
    log.setLevel(logging.NOTSET)


def test_setup_cli_logging_default_level_is_info(tmp_path):
    setup_cli_logging(False, tmp_path / "ocw.log")
    assert logging.getLogger("ocw").level == logging.INFO


def test_setup_cli_logging_debug_level_is_debug(tmp_path):
    setup_cli_logging(True, tmp_path / "ocw.log")
    assert logging.getLogger("ocw").level == logging.DEBUG


def test_setup_cli_logging_writes_log_file(tmp_path):
    log_path = tmp_path / "ocw.log"
    setup_cli_logging(False, log_path)
    logging.getLogger("ocw").info("hello")
    assert "hello" in log_path.read_text()


def test_colour_formatter_wraps_warning_levelname():
    formatter = ColourFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord("ocw", logging.WARNING, __file__, 1, "careful", None, None)
    formatted = formatter.format(record)
    assert "\033[33m" in formatted
    assert "WARNING" in formatted


def test_colour_formatter_leaves_info_levelname_plain():
    formatter = ColourFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord("ocw", logging.INFO, __file__, 1, "fine", None, None)
    formatted = formatter.format(record)
    assert "\033[33m" not in formatted
    assert formatted == "INFO fine"


def test_colour_formatter_highlights_known_phase_labels():
    formatter = ColourFormatter("%(message)s")
    record = logging.LogRecord(
        "ocw", logging.INFO, __file__, 1, "Parsing OLX: chapter 1", None, None
    )
    formatted = formatter.format(record)
    assert "\033[34mParsing OLX:\033[0m" in formatted


def test_colour_formatter_highlights_download_label():
    formatter = ColourFormatter("%(message)s")
    record = logging.LogRecord(
        "ocw", logging.INFO, __file__, 1, "DOWNLOAD: fetched x", None, None
    )
    formatted = formatter.format(record)
    assert "\033[34mDOWNLOAD:\033[0m" in formatted
