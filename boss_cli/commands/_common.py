"""Common helpers for Boss CLI commands."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any, TypeVar

import click
from rich.console import Console

from ..auth import Credential, get_credential
from ..client import BossClient
from ..exceptions import BossApiError, SessionExpiredError, error_code_for_exception

T = TypeVar("T")

# Rich output → stderr (so structured JSON/YAML stays clean on stdout)
console = Console(stderr=True)
error_console = Console(stderr=True)

# ── Schema envelope version ─────────────────────────────────────────
SCHEMA_VERSION = "1"


def require_auth() -> Credential:
    """Get credential or exit with error."""
    cred = get_credential()
    if not cred:
        console.print("[yellow]⚠️  未登录[/yellow]，使用 [bold]boss login[/bold] 扫码登录")
        sys.exit(1)
    return cred


def get_client(credential: Credential | None = None) -> BossClient:
    """Create a BossClient with optional credential."""
    return BossClient(credential)


def run_client_action(credential: Credential, action: Callable[[BossClient], T]) -> T:
    """Run an authenticated client action with auto-retry on session expiry.

    If SessionExpiredError is raised, tries once more with a fresh browser
    credential before giving up.
    """
    try:
        with get_client(credential) as client:
            return action(client)
    except SessionExpiredError:
        # Try refreshing from browser
        from ..auth import clear_credential, extract_browser_credential
        fresh, _ = extract_browser_credential()
        if fresh:
            with get_client(fresh) as client:
                return action(client)
        clear_credential()
        raise


def _wrap_envelope(data: Any, *, ok: bool = True, error: dict | None = None) -> dict:
    """Wrap data in the standard output envelope."""
    envelope: dict[str, Any] = {
        "ok": ok,
        "schema_version": SCHEMA_VERSION,
    }
    if ok:
        envelope["data"] = data
    else:
        envelope["data"] = None
        envelope["error"] = error or {}
    return envelope


def _output_structured(data: Any, *, as_json: bool, as_yaml: bool) -> None:
    """Output data wrapped in envelope as JSON or YAML."""
    envelope = _wrap_envelope(data)
    if as_json:
        click.echo(json.dumps(envelope, indent=2, ensure_ascii=False))
    elif as_yaml or not sys.stdout.isatty():
        try:
            import yaml
            click.echo(yaml.dump(envelope, allow_unicode=True, default_flow_style=False))
        except ImportError:
            click.echo(json.dumps(envelope, indent=2, ensure_ascii=False))


def handle_command(
    credential: Credential,
    *,
    action: Callable[[BossClient], T],
    render: Callable[[T], None] | None = None,
    as_json: bool = False,
    as_yaml: bool = False,
    error_hint: Callable[[BossApiError], None] | None = None,
) -> T | None:
    """Run a client action with structured output support.

    - If --json is set, print JSON envelope to stdout
    - If --yaml is set, print YAML envelope to stdout
    - If non-TTY and neither flag, auto YAML envelope
    - Otherwise, call render() for rich output

    On BossApiError, prints the standard error then invokes ``error_hint``
    (if provided) so callers can append a recovery hint to stderr before
    the process exits.
    """
    try:
        data = run_client_action(credential, action)

        if as_json or as_yaml or not sys.stdout.isatty():
            _output_structured(data, as_json=as_json, as_yaml=as_yaml)
            return data

        if render:
            render(data)
        return data

    except BossApiError as exc:
        _print_error(exc, as_json=as_json, as_yaml=as_yaml)
        if error_hint is not None:
            error_hint(exc)
        raise SystemExit(1) from None


def handle_errors(fn: Callable[[], T]) -> T | None:
    """Run arbitrary command logic and catch BossApiError."""
    try:
        return fn()
    except BossApiError as exc:
        _print_error(exc)
        raise SystemExit(1) from None


def _print_error(exc: BossApiError, *, as_json: bool = False, as_yaml: bool = False) -> None:
    """Print formatted error message, with envelope if structured output."""
    code = error_code_for_exception(exc)
    if as_json or as_yaml or not sys.stdout.isatty():
        envelope = _wrap_envelope(None, ok=False, error={"code": code, "message": str(exc)})
        if as_json:
            click.echo(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            try:
                import yaml
                click.echo(yaml.dump(envelope, allow_unicode=True, default_flow_style=False))
            except ImportError:
                click.echo(json.dumps(envelope, indent=2, ensure_ascii=False))
    else:
        console.print(f"[red]❌ [{code}] {exc}[/red]")


def structured_output_options(command: Callable) -> Callable:
    """Add --json/--yaml options to a Click command."""
    command = click.option("--yaml", "as_yaml", is_flag=True, help="以 YAML 格式输出")(command)
    command = click.option("--json", "as_json", is_flag=True, help="以 JSON 格式输出")(command)
    return command
