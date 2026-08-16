"""
SQLAlchemy 数据库模型与工具函数
用于：定义数据库表结构、创建数据库连接、管理会话
"""

from datetime import datetime
from typing import Generator
from sqlalchemy import (
    create_engine,          # 创建数据库引擎
    Column,                 # 定义列
    BigInteger,             # 大整数类型（64位）
    String,                 # 字符串类型
    Date,                   # 日期类型（年月日）
    Integer,                # 整数类型
    Numeric,                # 精确数字类型（适合金额）
    DateTime,               # 日期时间类型
    JSON,                   # JSON 类型（存储结构化数据）
    ForeignKey,             # 外键约束
    Text,                   # 长文本类型
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from configs.settings import settings


# ================================================================
# 1. 模型基类
# ================================================================

# declarative_base() 创建所有模型的基类
# 所有数据模型都要继承这个 Base
Base = declarative_base()


# ================================================================
# 2. 用户模型 (User)
# ================================================================

class User(Base):
    """用户表 - 存储系统用户信息"""
    # 指定数据库中的表名
    __tablename__ = "users"

    # -------- 字段定义 --------
    # 用户ID：主键，自增
    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    # BigInteger：64位整数，适合大数据量场景
    
    # 用户姓名：字符串，最大64字符，不能为空
    name = Column(String(64), nullable=False)
    # nullable=False：该字段必须有值
    
    # 邮箱：字符串，最大128字符，不能为空，唯一（不能重复）
    email = Column(String(128), nullable=False, unique=True)
    # unique=True：确保邮箱不重复
    
    # 偏好设置：JSON 类型，可为空
    preferences = Column(JSON, nullable=True)
    # JSON 类型可存储任意结构的键值对
    # 例如：{"theme": "dark", "language": "en"}
    
    # 创建时间：DateTime 类型，默认当前 UTC 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    # default：插入数据时自动填充

    # -------- 关联关系 --------
    # 一对多：一个用户可以有多个行程
    # back_populates：与 Itinerary 模型中的 "user" 字段双向关联
    # cascade：级联操作，删除用户时自动删除所有关联行程
    itineraries = relationship("Itinerary", back_populates="user", cascade="all, delete-orphan")
    # delete-orphan：被孤立（脱离关系）的行程也会被删除

    # -------- 特殊方法 --------
    def __repr__(self) -> str:
        """定义对象的字符串表示，方便调试"""
        return f"<User(user_id={self.user_id}, name='{self.name}')>"


# ================================================================
# 3. 行程模型 (Itinerary)
# ================================================================

class Itinerary(Base):
    """行程表 - 存储用户的旅行/出行计划"""
    __tablename__ = "itineraries"

    # -------- 字段定义 --------
    # 行程ID：主键，自增
    itinerary_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 用户ID：外键，关联 users 表，不能为空
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    # ForeignKey：外键约束，保证数据一致性
    
    # 目的地：字符串，最大64字符，不能为空
    destination = Column(String(64), nullable=False)
    
    # 开始日期：Date 类型（只有日期，没有时间）
    start_date = Column(Date, nullable=False)
    
    # 持续天数：整数，不能为空
    duration = Column(Integer, nullable=False)
    
    # 预算：精确数字，12位总长度，2位小数，可为空
    budget = Column(Numeric(12, 2), nullable=True)
    # Numeric(12,2)：最大 9999999999.99
    
    # 状态：字符串，最大16字符，默认 "draft"
    status = Column(String(16), default="draft")
    # 可选值：draft / confirmed / cancelled
    
    # 创建时间：默认当前时间
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 更新时间：创建时默认当前时间，更新时自动更新
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # onupdate：记录更新时自动刷新

    # -------- 关联关系 --------
    # 多对一：一个行程属于一个用户
    user = relationship("User", back_populates="itineraries")
    
    # 一对多：一个行程可以有多个预订
    bookings = relationship("Booking", back_populates="itinerary", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Itinerary(itinerary_id={self.itinerary_id}, destination='{self.destination}')>"


# ================================================================
# 4. 预订模型 (Booking)
# ================================================================

class Booking(Base):
    """预订表 - 存储行程中的具体预订（机票/酒店/门票）"""
    __tablename__ = "bookings"

    # -------- 字段定义 --------
    # 预订ID：主键，自增
    booking_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # 行程ID：外键，关联 itineraries 表，不能为空
    itinerary_id = Column(BigInteger, ForeignKey("itineraries.itinerary_id"), nullable=False)
    
    # 类型：字符串，最大16字符，不能为空
    type = Column(String(16), nullable=False)
    # 可选值：flight / hotel / ticket
    
    # 详情：JSON 类型，存储具体预订信息，可为空
    details = Column(JSON, nullable=True)
    # 例如：{"flight_no": "CA1234", "seat": "A1"}
    
    # 状态：字符串，最大16字符，默认 "pending"
    status = Column(String(16), default="pending")
    # 可选值：pending / paid / cancelled
    
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)

    # -------- 关联关系 --------
    # 多对一：一个预订属于一个行程
    itinerary = relationship("Itinerary", back_populates="bookings")

    def __repr__(self) -> str:
        return f"<Booking(booking_id={self.booking_id}, type='{self.type}')>"


# ================================================================
# 5. 数据库工具函数
# ================================================================

# 全局变量：缓存引擎和会话工厂，避免重复创建
_engine = None
_SessionLocal = None


def get_engine():
    """
    获取或创建 SQLAlchemy 数据库引擎
    引擎是数据库连接的核心对象，负责管理连接池
    """
    global _engine
    if _engine is None:
        # create_engine：创建数据库引擎
        # settings.mysql_dsn：从配置文件读取连接字符串
        # 格式：mysql+pymysql://user:pass@host:port/database
        _engine = create_engine(
            settings.mysql_dsn,
            pool_pre_ping=True,      # 连接前 ping 一下，检查连接是否有效
            pool_recycle=3600,       # 连接回收时间（秒），避免 MySQL 自动断开
            echo=False,              # 是否打印 SQL 日志（False 不打印）
        )
    return _engine


def get_session_factory():
    """
    获取或创建会话工厂
    会话工厂用于生成数据库会话（Session）
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        # sessionmaker：创建会话工厂
        # autocommit=False：不自动提交，需要手动 commit
        # autoflush=False：不自动刷新，需要手动 flush
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """
    获取数据库会话（用于 FastAPI 依赖注入）
    Generator 类型表示这是一个生成器函数
    使用 yield 返回会话，确保自动关闭

    用法：
        @app.get("/users")
        def get_users(session: Session = Depends(get_session)):
            return session.query(User).all()
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()  # 创建会话
    try:
        yield session  # 返回会话给调用方
    finally:
        session.close()  # 无论是否异常，最后都关闭会话


def init_db():
    """
    初始化数据库：创建所有表
    在应用启动时调用一次
    """
    engine = get_engine()
    # Base.metadata.create_all：根据所有模型定义创建表
    # bind=engine：指定使用哪个引擎
    Base.metadata.create_all(bind=engine)
    print(f"数据库初始化成功: {settings.mysql_database}")


def seed_default_user():
    """
    确保默认演示用户存在（user_id=1）
    用于开发和测试环境
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        # 查询 user_id=1 的用户是否存在
        user = session.query(User).filter(User.user_id == 1).first()
        if not user:
            # 不存在则创建
            user = User(
                name="演示用户",
                email="demo@smartvoyage.local",
                preferences={"theme": "light", "language": "zh-CN"},
            )
            session.add(user)  # 添加到会话
            session.commit()   # 提交事务（真正写入数据库）
            print("默认演示用户已创建 (user_id=1)")
        return user.user_id  # 返回用户ID
    finally:
        session.close()  # 关闭会话


def close_db():
    """
    关闭数据库连接
    在应用关闭时调用，释放资源
    """
    global _engine, _SessionLocal
    if _engine is not None:
        # dispose()：关闭所有连接，释放连接池
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        print("数据库连接已关闭")