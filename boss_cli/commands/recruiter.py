"""Recruiter (Boss) commands — Click subcommand group with 8+ commands."""

from __future__ import annotations

import csv
import io
import json
import logging
import time

import click
from rich.panel import Panel
from rich.table import Table

from ..client import BossClient, resolve_city
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


@click.group()
def recruiter() -> None:
    """招聘方/雇主端操作 (Recruiter mode)"""


# ── recruiter jobs ──────────────────────────────────────────────────


@recruiter.command("jobs")
@structured_output_options
def recruiter_jobs(as_json: bool, as_yaml: bool) -> None:
    """查看招聘中的职位列表"""
    cred = require_auth()

    def _render(data: list[dict]) -> None:
        if not data:
            console.print("[yellow]暂无在线职位[/yellow]")
            return

        table = Table(title=f"招聘职位 ({len(data)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("职位", style="bold cyan", max_width=25)
        table.add_column("薪资", style="yellow", max_width=12)
        table.add_column("地区", style="blue", max_width=15)
        table.add_column("encJobId", style="dim", max_width=30)

        for i, job in enumerate(data, 1):
            table.add_row(
                str(i),
                job.get("jobName", "-"),
                job.get("salaryDesc", "-"),
                job.get("address", "-"),
                job.get("encryptJobId", "-"),
            )

        console.print(table)
        console.print("  [dim]使用 boss recruiter inbox --job <encJobId> 查看该职位的候选人[/dim]")

    handle_command(
        cred, action=lambda c: c.get_boss_chatted_jobs(),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── recruiter search ──────────────────────────────────────────────


@recruiter.command("search")
@click.argument("keyword")
@click.option("-c", "--city", default="上海", help="城市名称或代码 (默认: 上海)")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="薪资筛选")
@click.option("--job", "encrypt_job_id", default="", help="关联职位 encryptJobId")
@click.option("-p", "--page", default=1, type=int, help="页码")
@structured_output_options
def recruiter_search(
    keyword: str, city: str, exp: str | None, degree: str | None,
    salary: str | None, encrypt_job_id: str, page: int,
    as_json: bool, as_yaml: bool,
) -> None:
    """搜索候选人 (Search candidates)"""
    cred = require_auth()
    city_code = resolve_city(city)
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None
    salary_code = SALARY_CODES.get(salary) if salary else None

    def _action(c: BossClient) -> dict:
        return c.search_geeks(
            query=keyword, city=city_code, page=page,
            experience=exp_code, degree=degree_code,
            salary=salary_code, encrypt_job_id=encrypt_job_id,
        )

    def _render(data: dict) -> None:
        geek_list = data.get("geekList", data.get("resultList", []))
        if not geek_list:
            console.print("[yellow]未找到匹配候选人 (可能需要 __zp_stoken__)[/yellow]")
            if data:
                console.print(f"  [dim]返回数据: {json.dumps(data, ensure_ascii=False)[:200]}[/dim]")
            return

        table = Table(title=f"搜索候选人: {keyword} ({len(geek_list)} 人)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("姓名", style="bold cyan", max_width=10)
        table.add_column("职位", style="green", max_width=20)
        table.add_column("经验", style="yellow", max_width=8)
        table.add_column("学历", max_width=6)
        table.add_column("encryptGeekId", style="dim", max_width=28)

        for i, geek in enumerate(geek_list, 1):
            table.add_row(
                str(i),
                geek.get("name", geek.get("geekName", "-")),
                geek.get("expectPositionName", geek.get("jobName", "-")),
                geek.get("workYearDesc", geek.get("workYear", "-")),
                geek.get("degreeDesc", geek.get("degree", "-")),
                geek.get("encryptGeekId", geek.get("encryptUid", "-")),
            )

        console.print(table)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter recommend ──────────────────────────────────────────


@recruiter.command("recommend")
@click.option("-p", "--page", default=1, type=int, help="页码")
@click.option("--job", "enc_job_id", default="", help="关联职位 encryptJobId")
@structured_output_options
def recruiter_recommend(page: int, enc_job_id: str, as_json: bool, as_yaml: bool) -> None:
    """推荐候选人列表 (greetRecSortList)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_boss_recommend_geeks(page=page, enc_job_id=enc_job_id)

    def _render(data: dict) -> None:
        friend_list = data.get("friendList", [])
        limit = data.get("limit", 0)

        if not friend_list:
            console.print("[yellow]暂无推荐候选人[/yellow]")
            return

        table = Table(
            title=f"推荐候选人 ({len(friend_list)} 人, 上限 {limit})",
            show_lines=True,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("姓名", style="bold cyan", max_width=10)
        table.add_column("职位", style="green", max_width=20)
        table.add_column("encJobId", style="dim", max_width=28)
        table.add_column("新牛人", max_width=4)
        table.add_column("时间", style="dim", max_width=10)

        for i, f in enumerate(friend_list, 1):
            new_flag = "NEW" if f.get("newGeek") else ""
            table.add_row(
                str(i),
                f.get("name", "-"),
                f.get("jobName", "-"),
                f.get("encryptJobId", "-"),
                new_flag,
                f.get("lastTime", "-"),
            )

        console.print(table)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter greet ──────────────────────────────────────────────


@recruiter.command("greet")
@click.argument("encrypt_geek_id")
@click.option("--job", "encrypt_job_id", default="", help="关联职位 encryptJobId")
@structured_output_options
def recruiter_greet(encrypt_geek_id: str, encrypt_job_id: str, as_json: bool, as_yaml: bool) -> None:
    """向候选人发起沟通 (Initiate conversation with candidate)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        # Get job id if not provided
        job_id = encrypt_job_id
        if not job_id:
            jobs = c.get_boss_chatted_jobs()
            if jobs:
                job_id = jobs[0].get("encryptJobId", "")

        # View the geek first to show info
        if job_id:
            info = c.get_boss_view_geek(
                encrypt_geek_id=encrypt_geek_id,
                encrypt_job_id=job_id,
            )
        else:
            info = {"encryptGeekId": encrypt_geek_id, "note": "无关联职位, 无法获取详情"}
        return info

    def _render(data: dict) -> None:
        geek_info = data.get("geekDetailInfo", data.get("geekBaseInfo", data))
        base_info = geek_info.get("geekBaseInfo", geek_info) if isinstance(geek_info, dict) else data
        name = base_info.get("name", base_info.get("geekName", "-"))
        console.print(f"[cyan]候选人: {name}[/cyan]  encryptGeekId={encrypt_geek_id}")
        console.print("[dim]提示: 使用 boss recruiter reply <friendId> <message> 发送消息[/dim]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter batch-greet ──────────────────────────────────────────


@recruiter.command("batch-greet")
@click.argument("keyword")
@click.option("-c", "--city", default="上海", help="城市名称或代码")
@click.option("-n", "--count", default=5, type=int, help="打招呼数量 (默认: 5)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("--job", "encrypt_job_id", default="", help="关联职位 encryptJobId")
@click.option("--dry-run", is_flag=True, help="仅预览, 不实际发送")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
def recruiter_batch_greet(
    keyword: str, city: str, count: int,
    salary: str | None, exp: str | None, degree: str | None,
    encrypt_job_id: str, dry_run: bool, yes: bool,
) -> None:
    """批量向搜索结果中的候选人发起沟通

    例: boss recruiter batch-greet "golang" --city 上海 -n 10
    """
    cred = require_auth()
    city_code = resolve_city(city)
    salary_code = SALARY_CODES.get(salary) if salary else None
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None

    try:
        data = run_client_action(
            cred,
            lambda client: client.search_geeks(
                query=keyword, city=city_code,
                experience=exp_code, degree=degree_code,
                salary=salary_code, encrypt_job_id=encrypt_job_id,
            ),
        )

        geek_list = data.get("geekList", data.get("resultList", []))
        if not geek_list:
            console.print("[yellow]未找到匹配候选人[/yellow]")
            return

        targets = geek_list[:count]

        # Preview table
        table = Table(title=f"将向以下 {len(targets)} 个候选人发起沟通", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("姓名", style="bold cyan", max_width=12)
        table.add_column("职位", style="green", max_width=20)
        table.add_column("经验", style="yellow", max_width=10)

        for i, geek in enumerate(targets, 1):
            table.add_row(
                str(i),
                geek.get("name", geek.get("geekName", "-")),
                geek.get("expectPositionName", geek.get("jobName", "-")),
                geek.get("workYearDesc", "-"),
            )

        console.print(table)

        if dry_run:
            console.print("\n  [dim]预览模式, 未实际发送[/dim]")
            return

        if not yes:
            confirm = click.confirm(f"\n确定向 {len(targets)} 个候选人发起沟通吗?")
            if not confirm:
                console.print("[dim]已取消[/dim]")
                return

        success = 0
        for i, geek in enumerate(targets, 1):
            geek_id = geek.get("encryptGeekId", geek.get("encryptUid", ""))
            name = geek.get("name", geek.get("geekName", "?"))

            if not geek_id:
                console.print(f"  [{i}] [yellow]跳过 {name} (无 encryptGeekId)[/yellow]")
                continue

            try:
                run_client_action(
                    cred,
                    lambda client, gid=geek_id: client.get_boss_view_geek(
                        encrypt_geek_id=gid,
                        encrypt_job_id=encrypt_job_id,
                    ),
                )
                console.print(f"  [{i}] [green]{name} - 已查看[/green]")
                success += 1
            except BossApiError as e:
                console.print(f"  [{i}] [red]{name}: {e}[/red]")

            if i < len(targets):
                time.sleep(1.5)

        console.print(f"\n[bold]完成: {success}/{len(targets)} 个候选人已处理[/bold]")

    except BossApiError as exc:
        console.print(f"[red]搜索失败: {exc}[/red]")
        raise SystemExit(1) from None


# ── recruiter inbox ──────────────────────────────────────────────


@recruiter.command("inbox")
@click.option("--job", "enc_job_id", default="", help="按职位 encryptJobId 筛选")
@click.option("--label", "label_id", default=0, type=int, help="按标签筛选 (0=全部)")
@structured_output_options
def recruiter_inbox(enc_job_id: str, label_id: int, as_json: bool, as_yaml: bool) -> None:
    """查看候选人消息列表 (招聘方沟通列表)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        friend_data = c.get_boss_friend_list(label_id=label_id, enc_job_id=enc_job_id)
        friend_list = friend_data.get("result", [])

        if not friend_list:
            return {"friendList": [], "lastMessages": []}

        friend_ids = [f["friendId"] for f in friend_list if f.get("friendId")]

        details = c.get_boss_friend_details(friend_ids)
        detail_list = details.get("friendList", [])

        batch_ids = friend_ids[:50]
        last_msgs = c.get_boss_last_messages(batch_ids)

        return {"friendList": detail_list, "lastMessages": last_msgs}

    def _render(data: dict) -> None:
        detail_list = data.get("friendList", [])
        last_msgs = data.get("lastMessages", [])

        if not detail_list:
            console.print("[yellow]暂无候选人消息[/yellow]")
            return

        msg_map: dict[int, dict] = {}
        if isinstance(last_msgs, list):
            for msg in last_msgs:
                uid = msg.get("uid", 0)
                if uid:
                    msg_map[uid] = msg

        table = Table(title=f"候选人列表 ({len(detail_list)} 人)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("候选人", style="bold cyan", max_width=12)
        table.add_column("职位", style="green", max_width=20)
        table.add_column("薪资", style="yellow", max_width=10)
        table.add_column("最近消息", style="dim", max_width=30)
        table.add_column("时间", style="dim", max_width=8)

        for i, friend in enumerate(detail_list, 1):
            uid = friend.get("uid", 0)
            msg_info = msg_map.get(uid, {})
            last_text = ""
            if msg_info.get("lastMsgInfo"):
                last_text = msg_info["lastMsgInfo"].get("showText", "")[:28]

            table.add_row(
                str(i),
                friend.get("name", "-"),
                friend.get("jobName", "-"),
                friend.get("salaryDesc", friend.get("lastTime", "-")),
                last_text or "-",
                msg_info.get("lastTime", friend.get("lastTime", "-")),
            )

        console.print(table)
        console.print("  [dim]使用 boss recruiter resume <encryptGeekId> 查看候选人简历[/dim]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter reply ──────────────────────────────────────────────


@recruiter.command("reply")
@click.argument("friend_id", type=int)
@click.argument("message")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
@structured_output_options
def recruiter_reply(friend_id: int, message: str, yes: bool, as_json: bool, as_yaml: bool) -> None:
    """发送消息给候选人 (Send message to candidate)"""
    cred = require_auth()

    if not yes:
        console.print(f"[cyan]将向 friendId={friend_id} 发送消息:[/cyan]")
        console.print(f"  {message}")
        confirm = click.confirm("\n确认发送?")
        if not confirm:
            console.print("[dim]已取消[/dim]")
            return

    def _action(c: BossClient) -> dict:
        return c.boss_send_message(gid=friend_id, content=message)

    def _render(data: dict) -> None:
        console.print(f"[green]消息已发送 -> friendId={friend_id}[/green]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter export ──────────────────────────────────────────────


@recruiter.command("export")
@click.option("--job", "enc_job_id", default="", help="按职位 encryptJobId 筛选")
@click.option("-o", "--output", "output_file", default=None, help="输出文件路径")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="输出格式")
def recruiter_export(enc_job_id: str, output_file: str | None, fmt: str) -> None:
    """导出候选人列表为 CSV 或 JSON"""
    cred = require_auth()

    try:
        def _collect(c: BossClient) -> list[dict]:
            friend_data = c.get_boss_friend_list(enc_job_id=enc_job_id)
            friend_list = friend_data.get("result", [])

            if not friend_list:
                return []

            friend_ids = [f["friendId"] for f in friend_list if f.get("friendId")]
            details = c.get_boss_friend_details(friend_ids)
            return details.get("friendList", [])

        all_candidates = run_client_action(cred, _collect)

        if not all_candidates:
            console.print("[yellow]暂无候选人数据[/yellow]")
            return

        if fmt == "json":
            output_text = json.dumps(all_candidates, indent=2, ensure_ascii=False)
        else:
            buf = io.StringIO()
            fieldnames = ["姓名", "关联职位", "来源", "最近时间", "新牛人", "encryptUid", "securityId"]
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for f in all_candidates:
                source_map = {1: "搜索", 2: "推荐", 3: "打招呼", 5: "主动沟通"}
                writer.writerow({
                    "姓名": f.get("name", ""),
                    "关联职位": f.get("jobName", ""),
                    "来源": source_map.get(f.get("sourceType"), str(f.get("sourceType", ""))),
                    "最近时间": f.get("lastTime", ""),
                    "新牛人": "是" if f.get("newGeek") else "",
                    "encryptUid": f.get("encryptUid", f.get("encryptFriendId", "")),
                    "securityId": f.get("securityId", ""),
                })
            output_text = buf.getvalue()

        if output_file:
            with open(output_file, "w", encoding="utf-8-sig" if fmt == "csv" else "utf-8") as fh:
                fh.write(output_text)
            console.print(f"\n[green]已导出 {len(all_candidates)} 个候选人到 {output_file}[/green]")
        else:
            click.echo(output_text)

    except BossApiError as exc:
        console.print(f"[red]导出失败: {exc}[/red]")
        raise SystemExit(1) from None


# ── recruiter resume ──────────────────────────────────────────────


@recruiter.command("resume")
@click.argument("encrypt_geek_id")
@click.option("--job", "encrypt_job_id", default="", help="关联职位 encryptJobId")
@click.option("--security-id", default="", help="候选人 securityId")
@structured_output_options
def recruiter_resume(
    encrypt_geek_id: str, encrypt_job_id: str, security_id: str,
    as_json: bool, as_yaml: bool,
) -> None:
    """查看候选人完整简历 (View candidate full resume)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        nonlocal encrypt_job_id, security_id
        if not encrypt_job_id:
            jobs = c.get_boss_chatted_jobs()
            if jobs:
                encrypt_job_id = jobs[0].get("encryptJobId", "")

        if not encrypt_job_id:
            return {"error": "未找到关联职位, 请通过 --job 指定 encryptJobId"}

        # Auto-fetch securityId from friend list if not provided
        if not security_id:
            friend_data = c.get_boss_friend_list()
            for f in friend_data.get("result", []):
                if f.get("encryptFriendId") == encrypt_geek_id:
                    friend_ids = [f["friendId"]]
                    details = c.get_boss_friend_details(friend_ids)
                    for fd in details.get("friendList", []):
                        security_id = fd.get("securityId", "")
                        break
                    break

        return c.get_boss_view_geek(
            encrypt_geek_id=encrypt_geek_id,
            encrypt_job_id=encrypt_job_id,
            security_id=security_id,
        )

    def _render(data: dict) -> None:
        if data.get("error"):
            console.print(f"[red]{data['error']}[/red]")
            return

        # Navigate the nested response structure
        geek_detail = data.get("geekDetailInfo", data)
        base_info = geek_detail.get("geekBaseInfo", geek_detail)

        name = base_info.get("name", base_info.get("geekName", "-"))
        gender_val = base_info.get("gender", 0)
        gender = "男" if gender_val == 1 else "女" if gender_val == 2 else "-"
        degree = base_info.get("degreeCategory", base_info.get("degree", "-"))
        work_year = base_info.get("workYearDesc", base_info.get("workYear", "-"))
        age = base_info.get("ageDesc", base_info.get("age", "-"))
        apply_status = base_info.get("applyStatusContent", base_info.get("applyStatus", "-"))
        expect_position = base_info.get("expectPosition", "-")
        expect_city = base_info.get("expectCity", "-")
        expect_salary = base_info.get("expectSalary", base_info.get("salaryDesc", "-"))

        panel_text = (
            f"[bold cyan]{name}[/bold cyan]  {gender}  {age}\n"
            f"学历: {degree} | 工作年限: {work_year}\n"
            f"求职状态: {apply_status}\n"
            f"\n"
            f"[bold yellow]期望:[/bold yellow] {expect_position} | {expect_city} | {expect_salary}\n"
        )

        # Work experience
        work_exp = geek_detail.get("geekWorkExpList", base_info.get("workExpList", []))
        if work_exp:
            panel_text += "\n[bold green]工作经历:[/bold green]\n"
            for w in work_exp[:6]:
                company = w.get("company", w.get("companyName", ""))
                position = w.get("positionName", w.get("position", ""))
                time_desc = w.get("timeDesc", w.get("workTime", ""))
                industry = w.get("industry", "")
                desc = w.get("description", w.get("workDesc", ""))
                panel_text += f"  {time_desc}  [cyan]{company}[/cyan]"
                if industry:
                    panel_text += f" ({industry})"
                panel_text += f"\n    {position}\n"
                if desc:
                    panel_text += f"    [dim]{desc[:80]}[/dim]\n"

        # Education
        edu_exp = geek_detail.get("geekEduExpList", base_info.get("eduExpList", []))
        if edu_exp:
            panel_text += "\n[bold magenta]教育经历:[/bold magenta]\n"
            for e in edu_exp[:4]:
                school = e.get("school", e.get("schoolName", ""))
                major_name = e.get("major", e.get("majorName", ""))
                degree_name = e.get("degree", e.get("degreeName", ""))
                time_desc = e.get("timeDesc", e.get("eduTime", ""))
                panel_text += f"  {time_desc}  [cyan]{school}[/cyan]  {degree_name}\n"
                if major_name:
                    panel_text += f"    {major_name}\n"

        # Projects
        project_exp = geek_detail.get("geekProjectExpList", base_info.get("projectExpList", []))
        if project_exp:
            panel_text += "\n[bold blue]项目经历:[/bold blue]\n"
            for p in project_exp[:4]:
                proj_name = p.get("projectName", p.get("name", ""))
                role = p.get("roleName", p.get("role", ""))
                time_desc = p.get("timeDesc", p.get("projectTime", ""))
                desc = p.get("description", p.get("projectDesc", ""))
                panel_text += f"  {time_desc}  [cyan]{proj_name}[/cyan]  ({role})\n"
                if desc:
                    panel_text += f"    [dim]{desc[:100]}[/dim]\n"

        panel = Panel(panel_text.rstrip(), title="候选人简历", border_style="cyan")
        console.print(panel)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter labels ──────────────────────────────────────────────


@recruiter.command("labels")
@structured_output_options
def recruiter_labels(as_json: bool, as_yaml: bool) -> None:
    """查看候选人标签列表"""
    cred = require_auth()

    def _render(data: dict) -> None:
        labels = data.get("labels", data.get("labelList", data.get("result", [])))
        if isinstance(data, list):
            labels = data

        if not labels:
            console.print("[yellow]暂无标签[/yellow]")
            return

        table = Table(title="标签列表", show_lines=False)
        table.add_column("ID", style="dim", width=6)
        table.add_column("名称", style="cyan", max_width=20)

        for label in labels:
            table.add_row(
                str(label.get("labelId", label.get("id", "-"))),
                label.get("label", label.get("name", label.get("labelName", "-"))),
            )

        console.print(table)

    handle_command(
        cred, action=lambda c: c.get_boss_friend_labels(),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── recruiter chat (history) ──────────────────────────────────────


@recruiter.command("chat")
@click.argument("friend_id", type=int)
@click.option("-n", "--count", default=20, type=int, help="消息数量 (默认: 20)")
@structured_output_options
def recruiter_chat(friend_id: int, count: int, as_json: bool, as_yaml: bool) -> None:
    """查看与候选人的聊天记录 (需要 friendId)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_boss_chat_history(gid=friend_id, count=count)

    def _render(data: dict) -> None:
        messages = data.get("messages", [])

        if not messages:
            console.print("[yellow]暂无聊天记录[/yellow]")
            return

        table = Table(title=f"聊天记录 ({len(messages)} 条)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("方向", max_width=6)
        table.add_column("内容", max_width=50)
        table.add_column("类型", style="dim", max_width=6)

        for i, msg in enumerate(messages, 1):
            direction = "[cyan]<-[/cyan]" if msg.get("received", True) else "[green]->[/green]"

            body = msg.get("body", {})
            if isinstance(body, str):
                text = body[:48]
            elif isinstance(body, dict):
                text = body.get("text", body.get("showText", ""))
                if not text and body.get("resume"):
                    resume = body["resume"]
                    text = f"[简历] {resume.get('user', {}).get('name', '')} {resume.get('positionCategory', '')}"
                text = text[:48] if text else "[多媒体消息]"
            else:
                text = str(body)[:48]

            msg_type = str(msg.get("type", "-"))

            table.add_row(str(i), direction, text, msg_type)

        console.print(table)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recruiter geek (legacy - kept as alias for resume) ────────────


@recruiter.command("geek")
@click.argument("encrypt_geek_id")
@click.option("--security-id", default="", help="候选人 securityId")
@click.option("--job-id", default=0, type=int, help="关联职位 ID")
@structured_output_options
def recruiter_geek(
    encrypt_geek_id: str, security_id: str, job_id: int,
    as_json: bool, as_yaml: bool,
) -> None:
    """查看候选人详细信息 (需要 encryptGeekId)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        nonlocal job_id, security_id
        if not job_id:
            jobs = c.get_boss_chatted_jobs()
            if jobs:
                job_id = jobs[0].get("jobId", 0)

        if not security_id:
            friend_data = c.get_boss_friend_list()
            for f in friend_data.get("result", []):
                if f.get("encryptFriendId") == encrypt_geek_id:
                    friend_details = c.get_boss_friend_details([f["friendId"]])
                    for fd in friend_details.get("friendList", []):
                        security_id = fd.get("securityId", "")
                        break
                    break

        return c.get_boss_chat_geek_info(
            encrypt_geek_id=encrypt_geek_id,
            security_id=security_id,
            job_id=job_id,
        )

    def _render(data: dict) -> None:
        geek = data.get("data", data)

        name = geek.get("name", "-")
        age = geek.get("ageDesc", "-")
        gender = "男" if geek.get("gender") == 1 else "女" if geek.get("gender") == 2 else "-"
        edu = geek.get("edu", "-")
        city = geek.get("city", "-")
        salary = geek.get("salaryDesc", "-")
        expect_salary = geek.get("price", "-")
        position = geek.get("positionName", geek.get("toPosition", "-"))
        status = geek.get("positionStatus", "-")
        last_company = geek.get("lastCompany", "-")
        last_position = geek.get("lastPosition", "-")
        school = geek.get("school", "-")
        major = geek.get("major", "-")
        work_year = geek.get("year", "-")

        work_exp = geek.get("workExpList", [])
        work_lines = []
        for w in work_exp[:5]:
            work_lines.append(
                f"  {w.get('timeDesc', '')}  {w.get('company', '')} · {w.get('positionName', '')}"
            )

        panel_text = (
            f"[bold cyan]{name}[/bold cyan]  {gender}  {age}\n"
            f"学历: {edu} | 工作年限: {work_year}\n"
            f"城市: {city} | 求职状态: {status}\n"
            f"\n"
            f"[bold yellow]期望薪资:[/bold yellow] {expect_salary}\n"
            f"[bold yellow]当前薪资:[/bold yellow] {salary}\n"
            f"期望职位: {position}\n"
            f"\n"
            f"[bold green]当前/最近:[/bold green] {last_company}\n"
            f"职位: {last_position}\n"
            f"学校: {school} | {major}\n"
        )

        if work_lines:
            panel_text += "\n[bold magenta]工作经历:[/bold magenta]\n" + "\n".join(work_lines)

        panel = Panel(panel_text, title="候选人详情", border_style="cyan")
        console.print(panel)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)
