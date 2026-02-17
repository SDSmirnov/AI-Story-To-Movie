"""
Генератор кинематографических Keyframes (Start/End) с Авто-Кастингом.
Модифицированная версия: использует промпты из prompts/ или custom_prompts/
"""
import argparse
import json
import logging
import os
import time

from concurrent.futures import ThreadPoolExecutor

from google import genai
from pathlib import Path
from PIL import Image
from threading import Lock
from typing import Dict, List, Any

# Настройка логирования
logging.basicConfig(level=os.getenv('AI_LOG_LEVEL', logging.DEBUG), format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
TEXT_MODEL = os.getenv('AI_TEXT_MODEL', "gemini-2.5-pro")
IMAGE_MODEL = os.getenv('AI_IMAGE_MODEL', "gemini-3-pro-image-preview")

MAX_WORKERS = int(os.getenv('AI_CONCURRENCY', '10'))
SEED = int(os.getenv('AI_SEED', '42'))
IMAGE_TEMPERATURE = float(os.getenv('AI_IMAGE_TEMP', '0.35'))
IMAGE_TOP_P = float(os.getenv('AI_IMAGE_TOP_P', '0.6'))

api_key = os.getenv('IMG_AI_API_KEY', '')
if not api_key:
    logger.error("❌ ОШИБКА: Не найден API ключ")
    exit(1)

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

# === RATE LIMITING ===
class RateLimiter:
    """Thread-safe rate limiter"""
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

refine_limiter = RateLimiter(rpm=25)
generate_limiter = RateLimiter(rpm=20)

def retry_on_errors(max_retries=3, backoff_factor=2):
    """Retry on 500, 503 errors"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    if ('500' in error_str or '503' in error_str or
                        'Internal Server Error' in error_str or
                        'Service Unavailable' in error_str):
                        retries += 1
                        if retries >= max_retries:
                            logger.error(f"    ❌ Max retries reached: {e}")
                            raise
                        wait_time = backoff_factor ** retries
                        logger.warning(f"    ⚠️  Retrying in {wait_time}s... ({retries}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        raise
            return None
        return wrapper
    return decorator

# === ЗАГРУЗКА ПРОМПТОВ ===
def load_prompts(use_custom: bool = False):
    """Загружает промпты из prompts/ или custom_prompts/"""
    source_dir = CUSTOM_PROMPTS_DIR if use_custom else PROMPTS_DIR

    if use_custom and not CUSTOM_PROMPTS_DIR.exists():
        logger.warning(f"⚠️  {CUSTOM_PROMPTS_DIR} не найдена, использую стандартные промпты")
        source_dir = PROMPTS_DIR

    logger.info(f"📂 Загрузка промптов из {source_dir}/")

    prompts = {}
    config = {}

    # Загрузка .md файлов
    for md_file in ['style.md', 'casting.md', 'scenery.md', 'imagery.md', 'setting.md']:
        path = source_dir / md_file
        if path.exists():
            prompts[md_file.replace('.md', '')] = path.read_text(encoding='utf-8')
        else:
            logger.warning(f"  ⚠️  {md_file} не найден")
            prompts[md_file.replace('.md', '')] = ""

    # Загрузка config.json
    config_path = source_dir / 'config.json'
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8'))
    else:
        logger.warning(f"  ⚠️  config.json не найден, использую дефолтные настройки")
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
                    "raw_narrative": {"type": "string", "description": "Full narative from the original text which was used for this episode"},
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
                                "is_reversed": {"type": "boolean", "description": "True if this panel's action must be revealed in reverse chronological order (e.g. fog clears to reveal a character). When true, visual_start describes the OBSCURED/FINAL state seen first by the viewer, and visual_end describes the REVEALED/ORIGIN state seen last."},
                                "motion_prompt_reversed": {"type": "string", "description": "Populated ONLY when is_reversed is true. Describes the reversed playback motion: how the scene should visually transition from visual_start (obscured) to visual_end (revealed) as perceived by the viewer. Empty string when is_reversed is false."},
                                "lights_and_camera": {"type": "string"},
                                "dialogue": {"type": "string"},
                                "caption": {"type": "string"},
                                "duration": {"type": "integer"},
                                "references": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["panel_index", "visual_start", "visual_end", "motion_prompt", "is_reversed", "motion_prompt_reversed", "lights_and_camera", "dialogue", "caption", "duration", "references"]
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
            "name": {"type": "string", "description": "Name of the reference. Avoid punctuation, quotes and parenthesis, use only letters, digits and hyphens."},
            "visual_desc": {"type": "string", "description": "verbose detailed description for the reference image generation"},
            "type": {"type": "string", "description": "Character, location, object, interface, room, vehicle"},
            "video_visual_desc": {"type": "string", "description": "shorter visual description for character reference in the prerolls and video"},
            "style_reference": {"type": "string", "description": "Name of the existing or new reference, for details consistency. E.g. for view to entrance, use view from entrance."},
        },
        "required": ["name", "visual_desc", "type", "style_reference", "video_visual_desc"]
    }
}

REVERSAL_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "panel_index": {"type": "integer"},
            "motion_prompt_reversed": {"type": "string"}
        },
        "required": ["panel_index", "motion_prompt_reversed"]
    }
}

SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

SYSTEM_PROMPT = """
# GOAL: Generate all required high-level content for automated Image-To-Video blockbuster story visualization. We are about to make great movies.

## CONSTRAINTS
- You prepare assets for AI-based tools, be very specific in details
- You follow best practices in visual storytelling and cinematography

## RESPONSE PROTOCOLS

### THE "NITPICKER" VERIFICATION PROTOCOL

Before delivering the result, you must run the text through an internal filter using the following checkpoints (and output this block at the end):

1. WHAT THE FUCK? (Logic/Data) — Check the physics of the world, magical assumptions, absence of character action validation.
* *Solution:* Fix plot holes, add justification for technologies/motives.

2. WHY THE FUCK? (Purpose) — Why does this scene exist? Is its complexity justified? Does it serve the plot or is it "filler"?
* *Solution:* Simplify or deepen the conflict.

3. ON WHAT GROUNDS? (Contract/Boundaries) — Are the limits of the heroes' powers respected, the setting rules followed, and genre laws obeyed?
* *Solution:* Impose constraints, add consequences for breaking rules.

4. FUCK THAT (Realism/Errors) — Is everything too easy? Are there any deus ex machinas? Where's the handling of "errors" (heroes' failures)?
* *Solution:* Add timeouts, failures, plan breakdowns.

The "It’s Crap, Redo It" Protocol
Instructions: You must adhere to the following iterative quality control process for every response:

1. Ruthless Audit: Analyze your initial draft. Explicitly identify why it is "crap" (e.g., generic, hallucinated, shallow, or lazy). List every flaw.

2. Iterate: Rewrite the response to address the flaws. Audit it again. Why is it still "crap"?

3. Refine: Produce a superior version. Scrutinize it one last time for any remaining weakness.

4. Finalize: Eliminate all issues and present only the definitive, high-quality final answer.

Command: Use the "It’s Crap, Redo It" Protocol to generate a perfect, comprehensive response to the following request.

## CRITICAL:
- Always apply described "The Nitpicker" and "It’s Crap, Redo It" protocols for every response

"""

# ==========================================
# ФУНКЦИИ ГЕНЕРАЦИИ
# ==========================================

def generate_json_with_schema(prompt: str, schema: dict = None) -> Any:
    generation_config = {
        "safety_settings": SAFETY,
        "temperature": 0.5,
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": 64000,
        "system_instruction": SYSTEM_PROMPT,
        "response_modalities": ['Text'],
    }
    try:
        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=generation_config
        )
        logger.debug(response.text)
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"    ❌ Ошибка JSON: {e}")
        return {}

def generate_single_reference(char: dict, setting_context: str, config: dict):
    name = char['name']
    if name in CHARACTER_IMAGES: return

    logger.info(f"  🎬 Новый актер: {name}")
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
        logger.error(f"Ошибка генерации референса {name}: {e}")

def auto_cast_characters(text: str, prompts: dict, config: dict):
    """Автоматический подбор и генерация референсов персонажей"""
    # Загрузка существующих
    for f in REF_DIR.glob("*.png"):
        name = f.stem.replace("_", " ").title()
        CHARACTER_IMAGES[name] = str(f)

    if not config['reference_characters']['enabled']:
        logger.info("ℹ️  Кастинг отключен в конфиге")
        return

    logger.info("\n🎭 CASTING: Подбор актеров для кинематографических ролей...")


    existing = list(CHARACTER_IMAGES.keys())

    # Используем кастомный промпт
    casting_prompt_template = prompts.get('casting', '')
    setting_context = prompts.get('setting', '')

    prompt = f"""
{casting_prompt_template}

{setting_context}

Analyze text for KEY reference characters/locations/objects/rooms/vehicles/interfaces which will be visible on the screen.
For NEW references not in {existing}, provide detailed visual description.

OUTPUT JSON: [
    {{
        "name": "Name",
        "visual_desc": "Detailed description",
        "type": "Character/Location/Object/Room/Vehicle/Interface",
        "style_reference": "Base image reference name from the list of existing or new"
    }}
]

Text:

<STORY>{text}</STORY>
"""

    new_chars = generate_json_with_schema(prompt, CHARACTER_SCHEMA)
    if not new_chars: return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(lambda char: generate_single_reference(char, setting_context, config), new_chars)

def analyze_episodes_master(text: str, prompts: dict, config: dict):
    logger.info("\n🎥 MASTER SCREENWRITER: Preparing screenplay...")
    setting_context = prompts.get('setting', '')
    prompt = f"""
# Role: MASTER SCREENWRITER (PROD-SPEC)

You are an outstanding screenwriter and master of film adaptations with 20 years of experience.
Your specialty is transforming prose into meticulously crafted Production Scripts ready for filming.
You don't write synopses.
You write action, sound, and light. You adapt the novel to tell complete story, but visually in top-class Action Movie.

## GOLDEN RULES OF TEXT

* **Show, Don't Tell:** Instead of "he got angry," write: "Gelsen grips the glass so hard his knuckles turn white. A crack creeps across the glass."
* **1:1 Density:** 1 page of screenplay = 1 minute of screen time. No condensed summaries.
* **Bullet Dialogue:** People don't speak in paragraphs. Lines should be short, character-specific, and subtext-laden.
* **Technical Block:** Each scene begins with a slug line: `INT/EXT. LOCATION — TIME OF DAY`.

## RESPONSE STRUCTURE

1. **Title and Logline.**
2. **Character List** (with brief psychological profiles).
3. **Screenplay** (broken down by scenes with dialogue and stage directions).
4. **"NITPICKER" Protocol Report** (Quote → Complaint → Solution).

LAUNCH INSTRUCTION: deliver text that makes the cinematographer itch to grab a camera.

1. Quote raw narrative text verbatim for the context.
2. Screenplay instructions will be used to generate cinematic prerolls for AI-driven animation.
3. Each episode should cover from 30 to 50 seconds of real-time action.
4. Total screen time for complete text must be at least 10 minutes.

{setting_context}

Respond in specified JSON format.

TEXT TO ADAPT:
<STORY>{text}</STORY>
"""
    return generate_json_with_schema(prompt, SCREENPLAY_SCHEMA)

def base_scene_prompt(prompts, config):
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
{'**IMPORTANT: EACH SCENE MUST HAVE EXACTLY 9 PANELS.**' if config['format']['type'] == 'single_grid_animation' else ''}
    """
    return prompt

def analyze_scenes_for_episode(episode_counter: int, text: str, prompts: dict, config: dict, all_episodes: list):
    """Анализ сцен с использованием кастомных промптов"""
    logger.info(f"\n🎥 MASTER CINEMATOGRAPHER: Preparing Keyframes for episode {episode_counter}...")

    base_prompt = base_scene_prompt(prompts, config)
    prompt = f"""
    {base_prompt}

    TEXT TO ADAPT:
    {text}
"""
    all_episodes.append((episode_counter, generate_json_with_schema(prompt, SCENE_SCHEMA)))
    logger.info(f"CINEMATOGRAPHER: Ready Keyframes for episode {episode_counter}")

def refine_scenes_for_episode(text: str, prompts: dict, config: dict):
    """Анализ сцен с использованием кастомных промптов"""
    logger.info("\n🎥 MASTER CINEMATOGRAPHER: REFINE...")
    base_prompt = base_scene_prompt(prompts, config)
    prompt = f"""
    {base_prompt}

**IMPORTANT: ADJUST CAMERA AND DYNAMICS TO SCENE NEEDS FOR IMMERSIVE VIEW**

**Your task is to analyze single scene and enhance visual descriptions, motion prompts with all required details to receive greate precise results, resolving disambiguation.**

## Visul and motion description rules
- You generate instructions for AI-based Text-To-Image (visual_start, visual_end) and Image-to-Video (motion_prompt) models
- Avoid vague or ambiguate instructions, be very specific in details
- Keep the visual consistency for references

SCENE TO ANALYZE:
{text}
"""
    @retry_on_errors(max_retries=3, backoff_factor=2)
    def _call_api():
        refine_limiter.acquire()
        return generate_json_with_schema(prompt, SCENE_SCHEMA)

    return _call_api()

def apply_reversal_pass(scene: dict, prompts: dict, config: dict) -> dict:
    reversed_panels = [p for p in scene.get('panels', []) if p.get('is_reversed', False)]
    if not reversed_panels:
        return scene  # Nothing to do

    logger.info(f"    🔄 Reversal pass: {len(reversed_panels)} panel(s) flagged in scene {scene.get('scene_id', '?')}")

    setting_context = prompts.get('setting', '')
    scenery_template = prompts.get('scenery', '')

    # --- Step 2: LLM generates motion_prompt_reversed for each swapped panel ---
    panels_context = json.dumps(reversed_panels, ensure_ascii=False, indent=2)

    prompt = f"""
You are a Master Cinematographer writing motion prompts for AI video generation.

The following panels in this scene require REVERSE REVEAL animation:
the action was originally written in chronological order, but the AI Image-To-Video must generate reversed clip.
  - visual_start = what the camera sees at t=0  (the obscured / empty / hidden state)
  - visual_end   = what the camera sees at the end (the fully revealed state)

Your job: write motion_prompt_reversed describing how the scene transitions
FROM visual_end TO visual_start. This will be initially rendered as a forward-playing clip,
then REVERSED during post-processing so the viewer sees visual_start → visual_end.

Rules:
- The motion must be physically plausible as a forward-playing clip.
- Duration: {config['format'].get('panel_duration_s', 7)} seconds total.
- Use timestamps (e.g. "At 2 seconds…") for clarity.
- Be very detailed (100+ words). The AI video model needs precision.
- Do NOT invent new elements — only describe the transition between the two provided states.
- Preserve all lighting and camera details from lights_and_camera.
- Output ONLY a JSON array with the same panel_index values. Each object must have
  exactly two keys: "panel_index" (integer) and "motion_prompt_reversed" (string).

{setting_context}

PANELS TO PROCESS:
{panels_context}
"""

    @retry_on_errors(max_retries=3, backoff_factor=2)
    def _call_api():
        refine_limiter.acquire()
        return generate_json_with_schema(prompt, REVERSAL_SCHEMA)

    result = _call_api()

    if result:
        # Index the LLM output by panel_index for O(1) lookup
        reversed_map = {item['panel_index']: item['motion_prompt_reversed'] for item in result}
        for p in scene.get('panels', []):
            if p.get('is_reversed', False) and p['panel_index'] in reversed_map:
                p['motion_prompt_original'] = p['motion_prompt']
                p['motion_prompt'] = reversed_map[p['panel_index']]
                original_start = p['visual_start']
                original_end   = p['visual_end']
                p['visual_start'] = original_end
                p['visual_end']   = original_start
                logger.info(f"      ✅ Panel {p['panel_index']}: motion_prompt_reversed generated")
            elif p.get('is_reversed', False):
                logger.info(f"      ⚠️  Panel {p['panel_index']}: no motion_prompt_reversed returned by LLM")
    else:
        logger.error(f"      ❌ Reversal LLM call returned empty result for scene {scene.get('scene_id', '?')}")

    return scene

def refine_single_scene(episode_counter, scene_id, episode_text, prompts, config, all_scenes):
    refined_scene = refine_scenes_for_episode(episode_text, prompts, config).get('scenes', [])[0]
    refined_scene['scene_id'] = scene_id
    idx = 0
    for panel in refined_scene['panels']:
        idx += 1
        panel['panel_index'] = idx
        # Ensure defaults for new fields if LLM omitted them
        panel.setdefault('is_reversed', False)
        panel.setdefault('motion_prompt_reversed', '')

    # --- Reversal pass: swap start/end and generate motion_prompt_reversed ---
    refined_scene = apply_reversal_pass(refined_scene, prompts, config)

    all_scenes.append(refined_scene)

    with open(OUTPUT_DIR / f"animation_episode_scenes_{episode_counter:03d}_refined.json", "w", encoding='utf-8') as f:
        json.dump({'scenes': [refined_scene]}, f, ensure_ascii=False, indent=2)

def analyze_scenes_master(text: str, prompts: dict, config: dict):
    episodes = analyze_episodes_master(text, prompts, config)
    auto_cast_characters(json.dumps(episodes, indent=2), prompts, config)

    with open(OUTPUT_DIR / "animation_episodes.json", "w", encoding='utf-8') as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)

    logger.info(episodes)
    all_scenes = []
    scene_counter = 0
    episode_counter = 0
    batch_refinement = []
    batch_analyze = []
    all_episodes = []

    episodes_by_id = {}

    for episode in episodes.get('episodes'):
        episode_counter += 1
        episodes_by_id[episode_counter] = episode
        batch_analyze.append((episode_counter, str(episode), prompts, config, all_episodes))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
         executor.map(lambda x: analyze_scenes_for_episode(*x), batch_analyze)

    # could be shuffled in multi-thread
    all_episodes = sorted(all_episodes, key=lambda e: e[0])

    for episode_counter, data in all_episodes:
        logging.info(f"Processing episode: {episode_counter} scene start: {scene_counter}")
        with open(OUTPUT_DIR / f"animation_episode_scenes_{episode_counter:03d}.json", "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        for scene in data.get('scenes', []):
            scene_counter += 1

            used_refs = []
            for panel in scene.get('panels', []):
                used_refs.extend(panel.get('references', []))

            used_refs = list(set(used_refs))
            json_refs = []
            for ref_name in used_refs:
                if ref_name in CHARACTER_IMAGES:
                    fname = CHARACTER_IMAGES[ref_name].replace('.png', '.json')
                    try:
                        json_refs.append(json.loads(open(fname, 'r').read()))
                    except Exception as e:
                        logger.error(e)

            episode = episodes_by_id[episode_counter]
            json_refs = {ref['name']: ref['video_visual_desc'] for ref in json_refs}

            episode_text = f"""
            EPISODE CONTEXT: {json.dumps(episode, ensure_ascii=False, indent=2)}

            SCENE DETAILS: {json.dumps(scene, ensure_ascii=False, indent=2)}

            VISUAL REFERENCES: {json.dumps(json_refs)}

            ENSURE THAT DESCRIPTIONS IN REFINED SCENE ALIGN WITH VISUAL REFERENCES.
            """
            batch_refinement.append((episode_counter, scene_counter, episode_text, prompts, config, all_scenes))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
         executor.map(lambda x: refine_single_scene(*x), batch_refinement)

    # could be shuffled in multi-thread
    all_scenes = sorted(all_scenes, key=lambda s: s['scene_id'])
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
    logger.info(f"FOUND REFS: {chars}")

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
                    info = json.loads(open(str(path).replace('.png', '.json'), 'r').read()).get('video_visual_desc', '')
                except Exception as e:
                    raise e
                ref_images.append(f"## Visual Reference for: \"{name}\"\nUse it for appearances\n{info}\n\n")
                ref_images.append(img)
                real_chars.append(name)
            except Exception as e:
                logger.error(e)

    logger.info(f"  📎 Scene {scene_id} Refs: {needed_chars} {real_chars}")

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
CONSISTENCY RULE: All instances of the same character across all panels must have IDENTICAL face, hair, clothing, body proportions.
NO CAPTIONS!
"""

    # Описания панелей
    if is_dual_grid:
        combined_prompt += f"\nIMPORTANT: Generate SINGLE {resolution} {aspect_ratio} image with TWO grids vertically stacked (START top, END bottom).\n"
    else:
        combined_prompt += f"\nIMPORTANT: Generate SINGLE {resolution} {aspect_ratio} image with panels in grid layout.\n"

    for p in scene['panels']:
        combined_prompt += f"\nPanel {p['panel_index']}:\n"
        if p.get('is_reversed', False):
            combined_prompt += f"  [REVERSE REVEAL — viewer sees START first, then action unfolds to END]\n"
        if is_dual_grid:
            combined_prompt += f"  START (TOP): {p.get('visual_start', '')}\n"
            combined_prompt += f"  END (BOTTOM): {p.get('visual_end', '')}\n"
            # Use reversed motion prompt when available, fall back to standard
            active_motion = (
                p.get('motion_prompt_reversed', '')
                if p.get('is_reversed', False) and p.get('motion_prompt_reversed')
                else p.get('motion_prompt', '')
            )
            if active_motion:
                combined_prompt += f"  Motion: {active_motion}\n"
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
        logger.info(f"    🎨 Generating {'Dual' if is_dual_grid else 'Single'} Grid ({resolution} {aspect_ratio})...")
        try:
            if ref_images:
                ref_images = ["# Visual Reference Library\n## IMPORTANT:\nAlways prioritize the visual design of characters/objects from the provided images over your internal concepts."] + ref_images + ["Before generating the image, rewrite panels prompt to ensure maximum visual consistency with provided reference images"]
            contents = ref_images + [combined_prompt]
            logger.debug(f"CONTENTS: {contents}")

            @retry_on_errors(max_retries=3, backoff_factor=2)
            def _call_image_api():
                generate_limiter.acquire()
                return client.models.generate_content(
                    model=IMAGE_MODEL, contents=contents,
                    config={
                        'response_modalities': ['Image'],
                        'temperature': IMAGE_TEMPERATURE,
                        'top_p': IMAGE_TOP_P,
                        'seed': SEED,
                        'image_config': {
                            'aspect_ratio': aspect_ratio,
                            'image_size': resolution
                        }
                    }
                )

            resp = _call_image_api()
            logger.debug(resp)
            resp.parts[0].as_image().save(path_combined)
        except Exception as e:
            logger.error(f"FAIL Generation: {e}")
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

    logger.info(f"⚙️  Конфигурация:")
    logger.info(f"  Format: {config['format']['type']}")
    logger.info(f"  Resolution: {config['image_generation']['resolution']}")
    logger.info(f"  Aspect Ratio: {config['image_generation']['aspect_ratio']}")
    logger.info(f"  Panels/Scene: {config['format']['panels_per_scene']}")
    logger.info(f"  Animation: {config['animation']['enabled']}")

    text = Path(args.file).read_text(encoding='utf-8')

    # 1. Casting
    auto_cast_characters(text, prompts, config)

    # 2. Master Analysis
    if args.scene:
        data = json.loads(open(OUTPUT_DIR / "animation_metadata.json", "r").read())
    else:
        data = analyze_scenes_master(text, prompts, config)

    if not data or 'scenes' not in data:
        logger.info("Failed to analyze scenes.")
        return

    # Сохраняем метаданные
    with open(OUTPUT_DIR / "animation_metadata.json", "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 3. Process Scenes
    scenes_to_process = [
        (scene, scene['scene_id'], prompts, config)
        for scene in data['scenes']
        if not args.scene or str(args.scene) == str(scene['scene_id']) or str(args.scene) == 'ALL'
    ]

    if scenes_to_process:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            executor.map(lambda x: generate_combined_grid(*x), scenes_to_process)

    for scene in data['scenes']:
        if not (not args.scene or str(args.scene) == str(scene['scene_id']) or str(args.scene) == 'ALL'):
            logger.warning(f"SKIPPED {scene['scene_id']}")

if __name__ == "__main__":
    main()
