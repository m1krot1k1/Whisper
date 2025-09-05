"""
Адаптивный сервер с контекстной коррекцией для WhisperLiveKit
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from whisperlivekit.adaptive_buffer import AdaptiveBuffer, CorrectionResult
from whisperlivekit.timed_objects import ASRToken

logger = logging.getLogger(__name__)

class AdaptiveTranscriptionServer:
    """
    Адаптивный сервер транскрипции с контекстной коррекцией
    """
    
    def __init__(self, websocket, config: Dict[str, Any]):
        self.websocket = websocket
        self.config = config
        self.adaptive_buffer = AdaptiveBuffer(
            max_context_tokens=config.get('max_context_tokens', 100),
            correction_interval=config.get('correction_interval', 0.5),
            confidence_threshold=config.get('confidence_threshold', 0.7),
            auto_punctuation=config.get('auto_punctuation', True),
            grammar_correction=config.get('grammar_correction', True),
            callback=self._on_correction
        )
        self.is_running = False
    
    async def start(self):
        """Запуск адаптивного сервера"""
        self.is_running = True
        await self.adaptive_buffer.start()
        logger.info("Адаптивный сервер запущен")
    
    async def stop(self):
        """Остановка адаптивного сервера"""
        self.is_running = False
        await self.adaptive_buffer.stop()
        logger.info("Адаптивный сервер остановлен")
    
    async def process_tokens(self, tokens: list) -> list:
        """
        Обработать токены через адаптивный буфер
        
        Возвращает токены для мгновенного отображения
        """
        if not self.is_running:
            return tokens
        
        # Конвертируем в ASRToken если нужно
        asr_tokens = []
        for token in tokens:
            if isinstance(token, dict):
                asr_token = ASRToken(
                    start=token.get('start', 0.0),
                    end=token.get('end', 0.0),
                    text=token.get('text', ''),
                    probability=token.get('probability', 0.0)
                )
                asr_tokens.append(asr_token)
            elif isinstance(token, ASRToken):
                asr_tokens.append(token)
        
        # Добавляем в адаптивный буфер
        instant_tokens = self.adaptive_buffer.add_tokens(asr_tokens)
        
        # Конвертируем обратно в формат для отправки
        result_tokens = []
        for token in instant_tokens:
            result_tokens.append({
                'start': token.start,
                'end': token.end,
                'text': token.text,
                'probability': token.probability,
                'type': 'instant'  # Маркер мгновенного отображения
            })
        
        return result_tokens
    
    async def _on_correction(self, correction: CorrectionResult):
        """Обработчик коррекции"""
        try:
            # Отправляем коррекцию на клиент
            correction_message = {
                'type': 'correction',
                'original_text': correction.original_text,
                'corrected_text': correction.corrected_text,
                'confidence': correction.confidence,
                'timestamp': correction.timestamp,
                'corrections': correction.corrections
            }
            
            await self.websocket.send_text(json.dumps(correction_message))
            logger.info(f"Отправлена коррекция: {correction.original_text} -> {correction.corrected_text}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке коррекции: {e}")
    
    async def send_instant_text(self, text: str, metadata: Dict[str, Any] = None):
        """Отправить текст для мгновенного отображения"""
        try:
            message = {
                'type': 'instant_text',
                'text': text,
                'metadata': metadata or {},
                'timestamp': asyncio.get_event_loop().time()
            }
            
            await self.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Ошибка при отправке мгновенного текста: {e}")
    
    async def send_corrected_text(self, text: str, corrections: list, metadata: Dict[str, Any] = None):
        """Отправить исправленный текст"""
        try:
            message = {
                'type': 'corrected_text',
                'text': text,
                'corrections': corrections,
                'metadata': metadata or {},
                'timestamp': asyncio.get_event_loop().time()
            }
            
            await self.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Ошибка при отправке исправленного текста: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику сервера"""
        return {
            'adaptive_buffer': self.adaptive_buffer.get_statistics(),
            'is_running': self.is_running,
            'config': self.config
        }
    
    def get_correction_history(self, limit: int = 10) -> list:
        """Получить историю коррекций"""
        return self.adaptive_buffer.get_correction_history(limit)

