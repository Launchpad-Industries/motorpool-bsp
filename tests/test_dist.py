# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
"""Printing with Edge: msedge.exe can return before the PDF has been written."""

import threading

from bsp.dist import wait_for_file


def test_wait_for_file_sees_a_file_that_arrives_late(tmp_path):
    p = tmp_path / "cards.pdf"
    threading.Timer(0.2, lambda: p.write_bytes(b"%PDF")).start()
    assert wait_for_file(p, timeout=5, poll=0.05)


def test_wait_for_file_gives_up_on_a_missing_or_empty_file(tmp_path):
    p = tmp_path / "cards.pdf"
    assert not wait_for_file(p, timeout=0.2, poll=0.05)
    p.write_bytes(b"")
    assert not wait_for_file(p, timeout=0.2, poll=0.05)
