import argparse
import json
import logging
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from google import genai
from PIL import Image
from threading import Lock

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# КОНФИГУРАЦИЯ
TEXT_MODEL = os.getenv('AI_TEXT_MODEL', "gemini-2.5-pro")
IMAGE_MODEL = os.getenv('AI_IMAGE_MODEL', "gemini-3-pro-image-preview")
MAX_WORKERS = int(os.getenv('AI_CONCURRENCY', '5'))

api_key = os.getenv('IMG_AI_API_KEY', '')
if not api_key:
    logger.error("❌ ОШИБКА: Не найден API ключ")
    exit(1)

client = genai.Client(api_key=api_key)

OUTPUT_DIR = Path("cinematic_render")
REF_DIR = Path("ref_thriller")

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.tokens = rpm
        self.max_tokens = rpm
        self.last_update = time.time()
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * (self.rpm / 60))
            self.last_update = now
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60 / self.rpm)
                time.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

limiter = RateLimiter(rpm=20)

def generate_json_with_schema(prompt: str, schema: dict = None):
    limiter.acquire()
    generation_config = {
        "temperature": 0.2, # Низкая температура для точности
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": 32000,
    }
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=generation_config
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"❌ Ошибка LLM: {e}")
        return None

# --- СХЕМЫ ---
UPDATED_REF_SCHEMA = {
    "type": "object",
    "properties": {
        "visual_desc": {"type": "string", "description": "Highly detailed, comprehensive visual description incorporating all new scene details."},
        "video_visual_desc": {"type": "string", "description": "Shorter summary of the updated description."}
    },
    "required": ["visual_desc", "video_visual_desc"]
}

SCENE_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "panels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "panel_index": {"type": "integer"},
                    "visual_start": {"type": "string"},
                    "visual_end": {"type": "string"}
                },
                "required": ["panel_index", "visual_start", "visual_end"]
            }
        }
    },
    "required": ["panels"]
}

def collect_reference_usage(metadata: dict) -> dict:
    """Собирает все описания панелей, где упоминается каждый референс."""
    ref_usage = {}
    for scene in metadata.get('scenes', []):
        for panel in scene.get('panels', []):
            for ref in panel.get('references', []):
                if ref not in ref_usage:
                    ref_usage[ref] = []
                # Сохраняем контекст того, как референс используется
                context = f"Scene {scene['scene_id']}, Panel {panel['panel_index']}: Start: {panel['visual_start']} | End: {panel['visual_end']} | Camera: {panel.get('lights_and_camera', '')}"
                ref_usage[ref].append(context)
    return ref_usage

def enrich_and_regenerate_reference(ref_name: str, usage_contexts: list):
    """Обогащает описание референса и перегенерирует картинку."""
    safe_name = ref_name.replace("/", "-").replace("'", " ").replace('"', '').replace(" ", "_").lower()
    json_path = REF_DIR / f"{safe_name}.json"
    png_path = REF_DIR / f"{safe_name}.png"
    
    if not json_path.exists():
        logger.warning(f"⚠️  JSON для {ref_name} не найден, пропускаем обогащение.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        ref_data = json.load(f)

    logger.info(f"🔍 Обогащение деталей для: {ref_name} (Использован в {len(usage_contexts)} панелях)")

    # 1. Заставляем LLM слить оригинальное описание с новыми деталями
    prompt = f"""
    You are a Lead Production Designer.
    We have an original visual description for the entity "{ref_name}":
    <ORIGINAL_DESC>
    {ref_data['visual_desc']}
    </ORIGINAL_DESC>

    However, the storyboard artist added specific new details in various scenes. 
    Here is how "{ref_name}" is actually described in the scenes:
    <SCENE_USAGES>
    {chr(10).join(usage_contexts[:20])} # limit to avoid context overload
    </SCENE_USAGES>

    TASK: 
    Merge the ORIGINAL_DESC with all specific physical details invented in the SCENE_USAGES (e.g., specific desk color, exact props, specific lighting fixtures, specific clothing details). 
    Do NOT include actions or temporary states. ONLY permanent visual design features.
    Generate a massive, highly detailed visual description that perfectly aligns with what the scenes require.
    """

    updated_desc = generate_json_with_schema(prompt, UPDATED_REF_SCHEMA)
    
    if updated_desc:
        ref_data['visual_desc'] = updated_desc['visual_desc']
        ref_data['video_visual_desc'] = updated_desc['video_visual_desc']
        
        # Сохраняем обновленный JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(ref_data, f, ensure_ascii=False, indent=2)

        # 2. Перегенерируем PNG
        logger.info(f"  🎨 Перегенерация PNG для {ref_name} с новыми деталями...")
        ref_prompt = f"CINEMATIC REFERENCE FOR {ref_data.get('type', 'Entity')}: {ref_name}. {ref_data['visual_desc']}. Close-up, neutral expression, uniform lighting, 8k."
        
        # Если есть style_reference, подгружаем его
        if ref_data.get('style_reference') and ref_data['style_reference'] != ref_name:
            style_safe = ref_data['style_reference'].replace("/", "-").replace(" ", "_").lower()
            style_path = REF_DIR / f"{style_safe}.png"
            if style_path.exists():
                img = Image.open(style_path)
                ref_prompt = [f"## Visual Style reference for {ref_data['style_reference']}", img, ref_prompt]

        try:
            limiter.acquire()
            resp = client.models.generate_content(
                model=IMAGE_MODEL, contents=ref_prompt,
                config={'response_modalities': ['Image'], 'image_config': {'aspect_ratio': '3:4', 'image_size': '1K'}}
            )
            if resp.parts[0].inline_data:
                resp.parts[0].as_image().save(png_path)
                logger.info(f"  ✅ {ref_name} успешно обновлен.")
        except Exception as e:
            logger.error(f"  ❌ Ошибка генерации картинки для {ref_name}: {e}")

def align_scene_prompts(scene: dict, all_refs_data: dict) -> dict:
    """Проверяет и правит панель сцены, чтобы она не противоречила финальным референсам."""
    logger.info(f"🎬 Синхронизация Сцены {scene['scene_id']}...")
    
    scene_refs = set()
    for panel in scene['panels']:
        scene_refs.update(panel.get('references', []))
    
    if not scene_refs:
        return scene

    ref_context = {}
    for ref in scene_refs:
        safe_name = ref.replace("/", "-").replace(" ", "_").lower()
        if safe_name in all_refs_data:
            ref_context[ref] = all_refs_data[safe_name]['video_visual_desc']

    prompt = f"""
    You are a Script Supervisor enforcing Visual Continuity.
    
    Here is the FINAL, APPROVED visual design for the entities in this scene:
    <APPROVED_REFERENCES>
    {json.dumps(ref_context, indent=2)}
    </APPROVED_REFERENCES>

    Here is the current scene data:
    <CURRENT_SCENE>
    {json.dumps(scene['panels'], indent=2)}
    </CURRENT_SCENE>

    TASK:
    Rewrite 'visual_start' and 'visual_end' for each panel ONLY IF they contradict the APPROVED_REFERENCES. 
    Ensure that colors, props, and materials mentioned in the scene exactly match the approved references.
    Do not change the action or cinematography, only enforce physical prop/character consistency.
    Return the full list of panels with your adjusted visual_start and visual_end.
    """

    aligned_data = generate_json_with_schema(prompt, SCENE_REWRITE_SCHEMA)
    
    if aligned_data and 'panels' in aligned_data:
        aligned_map = {p['panel_index']: p for p in aligned_data['panels']}
        for panel in scene['panels']:
            if panel['panel_index'] in aligned_map:
                panel['visual_start'] = aligned_map[panel['panel_index']]['visual_start']
                panel['visual_end'] = aligned_map[panel['panel_index']]['visual_end']
                
    return scene

def main():
    metadata_path = OUTPUT_DIR / "animation_metadata.json"
    if not metadata_path.exists():
        logger.error("❌ animation_metadata.json не найден. Сначала запустите 01_cinematic_preroll.py")
        return

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # ШАГ 1: Агрегация использования референсов
    logger.info("=== ШАГ 1: АНАЛИЗ ДРИФТА ДЕТАЛЕЙ ===")
    ref_usage = collect_reference_usage(metadata)
    
    # ШАГ 2: Обогащение и перегенерация референсов
    logger.info("=== ШАГ 2: ОБНОВЛЕНИЕ РЕФЕРЕНСОВ ===")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for ref_name, usages in ref_usage.items():
            executor.submit(enrich_and_regenerate_reference, ref_name, usages)

    # Загружаем обновленные референсы в память
    all_refs_data = {}
    for ref_file in REF_DIR.glob("*.json"):
        all_refs_data[ref_file.stem] = json.loads(ref_file.read_text(encoding='utf-8'))

    # ШАГ 3: Синхронизация описаний сцен
    logger.info("=== ШАГ 3: СИНХРОНИЗАЦИЯ СЦЕН ===")
    aligned_scenes = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(lambda s: align_scene_prompts(s, all_refs_data), metadata['scenes'])
        aligned_scenes = list(results)

    metadata['scenes'] = aligned_scenes

    # Сохраняем финальный, согласованный метаданные
    out_path = OUTPUT_DIR / "animation_metadata_consistent.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        
    logger.info(f"✅ Готово! Согласованные метаданные сохранены в {out_path}")
    logger.info("Теперь вы можете использовать этот файл для генерации панелей.")

if __name__ == "__main__":
    main()
