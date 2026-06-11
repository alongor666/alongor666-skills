"""数据湖根路径 — 单一事实源（SSOT）。

默认指向本机数据湖（chexian-api 仓库根）；非本机环境（云端会话、他人机器、CI）
用环境变量 `CHEXIAN_DATA_ROOT` 覆盖为同构目录，业务代码一律从这里派生子路径，
不得再写死绝对路径（与 ADR-001 消灭硬编码安装位同一精神）。
"""
import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get(
    "CHEXIAN_DATA_ROOT",
    "/Users/alongor666/Downloads/底层数据湖DUD/chexian-api",
))
