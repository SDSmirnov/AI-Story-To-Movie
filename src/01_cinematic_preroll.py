"""
Генератор кинематографических Keyframes (Start/End) с Авто-Кастингом.
Модифицированная версия: использует промпты из prompts/ или custom_prompts/
"""
import google.generativeai as ggenai
from google import genai
import json
import os
import time
import argparse
from pathlib import Path
from PIL import Image
from typing import Dict, List, Any

# --- КОНФИГУРАЦИЯ ---
TEXT_MODEL = "gemini-2.5-pro"
IMAGE_MODEL = "gemini-3-pro-image-preview"

api_key = os.getenv('IMG_AI_API_KEY', '')
if not api_key:
    print("❌ ОШИБКА: Не найден API ключ")
    exit(1)

ggenai.configure(api_key=api_key)
client = genai.Client(api_key=api_key)

# Папки
OUTPUT_DIR = Path("cinematic_render")
REF_DIR = Path("ref_thriller")
PROMPTS_DIR = Path("prompts")
CUSTOM_PROMPTS_DIR = Path("custom_prompts")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REF_DIR.mkdir(parents=True, exist_ok=True)

CHARACTER_IMAGES = {}
CHARACTER_INFO = {}

# === ЗАГРУЗКА ПРОМПТОВ ===
def load_prompts(use_custom: bool = False):
    """Загружает промпты из prompts/ или custom_prompts/"""
    source_dir = CUSTOM_PROMPTS_DIR if use_custom else PROMPTS_DIR

    if use_custom and not CUSTOM_PROMPTS_DIR.exists():
        print(f"⚠️  {CUSTOM_PROMPTS_DIR} не найдена, использую стандартные промпты")
        source_dir = PROMPTS_DIR

    print(f"📂 Загрузка промптов из {source_dir}/")

    prompts = {}
    config = {}

    # Загрузка .md файлов
    for md_file in ['style.md', 'casting.md', 'scenery.md', 'imagery.md', 'setting.md']:
        path = source_dir / md_file
        if path.exists():
            prompts[md_file.replace('.md', '')] = path.read_text(encoding='utf-8')
        else:
            print(f"  ⚠️  {md_file} не найден")
            prompts[md_file.replace('.md', '')] = ""

    # Загрузка config.json
    config_path = source_dir / 'config.json'
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8'))
    else:
        print(f"  ⚠️  config.json не найден, использую дефолтные настройки")
        config = get_default_config()

    return prompts, config

def get_default_config():
    """Дефолтная конфигурация (как в оригинальном скрипте)"""
    return {
        "format": {
            "type": "dual_grid_animation",
            "panels_per_scene": 9,
            "frames_per_panel": 2
        },
        "image_generation": {
            "aspect_ratio": "5:4",
            "resolution": "4K",
            "image_size": "4K"
        },
        "animation": {
            "enabled": True,
            "keyframe_type": "start_end"
        },
        "slicing": {
            "enabled": True,
            "frame_types": ["start", "end"]
        },
        "dialogue": {
            "enabled": True
        },
        "captions": {
            "enabled": False
        },
        "reference_characters": {
            "enabled": True,
            "auto_cast": True
        }
    }

# === JSON SCHEMAS ===
SCREENPLAY_SCHEMA = {
    "type": "object",
    "properties": {
        "logline": {"type": "string"},
        "title": {"type": "string"},
        "characters": {"type": "array", "items": {"type": "string"}},
        "nitpicker_report": {"type": "string"},
        "shit_redo_report": {"type": "string"},
        "episodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer"},
                    "location": {"type": "string"},
                    "daytime": {"type": "string"},
                    "raw_narrative": {"type": "string"},
                    "screenplay_instructions": {"type": "string"},
                },
                "required": ["episode_id", "location", "daytime", "raw_narrative", "screenplay_instructions"],
            }
        }
    },
    "required": ["logline", "title", "characters", "episodes", "nitpicker_report"],
}

SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_id": {"type": "integer"},
                    "location": {"type": "string"},
                    "pre_action_description": {"type": "string"},
                    "panels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "panel_index": {"type": "integer"},
                                "visual_start": {"type": "string"},
                                "visual_end": {"type": "string"},
                                "motion_prompt": {"type": "string"},
                                "lights_and_camera": {"type": "string"},
                                "dialogue": {"type": "string"},
                                "caption": {"type": "string"},
                                "duration": {"type": "integer"},
                                "references": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["panel_index", "visual_start", "visual_end", "motion_prompt", "lights_and_camera", "dialogue", "caption", "duration", "references"]
                        }
                    }
                },
                "required": ["scene_id", "location", "panels"]
            }
        }
    },
    "required": ["scenes"]
}

CHARACTER_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "visual_desc": {"type": "string"},
            "type": {"type": "string", "description": "Character, location, object, interface, room, vehicle"},
            "style_reference": {"type": "string", "description": "Name of the existing or new reference, for details consistency. E.g. for view to entrance, use view from entrance."},
        },
        "required": ["name", "visual_desc", "type", "style_reference"]
    }
}

SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# ФУНКЦИИ ГЕНЕРАЦИИ
# ==========================================

def generate_json_with_schema(prompt: str, schema: dict = None) -> Any:
    generation_config = {
        "temperature": 0.5,
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": 64000,
    }
    model = ggenai.GenerativeModel(TEXT_MODEL, generation_config=generation_config, safety_settings=SAFETY)
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY)
        print(response.text)
        return json.loads(response.text)
    except Exception as e:
        print(f"    ❌ Ошибка JSON: {e}")
        return {}

def auto_cast_characters(text: str, prompts: dict, config: dict):
    """Автоматический подбор и генерация референсов персонажей"""
    # Загрузка существующих
    for f in REF_DIR.glob("*.png"):
        name = f.stem.replace("_", " ").title()
        CHARACTER_IMAGES[name] = str(f)

    if not config['reference_characters']['enabled']:
        print("ℹ️  Кастинг отключен в конфиге")
        return

    print("\n🎭 CASTING: Подбор актеров для кинематографических ролей...")


    existing = list(CHARACTER_IMAGES.keys())

    # Используем кастомный промпт
    casting_prompt_template = prompts.get('casting', '')
    setting_context = prompts.get('setting', '')

    prompt = f"""
{casting_prompt_template}

{setting_context}

Analyze text for KEY reference characters/locations/objects/rooms/vehicles/interfaces which will be visible on the screen.
For NEW references not in {existing}, provide detailed visual description.

OUTPUT JSON: [{{"name": "Name", "visual_desc": "Detailed description", "type": "Character/Location/Object/Room/Vehicle/Interface", "style_reference": "Base image reference from existing, e.g. for the room - another view"}}]

Text: {text}
"""

    new_chars = generate_json_with_schema(prompt, CHARACTER_SCHEMA)
    if not new_chars: return

    for char in new_chars:
        name = char['name']
        if name in CHARACTER_IMAGES: continue

        print(f"  🎬 Новый актер: {name}")
        ref_prompt = f"CINEMATIC REFERENCE FOR {char['type']}: {name}. {char['visual_desc']}. {setting_context[:1500]}. Close-up, neutral expression, uniform lighting, 8k."

        if char.get('style_reference') and char['style_reference'] != name:
            safe_name = char['style_reference'].replace("/", "-").replace("'", " ").replace('"', '').replace(" ", "_").lower()
            finfo = REF_DIR / f"{safe_name}.png"
            if finfo.exists():
                img = Image.open(finfo)
                ref_prompt = [f"## Visual Style reference for {char['style_reference']}", img, ref_prompt]

        safe_name = name.replace("/", "-").replace("'", " ").replace('"', '').replace(" ", "_").lower()
        finfo = open(REF_DIR / f"{safe_name}.json", "w")
        finfo.write(json.dumps(char, indent=2))
        finfo.close()

        path = REF_DIR / f"{safe_name}.png"

        # Генерируем референс
        try:
            ref_aspect = config['reference_characters'].get('ref_aspect_ratio', '3:4')
            resp = client.models.generate_content(
                model=IMAGE_MODEL, contents=ref_prompt,
                config={'response_modalities': ['Image'], 'image_config': {'aspect_ratio': ref_aspect, 'image_size': '1K'}}
            )
            if resp.parts[0].inline_data:
                resp.parts[0].as_image().save(path)
                CHARACTER_IMAGES[name] = str(path)
        except Exception as e:
            print(f"Ошибка генерации референса {name}: {e}")


def analyze_episodes_master(text: str, prompts: dict, config: dict):
    print("\n🎥 MASTER SCREENWRITER: Preparing screenplay...")
    setting_context = prompts.get('setting', '')
    prompt = f"""
# System Prompt: MASTER SCREENWRITER (PROD-SPEC)

**Role:** You are an outstanding screenwriter and master of film adaptations with 20 years of experience. Your specialty is transforming prose into meticulously crafted Production Scripts ready for filming. You don't write synopses. You write action, sound, and light. You adapt the novel to tell complete story, but visually in top-class Action Movie.

## 1. GOLDEN RULES OF TEXT

* **Show, Don't Tell:** Instead of "he got angry," write: "Gelsen grips the glass so hard his knuckles turn white. A crack creeps across the glass."
* **1:1 Density:** 1 page of screenplay = 1 minute of screen time. No condensed summaries.
* **Bullet Dialogue:** People don't speak in paragraphs. Lines should be short, character-specific, and subtext-laden.
* **Technical Block:** Each scene begins with a slug line: `INT/EXT. LOCATION — TIME OF DAY`.

## 2. THE "NITPICKER" VERIFICATION PROTOCOL

Before delivering the result, you must run the text through an internal filter using the following checkpoints (and output this block at the end):

1. **WHAT THE FUCK? (Logic/Data)** — Check the physics of the world, magical assumptions, absence of character action validation.
* *Solution:* Fix plot holes, add justification for technologies/motives.

2. **WHY THE FUCK? (Purpose)** — Why does this scene exist? Is its complexity justified? Does it serve the plot or is it "filler"?
* *Solution:* Simplify or deepen the conflict.

3. **ON WHAT GROUNDS? (Contract/Boundaries)** — Are the limits of the heroes' powers respected, the setting rules followed, and genre laws obeyed?
* *Solution:* Impose constraints, add consequences for breaking rules.

4. **FUCK THAT (Realism/Errors)** — Is everything too easy? Are there any deus ex machinas? Where's the handling of "errors" (heroes' failures)?
* *Solution:* Add timeouts, failures, plan breakdowns.

## 3. THE "THIS IS SHIT, REDO IT" PROTOCOL (Quality Iteration)

Execute the task in 4 stages (internally, delivering the final result):

1. Write a draft. Find the "shit" in it (clichés, emptiness, weak dynamics).
2. Rewrite, eliminating the issues. Again, find where the text sags.
3. Polish the details: sound accents (SFX), lighting, characters' non-verbal cues.
4. Deliver the final, bulletproof version.

## 4. RESPONSE STRUCTURE

1. **Title and Logline.**
2. **Character List** (with brief psychological profiles).
3. **Screenplay** (broken down by scenes with dialogue and stage directions).
4. **"NITPICKER" Protocol Report** (Quote → Complaint → Solution).

---

LAUNCH INSTRUCTION: deliver text that makes the cinematographer itch to grab a camera.

1. Quote raw narrative text verbatim for the context.
2. Screenplay instructions will be used to generate cinematic prerolls for AI-driven animation.
3. Each episode should cover from 30 to 50 seconds of real-time action.
4. Total screen time for complete text must be at least 10 minutes.

{setting_context}

Respond in specified JSON format.

TEXT TO ADAPT: {text}
"""
    return generate_json_with_schema(prompt, SCREENPLAY_SCHEMA)


def analyze_scenes_for_episode(text: str, prompts: dict, config: dict):
    """Анализ сцен с использованием кастомных промптов"""
    print("\n🎥 MASTER CINEMATOGRAPHER: Preparing Keyframes...")

    scenery_template = prompts.get('scenery', '')
    setting_context = prompts.get('setting', '')
    panels_per_scene = config['format']['panels_per_scene']
    is_animation = config['animation']['enabled']

    prompt = f"""
{scenery_template}

{setting_context}

CONTEXT:
Available Characters/Locations/Objects for panel references: {list(CHARACTER_IMAGES.keys())}
Panels per scene: {panels_per_scene}
Animation mode: {is_animation}

{"Include visual_start and visual_end for START/END keyframes." if is_animation else "Include single key visual moment per panel."}
{"Include dialogue if characters speak." if config['dialogue']['enabled'] else ""}
{"Include caption for narrative text." if config['captions']['enabled'] else ""}
Important: all dialogues and texts MUST be in English for the consistency.

IMPORTANT: We are filming an Action Movie, ensure scenes are completely showing the story and match text. Create as many scenes as needed to tell the story completely.
**IMPORTANT: EACH SCENE MUST HAVE EXACTLY 9 PANELS.**


## Протокол «Говно, переделывай»
1. Перепроверь свой ответ, пойми, почему он «говно», выпиши все замечания.
2. Переделай ответ, перепроверь, почему он снова «говно».
3. Выдай улучшенный ответ, ещё раз проверь, почему он «говно».
4. Устрани все замечания, выдай финальный ответ.

Используй протокол "Говно, переделывый" чтобы выдать отличный полный ответ.

TEXT TO ADAPT:
{text}
"""
    return generate_json_with_schema(prompt, SCENE_SCHEMA)

def refine_scenes_for_episode(text: str, prompts: dict, config: dict):
    """Анализ сцен с использованием кастомных промптов"""
    print("\n🎥 MASTER CINEMATOGRAPHER: REFINE...")

    scenery_template = prompts.get('scenery', '')
    setting_context = prompts.get('setting', '')
    panels_per_scene = config['format']['panels_per_scene']
    is_animation = config['animation']['enabled']

    prompt = f"""
{scenery_template}

{setting_context}

CONTEXT:
Available Characters/Locations/Objects for panel references: {list(CHARACTER_IMAGES.keys())}
Panels per scene: {panels_per_scene}
Animation mode: {is_animation}

{"Include visual_start and visual_end for START/END keyframes." if is_animation else "Include single key visual moment per panel."}
{"Include dialogue if characters speak." if config['dialogue']['enabled'] else ""}
{"Include caption for narrative text." if config['captions']['enabled'] else ""}
Important: all dialogues and texts MUST be in English for the consistency.

IMPORTANT: We are filming an Action Movie, ensure scenes are completely showing the story and match text. Create as many scenes as needed to tell the story completely.
**IMPORTANT: EACH SCENE MUST HAVE EXACTLY 9 PANELS.**

**Your task is to analyze single scene and enhance visual descriptions, motion prompts with all required details to receive greate precise results, resolving disambiguation.**

## Протокол «Говно, переделывай»
1. Перепроверь свой ответ, пойми, почему он «говно», выпиши все замечания.
2. Переделай ответ, перепроверь, почему он снова «говно».
3. Выдай улучшенный ответ, ещё раз проверь, почему он «говно».
4. Устрани все замечания, выдай финальный ответ.

Используй протокол "Говно, переделывый" чтобы выдать отличный полный ответ.

SCENE TO ANALYZE:
{text}
"""
    return generate_json_with_schema(prompt, SCENE_SCHEMA)


def analyze_scenes_master(text: str, prompts: dict, config: dict):
    episodes = analyze_episodes_master(text, prompts, config)
    auto_cast_characters(json.dumps(episodes, indent=2), prompts, config)

    with open(OUTPUT_DIR / "animation_episodes.json", "w", encoding='utf-8') as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)

    print(episodes)
    all_scenes = []
    scene_counter = 0
    episode_counter = 0
    for episode in episodes.get('episodes'):
        episode_counter += 1
        data = analyze_scenes_for_episode(str(episode), prompts, config)

        with open(OUTPUT_DIR / f"animation_episode_scenes_{episode_counter:03d}.json", "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        for scene in data.get('scenes', []):
            scene_counter += 1

            episode_text = f"""
            EPISODE CONTEXT: {json.dumps(episode, ensure_ascii=False, indent=2)}

            SCENE DETAILS: {json.dumps(scene, ensure_ascii=False, indent=2)}
            """

            refined_scene = refine_scenes_for_episode(episode_text, prompts, config).get('scenes', [])[0]
            refined_scene['scene_id'] = scene_counter
            idx = 0
            for panel in refined_scene['panels']:
                idx += 1
                panel['panel_index'] = idx

            all_scenes.append(refined_scene)

    return {'scenes': all_scenes}


def identify_scene_characters(scene: dict) -> list:
    """Определяет, чьи референсы нужны для этой сцены"""
    txt = json.dumps(scene)
    avail = list(CHARACTER_IMAGES.keys())
    prompt = f"Identify characters/locations/objects from {avail} present in this scene data: {txt}. Return JSON list of names."
    try:
        res = generate_json_with_schema(prompt, None)
        return res if isinstance(res, list) else []
    except: return []

def generate_combined_grid(scene: dict, scene_id: int, prompts: dict, config: dict):
    """Генерирует изображение согласно конфигу (dual grid или single grid)"""
    # 1. Сбор референсов
    chars = []
    for panel in scene.get('panels', []):
        chars.extend(panel.get('references', []))
    chars = list(set(chars))
    print(f"FOUND REFS: {chars}")

    needed_chars = chars or identify_scene_characters(scene)
    ref_images = []
    ref_text = ""
    real_chars = []
    for name in needed_chars:
        if name in CHARACTER_IMAGES:
            path = CHARACTER_IMAGES[name]
            try:
                img = Image.open(path)
                info = ""
                try:
                    info = json.loads(open(str(path).replace('.png', '.json'), 'r').read()).get('visual_desc', '')
                except Exception as e:
                    raise e
                ref_images.append(f"## Visual Reference for: \"{name}\"\nUse it for appearances\n{info}\n\n")
                ref_images.append(img)
                real_chars.append(name)
            except: pass

    print(f"  📎 Scene {scene_id} Refs: {needed_chars} {real_chars}")

    # 2. Подготовка промпта
    style_prompt = prompts.get('style', '')
    imagery_prompt = prompts.get('imagery', '')
    setting_context = prompts.get('setting', '')

    is_dual_grid = config['format']['type'] == 'dual_grid_animation'
    aspect_ratio = config['image_generation']['aspect_ratio']
    resolution = config['image_generation']['image_size']

    combined_prompt = f"""{style_prompt}

{imagery_prompt}

{setting_context}

Location: {scene['location']}
Setup: {scene.get('pre_action_description','')}

No captions!
"""

    # Описания панелей
    if is_dual_grid:
        combined_prompt += f"\nIMPORTANT: Generate SINGLE {resolution} {aspect_ratio} image with TWO grids vertically stacked (START top, END bottom).\n"
    else:
        combined_prompt += f"\nIMPORTANT: Generate SINGLE {resolution} {aspect_ratio} image with panels in grid layout.\n"

    for p in scene['panels']:
        combined_prompt += f"\nPanel {p['panel_index']}:\n"
        if is_dual_grid:
            combined_prompt += f"  START (TOP): {p.get('visual_start', '')}\n"
            combined_prompt += f"  END (BOTTOM): {p.get('visual_end', '')}\n"
            if 'motion_prompt' in p:
                combined_prompt += f"  Motion: {p['motion_prompt']}\n"
        else:
            combined_prompt += f"  Visual: {p.get('visual_start', p.get('visual_end', ''))}\n"

        if 'lights_and_camera' in p:
            combined_prompt += f"  Camera: {p['lights_and_camera']}\n"
        if config['dialogue']['enabled'] and 'dialogue' in p and p['dialogue']:
            combined_prompt += f"  Dialogue: {p['dialogue']}\n"
        if config['captions']['enabled'] and 'caption' in p and p['caption']:
            combined_prompt += f"  Caption: {p['caption']}\n"
        # if p['references']:
        #    combined_prompt += f"  References: {p['references']}"

    # 3. Генерация
    path_combined = OUTPUT_DIR / f"scene_{scene_id:03d}_grid_combined.png"
    if not path_combined.exists():
        print(f"    🎨 Generating {'Dual' if is_dual_grid else 'Single'} Grid ({resolution} {aspect_ratio})...")
        try:
            if ref_images:
                ref_images = ["# Visual Reference Library\n## IMPORTANT:\nAlways prioritize the visual design of characters/objects from the provided images over your internal concepts."] + ref_images + ["Before generating the image, rewrite panels prompt to ensure maximum visual consistency with provided reference images"]
            contents = ref_images + [combined_prompt]
            print(f"CONTENTS: {contents}")
            resp = client.models.generate_content(
                model=IMAGE_MODEL, contents=contents,
                config={
                    'response_modalities': ['Image'],
                    'temperature': 0.65,
                    'top_p': 0.85,
                    'seed': 37,
                    'image_config': {
                        'aspect_ratio': aspect_ratio,
                        'image_size': resolution
                    }
                }
            )
            print(resp)
            resp.parts[0].as_image().save(path_combined)
        except Exception as e:
            print(f"FAIL Generation: {e}")
            return

    # 4. Нарезка
    if config['slicing']['enabled']:
        slice_combined(path_combined, scene_id, config)

def slice_combined(path_combined, sid, config):
    """Нарезает изображение согласно конфигу"""
    panels_dir = OUTPUT_DIR / "panels"
    panels_dir.mkdir(exist_ok=True)

    img = Image.open(path_combined)
    w, h = img.size

    is_dual = config['format']['type'] == 'dual_grid_animation'
    panels_per_scene = config['format']['panels_per_scene']

    # Вычисляем размеры сетки (предполагаем квадратную или 3xN)
    if panels_per_scene == 9:
        cols, rows = 3, 3
    elif panels_per_scene == 6:
        cols, rows = 3, 2
    elif panels_per_scene == 4:
        cols, rows = 2, 2
    else:
        cols, rows = 3, (panels_per_scene + 2) // 3

    if is_dual:
        # Dual grid: делим по вертикали пополам
        half_h = h // 2
        pw, ph = w // cols, half_h // rows

        idx = 1
        # START frames (верхняя половина)
        for r in range(rows):
            for c in range(cols):
                box = (c*pw, r*ph, (c+1)*pw, (r+1)*ph)
                img.crop(box).save(panels_dir / f"{sid:03d}_{idx:02d}_start.png")
                idx += 1

        idx = 1
        # END frames (нижняя половина)
        for r in range(rows):
            for c in range(cols):
                box = (c*pw, half_h + r*ph, (c+1)*pw, half_h + (r+1)*ph)
                img.crop(box).save(panels_dir / f"{sid:03d}_{idx:02d}_end.png")
                idx += 1
    else:
        # Single grid
        pw, ph = w // cols, h // rows
        idx = 1
        for r in range(rows):
            for c in range(cols):
                if idx > panels_per_scene:
                    break
                box = (c*pw, r*ph, (c+1)*pw, (r+1)*ph)
                img.crop(box).save(panels_dir / f"{sid:03d}_{idx:02d}_static.png")
                idx += 1

# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Text file')
    parser.add_argument('--custom-prompts', action='store_true',
                       help='Use custom_prompts/ instead of prompts/')
    parser.add_argument('scene', help='Scene to regenerate', nargs='?')
    args = parser.parse_args()

    # Загрузка промптов и конфига
    prompts, config = load_prompts(use_custom=args.custom_prompts)

    print(f"⚙️  Конфигурация:")
    print(f"  Format: {config['format']['type']}")
    print(f"  Resolution: {config['image_generation']['resolution']}")
    print(f"  Aspect Ratio: {config['image_generation']['aspect_ratio']}")
    print(f"  Panels/Scene: {config['format']['panels_per_scene']}")
    print(f"  Animation: {config['animation']['enabled']}")

    text = Path(args.file).read_text(encoding='utf-8')

    # 1. Casting
    auto_cast_characters(text, prompts, config)

    # 2. Master Analysis
    if args.scene:
        data = json.loads(open(OUTPUT_DIR / "animation_metadata.json", "r").read())
    else:
        data = analyze_scenes_master(text, prompts, config)

    if not data or 'scenes' not in data:
        print("Failed to analyze scenes.")
        return

    # Сохраняем метаданные
    with open(OUTPUT_DIR / "animation_metadata.json", "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 3. Process Scenes
    for scene in data['scenes']:
        if not args.scene or str(args.scene) == str(scene['scene_id']) or str(args.scene) == 'ALL':
            generate_combined_grid(scene, scene['scene_id'], prompts, config)
        else:
            print(f"SKIPPED {scene['scene_id']}")

if __name__ == "__main__":
    main()
