"""三级机构分组（业务字典）。

源头：项目 src/shared/config/org-groups.ts:9-12
独立维护副本以保持 skill 自包含。两边变更需手动同步。
"""
from __future__ import annotations

SAME_CITY: tuple[str, ...] = ("天府", "高新", "新都", "青羊", "武侯", "重客", "本部")
REMOTE: tuple[str, ...]    = ("宜宾", "德阳", "资阳", "泸州", "自贡", "乐山", "达州")

GROUP_KEYS = ("same-city", "remote", "other")
GROUP_LABELS = {
    "same-city": "同城",
    "remote":    "异地",
    "other":     "其他",
}


def classify_org(org: str) -> str:
    if org in SAME_CITY:
        return "same-city"
    if org in REMOTE:
        return "remote"
    return "other"
