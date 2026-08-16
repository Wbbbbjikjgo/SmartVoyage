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
            "北京天气怎么样" → "北京"

        Args:
            text: 用户输入文本
            exclude: 要排除的城市（如出发城市，防止和目的地混淆）

        Returns:
            提取到的城市名，如果没有则返回 None
        """
        # -------- 国内主要城市列表 --------
        # 这是一个预定义的常见城市名单，实际生产环境可能更全面
        cities = [
            "北京", "上海", "广州", "深圳", "成都", "杭州", "西安", "重庆",
            "武汉", "南京", "天津", "长沙", "青岛", "大连", "厦门", "昆明",
            "三亚", "海口", "苏州", "无锡", "郑州", "合肥", "福州", "哈尔滨",
            "沈阳", "济南", "石家庄", "太原", "兰州", "银川", "西宁", "乌鲁木齐",
            "拉萨", "贵阳", "南宁", "呼和浩特",
        ]

        # -------- 优先匹配"到X"模式 --------
        # 例如："从上海到北京" → 提取 "北京"（到后面的城市）
        # 正则：到 + 2-4个任意字符 + 可选（的/市/空格/句号/结尾）
        to_match = re.search(r"到(.{2,4}?)(?:的|市|$|[\s，。])", text)
        if to_match and to_match.group(1) in cities and to_match.group(1) != exclude:
            return to_match.group(1)

        # -------- 否则返回文本中出现的第一个城市 --------
        # 按文本中出现的位置排序，取最靠前的
        # 如果排除了出发城市，且有多个城市，取最后一个
        candidates = [(text.find(c), c) for c in cities if c in text and c != exclude]
        if candidates:
            # 按出现位置排序
            candidates.sort(key=lambda x: x[0])
            # 如果有排除的城市，且候选有多个，取最后一个（通常是目的地）
            if len(candidates) > 1 and exclude:
                return candidates[-1][1]
            # 否则返回第一个出现的城市
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
                city = match.group(1)
                # 城市名通常比较短（2-4个字）
                if len(city) <= 4:
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