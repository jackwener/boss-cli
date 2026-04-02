"""CLI entry point for Boss CLI.

Usage:
    boss login / status / logout
    boss search <keyword> [--city C] [--salary S] [--exp E] [--degree D]
    boss recommend [--page N]
    boss me / applied / interviews / chat
    boss greet <securityId>
    boss batch-greet <keyword> [-n N] [--city C] [--dry-run]
    boss cities
"""

from __future__ import annotations

import logging

import click

from . import __version__
from .commands import auth, personal, recruiter, search, social


@click.group()
@click.version_option(version=__version__, prog_name="boss")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging (show request URLs, timing)")
@click.pass_context
def cli(ctx, verbose: bool) -> None:
    """Boss CLI — 在终端使用 BOSS 直聘 🤝"""
    ctx.ensure_object(dict)
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)


# ─── Auth commands ───────────────────────────────────────────────────

cli.add_command(auth.login)
cli.add_command(auth.logout)
cli.add_command(auth.status)
cli.add_command(auth.me)

# ─── Search & Browse commands ────────────────────────────────────────

cli.add_command(search.search)
cli.add_command(search.recommend)
cli.add_command(search.detail)
cli.add_command(search.show)
cli.add_command(search.export)
cli.add_command(search.history)
cli.add_command(search.cities)

# ─── Personal Center commands ────────────────────────────────────────

cli.add_command(personal.applied)
cli.add_command(personal.interviews)

# ─── Social commands ────────────────────────────────────────────────

cli.add_command(social.chat_list)
cli.add_command(social.greet)
cli.add_command(social.batch_greet)

# ─── Recruiter (Boss) commands ──────────────────────────────────────

cli.add_command(recruiter.recruiter)


if __name__ == "__main__":
    cli()
