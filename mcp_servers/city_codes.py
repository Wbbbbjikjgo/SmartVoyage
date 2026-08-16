"""City code mappings for external APIs.

高德天气接口要求 ``city`` 参数为 adcode（行政区划编码），而航班接口要求
IATA 城市码 / 机场码。本模块维护「城市名 -> 编码」的静态映射，作为零额外
API 调用的首选解析方式（未知城市可回退到高德地理编码接口动态解析）。
"""

from typing import Optional


# ================================================================
# 城市名 -> 高德 adcode（主要城市，区县级以上行政区划编码）
# ================================================================
CITY_TO_ADCODE: dict = {
    "北京": "110000",
    "上海": "310000",
    "天津": "120000",
    "重庆": "500000",
    "广州": "440100",
    "深圳": "440300",
    "珠海": "440400",
    "汕头": "440500",
    "佛山": "440600",
    "东莞": "441900",
    "成都": "510100",
    "杭州": "330100",
    "宁波": "330200",
    "温州": "330300",
    "嘉兴": "330400",
    "西安": "610100",
    "武汉": "420100",
    "南京": "320100",
    "无锡": "320200",
    "苏州": "320500",
    "南通": "320600",
    "长沙": "430100",
    "青岛": "370200",
    "济南": "370100",
    "烟台": "370600",
    "大连": "210200",
    "沈阳": "210100",
    "厦门": "350200",
    "福州": "350100",
    "昆明": "530100",
    "三亚": "460200",
    "海口": "460100",
    "郑州": "410100",
    "合肥": "340100",
    "哈尔滨": "230100",
    "长春": "220100",
    "石家庄": "130100",
    "太原": "140100",
    "兰州": "620100",
    "银川": "640100",
    "西宁": "630100",
    "乌鲁木齐": "650100",
    "拉萨": "540100",
    "贵阳": "520100",
    "南宁": "450100",
    "桂林": "450300",
    "呼和浩特": "150100",
    "南昌": "360100",
    "徐州": "320300",
    "常州": "320400",
    "扬州": "321000",
    "泉州": "350500",
    "洛阳": "410300",
}

# ================================================================
# 城市名 -> IATA 城市码（航班查询接口使用）
# ================================================================
CITY_TO_IATA: dict = {
    "北京": "BJS",
    "上海": "SHA",
    "广州": "CAN",
    "深圳": "SZX",
    "成都": "CTU",
    "杭州": "HGH",
    "西安": "XIY",
    "重庆": "CKG",
    "武汉": "WUH",
    "南京": "NKG",
    "天津": "TSN",
    "长沙": "CSX",
    "青岛": "TAO",
    "大连": "DLC",
    "厦门": "XMN",
    "昆明": "KMG",
    "三亚": "SYX",
    "海口": "HAK",
    "苏州": "SZV",
    "无锡": "WUX",
    "郑州": "CGO",
    "合肥": "HFE",
    "福州": "FOC",
    "哈尔滨": "HRB",
    "沈阳": "SHE",
    "济南": "TNA",
    "石家庄": "SJW",
    "太原": "TYN",
    "兰州": "LHW",
    "银川": "INC",
    "西宁": "XNN",
    "乌鲁木齐": "URC",
    "拉萨": "LXA",
    "贵阳": "KWE",
    "南宁": "NNG",
    "呼和浩特": "HET",
    "南昌": "KHN",
    "长春": "CGQ",
    "桂林": "KWL",
    "温州": "WNZ",
    "宁波": "NGB",
    "珠海": "ZUH",
    "汕头": "SWA",
    "烟台": "YNT",
    "徐州": "XUZ",
    "常州": "CZX",
    "南通": "NTG",
}

# 反向映射：IATA 城市码 -> 城市名
IATA_TO_CITY: dict = {v: k for k, v in CITY_TO_IATA.items()}


def _normalize_city(city: str) -> str:
    """Normalize a city name by stripping common administrative suffixes.

    Examples:
        "北京市" -> "北京", "三亚市" -> "三亚"
    """
    city = city.strip()
    for suffix in ("特别行政区", "自治区", "自治州", "地区", "市", "省", "县"):
        if city.endswith(suffix) and len(city) > len(suffix):
            city = city[: -len(suffix)]
            break
    return city


def _lookup(table: dict, city: str) -> Optional[str]:
    """Resolve a (possibly decorated) city name against a mapping table.

    Tries, in order: exact match, suffix-normalized match, then longest
    known-city substring (handles "四川省成都市" -> "成都").
    """
    city = city.strip()
    if not city:
        return None

    if city in table:
        return table[city]

    normalized = _normalize_city(city)
    if normalized in table:
        return table[normalized]

    best = None
    for name in table:
        if name in city and (best is None or len(name) > len(best)):
            best = name
    return table.get(best) if best else None


def city_to_adcode(city: str) -> Optional[str]:
    """Resolve a city name to its AMap adcode.

    Args:
        city: City name (e.g. "北京" or "北京市").

    Returns:
        adcode string or ``None`` if unknown.
    """
    return _lookup(CITY_TO_ADCODE, city)


def city_to_iata(city: str) -> Optional[str]:
    """Resolve a city name to its IATA city code.

    Args:
        city: City name (e.g. "北京").

    Returns:
        IATA code (e.g. "BJS") or ``None`` if unknown.
    """
    return _lookup(CITY_TO_IATA, city)


def iata_to_city(code: str) -> Optional[str]:
    """Resolve an IATA city code back to a city name."""
    return IATA_TO_CITY.get(code.upper() if code else "")
