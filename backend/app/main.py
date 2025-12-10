from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import uuid
from datetime import datetime
from . import models
from .database import engine, get_db
import time
from typing import Dict, List
import asyncio
import json
from ai_service.collect_files import initial_analyzis
from ai_service.vectorizing import initial_vectorizing
from ai_service.generating import initital_generating, rewrite_review_with_instruction

from concurrent.futures import ThreadPoolExecutor



# Создаем таблицы
models.Base.metadata.create_all(bind=engine)
class ConnectionManager:
    def __init__(self):
        # Простой словарь для хранения соединений
        self.active_connections = {}
    
    async def send_personal_message(self, message: dict, client_id: str) -> bool:
        """Отправить сообщение конкретному клиенту"""
        if client_id not in self.active_connections:
            print(f"⚠️ Клиент {client_id} не найден в активных соединениях")
            return False
        
        websocket = self.active_connections[client_id]
        
        try:
            await websocket.send_json(message)
            print(f"📨 Сообщение отправлено клиенту {client_id}")
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки клиенту {client_id}: {e}")
            # Удаляем нерабочее соединение
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            return False
    
    async def broadcast(self, message: dict):
        """Отправить сообщение всем клиентам"""
        disconnected = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(client_id)
        
        # Удаляем отключенных клиентов
        for client_id in disconnected:
            if client_id in self.active_connections:
                del self.active_connections[client_id]

manager = ConnectionManager()
app = FastAPI(title="Chat API", version="1.0.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Адрес вашего фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Папка для загрузки файлов
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pydantic схемы
from pydantic import BaseModel
from typing import Optional
from datetime import datetime as dt

class ChatBase(BaseModel):
    title: str

class ChatCreate(ChatBase):
    pass

class ChatResponse(ChatBase):
    id: int
    created_at: dt
    updated_at: dt
    
    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    content: str
    role: str
    mode: Optional[str] = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    chat_id: int
    created_at: dt
    
    class Config:
        from_attributes = True

class FileResponse(BaseModel):
    id: int
    chat_id: int
    filename: str
    file_size: int
    uploaded_at: dt
    
    class Config:
        from_attributes = True

class ChatWithDetails(ChatResponse):
    messages: List[MessageResponse] = []
    files: List[FileResponse] = []

# API endpoints

@app.get("/api/chats", response_model=List[ChatResponse])
def get_chats(db: Session = Depends(get_db)):
    """Получить список всех чатов"""
    chats = db.query(models.Chat).order_by(models.Chat.updated_at.desc()).all()
    return chats

@app.post("/api/chats", response_model=ChatResponse)
def create_chat(chat: ChatCreate, db: Session = Depends(get_db)):
    """Создать новый чат"""
    db_chat = models.Chat(
        title=chat.title,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

@app.get("/api/chats/{chat_id}", response_model=ChatWithDetails)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    """Получить чат со всеми сообщениями и файлами"""
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    #time.sleep(10)
    
    return chat

@app.post("/api/chats/{chat_id}/messages", response_model=MessageResponse)
async def create_message(
    chat_id: int,
    message: str = Form(...),
    mode: str = Form("full"),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
    client_id: str = Form(None)
):
    """Отправить сообщение в чат (с файлами)"""
    # Проверяем существование чата
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        # Если чата нет, создаем его
        chat = models.Chat(
            title=message[:50] + "..." if len(message) > 50 else message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        chat_id = chat.id
    
    # Сохраняем файлы
    front_filenames = [file.filename for file in files]
    print(front_filenames)
    current_db_files = db.query(models.ChatFile)\
        .filter(models.ChatFile.chat_id == chat_id)\
        .all()
    db_filenames = [f.filename for f in current_db_files]

    saved_files = []
    same_lists_flag = False

    if set(front_filenames) == set(db_filenames):
        print("Списки файлов совпадают - не обновляем файлы")
        same_lists_flag = True
        # Файлы не менялись, работаем только с сообщением
    else:
        print("Списки файлов не совпадают - обновляем")
        # 3.1 Удаляем старые файлы
        for db_file in current_db_files:
            # Удаляем файл с диска
            if os.path.exists(db_file.file_path):
                os.remove(db_file.file_path)
            # Удаляем запись из БД
            db.delete(db_file)

        for file in files:
            if file.content_type != "application/pdf":
                continue
            
            # Генерируем уникальное имя файла
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            # Сохраняем файл
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Сохраняем информацию о файле в БД
            db_file = models.ChatFile(
                chat_id=chat_id,
                filename=file.filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                uploaded_at=datetime.utcnow()
            )
            db.add(db_file)
            saved_files.append(db_file)
    
    
    # Сохраняем сообщение пользователя
    user_message = models.Message(
        chat_id=chat_id,
        content=message,
        role="user",
        mode=mode,
        created_at=datetime.utcnow()
    )
    db.add(user_message)

    

    print(message)
    if message.startswith("уточнение"):
        print(123123)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        file_path = os.path.join(parent_dir, "compact_literature_review.txt")

        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        if client_id:
        # Создаем финальное сообщение с результатом
            final_message = models.Message(
                chat_id=chat_id,
                content=f"Вы выбрали уточнение запроса",
                role="assistant",
                created_at=datetime.utcnow()
            )
            db.add(final_message)
            db.commit()
            db.refresh(final_message)
            
            await manager.send_personal_message({
                "type": "message",
                "message": {
                    "id": final_message.id,
                    "chat_id": final_message.chat_id,
                    "content": final_message.content,
                    "role": final_message.role,
                    "created_at": final_message.created_at.isoformat()
                }
            }, client_id)

        try:
            # Если функция синхронная (не async), запускаем в thread pool
            
            # Создаем пул потоков
            with ThreadPoolExecutor() as executor:
                # Запускаем анализ в отдельном потоке
                analysis_future = executor.submit(
                    rewrite_review_with_instruction,  # ваша функция
                    text,           # сообщение пользователя
                    message       # список имен файлов
                )
                
                # Ждем завершения (блокируем, но в отдельном потоке)
                analysis_result = analysis_future.result(timeout=120)  # таймаут 120 секунд
                
        except Exception as e:
            # Если ошибка при анализе
            analysis_result = f"❌ Ошибка при анализе: {str(e)}"

        if client_id:
        # Создаем финальное сообщение с результатом
            final_message = models.Message(
                chat_id=chat_id,
                content=f"{analysis_result}",
                role="assistant",
                created_at=datetime.utcnow()
            )
            db.add(final_message)
            db.commit()
            db.refresh(final_message)
            
            await manager.send_personal_message({
                "type": "message",
                "message": {
                    "id": final_message.id,
                    "chat_id": final_message.chat_id,
                    "content": final_message.content,
                    "role": final_message.role,
                    "created_at": final_message.created_at.isoformat()
                }
            }, client_id)

        await manager.broadcast({"type": "chats_updated"})
    
    # Возвращаем сообщение пользователя (можно вернуть и AI сообщение)
        return user_message

        
    
    # Генерируем ответ от AI (заглушка)
    ai_response = f"Ваша тема исследования: '{message}'. Файлов загружено: {len(files)}"
    
    ai_message = models.Message(
        chat_id=chat_id,
        content=ai_response,
        role="assistant",
        created_at=datetime.utcnow()
    )
    db.add(ai_message)
    
    # Обновляем время изменения чата
    chat.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user_message)
    db.refresh(ai_message)

    if client_id:
        await manager.send_personal_message({
            "type": "message",
            "message": {
                "id": user_message.id,
                "chat_id": user_message.chat_id,
                "content": user_message.content,
                "role": user_message.role,
                "mode": user_message.mode,
                "created_at": user_message.created_at.isoformat()
            },
            "chat_id": chat_id
        }, client_id)
    
    # 3. Имитируем обработку (в реальности здесь будет работа с нейросетью)
    if client_id:
        await asyncio.sleep(1)  # 2 секунды задержки
        
        # 4. Сохраняем и отправляем ответ AI
        # ai_response = f"Ответ на: '{message}'. Файлов: {len(saved_files)}"
        # ai_message = models.Message(
        #     chat_id=chat_id,
        #     content=ai_response,
        #     role="assistant",
        #     created_at=datetime.utcnow()
        # )
        # db.add(ai_message)
        # db.commit()
        # db.refresh(ai_message)
        
        await manager.send_personal_message({
            "type": "message",
            "message": {
                "id": ai_message.id,
                "chat_id": ai_message.chat_id,
                "content": ai_message.content,
                "role": ai_message.role,
                "created_at": ai_message.created_at.isoformat()
            },
            "chat_id": chat_id
        }, client_id)

    current_db_files = db.query(models.ChatFile)\
        .filter(models.ChatFile.chat_id == chat_id)\
        .all()
    db_filenames = [f.file_path.split('\\')[1] for f in current_db_files]
    print(db_filenames)

    if not same_lists_flag:
        #analyz_result = initial_analyzis(message, db_filenames)
        try:
            # Если функция синхронная (не async), запускаем в thread pool
            
            # Создаем пул потоков
            with ThreadPoolExecutor() as executor:
                # Запускаем анализ в отдельном потоке
                analysis_future = executor.submit(
                    initial_analyzis,  # ваша функция
                    message,           # сообщение пользователя
                    db_filenames       # список имен файлов
                )
                
                # Ждем завершения (блокируем, но в отдельном потоке)
                analysis_result = analysis_future.result(timeout=120)  # таймаут 120 секунд
                
        except Exception as e:
            # Если ошибка при анализе
            analysis_result = f"❌ Ошибка при анализе: {str(e)}"

    else:
        analysis_result = "Список файлов не был изменен, повторный анализ на релевантность не требуется"

    # 5. Отправляем результат анализа
    if client_id:
        # Создаем финальное сообщение с результатом
        final_message = models.Message(
            chat_id=chat_id,
            content=f"{analysis_result}",
            role="assistant",
            created_at=datetime.utcnow()
        )
        db.add(final_message)
        db.commit()
        db.refresh(final_message)
        
        await manager.send_personal_message({
            "type": "message",
            "message": {
                "id": final_message.id,
                "chat_id": final_message.chat_id,
                "content": final_message.content,
                "role": final_message.role,
                "created_at": final_message.created_at.isoformat()
            }
        }, client_id)

    if not same_lists_flag:
        #analyz_result = initial_analyzis(message, db_filenames)
        try:
            # Если функция синхронная (не async), запускаем в thread pool
            
            # Создаем пул потоков
            with ThreadPoolExecutor() as executor:
                # Запускаем анализ в отдельном потоке
                analysis_future = executor.submit(
                    initial_vectorizing
                )
                
                # Ждем завершения (блокируем, но в отдельном потоке)
                analysis_result = analysis_future.result(timeout=120)  # таймаут 120 секунд
                
        except Exception as e:
            # Если ошибка при анализе
            analysis_result = f"❌ Ошибка при векторизации: {str(e)}"

    else:
        analysis_result = "Повторная векторизация не требуется"

    if client_id:
        # Создаем финальное сообщение с результатом
        final_message = models.Message(
            chat_id=chat_id,
            content=f"{analysis_result}",
            role="assistant",
            created_at=datetime.utcnow()
        )
        db.add(final_message)
        db.commit()
        db.refresh(final_message)
        
        await manager.send_personal_message({
            "type": "message",
            "message": {
                "id": final_message.id,
                "chat_id": final_message.chat_id,
                "content": final_message.content,
                "role": final_message.role,
                "created_at": final_message.created_at.isoformat()
            }
        }, client_id)

    try:
        # Если функция синхронная (не async), запускаем в thread pool
        
        # Создаем пул потоков
        with ThreadPoolExecutor() as executor:
            # Запускаем анализ в отдельном потоке
            analysis_future = executor.submit(
                initital_generating,
                message,
                mode
            )
            
            # Ждем завершения (блокируем, но в отдельном потоке)
            analysis_result = analysis_future.result(timeout=180)  # таймаут 180 секунд
            
    except Exception as e:
        # Если ошибка при анализе
        analysis_result = f"❌ Ошибка при генерации обзора: {str(e)}"

    if client_id:
        # Создаем финальное сообщение с результатом
        final_message = models.Message(
            chat_id=chat_id,
            content=f"{analysis_result}",
            role="assistant",
            created_at=datetime.utcnow()
        )
        db.add(final_message)
        db.commit()
        db.refresh(final_message)
        
        await manager.send_personal_message({
            "type": "message",
            "message": {
                "id": final_message.id,
                "chat_id": final_message.chat_id,
                "content": final_message.content,
                "role": final_message.role,
                "created_at": final_message.created_at.isoformat()
            }
        }, client_id)

        
    # 5. Обновляем список чатов
    await manager.broadcast({"type": "chats_updated"})
    
    # Возвращаем сообщение пользователя (можно вернуть и AI сообщение)
    return user_message

@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """Удалить чат и все связанные данные"""
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    # Удаляем файлы из файловой системы
    for file in chat.files:
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
    
    # Удаляем чат из БД (каскадное удаление сработает)
    db.delete(chat)
    db.commit()
    
    return {"message": "Чат удален"}

# В main.py добавьте:
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Простой WebSocket endpoint который работает"""
    # 1. Принимаем соединение
    await websocket.accept()
    print(f"✅ WebSocket подключен: {client_id}")
    
    # 2. Добавляем в активные соединения
    manager.active_connections[client_id] = websocket
    print(f"📊 Активных соединений: {len(manager.active_connections)}")
    
    # 3. Немедленно отправляем подтверждение подключения
    await websocket.send_json({
        "type": "connected",
        "message": f"Вы подключены как {client_id}",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    try:
        # 4. Бесконечный цикл для поддержания соединения
        while True:
            # Ждем сообщение от клиента
            # Это блокирующая операция - соединение будет держаться
            data = await websocket.receive_text()
            
            # Если клиент что-то отправил, можно обработать
            # Просто эхо для поддержания связи
            if data.strip():
                await websocket.send_json({
                    "type": "echo",
                    "echo": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        print(f"🔌 WebSocket отключен: {client_id}")
    except Exception as e:
        print(f"❌ Ошибка WebSocket {client_id}: {e}")
    finally:
        # 5. Удаляем из активных соединений при отключении
        if client_id in manager.active_connections:
            del manager.active_connections[client_id]
            print(f"🗑️ Удален клиент: {client_id}")
            print(f"📊 Осталось соединений: {len(manager.active_connections)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)