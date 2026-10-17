#!/usr/bin/env python3
"""Apply Django schema migrations against the configured Vercel database."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "atlasquest.settings")

from django.core.management import call_command


def main():
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):
        raise RuntimeError(
            "Configure DATABASE_URL (or POSTGRES_URL) in Vercel before deploying."
        )
    call_command("migrate", interactive=False)


if __name__ == "__main__":
    main()
