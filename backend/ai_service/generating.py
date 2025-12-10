import json
from typing import Dict, List, Tuple
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import chromadb
import re
import config as cn

client = OpenAI(api_key=cn.DEEPSEEK_API_KEY, base_url="https://openrouter.ai/api/v1")

def extract_citations(text: str) -> List[Tuple[int, int]]:
    """
    Извлекает все цитирования из текста в формате [X, p. Y].
    Возвращает список кортежей (source_id, approx_page).
    """
    citations = []
    
    # Ищем паттерны типа [X, p. Y]
    patterns = [
        r'\[#(\d+),\s*p\.~(\d+)\]',
        r'\[p\.~(\d+),\s*#(\d+)\]',
        r'\[#(\d+)\]',  # только номер источника
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) == 2:
                if 'p.' in pattern:  # первый паттерн
                    source_id = int(match[0])
                    page = int(match[1])
                else:  # второй паттерн
                    page = int(match[0])
                    source_id = int(match[1])
                citations.append((source_id, page))
            elif len(match) == 1:  # только номер источника
                citations.append((int(match[0]), 0))
    
    return list(set(citations))  # Убираем дубликаты

def search_in_vector_db(query: str, n_results: int = 5) -> List[Dict]:
    """
    Ищет релевантные чанки в векторной базе.
    """
    try:
        client = chromadb.PersistentClient(path="./chroma_db")
        collection = client.get_collection("research_papers")
    except:
        print("Ошибка: векторная база не найдена!")
        return []
    
    embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    query_embedding = embedding_model.encode([query], convert_to_numpy=True)
    
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    
    similar_chunks = []
    if results['documents']:
        for i in range(len(results['documents'][0])):
            similar_chunks.append({
                "text": results['documents'][0][i],
                "source_id": results['metadatas'][0][i]["source_id"],
                "approx_page": results['metadatas'][0][i]["approx_page"]
            })
    
    return similar_chunks

def call_deepseek(prompt: str, max_tokens: int = 2000, temperature: float = 1.0) -> str:
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-v3.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        result = response.choices[0].message.content.strip()
        return result
    except Exception as e:
        print(f"Ошибка оценки релевантности: {e}")
        return ""

def generate_compact_review(RESEARCH_TOPIC) -> Tuple[str, List[int], List[int]]:
    """
    Генерирует компактный аналитический обзор без явных разделов.
    """
    print("=" * 50)
    print("Генерация компактного литературного обзора (500-600 слов)")
    print("=" * 50)
    
    # 1. Сначала собираем ключевую информацию из источников
    print("\n[Шаг 1] Сбор ключевой информации из источников...")
    
    # Ищем информацию по ключевым аспектам
    search_queries = [
        "теория концепция подход",
        "методология исследование метод",
        "дискуссия противоречие разногласие",
        "хронология развитие история эволюция темы",
        "результат вывод исследование",
        "пробел ограничение"
    ]
    
    all_relevant_chunks = []
    for query in search_queries:
        chunks = search_in_vector_db(query, n_results=4)
        all_relevant_chunks.extend(chunks)
        print(f"  Поиск '{query}': найдено {len(chunks)} фрагментов")
    
    # Убираем дубликаты (по source_id и approx_page)
    unique_chunks = {}
    for chunk in all_relevant_chunks:
        key = (chunk['source_id'], chunk['approx_page'])
        if key not in unique_chunks:
            unique_chunks[key] = chunk
    
    # Формируем контекст для генерации
    context_chunks = []
    for chunk in list(unique_chunks.values())[:20]:  # Ограничиваем 20 ключевыми фрагментами
        context_chunks.append(
            f"[#{chunk['source_id']}, p.~{chunk['approx_page']}]: {chunk['text'][:400]}"
        )
    
    context = "\n\n".join(context_chunks)
    print(len(context))
    
    # 2. Генерируем единый компактный обзор
    print("\n[Шаг 2] Генерация единого аналитического обзора...")
    
    prompt = f'''Тема исследования: "{RESEARCH_TOPIC}"

На основе следующих источников напиши КОМПАКТНЫЙ аналитический литературный обзор (500-600 слов).
Обзор должен быть ЕДИНЫМ связным текстом без явных разделов и подзаголовков.

ИСХОДНЫЕ ДАННЫЕ:
{context}

ТРЕБОВАНИЯ К СОДЕРЖАНИЮ (все должно быть органично вплетено в текст):
1. Выдели КЛЮЧЕВЫЕ ТЕОРИИ, КОНЦЕПЦИИ И ПОДХОДЫ в исследованиях темы
2. Проанализируй основные МЕТОДОЛОГИИ, используемые в исследованиях
3. Обозначь НАУЧНЫЕ ДИСКУССИИ И ПРОТИВОРЕЧИЯ между разными авторами/школами
4. Проследи ХРОНОЛОГИЧЕСКУЮ ДИНАМИКУ развития темы: как менялись фокусы исследований
5. Проведи СРАВНИТЕЛЬНЫЙ АНАЛИЗ подходов, выдели их сильные и слабые стороны
6. Четко ОБОСНУЙ ВЫЯВЛЕННЫЙ НАУЧНЫЙ ПРОБЕЛ (research gap) - что недостаточно изучено и почему это важно

СТИЛЬ И ФОРМАТ:
- Аналитический, академический стиль
- Текст должен быть связным, плавные переходы между мыслями
- Каждое утверждение подкрепляй ссылками в формате [X, p. Y] (где X - номер источник, Y - страница из источника)
- Не используй маркированные списки, подзаголовки, нумерацию разделов
- Объем: 500-600 слов
- Пиши как единое эссе, а не как структурированный отчет

Начни обзор с краткого введения в проблематику:'''
    
    review_text = call_deepseek(prompt, max_tokens=2500, temperature=1.5)
    
    # 3. Извлекаем использованные источники
    all_citations = extract_citations(review_text)
    used_source_ids = list(set([citation[0] for citation in all_citations if citation[0] > 0]))
    used_source_ids.sort()
    
    # 4. Определяем неиспользованные источники
    try:
        with open('relevant_texts.json', 'r', encoding='utf-8') as f:
            all_relevant = json.load(f)
        all_relevant = {int(k): v for k, v in all_relevant.items()}
        all_relevant_ids = list(all_relevant.keys())
    except:
        all_relevant_ids = []
    
    all_sources = set(all_relevant_ids)
    used_sources = set(used_source_ids)
    unused_sources = list(all_sources - used_sources)
    unused_sources.sort()
    
    print(f"\nСтатистика генерации:")
    print(f"- Длина обзора: {len(review_text)} символов (~{len(review_text.split())} слов)")
    print(f"- Использовано источников: {len(used_source_ids)}")
    print(f"- Не использовано: {len(unused_sources)}")
    
    return review_text, used_source_ids, unused_sources


def generate_full_review(RESEARCH_TOPIC) -> Tuple[str, List[int], List[int]]:
    """
    Генерирует полный аналитический обзор без явных разделов.
    """
    print("=" * 50)
    print("Генерация полного литературного обзора (800-1200 слов)")
    print("=" * 50)
    
    # 1. Сначала собираем ключевую информацию из источников
    print("\n[Шаг 1] Сбор ключевой информации из источников...")
    
    # Ищем информацию по ключевым аспектам
    search_queries = [
        "теория концепция подход",
        "методология исследование метод",
        "дискуссия противоречие разногласие",
        "хронология развитие история эволюция темы",
        "результат вывод исследование",
        "пробел ограничение"
    ]
    
    all_relevant_chunks = []
    for query in search_queries:
        chunks = search_in_vector_db(query, n_results=4)
        all_relevant_chunks.extend(chunks)
        print(f"  Поиск '{query}': найдено {len(chunks)} фрагментов")
    
    # Убираем дубликаты (по source_id и approx_page)
    unique_chunks = {}
    for chunk in all_relevant_chunks:
        key = (chunk['source_id'], chunk['approx_page'])
        if key not in unique_chunks:
            unique_chunks[key] = chunk
    
    # Формируем контекст для генерации
    context_chunks = []
    for chunk in list(unique_chunks.values())[:20]:  # Ограничиваем 20 ключевыми фрагментами
        context_chunks.append(
            f"[#{chunk['source_id']}, p.~{chunk['approx_page']}]: {chunk['text'][:400]}"
        )
    
    context = "\n\n".join(context_chunks)
    
    # 2. Генерируем единый компактный обзор
    print("\n[Шаг 2] Генерация единого аналитического обзора...")
    
    prompt = f'''Тема исследования: "{RESEARCH_TOPIC}"

На основе следующих источников напиши ПОЛНЫЙ аналитический литературный обзор (800-1200 слов).
Обзор должен быть ЕДИНЫМ связным текстом без явных разделов и подзаголовков.

ИСХОДНЫЕ ДАННЫЕ:
{context}

ТРЕБОВАНИЯ К СОДЕРЖАНИЮ (все должно быть органично вплетено в текст):
1. Выдели КЛЮЧЕВЫЕ ТЕОРИИ, КОНЦЕПЦИИ И ПОДХОДЫ в исследованиях темы
2. Проанализируй основные МЕТОДОЛОГИИ, используемые в исследованиях
3. Обозначь НАУЧНЫЕ ДИСКУССИИ И ПРОТИВОРЕЧИЯ между разными авторами/школами
4. Проследи ХРОНОЛОГИЧЕСКУЮ ДИНАМИКУ развития темы: как менялись фокусы исследований
5. Проведи СРАВНИТЕЛЬНЫЙ АНАЛИЗ подходов, выдели их сильные и слабые стороны
6. Четко ОБОСНУЙ ВЫЯВЛЕННЫЙ НАУЧНЫЙ ПРОБЕЛ (research gap) - что недостаточно изучено и почему это важно

СТИЛЬ И ФОРМАТ:
- Аналитический, академический стиль
- Текст должен быть связным, плавные переходы между мыслями
- Каждое утверждение подкрепляй ссылками в формате [X, p. Y] (где X - номер источник, Y - страница из источника)
- Не используй маркированные списки, подзаголовки, нумерацию разделов
- Объем: 800-1200 слов
- Пиши как единое эссе, а не как структурированный отчет

Начни обзор с краткого введения в проблематику:'''
    
    review_text = call_deepseek(prompt, max_tokens=2500, temperature=1.5)
    
    # 3. Извлекаем использованные источники
    all_citations = extract_citations(review_text)
    used_source_ids = list(set([citation[0] for citation in all_citations if citation[0] > 0]))
    used_source_ids.sort()
    
    # 4. Определяем неиспользованные источники
    try:
        with open('relevant_texts.json', 'r', encoding='utf-8') as f:
            all_relevant = json.load(f)
        all_relevant = {int(k): v for k, v in all_relevant.items()}
        all_relevant_ids = list(all_relevant.keys())
    except:
        all_relevant_ids = []
    
    all_sources = set(all_relevant_ids)
    used_sources = set(used_source_ids)
    unused_sources = list(all_sources - used_sources)
    unused_sources.sort()
    
    print(f"\nСтатистика генерации:")
    print(f"- Длина обзора: {len(review_text)} символов (~{len(review_text.split())} слов)")
    print(f"- Использовано источников: {len(used_source_ids)}")
    print(f"- Не использовано: {len(unused_sources)}")
    
    return review_text, used_source_ids, unused_sources

def save_results(review_text: str, used_sources: List[int], unused_sources: List[int]):
    """
    Сохраняет обзор и информацию.
    """
    print("\n" + "=" * 50)
    print("Сохранение результатов")
    print("=" * 50)
    
    # 1. Сохраняем компактный обзор
    review_filename = "literature_review.txt"
    
    # Добавляем заголовок и статистику
    word_count = len(review_text.split())
    #char_count = len(review_text)
    
    final_text = f"{review_text}"
    
    with open(review_filename, 'w', encoding='utf-8') as f:
        f.write(final_text)
    
    print(f"Обзор сохранен в: {review_filename}")
    print(f"Объем: ~{word_count} слов")


def initital_generating(RESEARCH_TOPIC, mode):
    """
    Главная функция для генерации компактного обзора.
    """
    print("Запуск генерации КОМПАКТНОГО\ПОЛНОГО литературного обзора")
    print(f"Тема: {RESEARCH_TOPIC}")
    
    # Генерация обзоров по режимам
    if mode != 'full':
        review_text, used_sources, unused_sources = generate_compact_review(RESEARCH_TOPIC)
    else:
        used_sources, unused_sources, review_text = generate_full_review(RESEARCH_TOPIC)
    
    if not review_text or len(review_text) < 300:
        print("\nОШИБКА: не удалось сгенерировать обзор!")
        return
    
    # Сохранение результатов
    save_results(review_text, used_sources, unused_sources)
    
    print("\n" + "=" * 50)
    print("ГЕНЕРАЦИЯ ОБЗОРА ЗАВЕРШЕНА!")
    print("=" * 50)

    return review_text

def rewrite_review_with_instruction(original_review: str, 
                                
                                   user_instruction: str,
                                   ) -> str:
    """
    Переписывает существующий обзор по новой инструкции пользователя.
    """
    print("\n" + "=" * 50)
    print("ПЕРЕПИСЫВАНИЕ ОБЗОРА ПО ИНСТРУКЦИИ")
    print("=" * 50)
    print(f"Инструкция: {user_instruction}")
    
    # Создаем улучшенный промпт для перезаписи
    rewrite_prompt = f'''

ТЕКУЩИЙ ОБЗОР:
{original_review}

ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ ДЛЯ ИЗМЕНЕНИЯ:
{user_instruction}

ЗАДАЧА: Переработай литературный обзор, учитывая инструкцию пользователя.

КОНКРЕТНЫЕ ТРЕБОВАНИЯ:
1. Сохрани исходный объем и академический стиль
2. Сохрани ВСЕ цитирования источников в исходном формате [X, p. Y] (где X - номер источник, Y - страница из источника)
3. Учти инструкцию пользователя: {user_instruction}
4. Если инструкция касается конкретной части - измени именно её, сохраняя структуру остального
5. Если нужно переписать весь обзор - сделай это, сохранив ключевые аналитические моменты
6. Не выдумывай новые источники, используй только указанные

ПЕРЕРАБОТАННЫЙ ОБЗОР:'''
    
    new_review = call_deepseek(rewrite_prompt, max_tokens=2000)
    
    return new_review