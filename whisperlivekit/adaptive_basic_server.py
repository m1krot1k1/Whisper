"""
Адаптивный базовый сервер с контекстной коррекцией для WhisperLiveKit
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from whisperlivekit import TranscriptionEngine, AudioProcessor, get_inline_ui_html, parse_args
from whisperlivekit.adaptive_server import AdaptiveTranscriptionServer
import asyncio
import logging
import json
from starlette.staticfiles import StaticFiles
import pathlib
import whisperlivekit.web as webpkg

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

args = parse_args()
transcription_engine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    #to remove after 0.2.8
    if args.backend == "simulstreaming" and not args.disable_fast_encoder:
        logger.warning(f"""
{'='*50}
WhisperLiveKit 0.2.8 has introduced a new fast encoder feature using MLX Whisper or Faster Whisper for improved speed. Use --disable-fast-encoder to disable if you encounter issues.
{'='*50}
    """)
    
    global transcription_engine
    transcription_engine = TranscriptionEngine(
        **vars(args),
    )
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
web_dir = pathlib.Path(webpkg.__file__).parent
app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")

@app.get("/")
async def get():
    return HTMLResponse(get_inline_ui_html())

async def handle_websocket_results(websocket, results_generator, adaptive_server=None):
    """Consumes results from the audio processor and sends them via WebSocket with adaptive buffering."""
    try:
        async for response in results_generator:
            # Если это результат транскрипции, обрабатываем через адаптивный буфер
            if response.get('type') == 'transcript' and adaptive_server:
                tokens = response.get('tokens', [])
                if tokens:
                    # Обрабатываем токены через адаптивный буфер
                    processed_tokens = await adaptive_server.process_tokens(tokens)
                    
                    # Создаем новый ответ с обработанными токенами
                    adaptive_response = response.copy()
                    adaptive_response['tokens'] = processed_tokens
                    adaptive_response['adaptive'] = True  # Маркер адаптивной обработки
                    
                    await websocket.send_json(adaptive_response)
                else:
                    await websocket.send_json(response)
            else:
                await websocket.send_json(response)
                
        # when the results_generator finishes it means all audio has been processed
        logger.info("Results generator finished. Sending 'ready_to_stop' to client.")
        await websocket.send_json({"type": "ready_to_stop"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected while handling results (client likely closed connection).")
    except Exception as e:
        logger.error(f"Error in websocket results handler: {e}")

@app.websocket("/asr")
async def websocket_endpoint(websocket: WebSocket):
    global transcription_engine
    
    # Создаем адаптивный сервер
    adaptive_config = {
        'max_context_tokens': getattr(args, 'max_context_tokens', 100),
        'correction_interval': 0.5,
        'confidence_threshold': 0.7,
        'auto_punctuation': True,
        'grammar_correction': True
    }
    
    adaptive_server = AdaptiveTranscriptionServer(websocket, adaptive_config)
    
    audio_processor = AudioProcessor(
        transcription_engine=transcription_engine,
    )
    await websocket.accept()
    logger.info("WebSocket connection opened with adaptive buffering.")
    
    # Запускаем адаптивный сервер
    await adaptive_server.start()
            
    results_generator = await audio_processor.create_tasks()
    websocket_task = asyncio.create_task(handle_websocket_results(websocket, results_generator, adaptive_server))

    try:
        while True:
            data = await websocket.receive_bytes()
            await audio_processor.process_audio(data)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
    finally:
        # Останавливаем адаптивный сервер
        await adaptive_server.stop()
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass

@app.websocket("/asr-adaptive")
async def adaptive_websocket_endpoint(websocket: WebSocket):
    """Специальный endpoint для адаптивной транскрипции"""
    global transcription_engine
    
    # Расширенная конфигурация для адаптивной буферизации
    adaptive_config = {
        'max_context_tokens': getattr(args, 'max_context_tokens', 100),
        'correction_interval': 0.5,
        'confidence_threshold': 0.7,
        'auto_punctuation': True,
        'grammar_correction': True,
        'enable_context_correction': True,
        'correction_interval': 0.5,
        'correction_confidence_threshold': 0.7
    }
    
    adaptive_server = AdaptiveTranscriptionServer(websocket, adaptive_config)
    
    audio_processor = AudioProcessor(
        transcription_engine=transcription_engine,
    )
    await websocket.accept()
    logger.info("Adaptive WebSocket connection opened.")
    
    # Запускаем адаптивный сервер
    await adaptive_server.start()
            
    results_generator = await audio_processor.create_tasks()
    websocket_task = asyncio.create_task(handle_websocket_results(websocket, results_generator, adaptive_server))

    try:
        while True:
            data = await websocket.receive_bytes()
            await audio_processor.process_audio(data)
    except WebSocketDisconnect:
        logger.info("Adaptive WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Error in adaptive websocket: {e}")
    finally:
        # Останавливаем адаптивный сервер
        await adaptive_server.stop()
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass

@app.get("/stats")
async def get_stats():
    """Получить статистику адаптивной буферизации"""
    return {"message": "Adaptive buffering statistics endpoint"}

@app.get("/corrections")
async def get_corrections():
    """Получить историю коррекций"""
    return {"message": "Correction history endpoint"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)

