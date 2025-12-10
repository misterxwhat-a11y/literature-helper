// components/ChatList.tsx
import React from 'react';
import { Plus, MessageSquare } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import type { Chat } from '../types';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

interface ChatListProps {
  chats: Chat[];
  onSelectChat: (chatId: string) => void;
}

const ChatList: React.FC<ChatListProps> = ({ chats, onSelectChat }) => {
  const { createNewChat, currentChat } = useChatStore();

  const handleNewChat = () => {
    createNewChat();
  };

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'dd.MM.yyyy', { locale: ru });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Кнопка "Новая тема" */}
      <div className="p-4 border-b">
        <button
          onClick={handleNewChat}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg flex items-center justify-center space-x-2 transition-colors"
        >
          <Plus size={18} />
          <span>Новая тема</span>
        </button>
      </div>

      {/* Список чатов */}
      <div className="flex-1 overflow-y-auto">
        {chats.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <MessageSquare size={32} className="mx-auto mb-2 text-gray-300" />
            <p>Чатов пока нет</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {chats.map((chat) => (
              <li key={chat.id}>
                <button
                  onClick={() => onSelectChat(chat.id.toString())}
                  className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                    currentChat?.id === chat.id ? 'bg-blue-50 border-r-2 border-blue-600' : ''
                  }`}
                >
                  <div className="font-medium text-gray-900 truncate">
                    {chat.title}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {formatDate(chat.updated_at)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default ChatList;