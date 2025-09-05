"""
Адаптивная буферизация с контекстной коррекцией для WhisperLiveKit
Реализует двойную буферизацию: мгновенное отображение + контекстная коррекция
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from whisperlivekit.timed_objects import ASRToken, Transcript

logger = logging.getLogger(__name__)

@dataclass
class CorrectionResult:
    """Результат контекстной коррекции"""
    original_text: str
    corrected_text: str
    confidence: float
    corrections: List[Dict[str, Any]]
    timestamp: float

class AdaptiveBuffer:
    """
    Адаптивный буфер с контекстной коррекцией
    
    Особенности:
    - Мгновенное отображение текста
    - Контекстная коррекция предыдущих слов
    - Автоматическая пунктуация
    - Коррекция грамматики
    """
    
    def __init__(
        self,
        max_context_tokens: int = 100,
        correction_interval: float = 0.5,
        confidence_threshold: float = 0.7,
        auto_punctuation: bool = True,
        grammar_correction: bool = True,
        callback: Optional[Callable] = None
    ):
        self.max_context_tokens = max_context_tokens
        self.correction_interval = correction_interval
        self.confidence_threshold = confidence_threshold
        self.auto_punctuation = auto_punctuation
        self.grammar_correction = grammar_correction
        self.callback = callback
        
        # Буферы
        self.instant_buffer: List[ASRToken] = []  # Мгновенный буфер
        self.context_buffer: List[ASRToken] = []  # Контекстный буфер
        self.correction_queue: List[ASRToken] = []  # Очередь на коррекцию
        
        # Состояние
        self.last_correction_time = 0.0
        self.correction_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Статистика
        self.total_corrections = 0
        self.correction_history: List[CorrectionResult] = []
    
    async def start(self):
        """Запуск адаптивного буфера"""
        if self.is_running:
            return
            
        self.is_running = True
        self.correction_task = asyncio.create_task(self._correction_loop())
        logger.info("Адаптивный буфер запущен")
    
    async def stop(self):
        """Остановка адаптивного буфера"""
        self.is_running = False
        if self.correction_task:
            self.correction_task.cancel()
            try:
                await self.correction_task
            except asyncio.CancelledError:
                pass
        logger.info("Адаптивный буфер остановлен")
    
    def add_tokens(self, tokens: List[ASRToken]) -> List[ASRToken]:
        """
        Добавить новые токены в буфер
        
        Возвращает токены для мгновенного отображения
        """
        if not tokens:
            return []
        
        # Добавляем в мгновенный буфер
        self.instant_buffer.extend(tokens)
        
        # Добавляем в контекстный буфер
        self.context_buffer.extend(tokens)
        
        # Добавляем в очередь коррекции
        self.correction_queue.extend(tokens)
        
        # Ограничиваем размер контекстного буфера
        if len(self.context_buffer) > self.max_context_tokens:
            self.context_buffer = self.context_buffer[-self.max_context_tokens:]
        
        # Возвращаем токены для мгновенного отображения
        return tokens.copy()
    
    async def _correction_loop(self):
        """Основной цикл коррекции"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Проверяем, нужно ли выполнить коррекцию
                if (current_time - self.last_correction_time >= self.correction_interval and 
                    self.correction_queue):
                    
                    await self._perform_correction()
                    self.last_correction_time = current_time
                
                await asyncio.sleep(0.1)  # Небольшая задержка
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле коррекции: {e}")
                await asyncio.sleep(1)
    
    async def _perform_correction(self):
        """Выполнить контекстную коррекцию"""
        if not self.correction_queue:
            return
        
        # Берем токены для коррекции
        tokens_to_correct = self.correction_queue.copy()
        self.correction_queue.clear()
        
        # Выполняем коррекцию
        corrections = await self._correct_tokens(tokens_to_correct)
        
        # Применяем коррекции
        if corrections:
            await self._apply_corrections(corrections)
    
    async def _correct_tokens(self, tokens: List[ASRToken]) -> List[CorrectionResult]:
        """Корректировать токены на основе контекста"""
        corrections = []
        
        for token in tokens:
            if token.probability and token.probability < self.confidence_threshold:
                continue  # Пропускаем токены с низкой уверенностью
            
            # Получаем контекст
            context = self._get_context_for_token(token)
            
            # Выполняем коррекцию
            corrected_text = await self._correct_token_with_context(token, context)
            
            if corrected_text != token.text:
                correction = CorrectionResult(
                    original_text=token.text,
                    corrected_text=corrected_text,
                    confidence=token.probability or 0.0,
                    corrections=[{
                        'type': 'context_correction',
                        'original': token.text,
                        'corrected': corrected_text,
                        'context': context
                    }],
                    timestamp=time.time()
                )
                corrections.append(correction)
                self.total_corrections += 1
        
        return corrections
    
    def _get_context_for_token(self, token: ASRToken) -> str:
        """Получить контекст для токена"""
        # Находим позицию токена в контекстном буфере
        try:
            token_index = next(i for i, t in enumerate(self.context_buffer) if t == token)
        except StopIteration:
            return ""
        
        # Берем контекст вокруг токена
        context_start = max(0, token_index - 10)
        context_end = min(len(self.context_buffer), token_index + 10)
        
        context_tokens = self.context_buffer[context_start:context_end]
        context_text = " ".join(t.text for t in context_tokens)
        
        return context_text
    
    async def _correct_token_with_context(self, token: ASRToken, context: str) -> str:
        """Корректировать токен с учетом контекста"""
        original_text = token.text
        
        # Простая коррекция на основе контекста
        corrected_text = original_text
        
        # Коррекция пунктуации
        if self.auto_punctuation:
            corrected_text = self._correct_punctuation(corrected_text, context)
        
        # Коррекция грамматики
        if self.grammar_correction:
            corrected_text = self._correct_grammar(corrected_text, context)
        
        # Коррекция на основе контекста
        corrected_text = self._correct_with_context(corrected_text, context)
        
        return corrected_text
    
    def _correct_punctuation(self, text: str, context: str) -> str:
        """Коррекция пунктуации"""
        # Простые правила пунктуации
        if text.endswith(('а', 'о', 'е', 'и', 'ы', 'у', 'ю', 'я')):
            # Если это конец предложения по контексту
            if any(word in context.lower() for word in ['.', '!', '?', 'конец', 'закончил']):
                if not text.endswith(('.', '!', '?')):
                    text += '.'
        
        return text
    
    def _correct_grammar(self, text: str, context: str) -> str:
        """Коррекция грамматики"""
        # Простые правила грамматики
        corrections = {
            'а': 'я',
            'о': 'он',
            'е': 'его',
            'и': 'или',
            'ы': 'мы',
            'у': 'у',
            'ю': 'ю',
            'я': 'я'
        }
        
        for wrong, correct in corrections.items():
            if text == wrong and correct in context:
                text = correct
                break
        
        return text
    
    def _correct_with_context(self, text: str, context: str) -> str:
        """Коррекция на основе контекста"""
        # Простые контекстные коррекции
        context_lower = context.lower()
        
        # Если слово не входит в контекст, попробуем найти похожее
        if text not in context_lower:
            # Простой поиск похожих слов
            words = context_lower.split()
            for word in words:
                if len(word) > 2 and self._similarity(text, word) > 0.7:
                    return word
        
        return text
    
    def _similarity(self, a: str, b: str) -> float:
        """Вычислить схожесть строк"""
        if not a or not b:
            return 0.0
        
        # Простой алгоритм схожести
        longer = a if len(a) > len(b) else b
        shorter = b if len(a) > len(b) else a
        
        if len(longer) == 0:
            return 1.0
        
        return (len(longer) - self._edit_distance(a, b)) / len(longer)
    
    def _edit_distance(self, a: str, b: str) -> int:
        """Вычислить расстояние редактирования"""
        if len(a) < len(b):
            return self._edit_distance(b, a)
        
        if len(b) == 0:
            return len(a)
        
        previous_row = list(range(len(b) + 1))
        for i, c1 in enumerate(a):
            current_row = [i + 1]
            for j, c2 in enumerate(b):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    async def _apply_corrections(self, corrections: List[CorrectionResult]):
        """Применить коррекции"""
        for correction in corrections:
            # Обновляем токены в буферах
            self._update_tokens_in_buffers(correction)
            
            # Сохраняем в историю
            self.correction_history.append(correction)
            
            # Вызываем callback
            if self.callback:
                try:
                    await self.callback(correction)
                except Exception as e:
                    logger.error(f"Ошибка в callback коррекции: {e}")
            
            logger.info(f"Коррекция: '{correction.original_text}' -> '{correction.corrected_text}'")
    
    def _update_tokens_in_buffers(self, correction: CorrectionResult):
        """Обновить токены в буферах"""
        # Обновляем в контекстном буфере
        for token in self.context_buffer:
            if token.text == correction.original_text:
                token.text = correction.corrected_text
        
        # Обновляем в мгновенном буфере
        for token in self.instant_buffer:
            if token.text == correction.original_text:
                token.text = correction.corrected_text
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику буфера"""
        return {
            'total_corrections': self.total_corrections,
            'instant_buffer_size': len(self.instant_buffer),
            'context_buffer_size': len(self.context_buffer),
            'correction_queue_size': len(self.correction_queue),
            'correction_history_size': len(self.correction_history),
            'is_running': self.is_running
        }
    
    def get_correction_history(self, limit: int = 10) -> List[CorrectionResult]:
        """Получить историю коррекций"""
        return self.correction_history[-limit:]


