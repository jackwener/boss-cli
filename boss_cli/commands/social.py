"""Social commands: chat, greet, batch-greet."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

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
@structured_output_options
def chat_list(as_json: bool, as_yaml: bool) -> None:
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

        for i, friend in enumerate(friend_list, 1):
            table.add_row(
                str(i),
                friend.get("name", friend.get("bossName", "-")),
                friend.get("brandName", "-"),
                friend.get("jobName", "-"),
                friend.get("lastMsg", friend.get("lastText", "-")),
            )

        console.print(table)

    handle_command(cred, action=lambda c: c.get_friend_list(), render=_render, as_json=as_json, as_yaml=as_yaml)


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


@click.command("messages")
@click.option("-n", "--count", default=20, type=int, help="显示最近 N 条会话 (默认: 20)")
@structured_output_options
def messages(count: int, as_json: bool, as_yaml: bool) -> None:
    """查看收到的消息列表（所有沟通过的 Boss 及最近一条消息）"""
    cred = require_auth()

    def _action(client):
        friends_data = client.get_geek_friend_list()
        friends = friends_data.get("friendList", [])[:count]
        if not friends:
            return {"friends": [], "messages": []}

        # Batch fetch last messages in chunks of 20
        BATCH = 20
        all_msgs: list[dict] = []
        for i in range(0, len(friends), BATCH):
            batch_ids = [f["friendId"] for f in friends[i:i + BATCH]]
            all_msgs.extend(client.get_geek_last_messages(batch_ids))

        return {"friends": friends, "messages": all_msgs}

    def _render(data: dict) -> None:
        friends = data.get("friends", [])
        msgs = data.get("messages", [])

        if not friends:
            console.print("[yellow]暂无沟通记录[/yellow]")
            return

        # Build boss_id -> msg map; the peer is whichever of fromId/toId is NOT the user's uid
        my_uid = None
        for m in msgs:
            info = m.get("lastMsgInfo", {})
            to_id = info.get("toId")
            from_id = info.get("fromId")
            # uid field is always the current user's uid
            if m.get("uid"):
                my_uid = m["uid"]
                break

        msg_map: dict[int, dict] = {}
        for m in msgs:
            info = m.get("lastMsgInfo", {})
            from_id = info.get("fromId")
            to_id = info.get("toId")
            # peer is the non-self side
            peer_id = to_id if from_id == my_uid else from_id
            if peer_id:
                msg_map[peer_id] = m

        table = Table(title=f"💬 消息列表 ({len(friends)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Boss", style="bold cyan", max_width=10)
        table.add_column("公司", style="green", max_width=18)
        table.add_column("职位", max_width=22)
        table.add_column("时间", style="dim", width=8)
        table.add_column("最近消息", max_width=40)

        for i, friend in enumerate(friends, 1):
            fid = friend["friendId"]
            msg = msg_map.get(fid, {})
            info = msg.get("lastMsgInfo", {})
            last_text = info.get("showText", "-")
            last_time = msg.get("lastTime", "-")
            table.add_row(
                str(i),
                friend.get("name", "-"),
                friend.get("brandName", "-"),
                friend.get("jobName", "-"),
                last_time,
                last_text[:60] + ("…" if len(last_text) > 60 else ""),
            )

        console.print(table)
        console.print(f"\n[dim]提示: 使用 boss history <friendId> 查看完整聊天记录[/dim]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


@click.command("unread")
@click.option("-n", "--count", default=50, type=int, help="检查最近 N 个会话 (默认: 50)")
@structured_output_options
def unread_messages(count: int, as_json: bool, as_yaml: bool) -> None:
    """查看未回复的消息（Boss 发来但你还没回复的会话）"""
    cred = require_auth()

    def _action(client):
        friends_data = client.get_geek_friend_list()
        friends = friends_data.get("friendList", [])[:count]
        if not friends:
            return {"unread": [], "my_uid": None}

        my_info = client.get_user_info()
        my_uid = my_info.get("userId")

        BATCH = 20
        all_msgs: list[dict] = []
        for i in range(0, len(friends), BATCH):
            batch_ids = [f["friendId"] for f in friends[i:i + BATCH]]
            all_msgs.extend(client.get_geek_last_messages(batch_ids))

        # Build peer_id -> msg map
        msg_map: dict[int, dict] = {}
        for m in all_msgs:
            info = m.get("lastMsgInfo", {})
            from_id = info.get("fromId")
            to_id = info.get("toId")
            peer = to_id if from_id == my_uid else from_id
            if peer:
                msg_map[peer] = m

        # Unread = last message is FROM boss (not from me)
        unread = []
        for friend in friends:
            fid = friend["friendId"]
            msg = msg_map.get(fid, {})
            info = msg.get("lastMsgInfo", {})
            from_id = info.get("fromId")
            if from_id and from_id != my_uid:
                unread.append({"friend": friend, "lastMsg": msg})

        return {"unread": unread, "my_uid": my_uid}

    def _render(data: dict) -> None:
        unread = data.get("unread", [])
        if not unread:
            console.print("[green]✅ 没有未回复的消息[/green]")
            return

        table = Table(title=f"📬 未回复消息 ({len(unread)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("friendId", style="dim", width=10)
        table.add_column("Boss", style="bold cyan", max_width=10)
        table.add_column("公司", style="green", max_width=18)
        table.add_column("时间", style="dim", width=8)
        table.add_column("消息", max_width=45)

        for i, item in enumerate(unread, 1):
            friend = item["friend"]
            msg = item["lastMsg"]
            info = msg.get("lastMsgInfo", {})
            text = info.get("showText", "-")
            last_time = msg.get("lastTime", "-")
            table.add_row(
                str(i),
                str(friend["friendId"]),
                friend.get("name", "-"),
                friend.get("brandName", "-"),
                last_time,
                text[:60] + ("…" if len(text) > 60 else ""),
            )

        console.print(table)
        console.print(f"\n[dim]提示: 使用 boss reply <friendId> \"回复内容\" 发送消息[/dim]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


@click.command("reply")
@click.argument("friend_id", type=int)
@click.argument("message")
def geek_reply(friend_id: int, message: str) -> None:
    """向 Boss 发送消息 (需要 friendId，可从 boss messages 获取)

    例: boss reply 605029326 "您好，我对这个职位很感兴趣"
    """
    cred = require_auth()

    try:
        from ..mqtt_chat import BossMQTTChat
    except ImportError as exc:
        console.print(f"[red]❌ {exc}[/red]")
        raise SystemExit(1) from None

    console.print(f"[dim]正在获取认证信息...[/dim]")

    # Step 1: Get all needed info via HTTP
    try:
        friends_data = run_client_action(cred, lambda c: c.get_geek_friend_list())
        friends = friends_data.get("friendList", [])
        friend = next((f for f in friends if f["friendId"] == friend_id), None)
        if not friend:
            console.print(f"[red]❌ 找不到 friendId={friend_id}，请用 boss messages 查看列表[/red]")
            raise SystemExit(1)

        # Get my own info
        my_info = run_client_action(cred, lambda c: c.get_user_info())
        my_uid = my_info.get("userId")
        my_enc_uid = my_info.get("encryptUserId", "")

        # Get MQTT auth tokens
        page_token, wt2 = run_client_action(cred, lambda c: c.get_ws_auth())

    except BossApiError as exc:
        console.print(f"[red]❌ 获取信息失败: {exc}[/red]")
        raise SystemExit(1) from None

    boss_uid = friend["friendId"]
    boss_enc_uid = friend.get("encryptFriendId", "")
    boss_name = friend.get("name", str(boss_uid))
    cookies = dict(cred.cookies)

    console.print(f"[dim]连接 MQTT...[/dim]")

    try:
        with BossMQTTChat(page_token, wt2, cookies=cookies, timeout=12) as chat:
            chat.send(
                from_uid=my_uid,
                from_encrypt_uid=my_enc_uid,
                to_uid=boss_uid,
                to_encrypt_uid=boss_enc_uid,
                text=message,
            )
        console.print(f"[green]✅ 消息已发送给 {boss_name}[/green]")
        console.print(f"  [dim]{message}[/dim]")
    except Exception as exc:
        console.print(f"[red]❌ 发送失败: {exc}[/red]")
        raise SystemExit(1) from None


@click.command("chat-history")
@click.argument("friend_id", type=int)
@click.option("-n", "--count", default=20, type=int, help="获取最近 N 条消息 (默认: 20)")
@structured_output_options
def chat_history(friend_id: int, count: int, as_json: bool, as_yaml: bool) -> None:
    """查看与某个 Boss 的双向聊天记录 (需要 friendId，可从 boss messages 获取)"""
    cred = require_auth()

    def _action(client):
        return client.get_geek_chat_history(boss_id=friend_id, count=count)

    def _render(data: dict) -> None:
        msg_list = data.get("messages", data.get("msgList", []))
        if not msg_list:
            console.print("[yellow]暂无聊天记录（仅显示双向对话记录，如对方发消息但你未回复则为空）[/yellow]")
            return

        my_uid = None
        for m in msg_list:
            if m.get("fromType") == 1:
                my_uid = m.get("fromId")
                break

        console.print(f"\n[bold]聊天记录 (friendId={friend_id})[/bold]\n")
        for m in reversed(msg_list):
            from_id = m.get("fromId")
            content = m.get("body", m.get("content", m.get("showText", "-")))
            ts = m.get("msgTime", 0)
            time_str = datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M") if ts else "-"
            is_me = from_id == my_uid
            prefix = "[bold blue]我[/bold blue]" if is_me else "[bold green]Boss[/bold green]"
            console.print(f"  {time_str}  {prefix}: {content}")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)


def _exchange_command(exchange_type: int, success_msg: str):
    """Factory for exchange commands (send-resume, request-phone, request-wechat)."""
    def _cmd(friend_id: int, as_json: bool, as_yaml: bool) -> None:
        cred = require_auth()

        def _action(client):
            boss_data = client.get_geek_boss_data(friend_id)
            security_id = boss_data.get("securityId", "")
            if not security_id:
                raise BossApiError(f"无法获取 securityId (friendId={friend_id})")
            return client.geek_exchange_request(friend_id, security_id, exchange_type)

        def _render(data: dict) -> None:
            status = data.get("status", -1)
            if status == 0:
                console.print(f"[green]✅ {success_msg}[/green]")
            else:
                console.print(f"[yellow]已发送请求 (status={status})[/yellow]")

        handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)

    return _cmd


@click.command("send-resume")
@click.argument("friend_id", type=int)
@structured_output_options
def send_resume(friend_id: int, as_json: bool, as_yaml: bool) -> None:
    """向 Boss 发送附件简历 (需要 friendId)"""
    _exchange_command(3, "简历已发送")(friend_id, as_json, as_yaml)


@click.command("request-phone")
@click.argument("friend_id", type=int)
@structured_output_options
def request_phone(friend_id: int, as_json: bool, as_yaml: bool) -> None:
    """向 Boss 请求交换手机号 (需要 friendId)"""
    _exchange_command(1, "手机号交换请求已发送")(friend_id, as_json, as_yaml)


@click.command("request-wechat")
@click.argument("friend_id", type=int)
@structured_output_options
def request_wechat(friend_id: int, as_json: bool, as_yaml: bool) -> None:
    """向 Boss 请求交换微信 (需要 friendId)"""
    _exchange_command(2, "微信交换请求已发送")(friend_id, as_json, as_yaml)


@click.command("accept")
@click.argument("friend_id", type=int)
@click.option("--reject", is_flag=True, help="拒绝请求（默认同意）")
@structured_output_options
def accept_exchange(friend_id: int, reject: bool, as_json: bool, as_yaml: bool) -> None:
    """同意（或拒绝）Boss 发来的交换请求（手机/微信/简历）

    例: boss accept 629683122
        boss accept 629683122 --reject
    """
    cred = require_auth()

    def _action(client):
        # 从 userLastMsg 获取最新的 exchange 请求消息
        msgs = client.get_geek_last_messages([friend_id])
        if not msgs:
            raise BossApiError(f"找不到与 friendId={friend_id} 的消息记录")
        info = msgs[0].get("lastMsgInfo", {})
        mid = info.get("msgId")
        text = info.get("showText", "")
        if not mid:
            raise BossApiError("无法获取消息 ID")
        # 检查是否是 exchange 请求
        exchange_keywords = ["是否同意", "交换", "附件简历", "联系方式"]
        if not any(kw in text for kw in exchange_keywords):
            raise BossApiError(f"最新消息不是交换请求: {text[:40]!r}")
        boss_data = client.get_geek_boss_data(friend_id)
        sec = boss_data.get("securityId", "")
        if reject:
            return client.geek_reject_exchange(friend_id, mid, sec)
        else:
            # 微信请求用 acceptItemWeiXinRequest，其他用 acceptItemContact
            if "微信" in text:
                return client.geek_accept_wechat(friend_id, mid, sec)
            return client.geek_accept_exchange(friend_id, mid, sec)

    def _render(data: dict) -> None:
        action = "拒绝" if reject else "同意"
        console.print(f"[green]✅ 已{action}交换请求[/green]")

    handle_command(cred, action=_action, render=_render, as_json=as_json, as_yaml=as_yaml)
