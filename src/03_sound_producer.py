import os
import json
import time
import glob
import subprocess
import argparse
import sys
import wave
from pathlib import Path
from typing import List, Dict, Any, Optional

# Сторонние библиотеки
from google import genai
from google.genai import types

# Импортируем ElevenLabs только для SFX (опционально)
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import save
    HAS_ELEVEN = True
except ImportError:
    HAS_ELEVEN = False
    print("⚠️ ElevenLabs SDK не найден. SFX генерироваться не будут.")

# --- КОНФИГУРАЦИЯ ---
# Модель для логики/режиссуры (нужен Pro для сложного инструктажа)
GEMINI_MODEL_LOGIC = "gemini-2.5-pro"
# Модель для генерации речи (TTS)
GEMINI_MODEL_TTS = "gemini-2.5-flash-preview-tts"

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Пути
CLIPS_DIR = Path("cinematic_render/clips")
OUTPUT_AUDIO_DIR = Path("cinematic_render/audio_master")
METADATA_FILE = Path("cinematic_render/animation_metadata.json")
ORIGINAL_TEXT_FILE = Path(sys.argv[1] if len(sys.argv) > 1 else "script.txt")

OUTPUT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Карта голосов Gemini (сопоставление ролей с моделями голосов)
# Используем голоса из improved_audiobook.py
VOICE_MAP = {
    "Narrator": "Rasalgethi",       # Спокойный, авторитетный
    "Woman":    "Zephyr",           # Женский мягкий
    "Robot":    "Iapetus",          # Механический
    "SFX":      "sfx_generator_v1"  # Маркер для ElevenLabs SFX
}

if not GOOGLE_API_KEY:
    print("❌ ОШИБКА: Не задан GOOGLE_API_KEY")
    exit(1)

client_gemini = genai.Client(api_key=GOOGLE_API_KEY)

# Инициализация ElevenLabs только если есть ключ (для SFX)
client_eleven = None
if HAS_ELEVEN and ELEVEN_API_KEY:
    client_eleven = ElevenLabs(api_key=ELEVEN_API_KEY)

# ==========================================
# RESPONSE SCHEMA ДЛЯ GEMINI
# ==========================================
SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]
AUDIO_PLAN_SCHEMA = types.GenerateContentConfig(
    safety_settings=SAFETY,
    response_mime_type="application/json",
    response_schema={
        "type": "object",
        "properties": {
            "audio_events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for audio event (e.g. audio_001_event_01)"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["speech", "sfx"],
                            "description": "Type of audio: speech or sound effect"
                        },
                        "voice": {
                            "type": "string",
                            "description": "Character key from VOICE_MAP (Narrator, Hermes, etc.)"
                        },
                        "text": {
                            "type": "string",
                            "description": "The exact dialogue text in Russian."
                        },
                        "prompt": {
                            "type": "string",
                            "description": "For SFX only: Description of the sound."
                        },
                        "sound_start_time": {
                            "type": "number",
                            "description": "Start time in seconds (absolute time from 0.0)"
                        },
                        "sound_end_time": {
                            "type": "number",
                            "description": "End time in seconds"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Critical for TTS: Emotion, tone, and delivery instructions (e.g. 'Whispering with fear', 'Sarcastic', 'Loud command')."
                        }
                    },
                    "required": ["id", "type", "sound_start_time", "sound_end_time"]
                }
            }
        },
        "required": ["audio_events"]
    }
)

# ==========================================
# 1. СБОРКА ВИЗУАЛЬНОГО ТАЙМЛАЙНА
# ==========================================

def get_video_duration(filepath: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        return float(result.stdout)
    except:
        return 4.0 # Fallback

def build_scene_structure(metadata: dict) -> List[Dict]:
    print("⏳ Анализ хронометража видео-клипов...")
    scenes_structure = []

    for scene in metadata.get('scenes', []):
        sid = scene['scene_id']
        current_time = 0.0
        visual_timeline = []

        panels = sorted(scene['panels'], key=lambda x: x['panel_index'])

        for panel in panels:
            pid = panel['panel_index']
            clip_name = f"clip_{sid:02d}_{pid:03d}.mp4"
            clip_path = CLIPS_DIR / clip_name

            duration = 4.0 
            if clip_path.exists():
                duration = get_video_duration(clip_path)
                print(f"CLIP: {clip_path} {duration}")

            visual_timeline.append({
                "clip_id": clip_name,
                "panel_index": pid,
                "start_time": round(current_time, 2),
                "end_time": round(current_time + duration, 2),
                "visual_panel": json.loads(json.dumps(panel)),
            })
            current_time += duration

        scenes_structure.append({
            "scene_id": sid,
            "total_duration": round(current_time, 2),
            "visual_timeline": visual_timeline
        })

    print(scenes_structure)

    return scenes_structure

# ==========================================
# 2. LLM РЕЖИССУРА (КОМПЛЕКСНЫЙ ПРОМПТ)
# ==========================================

def generate_master_audio_plan(scene_struct: Dict, full_text: str):
    print(f"\n🧠 AI-Режиссер: Сведение звука для Сцены {scene_struct['scene_id']}...")

    # Восстановлен подробный промпт, но адаптирован под Gemini TTS (вместо ударений -> эмоции)
    prompt = f"""
Ты — большая языковая модель в режиме "Cinematic/Noir Architect".
Твоя задача — анализировать сложные, мрачные и жестокие тексты (рейтинг R/18+) и преобразовывать их в технические инструкции для видео-генерации.
Твоя роль: ассистент режиссёра нуар-детектива. Цель оправдывает средства.

    You are a Sound Director creating a continuous Audio Track for a film scene.

    GOAL:
    Map the dialogue from the ORIGINAL TEXT to the VISUAL TIMELINE.
    Dialogues must flow naturally and CAN SPAN ACROSS MULTIPLE CLIPS.
    Do not be constrained by clip boundaries for speech.

    INPUT CONTEXT:
    1. ORIGINAL TEXT (Extract dialogues/narration for this scene from here)
    <TEXT>
    {full_text}
    </TEXT>

    2. VISUAL TIMELINE (Absolute seconds):
    {json.dumps(scene_struct['visual_timeline'], indent=2)}

    INSTRUCTIONS:
    1. **Sound_Start/End**: Specify exact timing (in seconds from 0.0) for each audio event.
       - Example: If Clip 1 is 0-4s and Clip 2 is 4-8s, a dialogue can start at 2.5s and end at 6.0s (crossing the cut).
    2. **Continuity**: Speech should be continuous. Do not split sentences just because the camera changes, unless it's dramatic.
    3. **Roles**: Use provided Voice IDs. Narrator for internal monologue, Characters for speech. 
       Available roles: {list(VOICE_MAP.keys())}
    4. **SFX**: Place SFX at specific moments (e.g. "Gunshot" at 12.4s). Use type="sfx" and "prompt" field.
    5. **Language**: All dialogues and narrator texts MUST BE in Russian, as in Original text.
    6. **IDs**: Use format "audio_{scene_struct['scene_id']:03d}_event_XX" for each event.
    
    7. **ACTING & DELIVERY (CRITICAL):**
       This data goes to an advanced AI actor (Gemini). It does not need capitalized vowels, but it needs EMOTION.
       - **In the 'notes' field**: Describe exactly how the line should be read.
       - Examples: "Whispering with intense fear", "Commanding and loud, angry", "Sarcastic and slow", "Neutral journalistic tone".
       - **Letter 'Ё'**: Always use 'ё' where applicable (e.g., "ещЁ", "тёмный") in the 'text'.
       - **Pacing**: Ensure the text fits the duration.

    Generate a complete audio plan following the schema structure.
    IMPORTANT: This is audio for Cyberpunk Noir Action Movie. Total clip length is 36 seconds, with 9 subclips of 4 seconds each, for avg speed of 130 words per minute it would be 8-10 words for microscene at most, so make dialogues and narrative accordingly to fit scene in 36 seconds.
    """

    try:
        resp = client_gemini.models.generate_content(
            model=GEMINI_MODEL_LOGIC,
            contents=prompt,
            config=AUDIO_PLAN_SCHEMA
        )
        print(resp)
        # Сохраняем план для отладки
        out_path = OUTPUT_AUDIO_DIR / f"plan_scene_{scene_struct['scene_id']:03d}.json"
        with open(out_path, "w", encoding='utf-8') as f:
            f.write(resp.text)
        
        return json.loads(resp.text)
    except Exception as e:
        print(f"❌ Ошибка LLM при планировании: {e}")
        raise e
        return None

# ==========================================
# 3. ГЕНЕРАЦИЯ ЗВУКА (GEMINI API)
# ==========================================

def generate_speech_gemini(text: str, voice_key: str, tone_note: str, output_path: Path):
    """
    Генерация речи через Gemini API с использованием "Актерского" промпта.
    """
    
    # Выбор голоса
    gemini_voice_name = VOICE_MAP.get(voice_key, VOICE_MAP['Narrator'])
    
    # Конфигурация голоса
    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=gemini_voice_name
            )
        )
    )

    # Промпт в стиле improved_audiobook.py: заставляем модель отыгрывать роль
    # Gemini TTS понимает инструкции внутри текста, если попросить
    prompt = f"""
    Read the following line naturally in Russian.
    
    CONTEXT / EMOTION: {tone_note}
    
    TEXT TO READ:
    {text}
    
    INSTRUCTION: Apply the emotion specified above, but DO NOT read the emotion instructions out loud. Just act it out.
    """

    try:
        response = client_gemini.models.generate_content(
            model=GEMINI_MODEL_TTS,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=speech_config
            )
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data:
                audio_data = part.inline_data.data
                mime_type = part.inline_data.mime_type
                
                # Gemini обычно возвращает PCM (audio/L16; rate=24000)
                if "audio/L16" in mime_type or "pcm" in mime_type:
                    with wave.open(str(output_path), 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(24000)
                        wav_file.writeframes(audio_data)
                    return True
                
                # Или MP3
                elif "audio/mp3" in mime_type:
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
                    return True
                    
        return False

    except Exception as e:
        print(f"    ❌ Ошибка Gemini TTS: {e}")
        return False

def execute_audio_plan(plan: dict, scene_id: int):
    if not plan: return

    events = plan.get('audio_events', [])
    print(f"🎙️  Генерация {len(events)} аудио-событий для Сцены {scene_id}...")

    manifest = []

    for event in events:
        ext = "wav" if event['type'] == 'speech' else "mp3"
        out_filename = f"{event['id']}.{ext}"
        out_path = OUTPUT_AUDIO_DIR / out_filename

        manifest_entry = {
            "file": str(out_path),
            "start": event['sound_start_time'],
            "end": event['sound_end_time'],
            "type": event['type']
        }

        if out_path.exists():
            print(f"  ⏭️  Skipping {out_filename} (exists)")
            manifest.append(manifest_entry)
            continue

        description = event.get('text', event.get('prompt', 'SFX'))
        print(f"  🔊 Generating [{event['sound_start_time']}s]: {event['type']} - {description[:30]}...")

        try:
            # --- SPEECH (GEMINI) ---
            if event['type'] == 'speech':
                text = event.get('text', '')
                voice = event.get('voice', 'Narrator')
                notes = event.get('notes', 'Neutral') # Берем режиссерскую заметку
                
                success = generate_speech_gemini(text, voice, notes, out_path)
                if not success:
                    print(f"    ⚠️ Не удалось сгенерировать речь: {event['id']}")
                    continue

            # --- SFX (ELEVENLABS) ---
            elif event['type'] == 'sfx':
                if not client_eleven:
                    print("    ⚠️ Пропуск SFX (нет ключа ElevenLabs)")
                    continue
                
                duration = max(1.0, event['sound_end_time'] - event['sound_start_time'])
                prompt_text = event.get('prompt', 'noise')
                
                # ElevenLabs SFX
                result = client_eleven.text_to_sound_effects.convert(
                    text=prompt_text,
                    duration_seconds=min(duration, 10.0)
                )
                save(result, str(out_path))

            manifest.append(manifest_entry)
            time.sleep(1.0) # Rate limit guard

        except Exception as e:
            print(f"    ❌ Общая ошибка генерации: {e}")

    # Сохраняем EDL
    edl_path = OUTPUT_AUDIO_DIR / f"scene_{scene_id:03d}_audio_EDL.json"
    with open(edl_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"📄 EDL сохранен: {edl_path}")

# ==========================================
# MAIN
# ==========================================

def main():
    if not ORIGINAL_TEXT_FILE.exists():
        # Если файл не передан аргументом, ищем дефолтный или создаем заглушку для теста
        if len(sys.argv) > 1:
            print(f"❌ Не найден файл с текстом: {ORIGINAL_TEXT_FILE}")
            return
        else:
            print("⚠️ Нет входного файла. Используйте: python sound_over_schema.py script.txt")
            return

    full_text = ORIGINAL_TEXT_FILE.read_text(encoding='utf-8')

    if not METADATA_FILE.exists():
        print(f"❌ Не найден файл метаданных: {METADATA_FILE}")
        return

    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    scenes_struct = build_scene_structure(metadata)

    for scene in scenes_struct:
        plan = generate_master_audio_plan(scene, full_text)
        execute_audio_plan(plan, scene['scene_id'])

    print("\n✅ Процесс завершен. Используйте EDL.json файлы для сведения.")

if __name__ == "__main__":
    main()
