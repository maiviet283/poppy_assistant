#!/usr/bin/env python
"""Cửa ngõ dòng lệnh của project host demo (runserver, migrate, seed_business, ingest...)."""

import os
import sys


def _force_utf8_console() -> None:
    """Ép stdout/stderr sang UTF-8 để log tiếng Việt không vỡ trên console Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> None:
    _force_utf8_console()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Không import được Django. Đã kích hoạt venv và cài deps chưa?") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
