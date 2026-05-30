"""推送薄壳：调用 chexian-im-push skill 的 send-*-html.sh 工具。

依赖：
  - chexian-im-push skill 已安装（~/.claude/skills/chexian-im-push/tools/）
    命名记录：v2.1 之前是 xcl-ppt2im，2026-05-18 P3.2 治理改名
  - chexian-api 后端在线（HTML 链接出口前置）
  - lark-cli / wecom-cli 已 auth
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

IM_PUSH_TOOLS = Path.home() / ".claude/skills/chexian-im-push/tools"
SEND_LARK = IM_PUSH_TOOLS / "send-lark-html.sh"
SEND_WECOM = IM_PUSH_TOOLS / "send-wecom-html.sh"

DEFAULT_BASE_URL = "https://chexian.cretvalu.com"


def push_to_im(html_path: Path | str,
               title: str,
               channels: Iterable[str] = ("lark", "wecom"),
               base_url: str = DEFAULT_BASE_URL,
               sync_vps: bool = True) -> dict:
    """推送 HTML 到指定 IM 出口，返回每个渠道的执行结果。

    Args:
      html_path: 本地 HTML 文件路径
      title: 报告标题（推送时显示）
      channels: 子集 of {"lark", "wecom"}
      base_url: HTML 公网 base（默认生产域名）
      sync_vps: 是否在推送后 rsync server/data/reports/ 到 VPS

    Returns:
      {"lark": {"ok": True, "stdout": "..."}, "wecom": {...}, "vps_sync": {...}}
    """
    html_path = Path(html_path)
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML 不存在：{html_path}")

    env = os.environ.copy()
    env["PUBLIC_BASE_URL"] = base_url

    results: dict = {}

    if "lark" in channels:
        if not SEND_LARK.is_file():
            results["lark"] = {"ok": False, "error": f"找不到 {SEND_LARK}"}
        else:
            r = subprocess.run(
                ["bash", str(SEND_LARK), str(html_path), title],
                env=env, capture_output=True, text=True,
            )
            results["lark"] = {
                "ok": r.returncode == 0,
                "exit": r.returncode,
                "stdout": r.stdout[-2000:],
                "stderr": r.stderr[-500:],
            }

    if "wecom" in channels:
        if not SEND_WECOM.is_file():
            results["wecom"] = {"ok": False, "error": f"找不到 {SEND_WECOM}"}
        else:
            r = subprocess.run(
                ["bash", str(SEND_WECOM), str(html_path), title],
                env=env, capture_output=True, text=True,
            )
            results["wecom"] = {
                "ok": r.returncode == 0,
                "exit": r.returncode,
                "stdout": r.stdout[-2000:],
                "stderr": r.stderr[-500:],
            }

    if sync_vps and base_url == DEFAULT_BASE_URL:
        ssh_key = Path.home() / ".ssh/chexian_deploy"
        local_reports = Path("/Users/alongor666/Downloads/底层数据湖DUD/chexian-api/server/data/reports")
        if shutil.which("rsync") and ssh_key.is_file() and local_reports.is_dir():
            r = subprocess.run([
                "rsync", "-az", "--exclude", ".DS_Store",
                "-e", f"ssh -i {ssh_key}",
                f"{local_reports}/",
                "deployer@162.14.113.44:/var/www/chexian/server/data/reports/",
            ], capture_output=True, text=True)
            results["vps_sync"] = {
                "ok": r.returncode == 0,
                "exit": r.returncode,
                "stderr": r.stderr[-500:],
            }
        else:
            results["vps_sync"] = {"ok": False, "error": "rsync 或 SSH key 缺失，跳过"}

    return results
