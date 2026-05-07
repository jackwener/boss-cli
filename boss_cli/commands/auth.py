"""Authentication commands: login, logout, status, me."""

from __future__ import annotations

import json
import logging

import click
from rich.panel import Panel

from ._common import (
    console,
    handle_command,
    require_auth,
    structured_output_options,
)

logger = logging.getLogger(__name__)


@click.command()
@click.option("--qrcode", is_flag=True, help="使用二维码扫码登录")
@click.option("--cdp", is_flag=True, help="从已登录的 Chrome（--remote-debugging-port=9222）直接抓取 cookie，无需扫码")
@click.option("--cdp-port", default=9222, type=int, show_default=True, help="CDP 端口")
@click.option("--cookie-source", default=None, help="指定浏览器 (chrome/firefox/edge/brave/arc/safari等)")
def login(qrcode: bool, cdp: bool, cdp_port: int, cookie_source: str | None) -> None:
    """登录 Boss 直聘"""
    from ..auth import clear_credential, verify_credential

    def _finalize_login(cred, *, from_qr: bool = False) -> None:
        # __zp_stoken__ is JS-generated and treated as optional. If it's
        # missing, warn but don't reject the login — wt2/wbg/zp_at unlock
        # roughly half of the recruiter API surface.
        stoken_missing = "__zp_stoken__" not in cred.cookies

        authenticated, message = verify_credential(cred, force_refresh=True)
        if authenticated:
            console.print(f"[green]✅ 登录成功！[/green] ({len(cred.cookies)} cookies)")
            if stoken_missing:
                console.print(
                    "[yellow]⚠️  __zp_stoken__ 缺失（由站点 JS 生成，CDP/QR 均可能无法获取）。\n"
                    "   recommend / chat / inbox 等接口可用；search / 通信类接口可能返回「环境异常」。[/yellow]"
                )
            return
        if stoken_missing:
            console.print(
                f"[green]✅ 已保存 {len(cred.cookies)} 个 cookies[/green]"
            )
            console.print(
                "[yellow]⚠️  接口校验未通过，且 __zp_stoken__ 缺失。\n"
                "   部分接口可用，建议在浏览器登录后再次执行 boss login 补全。[/yellow]"
            )
            return
        clear_credential()
        console.print("[red]❌ 登录失败：凭证未通过实际接口校验[/red]")
        if message:
            console.print(f"[dim]{message}[/dim]")
        if not from_qr:
            console.print(
                "\n[yellow]💡 提示：浏览器运行时 Cookie 可能未写入磁盘，建议：\n"
                "   1. 关闭浏览器后重试 boss login\n"
                "   2. 或使用 boss login --cdp（已登录 Chrome 直接抓取，无需扫码）\n"
                "   3. 或使用 boss login --qrcode 扫码登录[/yellow]"
            )
        raise SystemExit(1)

    if cdp:
        try:
            from ..browser_login import cdp_login, BrowserLoginUnavailable
        except ImportError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise SystemExit(1) from None
        try:
            cred = cdp_login(debug_port=cdp_port)
        except BrowserLoginUnavailable as e:
            console.print(f"[red]❌ CDP 登录失败: {e}[/red]")
            console.print(
                "[yellow]💡 启动方式（macOS）:\n"
                "   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\\n"
                "     --remote-debugging-port=9222 --user-data-dir=/tmp/boss-chrome\n"
                "   然后在该 Chrome 中登录 zhipin.com，再运行 boss login --cdp[/yellow]"
            )
            raise SystemExit(1) from None
        _finalize_login(cred, from_qr=True)
        return

    if qrcode:
        # Prefer browser-assisted login (captures __zp_stoken__ via JS)
        # Fallback to HTTP-only QR flow when camoufox is unavailable
        try:
            from ..browser_login import browser_qr_login, BrowserLoginUnavailable
            try:
                cred = browser_qr_login()
                _finalize_login(cred, from_qr=True)
                return
            except BrowserLoginUnavailable as e:
                console.print(
                    f"[yellow]⚠️  浏览器辅助登录不可用: {e}\n"
                    "   安装方式: pip install 'kabi-boss-cli[browser]' && python -m camoufox fetch\n"
                    "   回退到 HTTP 扫码登录...[/yellow]\n"
                )
        except ImportError:
            pass

        # Fallback: HTTP-only QR login
        from ..auth import qr_login
        import asyncio
        try:
            cred = asyncio.run(qr_login())
        except RuntimeError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise SystemExit(1) from None
        _finalize_login(cred, from_qr=True)
    else:
        from ..auth import extract_browser_credential, _diagnose_extraction_issues
        # Try browser cookies first
        cred, diagnostics = extract_browser_credential(cookie_source=cookie_source)
        if cred:
            _finalize_login(cred)
        else:
            # Show diagnostics hint if available
            hint = _diagnose_extraction_issues(diagnostics)
            if hint:
                console.print("[yellow]⚠️  Cookie 提取诊断:[/yellow]")
                for line in hint.splitlines():
                    console.print(f"  [dim]{line}[/dim]")
                console.print()

            # Fallback to QR login
            console.print("[yellow]未找到浏览器 Cookie，尝试二维码登录...[/yellow]")
            console.print("[dim]💡 也可以手动设置 BOSS_COOKIES 环境变量来注入 cookie[/dim]")
            try:
                from ..browser_login import browser_qr_login, BrowserLoginUnavailable
                try:
                    cred = browser_qr_login()
                    _finalize_login(cred, from_qr=True)
                    return
                except BrowserLoginUnavailable:
                    pass
            except ImportError:
                pass

            from ..auth import qr_login
            import asyncio
            try:
                cred = asyncio.run(qr_login())
            except RuntimeError as e:
                console.print(f"[red]❌ {e}[/red]")
                raise SystemExit(1) from None
            _finalize_login(cred, from_qr=True)


@click.command()
def logout() -> None:
    """清除已保存的登录凭证"""
    from ..auth import clear_credential
    clear_credential()
    console.print("[green]✅ 已退出登录[/green]")


@click.command()
@structured_output_options
def status(as_json: bool, as_yaml: bool) -> None:
    """查看当前登录状态"""
    from ..auth import get_credential, verify_credential_details
    cred = get_credential()
    if cred:
        cookie_names = sorted(cred.cookies.keys())
        health = verify_credential_details(cred)
        authenticated = health["authenticated"]
        message = health.get("reason")
        data = {
            "credential_present": True,
            "cookie_count": len(cred.cookies),
            "cookies": cookie_names,
            **health,
        }
        if as_json:
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        elif as_yaml:
            try:
                import yaml
                click.echo(yaml.dump(data, allow_unicode=True))
            except ImportError:
                click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            n = len(cred.cookies)
            keys = ", ".join(cookie_names[:5])
            extra = f" (+{n - 5} more)" if n > 5 else ""
            if authenticated:
                console.print(f"[green]✅ 已登录[/green] ({n} cookies)")
                console.print(f"  [dim]{keys}{extra}[/dim]")
            else:
                console.print(f"[yellow]⚠️  本地存在凭证，但登录态无效[/yellow] ({n} cookies)")
                console.print(f"  [dim]{keys}{extra}[/dim]")
            console.print(
                "  [dim]"
                f"search={'ok' if health['search_authenticated'] else 'fail'} · "
                f"recommend={'ok' if health['recommend_authenticated'] else 'fail'}"
                "[/dim]"
            )
            if message:
                console.print(f"  [dim]{message}[/dim]")
    else:
        if as_json:
            click.echo(json.dumps({"authenticated": False, "credential_present": False}))
        elif as_yaml:
            data = {"authenticated": False, "credential_present": False}
            try:
                import yaml
                click.echo(yaml.dump(data, allow_unicode=True))
            except ImportError:
                click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            console.print("[yellow]⚠️  未登录[/yellow]，使用 [bold]boss login[/bold] 扫码登录")


@click.command()
@structured_output_options
def me(as_json: bool, as_yaml: bool) -> None:
    """查看个人资料和求职期望"""
    cred = require_auth()

    def _render(info: dict) -> None:
        name = info.get("name", info.get("nickName", "-"))
        age = info.get("age", "-")
        degree = info.get("degreeCategory", "-")
        account = info.get("account", "-")
        gender = "男" if info.get("gender") == 1 else "女" if info.get("gender") == 2 else "-"

        panel = Panel(
            f"[bold]{name}[/bold]  {gender}  {age}\n"
            f"学历: {degree}\n"
            f"账号: {account}",
            title="👤 个人资料",
            border_style="cyan",
        )
        console.print(panel)

    handle_command(
        cred,
        action=lambda c: c.get_resume_baseinfo(),
        render=_render,
        as_json=as_json,
        as_yaml=as_yaml,
    )
