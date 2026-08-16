"""
Pydantic 数据校验与序列化 Schema 定义
用于：请求参数校验、响应数据格式化、数据转换
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


# ================================================================
# 1. 枚举类 (Enum) - 定义固定的可选值，防止输入脏数据
# ================================================================

class IntentType(str, Enum):
    """
    用户意图类型枚举
    作用：限制意图识别的结果只能是以下6种之一
    """
    WEATHER_QUERY = "weather_query"          # 查询天气
    FLIGHT_BOOKING = "flight_booking"        # 预订机票
    TRAIN_BOOKING = "train_booking"          # 预订高铁/火车票
    HOTEL_BOOKING = "hotel_booking"          # 预订酒店
    ITINERARY_PLANNING = "itinerary_planning" # 行程规划
    GENERAL_QA = "general_qa"                # 通用问答（闲聊/其他）


class ItineraryStatus(str, Enum):
    """行程状态枚举"""
    DRAFT = "draft"           # 草稿（规划中）
    CONFIRMED = "confirmed"   # 已确认（定稿）
    CANCELLED = "cancelled"   # 已取消


class BookingType(str, Enum):
    """预订类型枚举"""
    FLIGHT = "flight"   # 机票
    HOTEL = "hotel"     # 酒店
    TICKET = "ticket"   # 门票/车票


class BookingStatus(str, Enum):
    """预订状态枚举"""
    PENDING = "pending"     # 待支付
    PAID = "paid"           # 已支付
    CANCELLED = "cancelled" # 已取消


# ================================================================
# 2. 用户相关 Schema
# ================================================================

class UserCreate(BaseModel):
    """
    创建用户时的请求体校验
    使用场景：POST /api/users 接收前端传参
    """
    name: str = Field(..., min_length=1, max_length=64)
    # Field(..., ...) 中 ... 表示必填字段
    # min_length=1 至少1个字符，max_length=64 最多64个字符

    email: EmailStr
    # EmailStr 是 Pydantic 内置类型，会自动校验邮箱格式

    preferences: Optional[Dict[str, Any]] = None
    # Optional 表示可选字段，不传则为 None
    # Dict[str, Any] 表示任意键值对的字典


class UserResponse(BaseModel):
    """
    返回用户信息时的响应格式
    使用场景：GET /api/users/{id} 返回给前端
    """
    user_id: int
    name: str
    email: str
    preferences: Optional[Dict[str, Any]] = None
    created_at: datetime  # 创建时间（从数据库读出）

    class Config:
        from_attributes = True
        # from_attributes = True (Pydantic v2)
        # 作用：允许从 ORM 对象（如 SQLAlchemy 模型）自动转换
        # v1 中叫 orm_mode = True


# ================================================================
# 3. 行程 (Itinerary) 相关 Schema
# ================================================================

class ItineraryCreate(BaseModel):
    """
    创建行程时的请求体校验
    使用场景：用户提交行程规划请求
    """
    user_id: int                          # 所属用户ID
    destination: str = Field(..., min_length=1, max_length=64)
    # 目的地，必填，1-64字符

    start_date: date                      # 开始日期（只有日期，无时间）
    duration: int = Field(..., gt=0)      # 持续天数，必须 > 0

    budget: Optional[Decimal] = Field(None, gt=0)
    # 预算，可选，如有则必须 > 0
    # Decimal 用于金额（比 float 更精确，无浮点数精度问题）


class ItineraryResponse(BaseModel):
    """
    返回行程信息时的响应格式
    包含数据库自动生成的字段（id、时间戳等）
    """
    itinerary_id: int                     # 行程ID（数据库自增）
    user_id: int
    destination: str
    start_date: date
    duration: int
    budget: Optional[Decimal] = None
    status: ItineraryStatus               # 使用上面定义的枚举
    created_at: datetime
    updated_at: datetime                  # 最后更新时间

    class Config:
        from_attributes = True


# ================================================================
# 4. 预订 (Booking) 相关 Schema
# ================================================================

class BookingCreate(BaseModel):
    """
    创建预订时的请求体校验
    使用场景：用户预订机票/酒店/门票
    """
    itinerary_id: int                     # 关联到哪个行程
    type: BookingType                     # 预订类型（机票/酒店/门票）
    details: Dict[str, Any]               # 具体预订信息（灵活字典）
    # 例如：{"flight_no": "CA1234", "seat": "A1"}
    # 或者：{"hotel_name": "希尔顿", "room": "大床房"}

    status: BookingStatus = BookingStatus.PENDING
    # 默认状态为 "待支付"，可不传


class BookingResponse(BaseModel):
    """
    返回预订信息时的响应格式
    """
    booking_id: int
    itinerary_id: int
    type: BookingType
    details: Dict[str, Any]
    status: BookingStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ================================================================
# 5. 聊天 (Chat) 相关 Schema
# ================================================================

class ChatMessage(BaseModel):
    """
    聊天消息格式（单条消息）
    使用场景：与 AI 助手对话时传入消息
    """
    role: str = Field(..., description="角色：user/assistant/system")
    # role: 消息发送者身份
    # user → 用户发送；assistant → AI 回复；system → 系统提示

    content: str = Field(..., description="消息内容")
    # 具体的消息文本


class ChatResponse(BaseModel):
    """
    AI 助手的回复格式
    使用场景：/api/chat 接口返回
    """
    message: str = Field(..., description="AI 回复内容")
    # 返回给用户的文本回复

    intent: Optional[IntentType] = None
    # 识别出的用户意图（如果有）

    data: Optional[Dict[str, Any]] = None
    # 附加的结构化数据（如查询到的天气、航班信息等）

    session_id: Optional[str] = None
    # 会话ID（用于多轮对话上下文关联）


# ================================================================
# 6. 意图识别相关 Schema
# ================================================================

class IntentResult(BaseModel):
    """
    意图识别结果格式
    使用场景：IntentAgent 的输出
    """
    intent: IntentType                    # 识别出的意图（枚举）
    confidence: float = Field(..., ge=0, le=1)
    # 置信度，范围 0.0 ~ 1.0
    # ge=0 表示 >= 0，le=1 表示 <= 1

    slots: Dict[str, Any] = Field(default_factory=dict)
    # 槽位信息（提取的关键字段）
    # 例如：{"destination": "北京", "date": "2024-08-20"}


# ================================================================
# 7. 外部数据 Schema（对接第三方 API 的数据格式）
# ================================================================

class WeatherData(BaseModel):
    """
    天气数据格式（高德开放平台归一化后）
    使用场景：调用天气 API 后的数据解析
    """
    location: str                          # 城市/地点
    adcode: Optional[str] = None           # 行政区划编码
    description: Optional[str] = None      # 天气描述（如：晴、多云、小雨）
    temperature: Optional[float] = None    # 温度（摄氏度）
    humidity: Optional[float] = None       # 湿度百分比
    wind_direction: Optional[str] = None   # 风向
    wind_power: Optional[str] = None       # 风力等级
    report_time: Optional[str] = None      # 数据发布时间
    forecast: Optional[List[Dict[str, Any]]] = None  # 天气预报列表（可选）


class FlightData(BaseModel):
    """
    航班数据格式（阿里云 API 市场归一化后）
    使用场景：调用机票 API 后的数据解析
    """
    flight_no: Optional[str] = None        # 航班号，如 "CA1234"
    airline: Optional[str] = None          # 航空公司，如 "中国国航"
    departure: Optional[str] = None        # 出发地
    arrival: Optional[str] = None          # 目的地
    departure_airport: Optional[str] = None  # 出发机场
    arrival_airport: Optional[str] = None    # 到达机场
    departure_time: Optional[str] = None   # 起飞时间
    arrival_time: Optional[str] = None     # 到达时间
    duration: Optional[str] = None         # 飞行时长
    price: Optional[Decimal] = None        # 票价（Decimal 保证金额精度）
    currency: str = "CNY"                  # 货币单位，默认人民币
    available_seats: Optional[int] = None  # 剩余座位数


class TrainData(BaseModel):
    """
    火车票数据格式（阿里云 API 市场归一化后）
    使用场景：调用火车票 API 后的数据解析
    """
    train_no: Optional[str] = None         # 车次号，如 "G123"
    train_type: Optional[str] = None       # 列车类型（高铁/动车/普速）
    departure: Optional[str] = None        # 出发地
    arrival: Optional[str] = None          # 到达地
    departure_station: Optional[str] = None  # 出发站
    arrival_station: Optional[str] = None    # 到达站
    departure_time: Optional[str] = None   # 发车时间
    arrival_time: Optional[str] = None     # 到达时间
    duration: Optional[str] = None         # 运行时长
    seats: Optional[Dict[str, float]] = None  # 各席别票价
    price: Optional[float] = None          # 参考票价


class HotelData(BaseModel):
    """
    酒店数据格式（高德 POI 归一化后）
    使用场景：调用酒店 API 后的数据解析
    """
    hotel_name: Optional[str] = None       # 酒店名称
    address: Optional[str] = None          # 地址
    location: Optional[str] = None         # 经纬度 "lng,lat"
    district: Optional[str] = None         # 所在区县
    price_per_night: Optional[float] = None  # 每晚价格（参考估值）
    currency: str = "CNY"                  # 货币单位
    rating: Optional[float] = Field(None, ge=0, le=5)  # 评分，范围 0 ~ 5 星
    amenities: List[str] = Field(default_factory=list)  # 设施列表
    photos: Optional[List[str]] = None     # 酒店图片链接