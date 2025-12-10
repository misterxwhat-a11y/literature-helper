// App.tsx - Главный компонент приложения
import React, { useEffect } from 'react';
import { useChatStore } from './store/chatStore';
import { chatApi } from './services/api';
import ChatList from './components/ChatList';
import ChatWindow from './components/ChatWindow';
import FileList from './components/FileList';
import { MessageSquare, Menu, X } from 'lucide-react';
import { websocketService } from './services/websocket';

function App() {
  const { addMessage, chats, setChats, currentChat, setCurrentChat, setLoading, setError } = useChatStore();
  const [isChatListVisible, setIsChatListVisible] = React.useState(true);
  const [isFileListVisible, setIsFileListVisible] = React.useState(true);

  // Загружаем список чатов при старте
  useEffect(() => {
    loadChats();
  }, []);

  useEffect(() => {
    console.log('🚀 Загружаем App, подключаем WebSocket...');
    
    const callbacks = {
      onConnected: () => {
        console.log('✅ WebSocket подключен глобально (в App.tsx)');
      },
      
      onDisconnected: () => {
        console.log('🔌 WebSocket отключен');
      },
      
      onNewMessage: (message: any) => {
        console.log('📨 Получено сообщение через WebSocket:', message);
        // Добавляем сообщение в хранилище
        addMessage(message);
      },
      
      onChatsUpdated: () => {
        console.log('🔄 Обновляем список чатов через WebSocket');
        // Загружаем обновленный список чатов
        refreshChats();
      },
      
      onError: (error: string) => {
        console.error('❌ WebSocket ошибка в App.tsx:', error);
      }
    };
    
    websocketService.connect(callbacks);
    
    // НЕ ОТКЛЮЧАЕМ при размонтировании App!
    // App почти никогда не размонтируется (только при закрытии вкладки)
    // return () => {
    //   websocketService.disconnect(); // ← ЗАКОММЕНТИРОВАТЬ!
    // };
    
  }, []);

  const refreshChats = async () => {
      try {
        const chats = await chatApi.getChats();
        setChats(chats);
      } catch (error) {
        console.error('Ошибка обновления чатов:', error);
      }
    };

  const loadChats = async () => {
  try {
    setLoading(true);
    // Загружаем чаты с сервера
    const fetchedChats = await chatApi.getChats();
    setChats(fetchedChats);
    
    // Если есть чаты, загружаем первый
    if (fetchedChats.length > 0) {
      await loadChat(fetchedChats[0].id.toString());
    } else {
      // Если чатов нет, создаем локальный временный чат
      const newChat = {
        id: `temp-${Date.now()}`,
        title: 'Новая тема',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
        files: [],
      };
      setCurrentChat(newChat);
    }
  } catch (error) {
    setError('Ошибка загрузки чатов');
    console.error(error);
  } finally {
    setLoading(false);
  }
};

  const loadChat = async (chatId: string) => {
  // Если это временный чат, просто устанавливаем его
  if (chatId.startsWith('temp-')) {
    // Ищем временный чат среди уже созданных
    const existingTempChat = chats.find(chat => chat.id === chatId);
    if (existingTempChat) {
      // Если нашли, загружаем его детали
      const tempChatDetail = {
        ...existingTempChat,
        messages: [],
        files: []
      };
      setCurrentChat(tempChatDetail);
    } else {
      // Создаем новый временный чат
      const newChat = {
        id: chatId,
        title: 'Новая тема',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
        files: [],
      };
      setCurrentChat(newChat);
    }
    return;
  }
  
  try {
    setLoading(true);
    // Загружаем чат с сервера
    const chat = await chatApi.getChat(chatId);
    setCurrentChat(chat);
    
    // Обновляем заголовок в хедере
    // (если у вас есть состояние для заголовка)
  } catch (error) {
    console.error('Ошибка загрузки чата:', error);
    // Можно показать уведомление
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* Шапка */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsChatListVisible(!isChatListVisible)}
            className="p-2 hover:bg-gray-100 rounded-lg"
            title={isChatListVisible ? "Скрыть список чатов" : "Показать список чатов"}
          >
            {isChatListVisible ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="flex items-center space-x-2">
            <img src="/logo.png" alt="Логотип" className="h-8 w-8" />
            <h1 className="text-xl font-semibold text-gray-800">Literature Observe Helper</h1>
          </div>
        </div>
        <div className="text-sm text-gray-500">
          {currentChat?.title || 'Выберите чат'}
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsFileListVisible(!isFileListVisible)}
            className="p-2 hover:bg-gray-100 rounded-lg"
            title={isFileListVisible ? "Скрыть список файлов" : "Показать список файлов"}
          >
            {isFileListVisible ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Основной контент */}
      <div className="flex flex-1 overflow-hidden">
        {/* Левая панель - Список чатов */}
        {isChatListVisible && (
          <div className="w-64 border-r border-gray-200 bg-white flex-shrink-0 overflow-y-auto">
            <ChatList chats={chats} onSelectChat={loadChat} />
          </div>
        )}

        {/* Центральная часть - Чат */}
        <div className="flex-1 overflow-hidden">
          {currentChat ? (
            <ChatWindow chat={currentChat} />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-500">
              <div className="text-center">
                <MessageSquare size={48} className="mx-auto mb-4 text-gray-300" />
                <p>Выберите чат или создайте новую тему</p>
              </div>
            </div>
          )}
        </div>

        {/* Правая панель - Список файлов */}
        {isFileListVisible && currentChat && (
          <div className="w-72 border-l border-gray-200 bg-white flex-shrink-0 overflow-y-auto">
            <FileList />
          </div>
        )}
      </div>

      {/* Индикатор загрузки */}
      {useChatStore((state: { isLoading: any; }) => state.isLoading) && (
        <div className="absolute inset-0 bg-black bg-opacity-10 flex items-center justify-center z-50">
          <div className="bg-white p-4 rounded-lg shadow-lg">Загрузка...</div>
        </div>
      )}
    </div>
  );
}

export default App;