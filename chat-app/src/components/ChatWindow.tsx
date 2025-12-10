// components/ChatWindow.tsx
import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Info, X } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { chatApi } from '../services/api';
import type { Message, ResponseMode } from '../types';
import { websocketService } from '../services/websocket'; // Импортируем WebSocket

interface ChatWindowProps {
  chat: {
    id: string;
    messages: Array<{
      id: string;
      content: string;
      role: 'user' | 'assistant';
      created_at: string;
    }>;
  };
}

const ChatWindow: React.FC<ChatWindowProps> = ({ chat }) => {
  const [message, setMessage] = useState('');
  const [responseMode, setResponseMode] = useState<ResponseMode>('full');
  const [isSending, setIsSending] = useState(false); // Новое состояние
  const [showInfo, setShowInfo] = useState(false);
  const { addMessage, currentChat, setLoading, addFileToCurrentCha, setChats } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [processingStages, setProcessingStages] = useState<Array<{
    stage: number;
    title: string;
    description: string;
    progress: number;
    completed: boolean;
  }>>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Прокрутка к последнему сообщению

    useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat.messages]);

//  useEffect(() => {
//   const callbacks = {
//     onConnected: () => {
//       console.log('✅ WebSocket подключен');
//     },
    
//     onDisconnected: () => {
//       console.log('🔌 WebSocket отключен');
//     },
    
//     onProcessingStarted: (data: any) => {
//       console.log('🚀 Началась обработка:', data);
//       setIsProcessing(true);
//     },
    
//     onNewMessage: (newMessage: Message) => {
//       console.log('📨 Получено новое сообщение через WebSocket:', newMessage);
      
//       // Проверяем, что сообщение для текущего чата
//       if (currentChat && String(currentChat.id) === String(newMessage.chat_id)) {
//         addMessage(newMessage);
        
//         // Если это ответ от AI, прекращаем обработку
//         if (newMessage.role === 'assistant') {
//           setIsProcessing(false);
//         }
//       }
//     },
    
//     onChatsUpdated: () => {
//       console.log('🔄 Обновляем список чатов через WebSocket');
//       // Обновляем список чатов
//       refreshChats();
//     },
    
//     onError: (error: string) => {
//       console.error('❌ WebSocket ошибка:', error);
//       setIsProcessing(false);
//     }
//   };
  
//   websocketService.connect(callbacks);
  
//   return () => {
//     websocketService.disconnect();
//   };
// }, [addMessage, currentChat]); // Добавьте currentChat в зависимости

  const refreshChats = async () => {
    try {
      const chats = await chatApi.getChats();
      setChats(chats);
    } catch (error) {
      console.error('Ошибка обновления чатов:', error);
    }
  };

  const handleSend = async () => {
  if (!message.trim() || !currentChat || isSending) return;

  console.log('Отправка сообщения в чат:', currentChat.id, 'сообщение:', message);

  const fileCount = currentChat.files.length;
  
  if (fileCount < 5) {
    alert(`Добавьте минимум 5 файлов. Сейчас добавлено: ${fileCount}`);
    return;
  }
  
  if (fileCount > 20) {
    alert(`Максимум можно добавить 20 файлов. Сейчас добавлено: ${fileCount}`);
    return;
  }
  
  setIsSending(true);
  setIsProcessing(true);
  try {
    //setLoading(true);

    if (!websocketService.isConnected()) {
        setValidationError('Нет подключения к серверу');
        setIsProcessing(false);
        return;
      }
    
    // Получаем файлы для отправки
    const filesToSend: File[] = [];
    
    // Проходим по всем файлам
    for (const chatFile of currentChat.files) {
      if (chatFile.file) {
        // Локальный файл - есть объект File
        filesToSend.push(chatFile.file);
      } else if (chatFile.filename) {
        // Файл с сервера - создаем "пустой" File объект
        // Просто чтобы отправить информацию о файле
        const emptyFile = new File([], chatFile.filename, {
          type: 'application/pdf',
          lastModified: Date.now()
        });
        
        // Добавляем custom property чтобы бэкенд понял, что это серверный файл
        (emptyFile as any).serverFileId = chatFile.id;
        (emptyFile as any).isServerFile = true;
        
        filesToSend.push(emptyFile);
      }
    }
    
    console.log('Файлов для отправки:', filesToSend.length);
    
    // Определяем chatId для отправки
    let chatIdForApi: number | null = null;
    
    if (currentChat.id.toString().startsWith('temp-')) {
      // Это временный чат - отправляем null
      chatIdForApi = null;
      console.log('Отправка в новый чат (temp)');
    } else {
      // Это существующий чат
      chatIdForApi = parseInt(currentChat.id.toString());
      console.log('Отправка в существующий чат ID:', chatIdForApi);
    }

    const clientId = websocketService.getClientId();
    
    // Отправляем сообщение на сервер
    const response = await chatApi.sendMessage(
      chatIdForApi?.toString(),
      message,
      responseMode,
      filesToSend,
      clientId
    );
    
    console.log('Ответ от сервера:', response);

    const userMessage: Message = {
        id: `temp-${Date.now()}`,
        chat_id: currentChat.id,
        content: message,
        role: 'user',
        created_at: new Date().toISOString(),
        mode: responseMode,
      };
      //addMessage(userMessage);
    
    // После успешной отправки:
    // 1. Очищаем поле ввода
    setMessage('');
    
    // 3. Перезагружаем чаты с сервера
    //const { loadChats } = useChat(); // Нужно получить loadChats из контекста
    
    // Если loadChats нет в useChat, добавьте его:
    // В ChatContext добавьте:
    // const loadChats = async () => { ... }
    // И экспортируйте из useChat
    
    // Временное решение - перезагружаем страницу чатов
    //window.location.reload(); // или лучше обновить состояние
    
  } catch (error) {
    console.error('Ошибка отправки сообщения:', error);
    alert('Ошибка отправки сообщения. Проверьте консоль.');
    setValidationError('Ошибка отправки сообщения');
      setIsProcessing(false);
  } finally {
    //setLoading(false);
    setIsSending(false);
  }
};

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Сообщения */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {chat.messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-2xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-gray-100 text-gray-800 rounded-bl-none'
              }`}
            >
              <div className="flex items-center space-x-2 mb-1">
                {msg.role === 'assistant' ? (
                  <Bot size={16} className="text-gray-500" />
                ) : (
                  <User size={16} className="text-blue-300" />
                )}
                <span className="text-xs font-medium">
                  {msg.role === 'assistant' ? 'AI Assistant' : 'Вы'}
                </span>
              </div>
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Поле ввода */}
      <div className="border-t border-gray-200 bg-white p-4">
        
        {/* Выбор режима ответа */}
        <div className="mb-3 flex items-center space-x-4">
          <span className="text-sm text-gray-600">Режим ответа:</span>
          <div className="flex space-x-2">
            <button
              onClick={() => setResponseMode('full')}
              className={`px-3 py-1 text-sm rounded-lg ${
                responseMode === 'full'
                  ? 'bg-blue-100 text-blue-700 border border-blue-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Полный
            </button>
            <button
              onClick={() => setResponseMode('brief')}
              className={`px-3 py-1 text-sm rounded-lg ${
                responseMode === 'brief'
                  ? 'bg-blue-100 text-blue-700 border border-blue-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Сокращенный
            </button>
          </div>
        </div>

        {/* Поле ввода сообщения */}
        <div className="flex items-start space-x-3"> {/* Изменил items-end на items-start */}
          <div className="flex-1 border border-gray-300 rounded-xl focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Введите вашу тему исследования..."
              className="w-full px-4 py-3 resize-none focus:outline-none rounded-xl"
              rows={3}
            />
          </div>
          
          {/* Контейнер для кнопок (информация + отправка) */}
          <div className="flex flex-col items-center space-y-2 h-full">
            {/* Кнопка информации - НАД кнопкой отправки */}
            <button
              onClick={() => setShowInfo(true)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg flex-shrink-0"
              title="Информация"
            >
              <Info size={20} />
            </button>
            
            {/* Кнопка отправки */}
            <button
              onClick={handleSend}
              disabled={!message.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0 mt-auto" /* mt-auto для прижатия к низу */
            >
              <Send size={20} />
            </button>
          </div>
        </div>

        {/* Окно информации */}
        {showInfo && (
          <div className="absolute right-4 bottom-24 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
            <div className="p-4">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-semibold text-gray-800">Информация</h3>
                <button
                  onClick={() => setShowInfo(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X size={18} />
                </button>
              </div>
              <div className="space-y-2 text-sm text-gray-600">
                <p>1. Система создает литературный обзор на основе загруженных PDF файлов</p>
                <p>2. Вы можете выбирать между полным и сокращенным форматом ответа</p>
                <p>3. Все загруженные файлы сохраняются и могут быть использованы повторно</p>
                <p>4. Для начала работы введите тему исследования и загрузите PDF файлы</p>
                <p>5. Каждый чат сохраняет историю переписки и прикрепленные файлы</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatWindow;
