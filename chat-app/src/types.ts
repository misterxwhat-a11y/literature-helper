// types.ts - Здесь определяем структуры данных
export interface Chat {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  chat_id: string;
  content: string;
  role: 'user' | 'assistant';
  created_at: string;
  mode?: 'full' | 'brief';
}

export interface ChatFile {
  id: number;
  chat_id: number;
  filename: string;
  file_size: number;
  uploaded_at: string;
  file?: File; // только для локальных файлов
  status?: 'pending' | 'uploading' | 'uploaded';
  progress?: number;
}

export interface ChatDetail extends Chat {
  messages: Message[];
  files: ChatFile[];
}

export type ResponseMode = 'full' | 'brief';