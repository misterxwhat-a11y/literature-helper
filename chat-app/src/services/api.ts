// services/api.ts - Все обращения к серверу
import axios from 'axios';
import type { Chat, ChatDetail, Message, ResponseMode } from '../types';

// Базовый URL вашего FastAPI бэкенда
const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Загрузка файлов требует отдельного конфига
const apiFile = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});

export const chatApi = {
  // Получить список всех чатов
  getChats: async (): Promise<Chat[]> => {
    const response = await api.get<Chat[]>('/api/chats');
    return response.data;
  },
  
  // Создать новый чат
   createChat: async (title: string = 'Новая тема'): Promise<Chat> => {
    const response = await api.post<Chat>('/api/chats', { title });
    return response.data;
  },
  
  // Получить конкретный чат с сообщениями и файлами
  getChat: async (chatId: string): Promise<ChatDetail> => {
    const response = await api.get<ChatDetail>(`/api/chats/${chatId}`);
    return response.data;
  },
  
  // Отправить сообщение
  sendMessage: async (
    chatId: string | null, 
    content: string, 
    mode: ResponseMode,
    files: File[],
    clientId?: string
  ): Promise<Message> => {
    const formData = new FormData();
    formData.append('message', content);
    formData.append('mode', mode);

    if (clientId) {
      formData.append('client_id', clientId);
    }
    
    // Добавляем все файлы
    files.forEach(file => {
      formData.append('files', file);
    });

    const endpoint = chatId ? `/api/chats/${chatId}/messages` : '/api/chats/0/messages';
    
    const response = await apiFile.post<Message>(
      endpoint,
      formData
    );
    return response.data;
  },
  
};