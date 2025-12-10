import type { Message } from '../types';

// Типы для WebSocket сообщений
export interface WebSocketMessage {
  type: 'message' | 'chats_updated' | 'processing_started' | 'error';
  [key: string]: any;
}

// Колбэки для обработки WebSocket событий
export interface WebSocketCallbacks {
  onNewMessage?: (message: Message) => void;
  onChatsUpdated?: () => void;
  onProcessingStarted?: (data: { chat_id: number }) => void;
  onError?: (error: string) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
  onConnecting?: () => void;
}

class WebSocketManager {
  private socket: WebSocket | null = null;
  private clientId: string = '';
  private callbacks: WebSocketCallbacks = {};
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectDelay: number = 1000;
  private isManuallyDisconnected: boolean = false;

  constructor() {
    this.generateClientId();
  }

  private generateClientId(): void {
    // Генерируем уникальный ID для клиента
    this.clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Получить clientId для отправки на сервер
  public getClientId(): string {
    return this.clientId;
  }

  // Проверить подключение
  public isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  // Подключиться к WebSocket
  public connect(callbacks: WebSocketCallbacks): void {
    if (this.isConnected()) {
      console.log('WebSocket уже подключен');
      return;
    }

    this.callbacks = callbacks;
    this.isManuallyDisconnected = false;
    
    // Уведомляем о начале подключения
    this.callbacks.onConnecting?.();

    try {
      // Определяем URL для WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname === 'localhost' ? 'localhost:8000' : window.location.host;
      const wsUrl = `${protocol}//${host}/ws/${this.clientId}`;
      
      console.log('Подключаемся к WebSocket:', wsUrl);
      
      this.socket = new WebSocket(wsUrl);
      this.setupEventListeners();
      
    } catch (error) {
      console.error('Ошибка создания WebSocket:', error);
      this.callbacks.onError?.('Ошибка создания соединения');
      this.attemptReconnect();
    }
  }

  private setupEventListeners(): void {
    if (!this.socket) return;

    this.socket.onopen = () => {
      console.log('✅ WebSocket подключен');
      this.reconnectAttempts = 0;
      this.callbacks.onConnected?.();
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        this.handleIncomingMessage(data);
      } catch (error) {
        console.error('Ошибка парсинга сообщения:', error, event.data);
      }
    };

    this.socket.onclose = (event: CloseEvent) => {
      console.log('🔌 WebSocket отключен:', event.code, event.reason);
      this.callbacks.onDisconnected?.();
      
      if (!this.isManuallyDisconnected && event.code !== 1000) {
        this.attemptReconnect();
      }
    };

    this.socket.onerror = (error: Event) => {
      console.error('❌ WebSocket ошибка детально:', error);
        console.error('WebSocket URL:', URL);
        console.error('readyState:', this.socket?.readyState);
        
        // Покажите больше информации
        const errorMessage = `WebSocket ошибка: ${error.type}. Статус: ${this.socket?.readyState}. 
        URL: ${URL}. Проверьте: 
        1. Запущен ли бэкенд на localhost:8000
        2. Поддерживает ли бэкенд WebSocket
        3. Нет ли проблем с CORS`;
        
        this.callbacks.onError?.(errorMessage);
    };
  }

  private handleIncomingMessage(data: WebSocketMessage): void {
    console.log('📨 Получено WebSocket сообщение:', data);
    
    switch (data.type) {
      case 'message':
        // Обработка нового сообщения
        if (data.message && typeof data.message === 'object') {
          const message: Message = {
            id: data.message.id,
            chat_id: data.message.chat_id,
            content: data.message.content,
            role: data.message.role,
            created_at: data.message.created_at,
            mode: data.message.mode
          };
          this.callbacks.onNewMessage?.(message);
        }
        break;
        
      case 'chats_updated':
        // Обновление списка чатов
        this.callbacks.onChatsUpdated?.();
        break;
        
      case 'processing_started':
        // Начало обработки сообщения
        this.callbacks.onProcessingStarted?.(data);
        break;
        
      case 'error':
        // Ошибка от сервера
        this.callbacks.onError?.(data.error || 'Неизвестная ошибка');
        break;
        
      default:
        console.warn('Неизвестный тип сообщения:', data.type);
    }
  }

  private attemptReconnect(): void {
    if (this.isManuallyDisconnected || this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Прекращены попытки переподключения');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000);
    
    console.log(`Попытка переподключения ${this.reconnectAttempts} через ${delay}ms`);
    
    setTimeout(() => {
      if (!this.isManuallyDisconnected) {
        this.connect(this.callbacks);
      }
    }, delay);
  }

  // Отправить сообщение через WebSocket (если нужно)
  public send(message: any): void {
    if (this.isConnected() && this.socket) {
      try {
        this.socket.send(JSON.stringify(message));
      } catch (error) {
        console.error('Ошибка отправки сообщения:', error);
      }
    } else {
      console.warn('WebSocket не подключен, сообщение не отправлено');
    }
  }

  // Отключиться от WebSocket
  public disconnect(): void {
    console.log('Отключаем WebSocket...');
    this.isManuallyDisconnected = true;
    
    if (this.socket) {
      this.socket.close(1000, 'Пользователь отключился');
      this.socket = null;
    }
  }
}

// Создаем и экспортируем singleton экземпляр
export const websocketService = new WebSocketManager();