"""数字格式化与中文名简化工具。

精度约定：
  - 绝对值（保费、赔款、件均、案均、保单数）一律取整，无小数
  - 率值（赔付率、出险率、费用率、变动成本率）保留 1 位小数

简称约定（v1.6 起，地区取最细一级）：
  - 经代：去 10 位编码 + 切品牌/地区段 + 删公司类型 + 应用品牌映射 + 拼「品牌-最细地区」
  - 业务员：去 8-12 位编码前缀，留中文名
"""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd


# ============== 数字格式化 ==============

def fmt_num(val: Optional[float], kind: str) -> str:
    """统一格式化入口。kind ∈ {wan, int, money0, pct, coef, raw}"""
    if val is None or pd.isna(val):
        return "—"
    if kind == "wan":
        return f"{round(val / 10000):,}"
    if kind == "int":
        return f"{int(val):,}"
    if kind == "money0":
        return f"{int(val):,}"
    if kind == "pct":
        return f"{val:.1f}%"
    if kind == "coef":
        return f"{val:.3f}"
    return str(val)


def fmt_wan(v: Optional[float]) -> str:
    return fmt_num(v, "wan")


def fmt_pct(v: Optional[float]) -> str:
    return fmt_num(v, "pct")


def fmt_int(v: Optional[float]) -> str:
    return fmt_num(v, "int")


# ============== 中文名简化 ==============

_AGENT_CODE_RE = re.compile(r"^\d{10}")
_SALESMAN_CODE_RE = re.compile(r"^\d{8,12}")

# 公司类型（用 search 找位置，不带 $ 锚定）
# 业务类型词放最前，按从长到短，避免「保险销售」吃掉「保险销售服务」
_COMPANY_TYPE_RE = re.compile(
    r"(?:保险销售服务|保险销售|保险代理|保险经纪|保险公估|"
    r"汽车销售服务|汽车服务销售|汽车销售|资产管理|金融租赁|商务服务)?"
    r"(?:股份)?(?:集团)?(?:有限责任|责任)?"
    r"有限公司"
)

# 品牌段后处理：删括号内容 + 删残留业务类型词（公司名「XX保险经纪（北京）有限公司」
# 因括号阻断 _COMPANY_TYPE_RE 整体匹配，会把「保险经纪（北京）」留在品牌段，需后处理）
_PAREN_RE = re.compile(r"[（(][^（()）]*[）)]")
_BUSINESS_TYPE_RE = re.compile(
    r"(?:保险销售服务|保险销售|保险代理|保险经纪|保险公估|"
    r"汽车销售服务|汽车服务销售|汽车销售|资产管理|金融租赁|商务服务)"
)

# 没有「有限公司」时的兜底切分点
_FALLBACK_SPLIT_RE = re.compile(r"(?:银行|信用社|信用合作社|储蓄所)")

# 分支机构后缀（含序号变体；从复杂到简单）
_BRANCH_SUFFIX_RE = re.compile(
    r"(?:第[一二三四五六七八九十百千\d]+)?"
    r"(?:省分公司|市分公司|分公司|分行|支行|分理处|分中心|经办处|"
    r"营业部|营业所|营业网点|营业网|营业中心|网点|代理点|代理处|"
    r"工作站|服务部|办事处|店|门店)$"
)

# 地区识别四级（从细到粗依次尝试）
_REGION_LEVELS = [
    re.compile(r"([一-龥]{2,5}(?:路|街|大道|巷|弄|里|大街))$"),         # 街道路名（最细）
    re.compile(r"([一-龥]{2,5}?(?:区|县|旗|新区|开发区|高新区|经开区))$"),
    re.compile(r"([一-龥]{2,4}?(?:市|州|盟|地区))$"),
    re.compile(r"([一-龥]{1,4}(?:省|自治区|特别行政区))$"),               # 省级（最粗，去后缀）
]

# 前缀地名（品牌段开头出现，删之）
_PREFIX_REGION_RE = re.compile(r"^[一-龥]{1,4}(?:省|市|自治区)")

# 已知城市前缀（用于「品牌名以某城市开头但无『市』字」的场景，如「成都曙光汽车销售」）
# 命中时该城市名转作 region，品牌段剥之
_KNOWN_CITY_PREFIX_RE = re.compile(
    r"^(成都|绵阳|德阳|乐山|宜宾|南充|泸州|达州|内江|遂宁|资阳|眉山|攀枝花|自贡|广元|"
    r"北京|上海|天津|重庆|"
    r"广州|深圳|珠海|佛山|东莞|中山|惠州|"
    r"南京|苏州|无锡|常州|徐州|南通|"
    r"杭州|宁波|温州|嘉兴|绍兴|金华|"
    r"武汉|长沙|郑州|济南|青岛|烟台|"
    r"西安|兰州|乌鲁木齐|银川|西宁|"
    r"沈阳|大连|长春|哈尔滨|鞍山|"
    r"福州|厦门|泉州|南昌|合肥|"
    r"昆明|贵阳|海口|三亚|拉萨|呼和浩特|包头|南宁|柳州|桂林|"
    r"石家庄|太原|唐山|秦皇岛"
    r")"
)

# 品牌核心简称映射（业内通用缩写优先）
_BRAND_MAP = {
    "中国邮政集团":           "邮政",
    "中国邮政":               "邮政",
    "中国邮政储蓄银行":       "邮储",
    "中国农业银行":           "农行",
    "中国工商银行":           "工行",
    "中国建设银行":           "建行",
    "中国银行":               "中行",
    "交通银行":               "交行",
    "招商银行":               "招行",
    "中信银行":               "中信",
    "平安银行":               "平安",
    "浦发银行":               "浦发",
    "兴业银行":               "兴业",
    "光大银行":               "光大",
    "民生银行":               "民生",
    "华夏银行":               "华夏",
    "广发银行":               "广发",
    "上海银行":               "上海",
    "北京银行":               "北京",
    "中国人寿":               "国寿",
    "中国太平":               "太平",
    "中国太平洋保险":         "太保",
    "中国平安":               "平安",
    "中国人民财产保险":       "人保财",
    "中国人民人寿保险":       "人保寿",
}

# 个人代理人判定
_PERSON_INDICATORS = re.compile(
    r"公司|银行|集团|代理|经纪|分行|支行|社|店|商行|营业部|网点|办事处"
)


# 各级地区识别：用 (?=(...)) lookahead 让 finditer 在每个位置都试，不消耗字符
# 这样能拿到所有重叠候选，再按"起点最大 + 满足最小长度"取最末段
_LEVEL_PATTERNS = [
    # (lookahead_pat, min_len, strip_admin_suffix, level_name)
    (re.compile(r"(?=([一-龥]{2,4}(?:路|街|大道|巷|弄|里|大街|胡同)))"), 3, False, "街道"),
    (re.compile(r"(?=([一-龥]{1,3}(?:区|县|旗|新区|开发区|高新区|经开区)))"), 3, False, "区县"),
    (re.compile(r"(?=([一-龥]{1,3}(?:市|州|盟|地区)))"), 2, True, "市州"),
    (re.compile(r"(?=([一-龥]{1,3}(?:省|自治区|特别行政区)))"), 2, True, "省级"),
]


_BOUNDARY_CHARS = set("区县市省盟州旗")


def _extract_region(s: str) -> str:
    """从公司类型之后的字符串中抽最细一级地区。

    算法：
      1. 剥末尾分支后缀
      2. 从最细级（街道）开始尝试，每级用 lookahead finditer 收集所有占据末尾的候选
      3. 优先取「起点是字符串开头 或 前一字符是行政分隔符（区/县/市/省/盟/州/旗）」的候选
         的起点最大者（最末段，确保完整地名）
      4. 若无满足边界的候选，兜底取最短的（避免吞前面非边界中文）
    """
    s = _BRANCH_SUFFIX_RE.sub("", s).strip()
    if not s:
        return ""

    n = len(s)
    for pat, min_len, strip_admin, _ in _LEVEL_PATTERNS:
        candidates = []
        for m in pat.finditer(s):
            content = m.group(1)
            if m.start() + len(content) == n and len(content) >= min_len:
                candidates.append((m.start(), content))
        if not candidates:
            continue

        # 优先：起点是 0 或前一字符是行政分隔符
        bounded = [
            c for c in candidates
            if c[0] == 0 or s[c[0] - 1] in _BOUNDARY_CHARS
        ]
        if bounded:
            # 起点最大 = 最末段（如 "成都武侯区" 取 "佳灵路" 而非 "区佳灵路"）
            _, region = max(bounded, key=lambda x: x[0])
        else:
            # 兜底：取最短候选（如 "成都武侯区" 既无街道边界又非开头，取最短"武侯区"）
            _, region = min(candidates, key=lambda x: len(x[1]))

        if strip_admin:
            region = re.sub(r"(?:省|市|州|盟|地区|自治区|特别行政区)$", "", region)
        return region

    return s.strip()


def short_agent_name(name: Optional[str]) -> str:
    """经代简称：「品牌-最细一级地区」结构。

    地区粒度：街道路名 > 区/县 > 市 > 省（取最细那一级）。

    例：
      "0110105059中国邮政集团有限公司四川省分公司"               → "邮政-四川"
      "0110104907四川省永成保险代理有限公司简阳分公司"           → "永成-简阳"
      "0110104388中国农业银行股份有限公司成都分行"               → "农行-成都"
      "0110100xxx泰源保险代理有限公司成都武侯区佳灵路第二营业部" → "泰源-佳灵路"
      "0110102561宋红浪"                                          → "宋红浪"
    """
    if not name:
        return ""

    s = _AGENT_CODE_RE.sub("", name).strip()
    if not s:
        return name

    # 个人代理人
    if len(s) <= 8 and not _PERSON_INDICATORS.search(s):
        return s

    # 切分品牌段 / 地区段
    m = _COMPANY_TYPE_RE.search(s)
    if m:
        brand_raw = s[: m.start()]
        region_raw = s[m.end():]
    else:
        m2 = _FALLBACK_SPLIT_RE.search(s)
        if m2:
            brand_raw = s[: m2.end()]
            region_raw = s[m2.end():]
        else:
            return s

    # 品牌段处理
    brand = _PAREN_RE.sub("", brand_raw)             # 删括号内容
    brand = _BUSINESS_TYPE_RE.sub("", brand)          # 删残留业务类型词

    # 识别开头城市作 fallback 地区（如「成都曙光」→ city=成都, brand=曙光）
    fallback_region = ""
    m_city = _KNOWN_CITY_PREFIX_RE.match(brand)
    if m_city:
        fallback_region = m_city.group(1)
        brand = brand[m_city.end():].strip()
    else:
        brand = _PREFIX_REGION_RE.sub("", brand).strip()  # 否则删「四川省」「成都市」类前缀

    if brand in _BRAND_MAP:
        brand = _BRAND_MAP[brand]
    if not brand:
        brand = brand_raw  # 兜底

    # 地区段处理（region_raw 提取优先，无则用 fallback_region）
    region = _extract_region(region_raw) or fallback_region

    return f"{brand}-{region}" if region else brand


def short_salesman_name(name: Optional[str]) -> str:
    """业务员去编码：留中文名。

    例：
      "210011913曾玲" → "曾玲"
      "110030687黎蓓" → "黎蓓"
    """
    if not name:
        return ""
    s = _SALESMAN_CODE_RE.sub("", name).strip()
    return s or name


def short_team_name(name: Optional[str]) -> str:
    """销售团队简称（v1.18 新增）。

    规则：
      1. 全名中删除"业务"二字
      2. 若末尾仍是"团队"，再删之

    例：
      "蒲江业务团队"   → "蒲江"
      "成华业务团队"   → "成华"
      "都江堰业务团队" → "都江堰"
      "天府业务一部"   → "天府一部"
      "天府业务二部"   → "天府二部"
      "未归属"         → "未归属"  （无变化）
      "未分配"         → "未分配"  （无变化）
      "天府团队"       → "天府"
    """
    if not name:
        return ""
    s = name.replace("业务", "")
    if s.endswith("团队"):
        s = s[: -len("团队")]
    return s.strip() or name
