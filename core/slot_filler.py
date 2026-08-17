"""
槽位填充模块：从用户输入中提取结构化信息
例如：从 "我想从北京去上海玩3天" 中提取出 {departure: "北京", destination: "上海", duration: 3}
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
import re

# 获取当前模块的日志记录器，用于记录调试/错误信息
logger = logging.getLogger(__name__)


# ================================================================
# 国内地级行政区名称列表（用于从文本中识别城市/目的地）
# ================================================================

# 直辖市、省会、计划单列市及各地级市（按省分组，覆盖绝大多数常见出行目的地）
_CITIES = (
    "北京", "上海", "天津", "重庆",
    # 河北
    "石家庄", "唐山", "秦皇岛", "邯郸", "邢台", "保定", "张家口", "承德",
    "沧州", "廊坊", "衡水",
    # 山西
    "太原", "大同", "阳泉", "长治", "晋城", "朔州", "晋中", "运城", "忻州",
    "临汾", "吕梁",
    # 内蒙古
    "呼和浩特", "包头", "乌海", "赤峰", "通辽", "鄂尔多斯", "呼伦贝尔",
    "巴彦淖尔", "乌兰察布",
    # 辽宁
    "沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新",
    "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛",
    # 吉林
    "长春", "吉林", "四平", "辽源", "通化", "白山", "松原", "白城", "延边",
    # 黑龙江
    "哈尔滨", "齐齐哈尔", "鸡西", "鹤岗", "双鸭山", "大庆", "伊春", "佳木斯",
    "七台河", "牡丹江", "黑河", "绥化",
    # 江苏
    "南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港", "淮安", "盐城",
    "扬州", "镇江", "泰州", "宿迁",
    # 浙江
    "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山",
    "台州", "丽水",
    # 安徽
    "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山",
    "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城",
    # 福建
    "福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德",
    # 江西
    "南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春",
    "抚州", "上饶",
    # 山东
    "济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安",
    "威海", "日照", "临沂", "德州", "聊城", "滨州", "菏泽",
    # 河南
    "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳",
    "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店",
    # 湖北
    "武汉", "黄石", "十堰", "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州",
    "黄冈", "咸宁", "随州", "恩施",
    # 湖南
    "长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳",
    "郴州", "永州", "怀化", "娄底",
    # 广东
    "广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名",
    "肇庆", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山",
    "潮州", "揭阳", "云浮",
    # 广西
    "南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林",
    "百色", "贺州", "河池", "来宾", "崇左",
    # 海南
    "海口", "三亚", "儋州",
    # 四川
    "成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江",
    "乐山", "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳",
    # 贵州
    "贵阳", "六盘水", "遵义", "安顺", "毕节", "铜仁",
    # 云南
    "昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "大理",
    "楚雄", "红河", "文山",
    # 西藏
    "拉萨", "日喀则", "昌都", "林芝", "山南", "那曲",
    # 陕西
    "西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康",
    "商洛",
    # 甘肃
    "兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉",
    "庆阳", "定西", "陇南", "临夏", "甘南",
    # 青海
    "西宁", "海东",
    # 宁夏
    "银川", "石嘴山", "吴忠", "固原", "中卫",
    # 新疆
    "乌鲁木齐", "克拉玛依", "吐鲁番", "哈密", "昌吉", "喀什", "和田", "伊犁",
    "塔城", "阿勒泰",
)

# 常见旅行/服务关键词，用于「X的酒店」「X天气」这类无介词结构的城市识别
_TRAVEL_KEYWORDS = (
    "酒店", "宾馆", "住宿", "天气", "气温", "天气预报", "机票", "航班",
    "高铁", "动车", "火车", "火车票", "车票", "旅游", "旅行", "攻略",
    "三日游", "二日游", "一日游",
)


def _strip_city_suffix(name: str) -> str:
    """去掉城市名后常见的行政区划后缀（市/省/县/区/州等）。"""
    for suffix in ("自治州", "自治县", "地区", "市", "省", "县", "区", "州"):
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[: -len(suffix)]
            break
    return name


# ================================================================
# 1. 槽位填充类 (SlotFiller)
# ================================================================

class SlotFiller:
    """
    槽位填充器：从用户输入中提取结构化信息
    槽位（Slot）是指一个预定义的"空位"，需要从用户的话里提取出来填上
    例如：目的地、日期、人数、预算等
    """

    def __init__(self):
        """初始化槽位填充器（目前无需特殊初始化，保留用于未来扩展）"""
        pass

    # ================================================================
    # 主入口方法
    # ================================================================

    def fill_slots(self, user_input: str, initial_slots: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        从用户输入中填充槽位（提取结构化信息）

        Args:
            user_input: 用户的自然语言输入（如："我想从北京去上海玩3天"）
            initial_slots: 意图识别阶段已经提取的初始槽位（可选）

        Returns:
            填充后的槽位字典（如：{"destination": "上海", "duration": 3, ...}）
        """
        # 1. 如果有初始槽位则复制一份，否则创建空字典
        slots = initial_slots.copy() if initial_slots else {}

        # ================================================================
        # 第一步：规范化日期（把"明天"、"8月15日"转为标准日期格式）
        # ================================================================
        # 遍历所有可能是日期类型的槽位
        for key in ("date", "check_in", "check_out", "start_date"):
            # 如果该槽位存在且值是字符串类型
            if key in slots and isinstance(slots[key], str):
                # 调用规范化方法，把中文日期转为 "YYYY-MM-DD" 格式
                normalized = self._normalize_date_text(slots[key])
                if normalized:
                    # 替换原来的值为规范化后的日期
                    slots[key] = normalized

        # ================================================================
        # 第二步：提取出发城市（用于后续排除目的地时使用）
        # ================================================================
        # 如果用户没有提供出发城市
        if "departure" not in slots:
            # 尝试从文本中提取出发城市（如 "从北京出发" → "北京"）
            departure = self._extract_departure(user_input)
            if departure:
                slots["departure"] = departure

        # ================================================================
        # 第三步：提取目的地城市（排除出发城市，避免混淆）
        # ================================================================
        if "destination" not in slots:
            # 提取城市，传入 exclude 参数排除出发城市
            # 例如："从北京到上海" → 提取"上海"而不是"北京"
            destination = self._extract_city(user_input, exclude=slots.get("departure"))
            if destination:
                slots["destination"] = destination

        # ================================================================
        # 第四步：提取日期
        # ================================================================
        if "date" not in slots:
            # 尝试从文本中提取日期（"明天" → "2024-08-17"）
            date_str = self._extract_date(user_input)
            if date_str:
                slots["date"] = date_str

        # ================================================================
        # 第五步：提取持续天数
        # ================================================================
        if "duration" not in slots:
            # 尝试从文本中提取天数（"3天" → 3）
            duration = self._extract_duration(user_input)
            if duration:
                slots["duration"] = duration

        # ================================================================
        # 第六步：提取预算
        # ================================================================
        if "budget" not in slots:
            # 尝试从文本中提取预算（"5000元" → 5000.0）
            budget = self._extract_budget(user_input)
            if budget:
                slots["budget"] = budget

        # ================================================================
        # 第七步：提取人数
        # ================================================================
        if "guests" not in slots:
            # 尝试从文本中提取人数（"两个人" → 2）
            guests = self._extract_guests(user_input)
            if guests:
                slots["guests"] = guests

        # ================================================================
        # 第八步：判断是否仅需高铁（用于火车票查询）
        # ================================================================
        if "is_high_speed" not in slots:
            if any(kw in user_input for kw in ("高铁", "动车", "城际")):
                slots["is_high_speed"] = 1

        # 返回填充好的槽位字典
        return slots

    # ================================================================
    # 辅助方法：日期规范化
    # ================================================================

    def _normalize_date_text(self, text: str) -> Optional[str]:
        """
        将中文日期表达转为 ISO 标准日期格式

        输入示例：
            "今天" → "2024-08-16"
            "明天" → "2024-08-17"
            "8月15日" → "2024-08-15"
            "2026年8月15日" → "2026-08-15"

        返回：
            标准日期字符串 "YYYY-MM-DD"，如果无法解析则返回 None
        """
        # 获取今天的日期
        today = date.today()
        # 去除首尾空格
        text = text.strip()

        # -------- 处理相对日期 --------
        if text == "今天":
            return today.isoformat()  # isoformat() 返回 "2024-08-16"
        if text == "明天":
            return (today + timedelta(days=1)).isoformat()
        if text == "后天":
            return (today + timedelta(days=2)).isoformat()

        # -------- 已经是 ISO 格式 --------
        # 正则匹配：4位数字-2位数字-2位数字
        if re.match(r"\d{4}-\d{2}-\d{2}", text):
            return text

        # -------- 处理中文日期格式 --------
        # 匹配：2026年8月15日 或 8月15日 或 8月15号
        # (\d{4})年? → 年份可选（4位数字）
        # (\d{1,2})月 → 月份（1-2位数字）
        # (\d{1,2})[日号] → 日期（1-2位数字）
        match = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]", text)
        if match:
            # 如果有年份则使用，否则使用今年
            year = int(match.group(1)) if match.group(1) else today.year
            month = int(match.group(2))
            day = int(match.group(3))
            try:
                target = date(year, month, day)
                # 如果没写年份且日期已经过了今年，说明是明年的日期
                # 例如：12月25日（今天是8月，12月还没到，用今年）
                #       但如果是 1月1日（已经过了），则用明年
                if not match.group(1) and target < today:
                    target = date(year + 1, month, day)
                return target.isoformat()
            except ValueError:
                # 日期非法（如 2月30日）则返回 None
                return None
        return None

    # ================================================================
    # 辅助方法：提取城市
    # ================================================================

    def _extract_city(self, text: str, exclude: Optional[str] = None) -> Optional[str]:
        """
        从文本中提取城市名，可选择排除某个城市

        输入示例：
            "从上海到北京" → "北京"
            "我想去成都" → "成都"
            "洛阳的酒店搜搜" → "洛阳"
            "北京天气怎么样" → "北京"

        提取策略（按优先级）：
            1. 「到/去/往 + 城市」结构（不依赖白名单，兼容小城市）
            2. 「城市 + 的 + 旅行关键词」结构（如"洛阳的酒店"）
            3. 白名单兜底（覆盖全国地级市）

        Args:
            text: 用户输入文本
            exclude: 要排除的城市（如出发城市，防止和目的地混淆）

        Returns:
            提取到的城市名，如果没有则返回 None
        """
        # -------- 1. 结构模式：到/去/往 + 城市（目的地） --------
        # 例如："从上海到北京" → "北京"
        for prep in ("到", "去", "往"):
            match = re.search(
                f"{prep}([\\u4e00-\\u9fa5]{{2,4}}?)"
                f"(?:的|玩|市|省|县|区|州|$|[\\s，。！？、])",
                text,
            )
            if match:
                city = _strip_city_suffix(match.group(1))
                if city != exclude and city not in _TRAVEL_KEYWORDS:
                    return city

        # -------- 2. 结构模式：X 的 旅行关键词 --------
        # 例如："洛阳的酒店" → "洛阳"
        kw = "|".join(_TRAVEL_KEYWORDS)
        match = re.search(f"([\\u4e00-\\u9fa5]{{2,4}}?)的(?:{kw})", text)
        if match:
            city = _strip_city_suffix(match.group(1))
            if city != exclude:
                return city

        # -------- 3. 白名单兜底 --------
        # 按文本中出现的位置排序，取最靠前的
        # 如果排除了出发城市，且有多个城市，取最后一个（通常是目的地）
        candidates = [(text.find(c), c) for c in _CITIES if c in text and c != exclude]
        if candidates:
            candidates.sort(key=lambda x: x[0])
            if len(candidates) > 1 and exclude:
                return candidates[-1][1]
            return candidates[0][1]

        return None

    # ================================================================
    # 辅助方法：提取出发城市
    # ================================================================

    def _extract_departure(self, text: str) -> Optional[str]:
        """
        从文本中提取出发城市

        输入示例：
            "从北京出发" → "北京"
            "从上海到北京" → "上海"
            "从商丘到洛阳" → "商丘"

        Returns:
            提取到的出发城市，如果没有则返回 None
        """
        # -------- 匹配出发模式 --------
        # "从X出发" 或 "从X到" 或 "从X去" 或 "从X前往"
        departure_patterns = [
            r"从(.+?)出发",  # 从...出发
            r"从(.+?)前往",  # 从...前往
            r"从(.+?)到",    # 从...到
            r"从(.+?)去",    # 从...去
        ]

        for pattern in departure_patterns:
            match = re.search(pattern, text)
            if match:
                # 去掉「市/省」等后缀，并限制长度（城市名通常 2-4 字）
                city = _strip_city_suffix(match.group(1).strip())
                if city and len(city) <= 4:
                    return city

        return None

    # ================================================================
    # 辅助方法：提取日期
    # ================================================================

    def _extract_date(self, text: str) -> Optional[str]:
        """
        从文本中提取日期

        输入示例：
            "明天" → "2024-08-17"
            "2024-08-15" → "2024-08-15"
            "8月15日" → "2024-08-15"
            "下周一" → "2024-08-19"
            "3天后" → "2024-08-19"

        Returns:
            标准日期字符串 "YYYY-MM-DD"，如果没有则返回 None
        """
        # -------- 匹配显式日期格式（YYYY-MM-DD / YYYY/MM/DD）-------
        # 正则：4位数字 分隔符（-/） 1-2位数字 分隔符 1-2位数字
        date_pattern = r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
        match = re.search(date_pattern, text)
        if match:
            year, month, day = match.groups()
            # 格式化为 YYYY-MM-DD（月份和日期补零到2位）
            return f"{year}-{int(month):02d}-{int(day):02d}"

        # -------- 尝试相对日期（通过规范化方法）-------
        # 调用之前定义的规范化方法，处理"今天"、"明天"等
        normalized = self._normalize_date_text(text)
        if normalized:
            return normalized

        # -------- 处理"下周X"模式 --------
        # 工作日映射：中文星期几 → 数字（0=周一, 6=周日）
        today = date.today()
        weekday_map = {
            "一": 0, "二": 1, "三": 2, "四": 3,
            "五": 4, "六": 5, "日": 6, "天": 6,
        }
        for day_name, day_num in weekday_map.items():
            if f"下周{day_name}" in text:
                # 计算距离下周一还有几天
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7  # 再加7天，确保是下周
                return (today + timedelta(days=days_ahead)).isoformat()

        # -------- 处理"X天后"模式 --------
        # 正则：数字 + 天后（如 "3天后"）
        days_pattern = r"(\d+)\s*天后"
        match = re.search(days_pattern, text)
        if match:
            days = int(match.group(1))
            return (today + timedelta(days=days)).isoformat()

        # 无法解析
        return None

    # ================================================================
    # 辅助方法：提取持续天数
    # ================================================================

    def _extract_duration(self, text: str) -> Optional[int]:
        """
        从文本中提取持续天数

        输入示例：
            "3天" → 3
            "一周" → 7
            "半个月" → 15

        Returns:
            天数（整数），如果没有则返回 None
        """
        # -------- 匹配"X天" / "X日" --------
        duration_pattern = r"(\d+)\s*[天日]"  # 数字 + 天/日
        match = re.search(duration_pattern, text)
        if match:
            return int(match.group(1))

        # -------- 匹配"一周" / "一个星期" --------
        if "一周" in text or "一个星期" in text:
            return 7

        # -------- 匹配"半个月" --------
        if "半个月" in text:
            return 15

        return None

    # ================================================================
    # 辅助方法：提取预算
    # ================================================================

    def _extract_budget(self, text: str) -> Optional[float]:
        """
        从文本中提取预算金额

        输入示例：
            "5000元" → 5000.0
            "预算3000" → 3000.0
            "2千" → 2000.0
            "1万" → 10000.0

        Returns:
            预算金额（浮点数），如果没有则返回 None
        """
        # -------- 匹配"X元" / "X块" --------
        budget_pattern = r"(\d+)\s*[元块]"
        match = re.search(budget_pattern, text)
        if match:
            return float(match.group(1))

        # -------- 匹配"预算X" --------
        budget_pattern2 = r"预算\s*(\d+)"
        match = re.search(budget_pattern2, text)
        if match:
            return float(match.group(1))

        # -------- 匹配"X千"（如 "2千" → 2000）-------
        thousand_pattern = r"(\d+)\s*千"
        match = re.search(thousand_pattern, text)
        if match:
            return float(match.group(1)) * 1000

        # -------- 匹配"X万"（如 "1万" → 10000）-------
        ten_thousand_pattern = r"(\d+)\s*万"
        match = re.search(ten_thousand_pattern, text)
        if match:
            return float(match.group(1)) * 10000

        return None

    # ================================================================
    # 辅助方法：提取人数
    # ================================================================

    def _extract_guests(self, text: str) -> Optional[int]:
        """
        从文本中提取出行人数

        输入示例：
            "3人" → 3
            "两个人" → 2
            "三人" → 3

        Returns:
            人数（整数），如果没有则返回 None
        """
        # -------- 匹配"X人" --------
        guests_pattern = r"(\d+)\s*人"
        match = re.search(guests_pattern, text)
        if match:
            return int(match.group(1))

        # -------- 匹配"两个人" / "两人" --------
        if "两个人" in text or "两人" in text:
            return 2

        # -------- 匹配"三个人" / "三人" --------
        if "三个人" in text or "三人" in text:
            return 3

        return None


# ================================================================
# 全局单例实例
# ================================================================

# 创建 SlotFiller 的全局实例，方便其他模块直接导入使用
slot_filler = SlotFiller()