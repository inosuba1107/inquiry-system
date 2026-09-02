from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from .database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="user")

    staff_category = Column(String(50), nullable=True)

class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, index=True)

    #問い合わせ日時
    created_at = Column(DateTime, default=datetime.now)

    #件名
    title = Column(String(100), nullable=False)

    #問い合わせ内容
    content = Column(Text, nullable=False)

    #問い合わせ者
    username = Column(String(50), nullable=False)

    #カテゴリ
    category = Column(String(50), nullable=False)

    #ステータス
    status = Column(String(20), nullable=False, default="未対応")

    #優先度
    priority = Column(String(20), nullable=False, default="中")

    #添付ファイル
    attachment = Column(String(255),)

    #対応内容
    response = Column(Text, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    #通知を受け取るユーザー
    username = Column(String(50), nullable=False)

    #通知メッセージ
    message = Column(String(255), nullable=False)

    #関連する問い合わせID
    inquiry_id = Column(Integer, nullable=True)

    #未読/既読
    is_read = Column(Boolean, nullable=False, default=False)

    #通知日時
    created_at = Column(DateTime, default=datetime.now)