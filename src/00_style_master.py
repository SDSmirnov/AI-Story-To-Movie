"""
Style Master - генератор кастомных промптов под заданный визуальный стиль.
Анализирует книгу (жанр, сеттинг, POV) и создаёт оптимальные промпты для стиля.
"""
import google.generativeai as ggenai
import json
import os
import argparse
from pathlib import Path

# --- КОНФИГУРАЦИЯ ---
TEXT_MODEL = "gemini-2.5-pro"

api_key = os.getenv('IMG_AI_API_KEY', '')
if not api_key:
    print("❌ ОШИБКА: Не найден API ключ")
    exit(1)

ggenai.configure(api_key=api_key)

# Папки
PROMPTS_DIR = Path("prompts")
CUSTOM_DIR = Path("custom_prompts")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

SYSTEM = """
Твоя роль: ассистент редактора, задача - анализ произведения.
"""

# === СТИЛИ И ИХ ХАРАКТЕРИСТИКИ ===
STYLE_PRESETS = {
    "realistic_movie": {
        "name": "Realistic Cinematic",
        "format": "single_grid_animation",
        "panels_per_scene": 9,
        "aspect_ratio": "16:9",
        "resolution": "2K",
        "needs_start_end": True,
        "needs_dialogue": True,
        "needs_captions": False,
        "camera_style": "cinematic_fpov"
    },
    "anime": {
        "name": "Anime Style",
        "format": "single_grid",
        "panels_per_scene": 6,
        "aspect_ratio": "16:9",
        "resolution": "2K",
        "needs_start_end": False,
        "needs_dialogue": True,
        "needs_captions": False,
        "camera_style": "dynamic_angles"
    },
    "comic_book": {
        "name": "Comic Book",
        "format": "single_grid",
        "panels_per_scene": 9,
        "aspect_ratio": "2:3",
        "resolution": "2K",
        "needs_start_end": False,
        "needs_dialogue": True,
        "needs_captions": False,
        "camera_style": "comic_dramatic"
    },
    "graphic_novel": {
        "name": "Graphic Novel",
        "format": "single_grid",
        "panels_per_scene": 6,
        "aspect_ratio": "2:3",
        "resolution": "2K",
        "needs_start_end": False,
        "needs_dialogue": False,
        "needs_captions": True,
        "camera_style": "artistic_composition"
    },
    "watchmen_style": {
        "name": "The Watchmen Comic",
        "format": "single_grid",
        "panels_per_scene": 9,
        "aspect_ratio": "2:3",
        "resolution": "2K",
        "needs_start_end": False,
        "needs_dialogue": True,
        "needs_captions": True,
        "camera_style": "symmetrical_grounded"
    }
}

def load_template(filename: str) -> str:
    """Загружает шаблон из prompts/"""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ""

def analyze_novel(text: str) -> dict:
    """Анализирует текст романа для извлечения метаданных"""
    print("📖 Анализ романа...")

    prompt = f"""
Analyze this novel excerpt and extract key metadata:

1. **Genre**: What are the primary genres? (e.g., Fantasy, Sci-Fi, Historical, LitRPG, Romance, Thriller)
2. **Setting**: Time period, location, world type (realistic, fantasy, sci-fi, alternate history)
3. **POV**: First-person, Third-person limited, Third-person omniscient, Second-person
4. **Tone**: Overall atmosphere (dark, heroic, comedic, serious, romantic, gritty)
5. **Main Character**: Name and brief description of protagonist
6. **Special Elements**: Magic systems, technology, supernatural elements, game mechanics, etc.
7. **Visual Atmosphere**: Key visual themes (dark alleys, grand ballrooms, space stations, medieval castles)

Return as JSON:
{{
  "genre": ["genre1", "genre2"],
  "setting": {{"period": "...", "location": "...", "world_type": "..."}},
  "pov": "...",
  "tone": ["tone1", "tone2"],
  "main_character": {{"name": "...", "description": "..."}},
  "special_elements": ["element1", "element2"],
  "visual_atmosphere": ["atmosphere1", "atmosphere2"]
}}

Novel excerpt (first 3000 chars):
{text[:100000]}
"""

    generation_config = {
        "temperature": 0.3,
        "response_mime_type": "application/json",
        "max_output_tokens": 4096,
    }

    model = ggenai.GenerativeModel(TEXT_MODEL, generation_config=generation_config, safety_settings=SAFETY, system_instruction=SYSTEM)
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY)
        return json.loads(response.text)
    except Exception as e:
        print(f"    ❌ Ошибка анализа: {e}")
        return {}

def generate_custom_prompts(novel_data: dict, style_name: str):
    """Генерирует кастомные промпты под заданный стиль"""
    print(f"\n🎨 Генерация промптов для стиля: {style_name}")

    # Нормализация имени стиля
    style_key = style_name.lower().replace(" ", "_").replace("the_", "")
    if style_key not in STYLE_PRESETS:
        # Попытка найти похожий
        for key in STYLE_PRESETS:
            if key in style_key or style_key in key:
                style_key = key
                break
        else:
            style_key = "realistic_movie"  # Default

    preset = STYLE_PRESETS[style_key]
    print(f"  ✓ Использую пресет: {preset['name']}")

    # === 1. STYLE.MD ===
    print("  📝 Генерация style.md...")
    style_template = load_template("style.md")

    style_prompt = f"""
Based on this novel metadata: {json.dumps(novel_data, ensure_ascii=False)}
And target visual style: {preset['name']}

Generate a complete style.md file following this template structure:
{style_template}

Fill ALL placeholders with specific values appropriate for {preset['name']} style.

For {preset['name']}:
- Camera equipment and techniques specific to this medium
- Rendering style (photorealistic, cel-shaded, ink and halftone, painted, etc.)
- Appropriate atmosphere keywords from the novel's tone
- Color grading matching both style and novel atmosphere
- Technical specs: resolution={preset['resolution']}, aspect_ratio={preset['aspect_ratio']}

Return ONLY the filled markdown content, no explanations.
"""

    style_md = generate_text(style_prompt)
    (CUSTOM_DIR / "style.md").write_text(style_md, encoding='utf-8')

    # === 2. CASTING.MD ===
    print("  📝 Генерация casting.md...")
    casting_template = load_template("casting.md")

    casting_prompt = f"""
Based on novel: {json.dumps(novel_data, ensure_ascii=False)}
Visual style: {preset['name']}

Generate casting.md following template:
{casting_template}

Adjust character description format for {preset['name']}:
- Realistic movie: photorealistic actor descriptions
- Anime: anime character design (hair style, eye shape, costume details)
- Comic: bold features, distinctive visual traits, iconic costume
- Graphic novel: artistic, expressive features

Reference shot should match style ({preset['ref_aspect_ratio'] if 'ref_aspect_ratio' in preset else '3:4'}).

Return filled markdown.
"""

    casting_md = generate_text(casting_prompt)
    (CUSTOM_DIR / "casting.md").write_text(casting_md, encoding='utf-8')

    # === 3. SCENERY.MD ===
    print("  📝 Генерация scenery.md...")
    scenery_template = load_template("scenery.md")

    scenery_prompt = f"""
Novel metadata: {json.dumps(novel_data, ensure_ascii=False)}
Style: {preset['name']}
Format: {preset['format']}
Panels per scene: {preset['panels_per_scene']}

Generate scenery.md from template:
{scenery_template}

Key adjustments:
- If needs_start_end={preset['needs_start_end']}: Include START/END frame instructions
- If needs_start_end=False: Focus on single key moment per panel
- Panel duration: {"6-8s for animation" if preset['needs_start_end'] else "N/A (static)"}
- Camera POV: {preset['camera_style']}
- Composition: Match {preset['name']} conventions

Return filled markdown.
"""

    scenery_md = generate_text(scenery_prompt)
    (CUSTOM_DIR / "scenery.md").write_text(scenery_md, encoding='utf-8')

    # === 4. IMAGERY.MD ===
    print("  📝 Генерация imagery.md...")
    imagery_template = load_template("imagery.md")

    imagery_prompt = f"""
Style: {preset['name']}
Format: {preset['format']}
Resolution: {preset['resolution']}
Aspect ratio: {preset['aspect_ratio']}
Panels: {preset['panels_per_scene']}

Generate imagery.md from template:
{imagery_template}

Specify:
- Grid structure for {preset['format']}
- Layout description (single grid vs dual grid)
- Composition rules specific to {preset['name']}
- Visual consistency requirements
- Special rendering instructions (film grain, halftone dots, cel shading, etc.)

Return filled markdown.
"""

    imagery_md = generate_text(imagery_prompt)
    (CUSTOM_DIR / "imagery.md").write_text(imagery_md, encoding='utf-8')

    # === 5. SETTING.MD ===
    print("  📝 Генерация setting.md...")
    setting_template = load_template("setting.md")

    setting_md_content = setting_template
    # Заполняем из novel_data
    replacements = {
        "{{genre_description}}": ", ".join(novel_data.get('genre', [])),
        "{{setting_description}}": json.dumps(novel_data.get('setting', {}), ensure_ascii=False),
        "{{atmosphere_description}}": ", ".join(novel_data.get('tone', [])),
        "{{pov_character}}": novel_data.get('main_character', {}).get('name', 'Unknown'),
        "{{narrator_style}}": novel_data.get('pov', 'Third-person'),
        "{{visual_tone}}": ", ".join(novel_data.get('tone', [])),
        "{{special_visual_elements}}": "\n  - ".join(novel_data.get('special_elements', [])),
        "{{hero_visual_description}}": novel_data.get('main_character', {}).get('description', ''),
        "{{composition_preferences}}": preset['camera_style'],
        "{{world_specific_details}}": "\n  - ".join(novel_data.get('visual_atmosphere', []))
    }

    for key, value in replacements.items():
        setting_md_content = setting_md_content.replace(key, str(value))

    (CUSTOM_DIR / "setting.md").write_text(setting_md_content, encoding='utf-8')

    # === 6. CONFIG.JSON ===
    print("  📝 Генерация config.json...")

    config = {
        "format": {
            "type": preset['format'],
            "panels_per_scene": preset['panels_per_scene'],
            "frames_per_panel": 2 if preset['needs_start_end'] else 1
        },
        "image_generation": {
            "aspect_ratio": preset['aspect_ratio'],
            "resolution": preset['resolution'],
            "image_size": preset['resolution']
        },
        "animation": {
            "enabled": preset['needs_start_end'],
            "keyframe_type": "start_end" if preset['needs_start_end'] else "static"
        },
        "slicing": {
            "enabled": True,
            "frame_types": ["start", "end"] if preset['needs_start_end'] else ["static"]
        },
        "dialogue": {
            "enabled": preset['needs_dialogue'],
            "placement": "metadata_only" if not preset['needs_captions'] else "captions"
        },
        "captions": {
            "enabled": preset['needs_captions']
        },
        "reference_characters": {
            "enabled": True,
            "auto_cast": True
        }
    }

    (CUSTOM_DIR / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\n✅ Кастомные промпты созданы в {CUSTOM_DIR}/")

def generate_text(prompt: str) -> str:
    """Генерирует текст через Gemini"""
    generation_config = {
        "temperature": 0.5,
        "max_output_tokens": 8192,
    }
    model = ggenai.GenerativeModel(TEXT_MODEL, generation_config=generation_config, safety_settings=SAFETY, system_instruction=SYSTEM)
    try:
        response = model.generate_content(prompt, safety_settings=SAFETY)
        return response.text
    except Exception as e:
        print(f"    ❌ Ошибка генерации: {e}")
        return ""

def main():
    parser = argparse.ArgumentParser(description="Генерация кастомных промптов под визуальный стиль")
    parser.add_argument('novel', help='Путь к файлу с текстом романа')
    parser.add_argument('--style', default='realistic_movie',
                       help='Визуальный стиль: realistic_movie, anime, comic_book, graphic_novel, watchmen_style')
    args = parser.parse_args()

    # Загрузка текста
    novel_path = Path(args.novel)
    if not novel_path.exists():
        print(f"❌ Файл не найден: {args.novel}")
        return

    text = novel_path.read_text(encoding='utf-8')

    # Анализ романа
    novel_data = analyze_novel(text)
    if not novel_data:
        print("❌ Не удалось проанализировать роман")
        return

    print(f"\n📊 Метаданные романа:")
    print(f"  Жанр: {', '.join(novel_data.get('genre', []))}")
    print(f"  POV: {novel_data.get('pov', 'N/A')}")
    print(f"  ГГ: {novel_data.get('main_character', {}).get('name', 'N/A')}")

    # Генерация промптов
    generate_custom_prompts(novel_data, args.style)

    print(f"\n🎬 Готово! Теперь запустите:")
    print(f"   python 01_cinematic_preroll.py {args.novel} --custom-prompts")

if __name__ == "__main__":
    main()
