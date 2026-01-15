import json
import argparse
import logging
import subprocess
import tempfile
import os
from pathlib import Path
from pydub import AudioSegment

# --- КОНФИГУРАЦИЯ ---
VOL_SPEECH = 0.0
VOL_SFX = -9.0

FADE_IN_SFX = 500
FADE_OUT_SFX = 1000
MICRO_FADE = 20

# Минимальная пауза между репликами (чтобы не тараторили)
MIN_SPEECH_PAUSE_MS = 150 

# Максимальное допустимое ускорение, чтобы попытаться догнать график
# 1.1 = 10% ускорения (почти незаметно). Если нужно больше - скрипт выберет сдвиг.
MAX_CATCHUP_TEMPO = 1.1

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_tempo_ffmpeg(input_path: str, tempo: float) -> AudioSegment:
    """Изменяет темп без изменения тона (atempo)"""
    tempo = max(0.5, min(tempo, 2.0))
    if abs(tempo - 1.0) < 0.01:
        return AudioSegment.from_file(input_path)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        output_tmp = tmp.name

    try:
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(input_path),
            "-filter:a", f"atempo={tempo}", "-vn", str(output_tmp)
        ], check=True)
        return AudioSegment.from_file(output_tmp)
    except Exception:
        return AudioSegment.from_file(input_path)
    finally:
        if os.path.exists(output_tmp): os.remove(output_tmp)

def loop_audio_to_duration(audio: AudioSegment, target_ms: int) -> AudioSegment:
    if len(audio) >= target_ms: return audio[:target_ms]
    repeats = (target_ms // len(audio)) + 1
    return (audio * repeats)[:target_ms]

def process_edl(edl_path: str, output_path: str):
    path_edl = Path(edl_path)
    if not path_edl.exists():
        logger.error("EDL файл не найден")
        return

    with open(path_edl, 'r', encoding='utf-8') as f:
        events = json.load(f)

    if not events: return

    # Разделяем потоки
    sfx_events = [e for e in events if e.get('type') == 'sfx']
    speech_events = [e for e in events if e.get('type') != 'sfx']
    
    # Сортируем речь хронологически
    speech_events.sort(key=lambda x: x['start'])

    # 1. Рассчитываем реальную длительность речи с учетом сдвигов
    # Это нужно, чтобы заранее создать Canvas нужной длины
    
    dummy_cursor = 0
    for e in speech_events:
        # Эмуляция: просто читаем длительность файла (примерно) или берем из EDL?
        # Точнее будет делать это в процессе сведения, а Canvas расширять динамически.
        pass

    # Базовая длительность по EDL (для SFX)
    max_edl_end = max((e['end'] for e in events), default=0)
    canvas_duration = int(max_edl_end * 1000) + 5000 # +5 сек запас
    
    # Создаем холст
    master_track = AudioSegment.silent(duration=canvas_duration, frame_rate=44100).set_channels(2)

    # --- СЛОЙ 1: SFX (ФОН) ---
    # SFX кладем строго по таймкодам EDL, так как они привязаны к действиям в видео (выстрелы, шум поезда)
    logger.info("🔨 Processing SFX Layer...")
    for event in sfx_events:
        file_path = Path(event['file'])
        if not file_path.exists(): continue
        
        try:
            sound = AudioSegment.from_file(str(file_path))
            start_ms = int(event['start'] * 1000)
            target_dur = int((event['end'] - event['start']) * 1000)
            
            if target_dur > 0:
                sound = loop_audio_to_duration(sound, target_dur)
                sound = sound.apply_gain(VOL_SFX)
                sound = sound.fade_in(FADE_IN_SFX).fade_out(FADE_OUT_SFX)
                master_track = master_track.overlay(sound, position=start_ms)
        except Exception as e:
            logger.error(f"SFX Error {file_path}: {e}")

    # --- СЛОЙ 2: SPEECH (CUMULATIVE SHIFT) ---
    logger.info("🗣️ Processing Speech Layer (Cumulative Mode)...")
    
    speech_cursor_ms = 0 # Указатель: где закончилась последняя фраза
    
    for i, event in enumerate(speech_events):
        file_path = Path(event['file'])
        if not file_path.exists(): continue

        try:
            # Исходные данные
            original_start_ms = int(event['start'] * 1000)
            
            # Загружаем аудио
            sound = AudioSegment.from_file(str(file_path))
            original_len = len(sound)
            
            # --- ЛОГИКА СДВИГА ---
            
            # 1. Определяем желаемое время начала
            # Оно не может быть раньше, чем (конец_предыдущей + пауза)
            min_start_ms = speech_cursor_ms + MIN_SPEECH_PAUSE_MS
            
            # Реальный старт: либо по плану (если успеваем), либо со сдвигом
            actual_start_ms = max(original_start_ms, min_start_ms)
            
            shift_amount = actual_start_ms - original_start_ms
            
            # 2. Логика "Догонялок" (Catch-up)
            # Если мы отстаем от графика (shift > 0), можно чуть-чуть ускорить текущую фразу, 
            # чтобы сократить отставание для СЛЕДУЮЩЕЙ фразы.
            
            final_sound = sound
            if shift_amount > 500: # Если отставание больше полсекунды
                # Пробуем ускорить в пределах разумного (1.1x)
                new_len = int(original_len / MAX_CATCHUP_TEMPO)
                # Ускоряем
                logger.info(f"   ⚡ Catch-up: {file_path.name} (Tempo x{MAX_CATCHUP_TEMPO})")
                final_sound = apply_tempo_ffmpeg(str(file_path), MAX_CATCHUP_TEMPO)
            
            final_sound = final_sound.apply_gain(VOL_SPEECH)
            final_sound = final_sound.fade_in(MICRO_FADE).fade_out(MICRO_FADE)
            
            # 3. Наложение
            # Если звук выходит за пределы текущего холста -> расширяем холст
            needed_duration = actual_start_ms + len(final_sound)
            if needed_duration > len(master_track):
                padding = needed_duration - len(master_track) + 2000 # +2 сек запас
                master_track += AudioSegment.silent(duration=padding)
            
            master_track = master_track.overlay(final_sound, position=actual_start_ms)
            
            # Обновляем курсор
            speech_cursor_ms = actual_start_ms + len(final_sound)
            
            # Логирование сдвига
            if shift_amount > 0:
                logger.info(f"   -> Shifted: {file_path.name} by +{shift_amount}ms (Start: {original_start_ms} -> {actual_start_ms})")
            else:
                logger.info(f"   OK: {file_path.name} @ {actual_start_ms}ms")

        except Exception as e:
            logger.error(f"Speech Error {file_path}: {e}")

    # Экспорт
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    master_track.export(output_path, format="mp3", bitrate="192k")
    logger.info(f"✅ Master Audio created: {output_path} (Dur: {len(master_track)/1000:.1f}s)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("edl_json", help="Path to EDL JSON")
    parser.add_argument("output_mp3", help="Output MP3 path")
    args = parser.parse_args()
    
    process_edl(args.edl_json, args.output_mp3)
