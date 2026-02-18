"""
Panel Refinement Script - Постобработка для уточнения деталей и консистентности
Использует существующую панель как референс композиции и уточняет детали по референсам персонажей/локаций

Usage:
    python panel_refinement.py <scene_id> <panel_id> [--frame start|end|both]
    python panel_refinement.py 1 3 --frame start
    python panel_refinement.py 2 5 --frame both
"""

import google.generativeai as ggenai
from google import genai
import json
import os
import argparse
from pathlib import Path
from PIL import Image
from typing import List, Dict, Any, Optional

# --- КОНФИГУРАЦИЯ ---
TEXT_MODEL = "gemini-2.5-pro"
IMAGE_MODEL = "gemini-3-pro-image-preview"

api_key = os.getenv('IMG_AI_API_KEY', '')
if not api_key:
    print("❌ ОШИБКА: Не найден API ключ IMG_AI_API_KEY")
    exit(1)

ggenai.configure(api_key=api_key)
client = genai.Client(api_key=api_key)

# Папки
OUTPUT_DIR = Path("cinematic_render")
PANELS_DIR = OUTPUT_DIR / "panels"
REFINED_DIR = OUTPUT_DIR / "refined"
REF_DIR = Path("ref_thriller")
PROMPTS_DIR = Path("prompts")
CUSTOM_PROMPTS_DIR = Path("custom_prompts")

REFINED_DIR.mkdir(parents=True, exist_ok=True)

SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

QUALITY_PROMPTS = {}

# ==========================================
# ФУНКЦИИ
# ==========================================

def load_metadata() -> Dict:
    """Загружает метаданные сцен"""
    metadata_path = OUTPUT_DIR / "animation_metadata.json"
    if not metadata_path.exists():
        print(f"❌ Не найден файл метаданных: {metadata_path}")
        exit(1)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_quality_report() -> Dict:
    """Загружает метаданные сцен"""
    metadata_path = OUTPUT_DIR / "quality_report.json"
    if not metadata_path.exists():
        print(f"❌ Не найден файл метаданных: {metadata_path}")
        exit(1)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for item in data['panels']:
            scene_id = item['scene_id']
            panel_id = item['panel_id']
            key = f"{scene_id}_{panel_id}"
            QUALITY_PROMPTS[key] = item['refinement_prompt']

def load_prompts(use_custom: bool = False) -> Dict:
    """Загружает промпты стиля"""
    source_dir = CUSTOM_PROMPTS_DIR if use_custom else PROMPTS_DIR
    
    if use_custom and not CUSTOM_PROMPTS_DIR.exists():
        print(f"⚠️  {CUSTOM_PROMPTS_DIR} не найдена, использую стандартные промпты")
        source_dir = PROMPTS_DIR
    
    prompts = {}
    
    for md_file in ['style.md', 'imagery.md', 'setting.md']:
        path = source_dir / md_file
        if path.exists():
            prompts[md_file.replace('.md', '')] = path.read_text(encoding='utf-8')
        else:
            prompts[md_file.replace('.md', '')] = ""
    
    return prompts

def find_scene_panel(metadata: Dict, scene_id: int, panel_id: int) -> Optional[Dict]:
    """Находит конкретную панель в метаданных"""
    for scene in metadata.get('scenes', []):
        if scene['scene_id'] == scene_id:
            for panel in scene.get('panels', []):
                if panel['panel_index'] == panel_id:
                    return {
                        'scene': scene,
                        'panel': panel
                    }
    return None

def load_character_references(references: List[str]) -> tuple[List, List[str]]:
    """
    Загружает изображения и описания персонажей/локаций
    Returns: (list of PIL Images and text blocks, list of loaded names)
    """
    ref_content = []
    loaded_refs = []
    
    for ref_name in references:
        # Пробуем разные варианты имени файла
        possible_names = [
            ref_name,
            ref_name.lower().replace(' ', '_'),
            ref_name.title().replace(' ', '_'),
        ]
        
        for name in possible_names:
            img_path = REF_DIR / f"{name}.png"
            json_path = REF_DIR / f"{name}.json"
            
            if img_path.exists():
                try:
                    # Загружаем изображение
                    img = Image.open(img_path)
                    
                    # Загружаем описание
                    desc = ""
                    if json_path.exists():
                        try:
                            data = json.load(open(json_path, 'r'))
                            desc = data.get('visual_desc', '')
                        except:
                            pass
                    
                    ref_content.append(f"## Visual Reference: \"{ref_name}\"\n{desc}\n")
                    ref_content.append(img)
                    loaded_refs.append(ref_name)
                    print(f"  ✓ Загружен референс: {ref_name}")
                    break
                except Exception as e:
                    print(f"  ⚠️  Ошибка загрузки {img_path}: {e}")
                    continue
    
    return ref_content, loaded_refs

def refine_panel(
    scene_id: int,
    panel_id: int,
    frame_type: str,
    metadata: Dict,
    prompts: Dict,
    config: Dict
) -> bool:
    """
    Уточняет панель по референсам с сохранением композиции
    
    Args:
        scene_id: ID сцены
        panel_id: ID панели
        frame_type: 'start', 'end' или 'static'
        metadata: Метаданные сцен
        prompts: Промпты стиля
        config: Конфигурация
    """
    
    # 1. Находим данные панели
    data = find_scene_panel(metadata, scene_id, panel_id)
    if not data:
        print(f"❌ Не найдена панель {panel_id} в сцене {scene_id}")
        return False
    
    scene = data['scene']
    panel = data['panel']
    
    print(f"\n{'='*60}")
    print(f"🔧 Refinement: Scene {scene_id}, Panel {panel_id}, Frame: {frame_type}")
    print(f"{'='*60}")
    
    # 2. Загружаем оригинальную панель
    panel_filename = f"{scene_id:03d}_{panel_id:02d}_{frame_type}.png"
    original_path = PANELS_DIR / panel_filename
    
    if not original_path.exists():
        print(f"❌ Не найден файл панели: {original_path}")
        return False
    
    print(f"📂 Загружена оригинальная панель: {original_path}")
    original_img = Image.open(original_path)
    
    # 3. Загружаем референсы персонажей/локаций
    references = panel.get('references', [])
    if not references:
        print("⚠️  Референсы не указаны для этой панели, пропускаем")
        return False
    
    print(f"📎 Референсы для загрузки: {references}")
    ref_content, loaded_refs = load_character_references(references)
    
    if not ref_content:
        print("⚠️  Не удалось загрузить ни одного референса")
        return False
    
    print(f"✓ Загружено референсов: {loaded_refs}")
    
    # 4. Формируем промпт для уточнения
    style_prompt = prompts.get('style', '')
    imagery_prompt = prompts.get('imagery', '')
    setting_context = prompts.get('setting', '')
    
    # Определяем какое описание использовать
    if frame_type == 'start':
        visual_desc = panel.get('visual_start', '')
    elif frame_type == 'end':
        visual_desc = panel.get('visual_end', '')
    else:  # static
        visual_desc = panel.get('visual_start', panel.get('visual_end', ''))
    
    key = f"{scene_id}_{panel_id}"
    if key in QUALITY_PROMPTS:
        panel_specific = f"""
        ## IMPORTANT PANEL-SPECIFIC INSTRUCTIONS
        {QUALITY_PROMPTS[key]}

        """
    else:
        panel_specific = ""

    refinement_prompt = f"""{style_prompt}

{imagery_prompt}

{setting_context}

# REFINEMENT TASK

You are given:
1. ORIGINAL IMAGE - current panel that serves as COMPOSITION REFERENCE
2. CHARACTER/LOCATION VISUAL REFERENCES - for accurate appearance details

## CRITICAL REQUIREMENTS:

### PRESERVE FROM ORIGINAL:
- Camera angle, framing, composition
- Lighting setup (direction, quality, mood)
- Character positions and poses
- Overall scene layout and depth
- Motion and dynamics (if any)

### REFINE/CORRECT:
- Character facial features (use reference images)
- Character clothing and accessories (use reference images)  
- Character hair, build, and physical traits (use reference images)
- Location/environment details (use reference images)
- Object appearances (use reference images)
- Fine details consistency with references

## SCENE CONTEXT:
Location: {scene.get('location', 'Unknown')}
Setup: {scene.get('pre_action_description', '')}

## PANEL DESCRIPTION:
{visual_desc}

Camera & Lighting: {panel.get('lights_and_camera', '')}
Motion: {panel.get('motion_prompt', '')}

## DIALOGUE:
{panel.get('dialogue', '')}

## INSTRUCTIONS:
Generate a refined version of the original image that:
1. Keeps EXACT same composition, framing, camera angle
2. Keeps EXACT same lighting setup and mood
3. Keeps EXACT same character positions and poses
4. CORRECTS character appearances to match reference images
5. CORRECTS location/object details to match reference images
6. Maintains visual quality and cinematic feel

{panel_specific}

DO NOT change the composition or layout - only refine the visual details!
No captions or text overlays!
"""

    print(refinement_prompt)

    # 5. Генерация уточненного изображения
    refined_filename = f"{scene_id:03d}_{panel_id:02d}_{frame_type}_refined.png"
    refined_path = REFINED_DIR / refined_filename
    
    if refined_path.exists():
        return True
        print(f"⚠️  Уточненная версия уже существует: {refined_path}")
        overwrite = input("Перезаписать? (y/n): ").lower()
        if overwrite != 'y':
            print("Пропускаем...")
            return True
    
    print(f"🎨 Генерация уточненной версии...")
    print(f"   Используется {len(loaded_refs)} референсов")
    
    try:
        # Формируем контент для API
        # Порядок: референсы -> оригинальное изображение -> промпт
        content = []
        
        # Header для референсов
        if ref_content:
            content.append("# CHARACTER/LOCATION REFERENCE LIBRARY\nUse these for accurate visual details:\n")
            content.extend(ref_content)
        
        # Оригинальное изображение как композиционный референс
        content.append("\n# ORIGINAL COMPOSITION REFERENCE\nPreserve this exact composition, lighting, and layout:\n")
        content.append(original_img)
        
        # Финальный промпт
        content.append(refinement_prompt)
        
        # Генерация
        aspect_ratio = config.get('image_generation', {}).get('aspect_ratio', '5:4')
        resolution = config.get('image_generation', {}).get('image_size', '4K')
        
        resp = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=content,
            config={
                'response_modalities': ['Image'],
                'temperature': 0.4,  # Ниже температура для большей точности
                'top_p': 0.8,
                'seed': 42,
                'image_config': {
                    'aspect_ratio': '16:9',
                    'image_size': '1K',
                }
            }
        )
        
        # Сохранение
        resp.parts[0].as_image().save(refined_path)
        print(f"✅ Сохранено: {refined_path}")
        
        # Сохраняем метаданные refinement
        meta_path = refined_path.with_suffix('.json')
        meta = {
            'scene_id': scene_id,
            'panel_id': panel_id,
            'frame_type': frame_type,
            'original_file': str(original_path),
            'references_used': loaded_refs,
            'visual_description': visual_desc,
            'timestamp': str(Path(refined_path).stat().st_mtime)
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description='Panel Refinement - уточнение деталей панели по референсам'
    )
    parser.add_argument('scene_id', type=int, help='ID сцены')
    parser.add_argument('panel_id', type=int, help='ID панели')
    parser.add_argument(
        '--frame',
        choices=['start', 'end', 'static', 'both'],
        default='both',
        help='Какие фреймы обработать (по умолчанию: both для start+end)'
    )
    parser.add_argument(
        '--custom-prompts',
        action='store_true',
        help='Использовать custom_prompts/ вместо prompts/'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("🎬 PANEL REFINEMENT - Уточнение деталей по референсам")
    print("="*60)
    
    # Проверка директорий
    if not PANELS_DIR.exists():
        print(f"❌ Не найдена папка с панелями: {PANELS_DIR}")
        print("   Сначала запустите основной скрипт генерации")
        exit(1)
    
    if not REF_DIR.exists():
        print(f"❌ Не найдена папка с референсами: {REF_DIR}")
        exit(1)
    
    # Загрузка данных
    print("\n📂 Загрузка метаданных и промптов...")
    metadata = load_metadata()
    load_quality_report()
    prompts = load_prompts(use_custom=args.custom_prompts)
    
    # Загрузка конфига (из metadata или дефолт)
    config = metadata.get('config', {
        'image_generation': {
            'aspect_ratio': '5:4',
            'image_size': '4K'
        }
    })
    
    # Определяем какие фреймы обрабатывать
    if args.frame == 'both':
        frames_to_process = ['start', 'end']
    else:
        frames_to_process = [args.frame]
    
    # Обработка
    success_count = 0
    for frame_type in frames_to_process:
        result = refine_panel(
            args.scene_id,
            args.panel_id,
            frame_type,
            metadata,
            prompts,
            config
        )
        if result:
            success_count += 1
    
    # Итоги
    print("\n" + "="*60)
    if success_count > 0:
        print(f"✅ Успешно обработано фреймов: {success_count}/{len(frames_to_process)}")
        print(f"📁 Результаты сохранены в: {REFINED_DIR}")
    else:
        print("❌ Не удалось обработать ни одного фрейма")
    print("="*60)

if __name__ == "__main__":
    main()
