# Дополнительные техники улучшения качества транскрипции

## 1. Предобработка аудио с FFmpeg

### Базовая обработка телефонных записей
```bash
# Фильтрация частот телефонного канала и увеличение громкости
ffmpeg -i input.wav \
  -af "highpass=f=300,lowpass=f=3400,volume=1.8,dynaudnorm=f=150:g=15" \
  -ar 16000 -ac 1 output.wav
```

### Продвинутая очистка с шумоподавлением
```bash
# Скачать модель RNNoise для шумоподавления
wget https://github.com/GregorR/rnnoise-models/raw/master/bd.rnnn -O ./models/bd.rnnn

# Применить шумоподавление
ffmpeg -i input.wav \
  -af "arnndn=m=./models/bd.rnnn:mix=0.8,highpass=f=200,lowpass=f=4000,volume=2.0" \
  -ar 16000 -ac 1 clean_output.wav
```

### Многопроходная обработка для очень плохого качества
```bash
# Проход 1: Базовая очистка
ffmpeg -i input.wav -af "highpass=f=200,lowpass=f=4000" temp1.wav

# Проход 2: Шумоподавление  
ffmpeg -i temp1.wav -af "arnndn=m=./models/bd.rnnn" temp2.wav

# Проход 3: Нормализация и компрессия
sox temp2.wav -r 16k final_output.wav norm -0.5 compand 0.3,1 -90,-90,-70,-70,-60,-20,0,0 -5 0 0.2

rm temp1.wav temp2.wav
```

## 2. Параметры faster-whisper для прямого использования

```python
from faster_whisper import WhisperModel

# Оптимизированные параметры для телефонии
model = WhisperModel("small", device="cpu", compute_type="float32")

segments, info = model.transcribe(
    audio_path,
    language="ru",
    
    # Основные параметры качества
    beam_size=5,                        # Больше лучей = лучшее качество
    temperature=0.0,                    # Детерминированность
    
    # Промпт для контекста
    initial_prompt="Деловой телефонный разговор на русском языке между коллегами с четким произношением и правильной грамматикой.",
    
    # Контекст между сегментами
    condition_on_previous_text=True,
    
    # Пороги для плохого аудио
    no_speech_threshold=0.3,            # Снижено для чувствительности
    logprob_threshold=-0.8,             # Менее строгий фильтр
    compression_ratio_threshold=2.6,     # Защита от галлюцинаций
    
    # Временные метки
    word_timestamps=True,
    prepend_punctuations="\"'"¿([{-",
    append_punctuations="\"'.。,，!！?？:：")]}、",
    
    # Дополнительные опции
    vad_filter=True,                    # Фильтр активности голоса
    vad_parameters=dict(
        min_silence_duration_ms=500,    # Минимальная тишина
        speech_pad_ms=400               # Отступы вокруг речи
    )
)
```

## 3. Мониторинг и отладка качества

### Скрипт для анализа качества транскрипции
```python
import json
import statistics

def analyze_transcription_quality(segments_file):
    with open(segments_file, 'r') as f:
        segments = json.load(f)
    
    # Анализ уверенности модели
    avg_probs = []
    short_segments = 0
    long_pauses = 0
    
    for i, segment in enumerate(segments):
        if 'words' in segment:
            word_probs = [word.get('probability', 0) for word in segment['words']]
            if word_probs:
                avg_probs.extend(word_probs)
        
        # Детектирование проблем
        duration = segment['end'] - segment['start']
        if duration < 0.5:
            short_segments += 1
        
        if i > 0:
            pause = segment['start'] - segments[i-1]['end']
            if pause > 3.0:
                long_pauses += 1
    
    print(f"Средняя уверенность: {statistics.mean(avg_probs):.3f}")
    print(f"Коротких сегментов: {short_segments}")
    print(f"Длинных пауз: {long_pauses}")
    
    # Рекомендации
    if statistics.mean(avg_probs) < 0.8:
        print("⚠️ Низкая уверенность - улучшите качество аудио или промпты")
    if short_segments > len(segments) * 0.3:
        print("⚠️ Много коротких сегментов - увеличьте min_chunk_size")
```

### Автоматическая корректировка параметров
```python
def auto_tune_parameters(audio_file, initial_config):
    """Автоматически подбирает оптимальные параметры"""
    
    # Анализ аудио
    import librosa
    y, sr = librosa.load(audio_file)
    
    # Определение характеристик
    noise_level = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    speech_rate = len(librosa.onset.onset_detect(y, sr=sr)) / (len(y) / sr)
    
    config = initial_config.copy()
    
    # Корректировка под шумность
    if noise_level > 2000:  # Шумное аудио
        config['logprob_threshold'] = -1.2
        config['no_speech_threshold'] = 0.2
        config['temperature'] = [0.0, 0.1]
    
    # Корректировка под скорость речи
    if speech_rate > 2.0:  # Быстрая речь
        config['beam_size'] = 3  # Меньше для скорости
        config['patience'] = 2.0
    else:  # Медленная речь
        config['beam_size'] = 5  # Больше для качества
        config['patience'] = 1.0
    
    return config
```

## 4. Специальные промпты для разных ситуаций

### Для очень плохого качества связи
```env
WLK_STATIC_INIT_PROMPT="Телефонный разговор с плохим качеством связи. Говорящие четко проговаривают каждое слово. Медленная внятная русская речь. Повторение важных слов. Избегание сложных оборотов. Простые предложения с паузами между словами."
```

### Для разговоров с акцентом
```env
WLK_STATIC_INIT_PROMPT="Телефонный разговор на русском языке с региональным акцентом. Говорящие стараются произносить слова четко. Литературный русский язык с небольшими особенностями произношения. Полные слова без сокращений."
```

### Для технических обсуждений
```env
WLK_STATIC_INIT_PROMPT="Техническое обсуждение по телефону. IT-специалисты говорят о программном обеспечении, серверах, базах данных, API, конфигурации системы. Профессиональная терминология на русском языке с английскими техническими терминами."
```

### Для международных звонков
```env
WLK_STATIC_INIT_PROMPT="Международный деловой звонок на русском языке. Участники говорят медленно и четко для лучшего понимания. Избегают идиом и сленга. Используют простые грамматические конструкции. Повторяют важную информацию."
```

## 5. Интеграция с системами мониторинга

### Webhook для уведомлений о качестве
```python
import requests
import asyncio

class QualityMonitor:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.quality_threshold = 0.7
    
    async def check_quality(self, transcription_result):
        if hasattr(transcription_result, 'confidence'):
            if transcription_result.confidence < self.quality_threshold:
                await self.send_alert({
                    'type': 'low_quality',
                    'confidence': transcription_result.confidence,
                    'text': transcription_result.text[:100],
                    'timestamp': transcription_result.timestamp
                })
    
    async def send_alert(self, data):
        requests.post(self.webhook_url, json=data)
```

## 6. Постобработка результатов

### Коррекция частых ошибок
```python
import re

def post_process_transcription(text):
    """Исправление типичных ошибок распознавания"""
    
    # Словарь замен для частых ошибок
    corrections = {
        # Числа
        r'\bодин\b': '1',
        r'\bдва\b': '2', 
        r'\bтри\b': '3',
        
        # Деловая лексика
        r'\bкомпания\b': 'компания',
        r'\bдокумент\b': 'документ',
        r'\bпроект\b': 'проект',
        
        # Телефонные фразы
        r'\bаллё\b': 'алло',
        r'\bслышно\b': 'слышно',
        r'\bсвязь\b': 'связь',
    }
    
    corrected_text = text
    for pattern, replacement in corrections.items():
        corrected_text = re.sub(pattern, replacement, corrected_text, flags=re.IGNORECASE)
    
    # Исправление пунктуации
    corrected_text = re.sub(r'\s+([.!?])', r'\1', corrected_text)
    corrected_text = re.sub(r'([.!?])([A-ZА-Я])', r'\1 \2', corrected_text)
    
    return corrected_text.strip()

def apply_domain_glossary(text, glossary_file):
    """Применение отраслевого словаря терминов"""
    with open(glossary_file, 'r') as f:
        glossary = json.load(f)
    
    for wrong_term, correct_term in glossary.items():
        text = re.sub(rf'\b{wrong_term}\b', correct_term, text, flags=re.IGNORECASE)
    
    return text
```

## 7. Создание специализированных моделей

### Тонкая настройка для вашего домена
```python
# Подготовка данных для файн-тюнинга
def prepare_training_data(audio_files, transcripts):
    """Подготовка данных для обучения на вашем домене"""
    
    training_data = []
    for audio_file, transcript in zip(audio_files, transcripts):
        # Предобработка аудио
        processed_audio = preprocess_audio(audio_file)
        
        # Создание обучающего примера
        training_data.append({
            'audio': processed_audio,
            'text': transcript,
            'language': 'ru'
        })
    
    return training_data

# Сохранение для использования с OpenAI fine-tuning API или Hugging Face
def save_for_finetuning(training_data, output_dir):
    import json
    with open(f"{output_dir}/training_data.jsonl", 'w') as f:
        for example in training_data:
            f.write(json.dumps(example) + '\n')
```