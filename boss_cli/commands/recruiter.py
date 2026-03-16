"""招聘方命令: search, recommend, detail, chat, greet, batch-greet, jobs, resumes, export."""

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


# ── Helper: render geek table ──────────────────────────────────────

def _render_geek_table(
    geek_list: list[dict], title: str, page: int = 1, hint_next: str = "",
) -> None:
    """将候选人列表渲染为 rich 表格。"""
    if not geek_list:
        console.print("[yellow]没有找到匹配的候选人[/yellow]")
        return

    table = Table(title=f"{title} — {len(geek_list)} 个结果", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("姓名", style="bold cyan", max_width=12)
    table.add_column("求职意向", style="green", max_width=20)
    table.add_column("薪资", style="yellow", max_width=12)
    table.add_column("经验", max_width=10)
    table.add_column("学历", max_width=8)
    table.add_column("城市", style="blue", max_width=12)
    table.add_column("技能", style="dim", max_width=20)

    for i, geek in enumerate(geek_list, 1):
        skills = geek.get("skills", geek.get("geekSkills", []))
        skill_str = ", ".join(skills[:3]) if skills else "-"
        name = geek.get("geekName", geek.get("name", "-"))
        expect = geek.get("expectPositionName", geek.get("jobName", "-"))
        salary = geek.get("salaryDesc", geek.get("expectSalaryDesc", "-"))
        exp = geek.get("experienceName", geek.get("geekExperience", "-"))
        degree = geek.get("degreeName", geek.get("geekDegree", "-"))
        city = geek.get("cityName", "-")

        table.add_row(str(i), name, expect, salary, exp, degree, city, skill_str)

    console.print(table)

    if hint_next:
        console.print(f"  [dim]▸ {hint_next}[/dim]")


# ── recruiter group ────────────────────────────────────────────────

@click.group()
def recruiter() -> None:
    """👔 招聘方模式 — 搜索候选人、打招呼、管理职位"""


# ── search ──────────────────────────────────────────────────────────

@recruiter.command()
@click.argument("keyword")
@click.option("-c", "--city", default="全国", help="城市名称或代码 (默认: 全国)")
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="期望薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@structured_output_options
def search(
    keyword: str, city: str, page: int,
    salary: str | None, exp: str | None, degree: str | None,
    as_json: bool, as_yaml: bool,
) -> None:
    """搜索候选人/牛人 (例: boss recruiter search Python --city 北京)"""
    cred = require_auth()

    city_code = resolve_city(city)
    salary_code = SALARY_CODES.get(salary) if salary else None
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None

    def _action(c: BossClient) -> dict:
        return c.search_geeks(
            query=keyword, city=city_code, page=page,
            experience=exp_code, degree=degree_code, salary=salary_code,
        )

    def _render(data: dict) -> None:
        geek_list = data.get("geekList", data.get("list", []))

        filters = [city]
        for f in (salary, exp, degree):
            if f:
                filters.append(f)
        filter_str = " · ".join(filters)

        _render_geek_table(
            geek_list,
            title=f"🔍 搜索候选人: {keyword} ({filter_str})",
            page=page,
            hint_next=(
                f"更多结果: boss recruiter search \"{keyword}\" --city {city} -p {page + 1}"
                if data.get("hasMore") else ""
            ),
        )

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recommend ──────────────────────────────────────────────────────

@recruiter.command()
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@structured_output_options
def recommend(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看推荐候选人"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_recommend_geeks(page=page)

    def _render(data: dict) -> None:
        geek_list = data.get("geekList", data.get("list", []))
        _render_geek_table(
            geek_list,
            title=f"⭐ 推荐候选人 (第 {page} 页)",
            page=page,
            hint_next=f"更多推荐: boss recruiter recommend -p {page + 1}" if data.get("hasMore") else "",
        )

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── detail ──────────────────────────────────────────────────────────

@recruiter.command()
@click.argument("security_id")
@structured_output_options
def detail(security_id: str, as_json: bool, as_yaml: bool) -> None:
    """查看候选人详情 (需要 securityId)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_geek_detail(security_id=security_id)

    def _render(data: dict) -> None:
        geek = data.get("geekInfo", data)
        name = geek.get("geekName", geek.get("name", "-"))
        expect = geek.get("expectPositionName", geek.get("jobName", "-"))
        salary = geek.get("salaryDesc", geek.get("expectSalaryDesc", "-"))
        exp = geek.get("experienceName", geek.get("geekExperience", "-"))
        degree = geek.get("degreeName", geek.get("geekDegree", "-"))
        city = geek.get("cityName", "-")
        age = geek.get("ageDesc", "-")

        skills = geek.get("skills", geek.get("geekSkills", []))
        skill_str = ", ".join(skills) if skills else "-"

        work_list = data.get("geekWorkList", data.get("workList", []))
        edu_list = data.get("geekEduList", data.get("eduList", []))

        desc = geek.get("geekDesc", geek.get("personalAdvantage", ""))

        panel_text = (
            f"[bold cyan]{name}[/bold cyan]  [yellow]{salary}[/yellow]\n"
            f"求职意向: {expect}\n"
            f"经验: {exp} · 学历: {degree} · 城市: {city} · 年龄: {age}\n"
            f"技能: {skill_str}\n"
        )

        if work_list:
            panel_text += "\n[bold green]工作经历:[/bold green]\n"
            for work in work_list:
                company = work.get("company", "-")
                position = work.get("positionName", work.get("position", "-"))
                duration = work.get("durationDesc", "")
                panel_text += f"  • {company} — {position}  {duration}\n"

        if edu_list:
            panel_text += "\n[bold blue]教育经历:[/bold blue]\n"
            for edu in edu_list:
                school = edu.get("school", "-")
                major = edu.get("major", "-")
                edu_degree = edu.get("degreeName", edu.get("degree", "-"))
                panel_text += f"  • {school} — {major} ({edu_degree})\n"

        if desc:
            if len(desc) > 500:
                desc = desc[:500] + "..."
            panel_text += f"\n[bold]个人优势:[/bold]\n{desc}"

        panel = Panel(panel_text, title="👤 候选人详情", border_style="cyan")
        console.print(panel)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── chat ────────────────────────────────────────────────────────────

@recruiter.command()
@structured_output_options
def chat(as_json: bool, as_yaml: bool) -> None:
    """查看沟通列表（招聘方视角）"""
    cred = require_auth()

    def _render(data: dict) -> None:
        friend_list = data.get("result", data.get("friendList", []))

        if not friend_list:
            console.print("[yellow]暂无沟通记录[/yellow]")
            return

        table = Table(title=f"💬 沟通列表 ({len(friend_list)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("候选人", style="bold cyan", max_width=15)
        table.add_column("求职意向", style="green", max_width=20)
        table.add_column("学历", max_width=8)
        table.add_column("经验", max_width=10)
        table.add_column("最近消息", style="dim", max_width=30)

        for i, friend in enumerate(friend_list, 1):
            table.add_row(
                str(i),
                friend.get("name", friend.get("geekName", "-")),
                friend.get("expectPositionName", friend.get("jobName", "-")),
                friend.get("degreeName", friend.get("geekDegree", "-")),
                friend.get("experienceName", friend.get("geekExperience", "-")),
                friend.get("lastMsg", friend.get("lastText", "-")),
            )

        console.print(table)

    handle_command(
        cred, action=lambda c: c.get_boss_friend_list(),
        render=_render, as_json=as_json, as_yaml=as_yaml,
    )


# ── greet ──────────────────────────────────────────────────────────

@recruiter.command()
@click.argument("security_id")
@click.option("--lid", default="", help="Lid parameter")
@structured_output_options
def greet(security_id: str, lid: str, as_json: bool, as_yaml: bool) -> None:
    """向候选人打招呼 (需要 securityId)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.boss_add_friend(security_id=security_id, lid=lid)

    def _render(data: dict) -> None:
        console.print("[green]✅ 打招呼成功！[/green]")
        if data:
            click.echo(json.dumps(data, indent=2, ensure_ascii=False))

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── batch-greet ────────────────────────────────────────────────────

@recruiter.command("batch-greet")
@click.argument("keyword")
@click.option("-c", "--city", default="全国", help="城市名称或代码")
@click.option("-n", "--count", default=5, type=int, help="打招呼数量 (默认: 5)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="期望薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("--dry-run", is_flag=True, help="仅预览，不实际发送")
@click.option("-y", "--yes", is_flag=True, help="跳过确认提示")
def batch_greet(
    keyword: str, city: str, count: int,
    salary: str | None, exp: str | None, degree: str | None,
    dry_run: bool, yes: bool,
) -> None:
    """批量向候选人打招呼

    例: boss recruiter batch-greet "Python" --city 杭州 -n 10 --exp 3-5年
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
                query=keyword,
                city=city_code,
                experience=exp_code,
                degree=degree_code,
                salary=salary_code,
            ),
        )

        geek_list = data.get("geekList", data.get("list", []))
        if not geek_list:
            console.print("[yellow]没有找到匹配的候选人[/yellow]")
            return

        targets = geek_list[:count]

        # 预览表格
        table = Table(title=f"🎯 将向以下 {len(targets)} 个候选人打招呼", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("姓名", style="bold cyan", max_width=15)
        table.add_column("求职意向", style="green", max_width=20)
        table.add_column("薪资", style="yellow", max_width=12)

        for i, geek in enumerate(targets, 1):
            table.add_row(
                str(i),
                geek.get("geekName", geek.get("name", "-")),
                geek.get("expectPositionName", geek.get("jobName", "-")),
                geek.get("salaryDesc", geek.get("expectSalaryDesc", "-")),
            )

        console.print(table)

        if dry_run:
            console.print("\n  [dim]📋 预览模式，未实际发送[/dim]")
            return

        if not yes:
            confirm = click.confirm(f"\n确定向 {len(targets)} 个候选人打招呼吗?")
            if not confirm:
                console.print("[dim]已取消[/dim]")
                return

        success = 0
        for i, geek in enumerate(targets, 1):
            security_id = geek.get("securityId", geek.get("encryptGeekId", ""))
            lid = geek.get("lid", "")
            name = geek.get("geekName", geek.get("name", "?"))
            expect = geek.get("expectPositionName", geek.get("jobName", "?"))

            if not security_id:
                console.print(f"  [{i}] [yellow]跳过 {name} (无 securityId)[/yellow]")
                continue

            try:
                run_client_action(
                    cred,
                    lambda client, sid=security_id, l=lid: client.boss_add_friend(
                        security_id=sid, lid=l,
                    ),
                )
                console.print(f"  [{i}] [green]✅ {name} ({expect})[/green]")
                success += 1
            except BossApiError as e:
                console.print(f"  [{i}] [red]❌ {name}: {e}[/red]")

            if i < len(targets):
                time.sleep(1.5)

        console.print(f"\n[bold]完成: {success}/{len(targets)} 个打招呼成功[/bold]")

    except BossApiError as exc:
        console.print(f"[red]❌ 搜索失败: {exc}[/red]")
        raise SystemExit(1) from None


# ── jobs ────────────────────────────────────────────────────────────

@recruiter.command()
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@structured_output_options
def jobs(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看我发布的职位"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_boss_jobs(page=page)

    def _render(data: dict) -> None:
        job_list = data.get("jobList", data.get("list", []))

        if not job_list:
            console.print("[yellow]暂无发布的职位[/yellow]")
            return

        table = Table(title=f"📋 我发布的职位 (第 {page} 页)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("职位", style="bold cyan", max_width=25)
        table.add_column("薪资", style="yellow", max_width=12)
        table.add_column("城市", style="blue", max_width=12)
        table.add_column("状态", max_width=8)
        table.add_column("更新时间", style="dim", max_width=15)

        for i, job in enumerate(job_list, 1):
            status = job.get("statusDesc", job.get("status", "-"))
            update_time = job.get("updateTime", job.get("lastModifyTime", "-"))
            table.add_row(
                str(i),
                job.get("jobName", job.get("positionName", "-")),
                job.get("salaryDesc", "-"),
                job.get("cityName", "-"),
                str(status),
                str(update_time),
            )

        console.print(table)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── resumes ────────────────────────────────────────────────────────

@recruiter.command()
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@structured_output_options
def resumes(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看收到的简历"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_resume_list(page=page)

    def _render(data: dict) -> None:
        resume_list = data.get("resumeList", data.get("list", data.get("geekList", [])))

        if not resume_list:
            console.print("[yellow]暂无收到的简历[/yellow]")
            return

        table = Table(title=f"📄 收到的简历 (第 {page} 页)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("候选人", style="bold cyan", max_width=15)
        table.add_column("求职意向", style="green", max_width=20)
        table.add_column("学历", max_width=8)
        table.add_column("经验", max_width=10)
        table.add_column("投递职位", style="blue", max_width=20)
        table.add_column("时间", style="dim", max_width=15)

        for i, resume in enumerate(resume_list, 1):
            table.add_row(
                str(i),
                resume.get("geekName", resume.get("name", "-")),
                resume.get("expectPositionName", "-"),
                resume.get("degreeName", resume.get("geekDegree", "-")),
                resume.get("experienceName", resume.get("geekExperience", "-")),
                resume.get("jobName", resume.get("positionName", "-")),
                resume.get("addTime", resume.get("createTime", "-")),
            )

        console.print(table)

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── export ──────────────────────────────────────────────────────────

@recruiter.command()
@click.argument("keyword")
@click.option("-c", "--city", default="全国", help="城市名称或代码")
@click.option("-n", "--count", default=30, type=int, help="导出数量 (默认: 30)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="期望薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("-o", "--output", "output_file", default=None, help="输出文件路径 (默认: stdout)")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="输出格式")
def export(
    keyword: str, city: str, count: int,
    salary: str | None, exp: str | None, degree: str | None,
    output_file: str | None, fmt: str,
) -> None:
    """导出候选人数据为 CSV 或 JSON

    例: boss recruiter export "golang" --city 杭州 -n 50 -o geeks.csv
    """
    cred = require_auth()

    city_code = resolve_city(city)
    salary_code = SALARY_CODES.get(salary) if salary else None
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None

    all_geeks: list[dict] = []
    pages_needed = (count + 14) // 15

    try:
        def _collect(c: BossClient) -> list[dict]:
            nonlocal all_geeks
            for pg in range(1, pages_needed + 1):
                data = c.search_geeks(
                    query=keyword, city=city_code, page=pg,
                    experience=exp_code, degree=degree_code, salary=salary_code,
                )
                geek_list = data.get("geekList", data.get("list", []))
                all_geeks.extend(geek_list)
                console.print(f"  [dim]📦 第 {pg} 页: {len(geek_list)} 个候选人 (累计: {len(all_geeks)})[/dim]")

                if not data.get("hasMore", False) or len(all_geeks) >= count:
                    break
            return all_geeks[:count]

        all_geeks = run_client_action(cred, _collect)

        if fmt == "json":
            output_text = json.dumps(all_geeks, indent=2, ensure_ascii=False)
        else:
            buf = io.StringIO()
            fieldnames = ["姓名", "求职意向", "薪资", "经验", "学历", "城市", "技能", "securityId"]
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for geek in all_geeks:
                skills = geek.get("skills", geek.get("geekSkills", []))
                writer.writerow({
                    "姓名": geek.get("geekName", geek.get("name", "")),
                    "求职意向": geek.get("expectPositionName", geek.get("jobName", "")),
                    "薪资": geek.get("salaryDesc", geek.get("expectSalaryDesc", "")),
                    "经验": geek.get("experienceName", geek.get("geekExperience", "")),
                    "学历": geek.get("degreeName", geek.get("geekDegree", "")),
                    "城市": geek.get("cityName", ""),
                    "技能": ", ".join(skills) if skills else "",
                    "securityId": geek.get("securityId", geek.get("encryptGeekId", "")),
                })
            output_text = buf.getvalue()

        if output_file:
            with open(output_file, "w", encoding="utf-8-sig" if fmt == "csv" else "utf-8") as f:
                f.write(output_text)
            console.print(f"\n[green]✅ 已导出 {len(all_geeks)} 个候选人到 {output_file}[/green]")
        else:
            click.echo(output_text)

    except BossApiError as exc:
        console.print(f"[red]❌ 导出失败: {exc}[/red]")
        raise SystemExit(1) from None
