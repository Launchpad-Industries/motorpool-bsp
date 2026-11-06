# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Which engine makes the PDF: Playwright in development, else Edge."""

import pytest

from bsp import app as app_module
from bsp import dist


def fail(message):
    def engine(html_doc):
        raise ImportError(message)
    return engine


def test_development_uses_playwright_first(monkeypatch):
    monkeypatch.setattr(dist, "DIST", False)
    monkeypatch.setattr(app_module, "playwright_pdf", lambda h: b"playwright")
    monkeypatch.setattr(dist, "html_to_pdf_edge", fail("Edge should not run"))
    assert app_module.html_to_pdf("<html>") == b"playwright"


def test_development_falls_back_to_edge(monkeypatch):
    monkeypatch.setattr(dist, "DIST", False)
    monkeypatch.setattr(app_module, "playwright_pdf", fail("No module named 'playwright'"))
    monkeypatch.setattr(dist, "html_to_pdf_edge", lambda h: b"edge")
    assert app_module.html_to_pdf("<html>") == b"edge"


def test_the_error_names_both_engines_when_neither_works(monkeypatch):
    monkeypatch.setattr(dist, "DIST", False)
    monkeypatch.setattr(app_module, "playwright_pdf", fail("No module named 'playwright'"))
    monkeypatch.setattr(dist, "html_to_pdf_edge", fail("Microsoft Edge was not found"))
    with pytest.raises(RuntimeError, match="playwright.*Microsoft Edge was not found"):
        app_module.html_to_pdf("<html>")


def test_tester_build_only_uses_edge(monkeypatch):
    monkeypatch.setattr(dist, "DIST", True)
    monkeypatch.setattr(app_module, "playwright_pdf", fail("Playwright should not run"))
    monkeypatch.setattr(dist, "html_to_pdf_edge", lambda h: b"edge")
    assert app_module.html_to_pdf("<html>") == b"edge"
