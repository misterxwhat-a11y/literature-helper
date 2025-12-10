// store/chatStore.ts - Центральное хранилище состояния
import { create } from 'zustand';
import type { Chat, ChatDetail, ChatFile, Message, ResponseMode } from '../types';

interface ChatStore {
  // Состояние
  chats: Chat[];
  currentChat: ChatDetail | null;
  isLoading: boolean;
  error: string | null;
  
  // Действия (actions)
  setChats: (chats: Chat[]) => void;
  setCurrentChat: (chat: ChatDetail | null) => void;
  addMessage: (message: Message) => void;
  addFileToCurrentChat: (file: ChatFile) => void;
  removeFileFromCurrentChat: (fileName: string) => void;
  clearCurrentChatFiles: () => void;
  createNewChat: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

const initialChatDetail: Omit<ChatDetail, 'id' | 'created_at' | 'updated_at'> = {
  title: 'Новая тема',
  messages: [],
  files: [],
};

export const useChatStore = create<ChatStore>((set: (arg0: { (state: any): { currentChat: any; }; (state: any): { currentChat: any; }; (state: any): { currentChat: any; }; (state: any): { currentChat: any; }; chats?: any; currentChat?: any; isLoading?: any; error?: any; }) => void) => ({
  chats: [],
  currentChat: null,
  isLoading: false,
  error: null,
  
  setChats: (chats: any) => set({ chats }),
  
  setCurrentChat: (chat: any) => set({ currentChat: chat }),
  
  addMessage: (message: any) => 
    set((state) => ({
      currentChat: state.currentChat 
        ? {
            ...state.currentChat,
            messages: [...state.currentChat.messages, message],
          }
        : null,
    })),
  
  addFileToCurrentChat: (file: any) =>
    set((state) => ({
      currentChat: state.currentChat
        ? {
            ...state.currentChat,
            files: [...state.currentChat.files, file],
          }
        : null,
    })),
  
  removeFileFromCurrentChat: (fileIdOrName: string | number) =>
  set((state) => ({
    currentChat: state.currentChat
      ? {
          ...state.currentChat,
          files: state.currentChat.files.filter(f => {
            // Если передали ID (число) - удаляем по ID
            if (typeof fileIdOrName === 'number') {
              return f.id !== fileIdOrName;
            }
            // Если передали имя (string) - удаляем по имени
            return (f.filename || f.name) !== fileIdOrName;
          }),
        }
      : null,
  })),
  
  clearCurrentChatFiles: () =>
    set((state) => ({
      currentChat: state.currentChat
        ? { ...state.currentChat, files: [] }
        : null,
    })),
  
  createNewChat: () => {
    const newChat: ChatDetail = {
      id: `temp-${Date.now()}`,
      title: 'Новая тема',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [],
      files: [],
    };
    set({ currentChat: newChat });
  },
  
  setLoading: (loading: any) => set({ isLoading: loading }),
  setError: (error: any) => set({ error }),
}));