"""
Agent 路由器：根据用户意图，将任务智能路由到对应的 Agent

工作流程：
用户输入 → 意图识别 → 槽位填充 → 路由到对应 Agent → 执行技能 → 返回结果
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from models.schemas import IntentType, IntentResult
from core.intent_recognizer import intent_recognizer
from core.slot_filler import slot_filler
from orchestrator.agent_network import agent_network

# 获取当前模块的日志记录器
logger = logging.getLogger(__name__)


# ================================================================
# 1. Agent 路由器类
# ================================================================

class AgentRouter:
    """
    路由器：根据用户意图，将任务路由到对应的 Agent

    核心职责：
    1. 识别用户意图（Intent）
    2. 提取槽位信息（Slots）
    3. 根据意图找到对应的 Agent 和 Skill
    4. 准备参数并调用 Agent
    5. 返回执行结果
    """

    def __init__(self):
        """初始化路由器，配置意图→Agent→技能的映射关系"""
        
        # ============================================================
        # 1.1 依赖注入：引用全局实例
        # ============================================================
        # agent_network：管理所有 Agent 的网络（注册、发现、调用）
        self.network = agent_network
        
        # intent_recognizer：意图识别器，判断用户想干什么
        self.intent_recognizer = intent_recognizer
        
        # slot_filler：槽位填充器，从用户输入中提取关键信息
        self.slot_filler = slot_filler

        # ============================================================
        # 1.2 意图 → Agent 映射表
        # ============================================================
        # 作用：根据意图类型，决定把任务交给哪个 Agent
        # 
        # 例如：用户说"查一下北京天气"
        # → 意图是 WEATHER_QUERY
        # → 路由到 "weather" Agent
        self.intent_to_agent: Dict[IntentType, str] = {
            IntentType.WEATHER_QUERY: "weather",        # 天气查询 → weather Agent
            IntentType.FLIGHT_BOOKING: "flight",        # 机票预订 → flight Agent
            IntentType.TRAIN_BOOKING: "train",          # 高铁/火车票 → train Agent
            IntentType.HOTEL_BOOKING: "hotel",          # 酒店预订 → hotel Agent
            IntentType.ITINERARY_PLANNING: "itinerary", # 行程规划 → itinerary Agent
        }

        # ============================================================
        # 1.3 意图 → 技能映射表
        # ============================================================
        # 作用：根据意图类型，决定调用 Agent 的哪个技能
        #
        # 例如：用户说"帮我订一张去上海的机票"
        # → 意图是 FLIGHT_BOOKING
        # → 调用 flight Agent 的 "search_flights" 技能
        self.intent_to_skill: Dict[IntentType, str] = {
            IntentType.WEATHER_QUERY: "get_current_weather",  # 天气查询 → 获取当前天气
            IntentType.FLIGHT_BOOKING: "search_flights",      # 机票预订 → 搜索航班
            IntentType.TRAIN_BOOKING: "search_trains",        # 高铁/火车票 → 搜索车次
            IntentType.HOTEL_BOOKING: "search_hotels",        # 酒店预订 → 搜索酒店
            IntentType.ITINERARY_PLANNING: "plan_trip",       # 行程规划 → 规划完整行程
        }

        # ============================================================
        # 1.4 槽位名称映射表（Slot → 参数名）
        # ============================================================
        # 作用：不同 Agent 对同一个槽位有不同的命名习惯
        # 需要把用户提取的槽位名称，映射为 Agent 能理解的参数名
        #
        # 例如：用户说"去北京"
        # → 槽位是 {"destination": "北京"}
        # → weather Agent 需要的是 {"location": "北京"}
        # → hotel Agent 需要的是 {"location": "北京"}
        # → flight Agent 需要的是 {"arrival": "北京"}
        self.slot_mapping: Dict[str, Dict[str, str]] = {
            # weather Agent：destination → location
            "weather": {
                "destination": "location",
            },
            # hotel Agent：destination → location, date → check_in
            "hotel": {
                "destination": "location",
                "date": "check_in",
                "guests": "guests",
            },
            # flight Agent：destination → arrival
            "flight": {
                "destination": "arrival",
                "guests": "passengers",
            },
            # train Agent：departure → start, destination → end
            "train": {
                "departure": "start",
                "destination": "end",
            },
        }

        # ============================================================
        # 1.5 技能所需参数列表
        # ============================================================
        # 作用：定义每个技能需要哪些参数
        # 用于：
        #   1. 过滤多余的槽位（只保留技能需要的）
        #   2. 检查是否缺少必要参数（需要追问用户）
        #
        # 例如：search_flights 需要 departure, arrival, date, passengers
        # 如果用户只提供了 departure 和 arrival，缺少 date
        # 路由器会返回 "还需要提供日期"
        self.skill_required_params: Dict[str, List[str]] = {
            "get_current_weather": ["location"],                              # 天气：需要位置
            "search_flights": ["departure", "arrival", "date", "passengers"], # 航班：出发地、目的地、日期、人数
            "search_trains": ["start", "end", "date", "is_high_speed"],       # 火车票：出发、到达、日期、是否高铁
            "search_hotels": ["location", "check_in", "check_out", "guests"], # 酒店：位置、入住、退房、人数
            "create_itinerary": ["user_id", "destination", "start_date", "duration", "budget"],  # 行程：用户ID、目的地、开始日期、天数、预算
            "plan_trip": ["user_id", "destination", "start_date", "duration", "budget", "guests"],  # 完整行程规划
        }

    # ================================================================
    # 2. 参数准备方法（核心）
    # ================================================================

    def _prepare_parameters(
        self,
        agent_name: str,          # Agent 名称（如 "flight"）
        skill_name: str,          # 技能名称（如 "search_flights"）
        slots: Dict[str, Any],    # 从用户输入中提取的槽位信息
    ) -> Dict[str, Any]:
        """
        准备调用技能所需的参数

        功能：
        1. 复制槽位数据
        2. 槽位名称映射（destination → arrival）
        3. 过滤多余参数（只保留技能需要的）
        4. 填充默认值（日期默认明天，天数默认3天）

        示例：
            输入 slots: {"departure": "北京", "destination": "上海", "date": "明天"}
            输出: {"departure": "北京", "arrival": "上海", "date": "2024-08-17"}
        """
        # -------- 2.1 复制槽位 --------
        # 复制一份，避免修改原始数据
        params = dict(slots)

        # -------- 2.2 保存持续天数（酒店退房日期计算要用）-------
        duration_hint = params.get("duration")

        # -------- 2.3 槽位名称映射 --------
        # 获取当前 Agent 的映射规则
        mapping = self.slot_mapping.get(agent_name, {})
        
        # 遍历映射规则
        for slot_key, param_name in mapping.items():
            # 如果槽位有这个 key，且目标参数名不存在
            if slot_key in params and param_name not in params:
                # 重命名：slot_key → param_name
                # 例如：{"destination": "上海"} → {"arrival": "上海"}
                params[param_name] = params.pop(slot_key)
            # 如果槽位有这个 key，但目标参数名已存在
            elif slot_key in params:
                # 直接删除原 key，避免重复
                params.pop(slot_key)

        # -------- 2.4 过滤参数 --------
        # 只保留技能需要的参数
        required = self.skill_required_params.get(skill_name)
        if required:
            # 字典推导式：只保留 required 列表中的 key
            params = {k: v for k, v in params.items() if k in required}

        # -------- 2.5 填充默认值 --------
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()  # 明天的日期

        # 技能：搜索航班
        if skill_name == "search_flights" and not params.get("date"):
            params["date"] = tomorrow
            params.setdefault("_defaults_used", []).append("date=明天")

        # 技能：搜索高铁/火车票
        if skill_name == "search_trains":
            if not params.get("date"):
                params["date"] = tomorrow
                params.setdefault("_defaults_used", []).append("date=明天")
            params.setdefault("is_high_speed", 0)

        # 技能：搜索酒店
        if skill_name == "search_hotels":
            if not params.get("check_in"):
                params["check_in"] = tomorrow
                params.setdefault("_defaults_used", []).append("check_in=明天")
            
            if not params.get("check_out"):
                try:
                    check_in = date.fromisoformat(params["check_in"])
                    duration = int(duration_hint or 2)
                    params["check_out"] = (check_in + timedelta(days=duration)).isoformat()
                    params.setdefault("_defaults_used", []).append(f"check_out={params['check_out']}")
                except (ValueError, TypeError):
                    params["check_out"] = (date.today() + timedelta(days=3)).isoformat()

        # 技能：创建行程
        if skill_name in ("create_itinerary", "plan_trip"):
            if not params.get("start_date"):
                params["start_date"] = tomorrow
                params.setdefault("_defaults_used", []).append("start_date=明天")
            if not params.get("duration"):
                params["duration"] = 3
                params.setdefault("_defaults_used", []).append("duration=3天")

        return params

    # ================================================================
    # 3. 主路由方法
    # ================================================================

    async def route(self, user_input: str) -> Dict[str, Any]:
        """
        路由用户输入到对应的 Agent

        完整流程：
        1. 意图识别：用户想干什么？
        2. 槽位填充：提取了什么信息？
        3. 找到 Agent：哪个 Agent 能做这件事？
        4. 准备参数：槽位 → 技能参数
        5. 检查参数：是否缺少必要信息？
        6. 执行技能：调用 Agent 干活
        7. 返回结果

        Args:
            user_input: 用户的自然语言输入

        Returns:
            路由结果，包含 Agent 的响应
        """
        # -------- 3.1 意图识别 --------
        # 调用意图识别器，判断用户想干什么
        intent_result = await self.intent_recognizer.recognize_with_fallback(user_input)
        logger.info(f"识别到意图: {intent_result.intent} (置信度: {intent_result.confidence})")

        # -------- 3.2 槽位填充 --------
        # 从用户输入中提取关键信息
        slots = self.slot_filler.fill_slots(user_input, intent_result.slots)
        logger.info(f"提取到槽位: {slots}")

        # -------- 3.3 处理通用问答 --------
        # 如果用户只是闲聊，不走 Agent，直接回复
        if intent_result.intent == IntentType.GENERAL_QA:
            return await self._handle_general_qa(user_input, intent_result, slots)

        # -------- 3.4 查找对应的 Agent --------
        agent_name = self.intent_to_agent.get(intent_result.intent)
        if not agent_name:
            # 没有找到对应的 Agent，返回错误
            return {
                "error": True,
                "message": f"未找到处理该意图的 Agent: {intent_result.intent}",
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
            }

        # -------- 3.5 查找对应的技能 --------
        skill_name = self.intent_to_skill.get(intent_result.intent)

        # -------- 3.6 准备参数 --------
        # 槽位 → 技能参数（映射 + 过滤 + 默认值）
        parameters = self._prepare_parameters(agent_name, skill_name, slots)

        # -------- 3.7 检查是否缺少必要参数 --------
        # 有些参数是必需的，如果缺失需要追问用户
        # 排除 passengers, guests, budget, user_id（这些可以有默认值或可选）
        missing = [
            p for p in self.skill_required_params.get(skill_name, [])
            if p not in parameters and p not in ("passengers", "guests", "budget", "user_id")
        ]
        if missing:
            # 缺少必要参数，返回提示让用户补充
            return {
                "success": True,
                "agent": agent_name,
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "slots": slots,
                "missing_slots": missing,
                "data": {
                    "message": f"还需要以下信息才能完成查询：{', '.join(missing)}，请补充后重试。",
                },
            }

        # -------- 3.8 设置默认用户ID --------
        # 创建行程/规划行程时需要 user_id，如果用户没提供，默认用 1（演示用户）
        if skill_name in ("create_itinerary", "plan_trip") and "user_id" not in parameters:
            parameters["user_id"] = 1

        # -------- 3.9 移除内部元数据 --------
        # _defaults_used 只是用来记录用了哪些默认值，不传给 Agent
        defaults_used = parameters.pop("_defaults_used", None)

        # -------- 3.10 调用 Agent 执行技能 --------
        result = await self.network.invoke_agent(agent_name, skill_name, parameters)

        # -------- 3.11 返回结果 --------
        return {
            "success": True,
            "agent": agent_name,
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "defaults_used": defaults_used,  # 告诉用户用了哪些默认值
            "data": result,
        }

    # ================================================================
    # 4. 直接路由方法（跳过意图识别）
    # ================================================================

    async def route_to_agent(
        self,
        agent_name: str,
        skill: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        直接路由到指定的 Agent 和技能（跳过意图识别）

        使用场景：
        - 已经知道要调用哪个 Agent 和技能
        - 系统内部调用
        - 测试

        Args:
            agent_name: Agent 名称
            skill: 技能名称
            parameters: 技能参数

        Returns:
            Agent 响应
        """
        return await self.network.invoke_agent(agent_name, skill, parameters)

    # ================================================================
    # 5. 通用问答处理
    # ================================================================

    async def _handle_general_qa(
        self,
        user_input: str,
        intent_result: IntentResult,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        处理通用问答（闲聊/打招呼等）

        当用户输入不是具体的业务请求时，走这个分支

        Args:
            user_input: 用户输入
            intent_result: 意图识别结果
            slots: 提取的槽位

        Returns:
            响应字典
        """
        # 目前返回固定欢迎语
        # 生产环境可以接入 LLM 生成更自然的回复
        return {
            "success": True,
            "agent": "general",
            "intent": IntentType.GENERAL_QA.value,
            "confidence": intent_result.confidence,
            "slots": slots,
            "data": {
                "message": "我是 SmartVoyage 智能旅行助手，可以帮您查询天气、预订机票酒店、规划行程。请问有什么可以帮您的？",
            },
        }

    # ================================================================
    # 6. 获取路由配置信息
    # ================================================================

    def get_routing_info(self) -> Dict[str, Any]:
        """
        获取路由配置信息（用于调试和管理）

        Returns:
            包含所有映射关系和可用 Agent 列表的字典
        """
        return {
            "intent_to_agent": {
                k.value: v for k, v in self.intent_to_agent.items()
            },
            "intent_to_skill": {
                k.value: v for k, v in self.intent_to_skill.items()
            },
            "agents": self.network.list_agents(),  # 列出所有已注册的 Agent
        }


# ================================================================
# 7. 全局单例实例
# ================================================================

# 创建全局路由器实例，供其他模块导入使用
agent_router = AgentRouter()