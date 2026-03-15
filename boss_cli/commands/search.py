"""Search and browse commands: search, recommend, cities, detail, show, export, history."""

from __future__ import annotations

import csv
import io
import json
import logging

import click
from rich.panel import Panel
from rich.table import Table

from ..client import BossClient, list_cities, resolve_city
from ..constants import DEGREE_CODES, EXP_CODES, INDUSTRY_CODES, JOB_TYPE_CODES, SALARY_CODES, SCALE_CODES, STAGE_CODES
from ..exceptions import BossApiError
from ..index_cache import get_index_info, get_job_by_index, save_index
from ._common import (
    console,
    handle_command,
    require_auth,
    run_client_action,
    structured_output_options,
)

logger = logging.getLogger(__name__)


# ── Helper: render job table ────────────────────────────────────────

def _render_job_table(
    job_list: list[dict], title: str, page: int = 1, hint_next: str = "",
) -> None:
    """Render a list of jobs as a rich table and save to index cache."""
    if not job_list:
        console.print("[yellow]没有找到匹配的职位[/yellow]")
        return

    # Save to index cache for `boss show` navigation
    save_index(job_list, source=title[:30])

    table = Table(title=f"{title} — {len(job_list)} 个结果", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("职位", style="bold cyan", max_width=30)
    table.add_column("公司", style="green", max_width=20)
    table.add_column("薪资", style="yellow", max_width=12)
    table.add_column("经验", max_width=10)
    table.add_column("学历", max_width=8)
    table.add_column("地区", style="blue", max_width=15)
    table.add_column("技能", style="dim", max_width=20)

    for i, job in enumerate(job_list, 1):
        skills = job.get("skills", [])
        skill_str = ", ".join(skills[:3]) if skills else "-"
        area = job.get("areaDistrict", "")
        biz = job.get("businessDistrict", "")
        location = f"{area} {biz}".strip() if area else job.get("cityName", "-")

        table.add_row(
            str(i),
            job.get("jobName", "-"),
            job.get("brandName", "-"),
            job.get("salaryDesc", "-"),
            job.get("jobExperience", "-"),
            job.get("jobDegree", "-"),
            location,
            skill_str,
        )

    console.print(table)
    console.print("  [dim]💡 使用 boss show <编号> 查看职位详情[/dim]")

    if hint_next:
        console.print(f"  [dim]▸ {hint_next}[/dim]")


# ── search ──────────────────────────────────────────────────────────

@click.command()
@click.argument("keyword")
@click.option("-c", "--city", default="全国", help="城市名称或代码 (默认: 全国)")
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("--industry", type=click.Choice(list(INDUSTRY_CODES.keys())), help="行业筛选 (如: 互联网, 金融)")
@click.option("--scale", type=click.Choice(list(SCALE_CODES.keys())), help="公司规模筛选 (如: 1000-9999人)")
@click.option("--stage", type=click.Choice(list(STAGE_CODES.keys())), help="融资阶段筛选 (如: A轮, 已上市)")
@click.option("--job-type", type=click.Choice(list(JOB_TYPE_CODES.keys())), help="职位类型 (全职/兼职/实习)")
@structured_output_options
def search(
    keyword: str, city: str, page: int,
    salary: str | None, exp: str | None, degree: str | None,
    industry: str | None, scale: str | None, stage: str | None, job_type: str | None,
    as_json: bool, as_yaml: bool,
) -> None:
    """搜索职位 (例: boss search Python --city 北京 --industry 互联网)"""
    cred = require_auth()

    city_code = resolve_city(city)
    salary_code = SALARY_CODES.get(salary) if salary else None
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None
    industry_code = INDUSTRY_CODES.get(industry) if industry else None
    scale_code = SCALE_CODES.get(scale) if scale else None
    stage_code = STAGE_CODES.get(stage) if stage else None
    job_type_code = JOB_TYPE_CODES.get(job_type) if job_type else None

    def _action(c: BossClient) -> dict:
        return c.search_jobs(
            query=keyword, city=city_code, page=page,
            experience=exp_code, degree=degree_code, salary=salary_code,
            industry=industry_code, scale=scale_code, stage=stage_code,
            job_type=job_type_code,
        )

    def _render(data: dict) -> None:
        job_list = data.get("jobList", [])
        # Always save index cache for `boss show` navigation
        if job_list:
            save_index(job_list, source=f"search:{keyword}")

        filters = [city]
        for f in (salary, exp, degree, industry, scale, stage, job_type):
            if f:
                filters.append(f)
        filter_str = " · ".join(filters)

        _render_job_table(
            job_list,
            title=f"🔍 搜索: {keyword} ({filter_str})",
            page=page,
            hint_next=f"更多结果: boss search \"{keyword}\" --city {city} -p {page + 1}" if data.get("hasMore") else "",
        )

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── recommend ───────────────────────────────────────────────────────

@click.command()
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@structured_output_options
def recommend(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看推荐职位 (基于求职期望)"""
    cred = require_auth()

    def _action(c):
        return c.get_recommend_jobs(page=page)

    def _render(data: dict) -> None:
        job_list = data.get("jobList", [])
        _render_job_table(
            job_list,
            title=f"⭐ 推荐职位 (第 {page} 页)",
            page=page,
            hint_next=f"更多推荐: boss recommend -p {page + 1}" if data.get("hasMore") else "",
        )

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── detail ──────────────────────────────────────────────────────────

@click.command()
@click.argument("security_id")
@structured_output_options
def detail(security_id: str, as_json: bool, as_yaml: bool) -> None:
    """查看职位详情 (需要 securityId 或使用 boss show)"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_job_detail(security_id=security_id)

    handle_command(cred, action=_action, render=_render_detail, as_json=as_json, as_yaml=as_yaml)


# ── show (short-index) ──────────────────────────────────────────────

@click.command()
@click.argument("index", type=int)
@structured_output_options
def show(index: int, as_json: bool, as_yaml: bool) -> None:
    """按搜索结果编号查看职位详情 (例: boss show 3)

    使用 search 或 recommend 命令后，可用编号快速查看详情。
    """
    job = get_job_by_index(index)
    if not job:
        info = get_index_info()
        if not info.get("exists"):
            console.print("[yellow]暂无缓存的搜索结果，请先运行 boss search 或 boss recommend[/yellow]")
        else:
            console.print(f"[yellow]编号 {index} 超出范围 (共 {info.get('count', 0)} 个结果)[/yellow]")
        return

    security_id = job.get("securityId", "")
    if not security_id:
        console.print("[red]❌ 该职位缺少 securityId[/red]")
        return

    # Show brief info from cache first
    console.print(
        f"  [dim]#{index}[/dim] [cyan]{job.get('jobName', '-')}[/cyan] @ "
        f"[green]{job.get('brandName', '-')}[/green]  "
        f"[yellow]{job.get('salaryDesc', '-')}[/yellow]"
    )
    console.print()

    # Fetch full detail
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_job_detail(security_id=security_id)

    handle_command(cred, action=_action, render=_render_detail, as_json=as_json, as_yaml=as_yaml)


def _render_detail(data: dict) -> None:
    """Render job detail panel (shared by detail and show commands)."""
    job = data.get("jobInfo", data)
    boss = data.get("bossInfo", {})
    brand = data.get("brandComInfo", {})

    title = job.get("jobName", "-")
    salary = job.get("salaryDesc", "-")
    exp = job.get("experienceName", job.get("jobExperience", "-"))
    degree = job.get("degreeName", job.get("jobDegree", "-"))
    city = job.get("locationName", job.get("cityName", "-"))

    company = brand.get("brandName", job.get("brandName", "-"))
    industry = brand.get("industryName", "-")
    scale = brand.get("scaleName", "-")
    stage = brand.get("stageName", "-")

    boss_name = boss.get("name", "-")
    boss_title = boss.get("title", "-")

    skills = job.get("skills", [])
    skill_str = ", ".join(skills) if skills else "-"

    desc = job.get("postDescription", job.get("jobDesc", ""))
    if not desc:
        desc = data.get("jobDesc", "-")

    panel_text = (
        f"[bold cyan]{title}[/bold cyan]  [yellow]{salary}[/yellow]\n"
        f"经验: {exp} · 学历: {degree} · 地区: {city}\n"
        f"技能: {skill_str}\n"
        f"\n"
        f"[bold green]公司:[/bold green] {company}\n"
        f"行业: {industry} · 规模: {scale} · 阶段: {stage}\n"
        f"\n"
        f"[bold magenta]招聘者:[/bold magenta] {boss_name} ({boss_title})\n"
    )

    if desc:
        if len(desc) > 500:
            desc = desc[:500] + "..."
        panel_text += f"\n[bold]职位描述:[/bold]\n{desc}"

    panel = Panel(panel_text, title="📋 职位详情", border_style="cyan")
    console.print(panel)


# ── export ──────────────────────────────────────────────────────────

@click.command()
@click.argument("keyword")
@click.option("-c", "--city", default="全国", help="城市名称或代码")
@click.option("-n", "--count", default=30, type=int, help="导出数量 (默认: 30)")
@click.option("--salary", type=click.Choice(list(SALARY_CODES.keys())), help="薪资筛选")
@click.option("--exp", type=click.Choice(list(EXP_CODES.keys())), help="工作经验筛选")
@click.option("--degree", type=click.Choice(list(DEGREE_CODES.keys())), help="学历筛选")
@click.option("--industry", type=click.Choice(list(INDUSTRY_CODES.keys())), help="行业筛选")
@click.option("--scale", type=click.Choice(list(SCALE_CODES.keys())), help="公司规模筛选")
@click.option("--stage", type=click.Choice(list(STAGE_CODES.keys())), help="融资阶段筛选")
@click.option("--job-type", type=click.Choice(list(JOB_TYPE_CODES.keys())), help="职位类型")
@click.option("-o", "--output", "output_file", default=None, help="输出文件路径 (默认: stdout)")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="输出格式")
def export(
    keyword: str, city: str, count: int,
    salary: str | None, exp: str | None, degree: str | None,
    industry: str | None, scale: str | None, stage: str | None, job_type: str | None,
    output_file: str | None, fmt: str,
) -> None:
    """导出搜索结果为 CSV 或 JSON

    例: boss export "golang" --city 杭州 -n 50 -o jobs.csv
    """
    cred = require_auth()

    city_code = resolve_city(city)
    salary_code = SALARY_CODES.get(salary) if salary else None
    exp_code = EXP_CODES.get(exp) if exp else None
    degree_code = DEGREE_CODES.get(degree) if degree else None
    industry_code = INDUSTRY_CODES.get(industry) if industry else None
    scale_code = SCALE_CODES.get(scale) if scale else None
    stage_code = STAGE_CODES.get(stage) if stage else None
    job_type_code = JOB_TYPE_CODES.get(job_type) if job_type else None

    all_jobs: list[dict] = []
    pages_needed = (count + 14) // 15  # 15 per page

    try:
        def _collect(c: BossClient) -> list[dict]:
            nonlocal all_jobs
            for pg in range(1, pages_needed + 1):
                data = c.search_jobs(
                    query=keyword, city=city_code, page=pg,
                    experience=exp_code, degree=degree_code, salary=salary_code,
                    industry=industry_code, scale=scale_code, stage=stage_code,
                    job_type=job_type_code,
                )
                job_list = data.get("jobList", [])
                all_jobs.extend(job_list)
                console.print(f"  [dim]📦 第 {pg} 页: {len(job_list)} 个职位 (累计: {len(all_jobs)})[/dim]")

                if not data.get("hasMore", False) or len(all_jobs) >= count:
                    break
            return all_jobs[:count]

        all_jobs = run_client_action(cred, _collect)

        if fmt == "json":
            output_text = json.dumps(all_jobs, indent=2, ensure_ascii=False)
        else:
            # CSV
            buf = io.StringIO()
            fieldnames = ["职位", "公司", "薪资", "经验", "学历", "城市", "地区", "技能", "URL", "securityId"]
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for job in all_jobs:
                eid = job.get("encryptJobId", "")
                url = f"https://www.zhipin.com/job_detail/{eid}.html" if eid else ""
                writer.writerow({
                    "职位": job.get("jobName", ""),
                    "公司": job.get("brandName", ""),
                    "薪资": job.get("salaryDesc", ""),
                    "经验": job.get("jobExperience", ""),
                    "学历": job.get("jobDegree", ""),
                    "城市": job.get("cityName", ""),
                    "地区": job.get("areaDistrict", ""),
                    "技能": ", ".join(job.get("skills", [])),
                    "URL": url,
                    "securityId": job.get("securityId", ""),
                })
            output_text = buf.getvalue()

        if output_file:
            with open(output_file, "w", encoding="utf-8-sig" if fmt == "csv" else "utf-8") as f:
                f.write(output_text)
            console.print(f"\n[green]✅ 已导出 {len(all_jobs)} 个职位到 {output_file}[/green]")
        else:
            click.echo(output_text)

    except BossApiError as exc:
        console.print(f"[red]❌ 导出失败: {exc}[/red]")
        raise SystemExit(1) from None


# ── history ─────────────────────────────────────────────────────────

@click.command()
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@structured_output_options
def history(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看浏览历史"""
    cred = require_auth()

    def _action(c: BossClient) -> dict:
        return c.get_job_history(page=page)

    def _render(data: dict) -> None:
        job_list = data.get("jobList", [])
        _render_job_table(
            job_list,
            title=f"📜 浏览历史 (第 {page} 页)",
            page=page,
            hint_next=f"更多: boss history -p {page + 1}" if data.get("hasMore") else "",
        )

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


# ── cities ──────────────────────────────────────────────────────────

@click.command()
def cities() -> None:
    """列出支持的城市代码"""
    codes = list_cities()
    table = Table(title="🏙️ 支持的城市", show_lines=False)
    table.add_column("城市", style="cyan", width=10)
    table.add_column("代码", style="dim", width=12)

    for name, code in codes.items():
        table.add_row(name, code)

    console.print(table)
    console.print(f"\n  [dim]共 {len(codes)} 个城市。使用: boss search \"Python\" --city 杭州[/dim]")
