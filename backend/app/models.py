from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    files = relationship("ChatFile", back_populates="chat", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    content = Column(Text, nullable=False)
    role = Column(String, nullable=False)  # 'user' или 'assistant'
    mode = Column(String, nullable=True)   # 'full' или 'brief'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chat = relationship("Chat", back_populates="messages")

class ChatFile(Base):
    __tablename__ = "chat_files"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chat = relationship("Chat", back_populates="files")