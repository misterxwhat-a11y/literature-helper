import json
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from typing import Dict, List, Tuple
import hashlib
import re

# --- КОНФИГУРАЦИЯ ---
CHUNK_SIZE = 700  # символов на чанк
CHUNK_OVERLAP = 100  # перекрытие между чанками
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # хорошая для русского/английского

def split_into_chunks(text: str, source_id: int) -> List[Dict]:
    """
    Разбивает текст на перекрывающиеся чанки.
    Возвращает список словарей с чанками и метаданными.
    """
    chunks = []
    
    # Простое чанкование по количеству символов с перекрытием
    start = 0
    chunk_num = 1
    
    while start < len(text):
        # Определяем конец чанка
        end = start + CHUNK_SIZE
        
        # Если это не последний чанк и мы не на границе слова, пытаемся найти границу предложения
        if end < len(text):
            # Ищем точку, пробел или перевод строки для более аккуратного разрыва
            for i in range(min(50, len(text) - end)):  # смотрим вперед на 50 символов
                if text[end + i] in {'.', '!', '?', '\n', ' ', ';', ','}:
                    end = end + i + 1
                    break
        
        chunk_text = text[start:end].strip()
        
        if chunk_text and len(chunk_text) > 50:  # Игнорируем слишком короткие чанки
            # Приблизительный номер страницы (грубая оценка)
            approx_page = (start // 2000) + 1  # предполагаем ~2000 символов на страницу
            
            chunks.append({
                "source_id": source_id,
                "chunk_num": chunk_num,
                "approx_page": approx_page,
                "text": chunk_text,
                "start_char": start,
                "end_char": end
            })
            chunk_num += 1
        
        # Сдвигаем стартовую позицию с перекрытием
        start = end - CHUNK_OVERLAP
    
    return chunks

def create_vector_db(relevant_texts: Dict[int, str], collection_name: str = "research_papers") -> chromadb.Collection:
    """
    Создает векторную базу данных из релевантных текстов.
    Возвращает коллекцию ChromaDB.
    """
    
    print("Инициализация модели для эмбеддингов...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    
    print("Настройка ChromaDB...")
    # Создаем персистентную базу в папке chroma_db
    client = chromadb.PersistentClient(path="./chroma_db")
    
    # Удаляем старую коллекцию если существует
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    # Создаем новую коллекцию
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}  # используем косинусное расстояние
    )
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    print("Обработка источников и создание чанков...")
    for source_id, text in relevant_texts.items():
        chunks = split_into_chunks(text, source_id)
        
        for chunk in chunks:
            chunk_id = f"{source_id}_{chunk['chunk_num']}"
            
            all_chunks.append(chunk["text"])
            all_metadatas.append({
                "source_id": source_id,
                "chunk_num": chunk["chunk_num"],
                "approx_page": chunk["approx_page"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"]
            })
            all_ids.append(chunk_id)
        
        print(f"  Источник #{source_id}: создано {len(chunks)} чанков")
    
    print(f"Всего чанков: {len(all_chunks)}")
    
    if not all_chunks:
        print("Ошибка: нет чанков для обработки!")
        return collection
    
    print("Создание эмбеддингов...")
    # Создаем эмбеддинги для всех чанков
    embeddings = embedding_model.encode(all_chunks, show_progress_bar=True, convert_to_numpy=True)
    
    print("Добавление в векторную базу...")
    # Добавляем в коллекцию батчами (ограничение ChromaDB)
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        end_idx = min(i + batch_size, len(all_chunks))
        
        collection.add(
            embeddings=embeddings[i:end_idx].tolist(),
            documents=all_chunks[i:end_idx],
            metadatas=all_metadatas[i:end_idx],
            ids=all_ids[i:end_idx]
        )
        
        print(f"  Добавлено {end_idx}/{len(all_chunks)} чанков")
    
    print(f"Векторная база создана. Коллекция: {collection_name}")
    print(f"Всего документов: {collection.count()}")
    
    return collection

def search_similar_chunks(collection: chromadb.Collection, query: str, n_results: int = 5) -> List[Dict]:
    """
    Ищет похожие чанки по семантическому запросу.
    """
    # Используем ту же модель для эмбеддингов
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    
    # Создаем эмбеддинг для запроса
    query_embedding = embedding_model.encode([query], convert_to_numpy=True)
    
    # Ищем похожие чанки
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    
    # Форматируем результаты
    similar_chunks = []
    if results['documents']:
        for i in range(len(results['documents'][0])):
            similar_chunks.append({
                "text": results['documents'][0][i],
                "source_id": results['metadatas'][0][i]["source_id"],
                "approx_page": results['metadatas'][0][i]["approx_page"],
                "chunk_num": results['metadatas'][0][i]["chunk_num"],
                "similarity_score": 1 - results['distances'][0][i]  # преобразуем расстояние в сходство
            })
    
    return similar_chunks

def initial_vectorizing():
    print("=" * 50)
    print("ЭТАП 3: Подготовка RAG базы знаний")
    print("=" * 50)
    
    # Загружаем данные из предыдущих этапов
    try:
        with open('relevant_texts.json', 'r', encoding='utf-8') as f:
            relevant_texts = json.load(f)
        # Конвертируем ключи обратно в int (JSON сохраняет как строки)
        relevant_texts = {int(k): v for k, v in relevant_texts.items()}
    except FileNotFoundError:
        print("Ошибка: файл relevant_texts.json не найден!")
        print("Сначала выполните Этапы 1-2")
        return
    
    print(f"Загружено {len(relevant_texts)} релевантных источников")
    print(f"Номера источников: {list(relevant_texts.keys())}")
    
    # Создаем векторную базу
    collection = create_vector_db(relevant_texts)
    
    # Сохраняем информацию о коллекции
    collection_info = {
        "collection_name": "research_papers",
        "num_sources": len(relevant_texts),
        "source_ids": list(relevant_texts.keys()),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL
    }
    
    with open('vector_db_info.json', 'w', encoding='utf-8') as f:
        json.dump(collection_info, f, indent=2, ensure_ascii=False)
    
    # print("\nТест поиска (опционально)...")
    # test_query = "методология исследования"
    # test_results = search_similar_chunks(collection, test_query, n_results=3)
    
    # if test_results:
    #     print(f"Тестовый запрос: '{test_query}'")
    #     for i, result in enumerate(test_results, 1):
    #         print(f"\nРезультат {i}:")
    #         print(f"  Источник: #{result['source_id']} (стр.~{result['approx_page']})")
    #         print(f"  Сходство: {result['similarity_score']:.3f}")
    #         print(f"  Текст: {result['text'][:150]}...")
    # else:
    #     print("Тестовый поиск не дал результатов")
    
    print("\n" + "=" * 50)
    print("Этап 3 завершен!")
    print(f"Векторная база сохранена в папке: ./chroma_db/")
    print(f"Информация о базе: vector_db_info.json")

    return "Векторизация успешно завершена, переход к генерации обзора"