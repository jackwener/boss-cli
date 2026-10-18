"""Social commands: chat, greet, batch-greet."""

from __future__ import annotations

import json
import logging
import time

import click
from rich.table import Table

from ..client import resolve_city
from ..constants import DEGREE_CODES, EXP_CODES, SALARY_CODES
from ..exceptions import BossApiError
from ._common import (
    console,
    handle_command,
    require_auth,
    run_client_action,
    structured_output_options,
)

logger = logging.getLogger(__name__)


@click.command("chat")
@click.option("-p", "--page", default=1, type=int, help="页码 (每页 100 个)")
@structured_output_options
def chat_list(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看沟通过的 Boss 列表"""
    cred = require_auth()

    def _render(data: dict) -> None:
        friend_list = data.get("result", data.get("friendList", []))

        if not friend_list:
            console.print("[yellow]暂无沟通记录[/yellow]")
            return

        table = Table(title=f"💬 沟通列表 ({len(friend_list)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Boss", style="bold cyan", max_width=15)
        table.add_column("公司", style="green", max_width=20)
        table.add_column("职位", max_width=25)
        table.add_column("最近消息", style="dim", max_width=30)
        table.add_column("最后发言", width=6)

        for i, friend in enumerate(friend_list, 1):
            last = friend.get("lastMessageInfo") or {}
            table.add_row(
                str(i),
                friend.get("name", friend.get("bossName", "-")),
                friend.get("brandName", "-"),
                friend.get("jobName", "-"),
                friend.get("lastMsg", friend.get("lastText", "-")),
                "Boss" if last.get("fromId") and last.get("fromId") == friend.get("uid") else "我",
            )

        console.print(table)

    handle_command(cred, action=lambda c: c.get_friend_list(page=page), render=_render, as_json=as_json, as_yaml=as_yaml)


@click.command()
@click.argument("security_id")
@click.option("--lid", default="", help="Lid parameter from search results")
@structured_output_options
def greet(security_id: str, lid: str, as_json: bool, as_yaml: bool) -> None:
    """向 Boss 打招呼 / 投递简历 (需要 securityId)"""
    cred = require_auth()

    def _action(c):
        return c.add_friend(security_id=security_id, lid=lid)

    def _render(data: dict) -> None:
        console.print("[green]✅ 打招呼成功！[/green]")
        if data:
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


@click.command("batch-greet")
@click.argument("keyword")
@click.option("-c", "--city", default="全国", help="城市名称或代码")
@click.option("-n", "--count", default=5, type=int, help="打招呼数量 (默认: 5)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("--dry-run", is_flag=True, help="仅预览，不实际发送")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
def batch_greet(keyword: str, city: str, count: int, salary: str | None, exp: str | None, degree: str | None, dry_run: bool, yes: bool) -> None:
    """批量向搜索结果中的 Boss 打招呼

    例: boss batch-greet "golang" --city 杭州 -n 10 --salary 20-30K
    """
    cred = require_auth()

    city_code = resolve_city(city)
    salary_code = SALARY_CODES.get(salary) if salary else None
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None

    try:
        data = run_client_action(
            cred,
            lambda client: client.search_jobs(
                query=keyword,
                city=city_code,
                experience=exp_code,
                degree=degree_code,
                salary=salary_code,
            ),
        )

        job_list = data.get("jobList", [])
        if not job_list:
            console.print("[yellow]没有找到匹配的职位[/yellow]")
            return

        targets = job_list[:count]

        # Preview table
        table = Table(title=f"🎯 将向以下 {len(targets)} 个职位打招呼", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("职位", style="bold cyan", max_width=25)
        table.add_column("公司", style="green", max_width=20)
        table.add_column("薪资", style="yellow", max_width=12)

        for i, job in enumerate(targets, 1):
            table.add_row(str(i), job.get("jobName", "-"), job.get("brandName", "-"), job.get("salaryDesc", "-"))

        console.print(table)

        if dry_run:
            console.print("\n  [dim]📋 预览模式，未实际发送[/dim]")
            return

        if not yes:
            confirm = click.confirm(f"\n确定向 {len(targets)} 个职位打招呼吗?")
            if not confirm:
                console.print("[dim]已取消[/dim]")
                return

        # Send greetings with auth auto-refresh on every request.
        success = 0
        for i, job in enumerate(targets, 1):
            security_id = job.get("securityId", "")
            lid = job.get("lid", "")
            job_name = job.get("jobName", "?")
            brand = job.get("brandName", "?")

            if not security_id:
                console.print(f"  [{i}] [yellow]跳过 {job_name} (无 securityId)[/yellow]")
                continue

            try:
                run_client_action(
                    cred,
                    lambda client, security_id=security_id, lid=lid: client.add_friend(
                        security_id=security_id,
                        lid=lid,
                    ),
                )
                console.print(f"  [{i}] [green]✅ {job_name} @ {brand}[/green]")
                success += 1
            except BossApiError as e:
                console.print(f"  [{i}] [red]❌ {job_name}: {e}[/red]")

            # Explicit rate-limit delay between greetings to avoid detection
            if i < len(targets):
                time.sleep(1.5)

        console.print(f"\n[bold]完成: {success}/{len(targets)} 个打招呼成功[/bold]")

    except BossApiError as exc:
        console.print(f"[red]❌ 搜索失败: {exc}[/red]")
        raise SystemExit(1) from None
