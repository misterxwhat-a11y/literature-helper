// components/FileList.tsx
import React, { useCallback, useState } from 'react';
import { FileText, X, Upload, Trash2, AlertCircle } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { useChatStore } from '../store/chatStore';
import type { ChatFile } from '../types';

const FileList: React.FC = () => {
  const { currentChat, addFileToCurrentChat, removeFileFromCurrentChat, clearCurrentChatFiles } = useChatStore();
  const [duplicateError, setDuplicateError] = useState<string | null>(null); // Новое состояние для ошибки

  const onDrop = useCallback((acceptedFiles: File[]) => {

    const existingFileNames = currentChat?.files.map(file => 
    file.filename || ''
        ).filter(name => name !== '') || [];
        
    const duplicates: string[] = [];
    const newFiles: File[] = [];

    acceptedFiles.forEach(file => {
    const fileName = file.name;
    
    if (existingFileNames.includes(fileName)) {
      // Найден дубликат
      duplicates.push(fileName);
    } else {
      // Уникальный файл
      newFiles.push(file);
    }
  });
  
  // Если есть дубликаты, показываем ошибку
  if (duplicates.length > 0) {
    const errorMessage = duplicates.length === 1 
      ? `Файл "${duplicates[0]}" уже добавлен`
      : `${duplicates.length} файла(ов) уже добавлены: ${duplicates.slice(0, 3).join(', ')}${duplicates.length > 3 ? '...' : ''}`;
    
    setDuplicateError(errorMessage);
    
    // Автоматически скрываем ошибку через 2 секунды
    setTimeout(() => {
      setDuplicateError(null);
    }, 2000);
  }
    
    newFiles.forEach(file => {
      if (file.type === 'application/pdf') {
        const chatFile: ChatFile = {
          id: 0, // временный ID для локальных файлов
          chat_id: currentChat?.id || 0,
          filename: file.name, // используем filename для совместимости
          file_size: file.size, // используем file_size для совместимости
          uploaded_at: new Date().toISOString(),
          file: file, // сохраняем объект File для отправки
          status: 'pending',
          // Для обратной совместимости добавляем name и size
          name: file.name,
          size: file.size,
        };
        addFileToCurrentChat(chatFile);
        
        // Симуляция загрузки с прогрессом
        simulateUpload(chatFile);
      }
    });
  }, [addFileToCurrentChat, currentChat]);

  const simulateUpload = (chatFile: ChatFile) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += 10;
      // В реальном приложении здесь было бы обновление прогресса
      if (progress >= 100) {
        clearInterval(interval);
      }
    }, 100);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true,
  });

  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return '';
    }
  };

  if (!currentChat) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Заголовок */}
      <div className="p-4 border-b">
        <h2 className="font-semibold text-gray-800 flex items-center">
          <FileText size={18} className="mr-2" />
          Файлы ({currentChat.files.length})
        </h2>
      </div>
      {/* Уведомление об ошибке дубликатов */}
    {duplicateError && (
      <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg animate-fade-in">
        <div className="flex items-center space-x-2 text-red-700">
          <AlertCircle size={16} />
          <span className="text-sm font-medium">{duplicateError}</span>
        </div>
        <div className="text-xs text-red-600 mt-1">
          Файлы с одинаковыми названиями не будут добавлены
        </div>
      </div>
    )}

      {/* Область загрузки */}
      <div
        {...getRootProps()}
        className={`m-4 p-6 border-2 border-dashed rounded-xl text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
        }`}
      >
        <input {...getInputProps()} />
        <Upload size={32} className="mx-auto mb-3 text-gray-400" />
        <p className="text-gray-600 mb-1">
          {isDragActive ? 'Отпустите файлы здесь...' : 'Перетащите PDF файлы сюда или кликните'}
        </p>
        <p className="text-sm text-gray-500">Поддерживаются только PDF файлы</p>
      </div>

      {/* Список файлов */}
      <div className="flex-1 overflow-y-auto px-4">
        {currentChat.files.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileText size={48} className="mx-auto mb-3 text-gray-300" />
            <p>Файлы не добавлены</p>
          </div>
        ) : (
          <div className="space-y-3 pb-4">
            {currentChat.files.map((file: ChatFile, index: number) => {
              // Для совместимости: используем filename, если есть, иначе name
              const fileName = file.filename || file.name || 'Без имени';
              // Для совместимости: используем file_size, если есть, иначе size
              const fileSize = file.file_size || file.size || 0;
              
              return (
                <div
                  key={file.id ? `file-${file.id}` : `temp-${index}-${fileName}`}
                  className="bg-gray-50 rounded-lg p-3 flex items-start space-x-3"
                >
                  <FileText size={20} className="text-red-500 flex-shrink-0 mt-1" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {index + 1}. {fileName}
                      </span>
                      <button
                        onClick={() => {
                            // Если у файла есть ID (уже сохранен на сервере) - удаляем по ID
                            // Если нет ID (локальный файл) - удаляем по имени
                            const identifier = file.id && file.id > 0 ? file.id : fileName;
                            removeFileFromCurrentChat(identifier);
                        }}
                        className="text-gray-400 hover:text-red-500"
                        title="Удалить файл"
                        >
                        <X size={16} />
                        </button>
                    </div>
                    <div className="text-xs text-gray-500">
                      {formatFileSize(fileSize)}
                    </div>
                    {file.status === 'uploading' && file.progress !== undefined && file.progress < 100 && (
                      <div className="mt-2">
                        <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 transition-all"
                            style={{ width: `${file.progress}%` }}
                          />
                        </div>
                        <div className="text-xs text-gray-500 mt-1 text-right">
                          {file.progress}%
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Кнопка удалить все */}
      {currentChat.files.length > 0 && (
        <div className="p-4 border-t">
          <button
            onClick={clearCurrentChatFiles}
            className="w-full py-2 px-4 text-red-600 hover:bg-red-50 border border-red-200 rounded-lg flex items-center justify-center space-x-2 transition-colors"
          >
            <Trash2 size={16} />
            <span>Удалить все файлы</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default FileList;