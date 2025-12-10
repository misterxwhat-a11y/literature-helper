import os
import PyPDF2
import openai
from typing import Dict, List, Tuple
from openai import OpenAI
import json
from pathlib import Path

import config as cn

BASE_DIR = Path(__file__).parent.parent  # поднимаемся из ai_service в backend
PDF_FOLDER = BASE_DIR / "uploads"

client = OpenAI(api_key=cn.DEEPSEEK_API_KEY, base_url="https://openrouter.ai/api/v1")

def extract_text_from_pdf(pdf_path: str) -> str:
    """Извлекает весь текст из PDF файла."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Ошибка чтения {pdf_path}: {e}")
    return text

def get_smart_text_sample(text: str, sample_size: int = 1500) -> str:
    """
    Берет текст из разных частей документа для лучшего понимания содержания.
    """
    text_len = len(text)
    
    if text_len <= sample_size:
        return text
    
    # Берем части из начала, середины и конца
    chunk_size = sample_size // 3
    
    # 1. Из начала (после возможных титульных страниц) - пропускаем первые 500 символов
    start_idx = min(500, text_len // 10)
    part1 = text[start_idx:start_idx + chunk_size]
    
    # 2. Из середины
    middle_start = text_len // 2 - chunk_size // 2
    part2 = text[middle_start:middle_start + chunk_size]
    
    # 3. Из конца (до списка литературы) - берем за 1000 символов до конца
    end_start = max(text_len - 1000 - chunk_size, text_len // 2)
    part3 = text[end_start:end_start + chunk_size]
    
    return f"{part1}\n[...]\n{part2}\n[...]\n{part3}"

def get_article_summary(text: str) -> str:
    """Получает свертку (основную тему) статьи из первых 1000 символов."""
    first_chunk = get_smart_text_sample(text)
    prompt = f"В одном предложении сформулируй основную тему этого научного текста: {first_chunk}"
    
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-v3.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Ошибка получения summary: {e}")
        return ""

def assess_relevance(topic: str, summary: str) -> int:
    """Оценивает релевантность summary теме исследования. Возвращает оценку 0-10."""
    if not summary:
        return 0
        
    prompt = f"""Оцени от 0 до 10, насколько следующая тема статьи релевантна теме исследования "{topic}".
Тема статьи: {summary}
Ответь ТОЛЬКО числом от 0 до 10."""
    
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-v3.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=3
        )
        score = response.choices[0].message.content.strip()
        return int(score) if score.isdigit() else 0
    except Exception as e:
        print(f"Ошибка оценки релевантности: {e}")
        return 0

# --- ОСНОВНАЯ ЛОГИКА ---
def process_pdfs(folder_path: str, research_topic: str, actual_files) -> Tuple[Dict[int, str], List[int]]:
    """
    Обрабатывает все PDF в папке, возвращает:
    - relevant_texts: словарь {номер_файла: полный_текст}
    - irrelevant_files: список номеров нерелевантных файлов
    """
    # Получаем список PDF файлов
    pdf_files_s = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

    pdf_files = [x for x in actual_files if x in pdf_files_s]
    print(actual_files)
    if not pdf_files:
        print(f"В папке {folder_path} не найдено PDF файлов")
        return {}, []
    
    print(f"Найдено {len(pdf_files)} PDF файлов")
    
    relevant_texts = {}
    irrelevant_files = []
    
    for idx, pdf_file in enumerate(pdf_files, start=1):
        file_path = os.path.join(folder_path, pdf_file)
        print(f"\nОбрабатываю файл #{idx}: {pdf_file}")
        
        # 1. Извлекаем текст
        text = extract_text_from_pdf(file_path)
        if not text:
            print(f"  Не удалось извлечь текст, пропускаю")
            irrelevant_files.append(idx)
            continue
            
        # 2. Получаем свертку (summary)
        summary = get_article_summary(text)
        print(f"  Тема статьи: {summary}")
        
        # 3. Оцениваем релевантность
        score = assess_relevance(research_topic, summary)
        print(f"  Оценка релевантности: {score}/10")
        
        # 4. Фильтруем (порог = 7)
        if score >= 7:
            relevant_texts[idx] = text
            print(f"  ✓ Сохранен как релевантный")
        else:
            irrelevant_files.append(idx)
            print(f"  ✗ Отклонен как нерелевантный")
    
    return relevant_texts, irrelevant_files


def initial_analyzis(RESEARCH_TOPIC, actual_files):
    relevant, irrelevant = process_pdfs(PDF_FOLDER, RESEARCH_TOPIC, actual_files)

    with open('relevant_texts.json', 'w', encoding='utf-8') as f:
        json.dump(relevant, f, ensure_ascii=False, indent=2)
    with open('irrelevant_files.json', 'w', encoding='utf-8') as f:
        json.dump(irrelevant, f, indent=2)

    return f"""
РЕЗУЛЬТАТ:
Релевантных источников: {len(relevant)} (номера: {list(relevant.keys())})
Нерелевантных источников: {len(irrelevant)} (номера: {irrelevant})
            """

# pdf_files = [f for f in os.listdir(UPLOADS_DIR) if f.lower().endswith('.pdf')]