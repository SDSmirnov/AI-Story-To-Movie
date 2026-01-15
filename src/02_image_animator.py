import os
import time
import json
from pathlib import Path
from google import genai
from google.api_core import exceptions
from PIL import Image
from google.genai import types
from io import BytesIO


# Инициализация
client = genai.Client()

# Конфигурация путей
PANELS_DIR = Path("cinematic_render/panels")
OUT_DIR    = Path("cinematic_render/clips")
META_FILE  = Path("cinematic_render/animation_metadata.json")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Модель (Veo 3.1 Fast - оптимальна для превью)
MODEL = "veo-3.1-fast-generate-preview" # "veo-3.1-generate-preview"
# MODEL = "veo-3.1-generate-preview" # "veo-3.1-generate-preview"

DEFAULT_RESOLUTION = '720p'

# load reference images
CHARACTER_IMAGES = {}
REF_DIR = Path("ref_thriller")

for f in REF_DIR.glob("*.png"):
    name = f.stem.replace("_", " ").title()
    CHARACTER_IMAGES[name] = str(f)

def load_metadata():
    if not META_FILE.exists():
        return {}
    with open(META_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    lookup = {}
    for scene in data.get('scenes', []):
        sid = scene['scene_id']
        for panel in scene['panels']:
            # Ключ: scene_ID_panel_ID
            key = f"{sid:03d}_{panel['panel_index']:02d}"
            lookup[key] = panel
    return lookup

def upload_image(image_path: Path):
    """Загружает изображение для API"""
    if not image_path.exists():
        return None
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    return {'image_bytes': image_bytes, 'mime_type': 'image/png'}

def need_references(meta, image):
    prompt = f"""
    Animation with references is expensive.
    Analyze scene image and visual descriptions, identify if any of character references are indeed needed here for animation.
    Example: motion_prompt or visual_end may reference something not yet present in visual start frame, or person on the first frame could have face turned from the camera.
    If chars are visible for quick 4 second Veo animation, then no need to pass refs.
    Find only references missing on the visual start but required for visual end according to scene.
    I do not need perfect animation, but I need cheap and fast.

    Scene Info:

    {json.dumps(meta, indent=2)}

    Response format, JSON:
    {{
        'need_references': "YES or SKIP",
        'reason': "Explain why",
        'refs_to_provide': 'List of the references from scene which MUST be used, max TWO most important items'
    }}

    """
    schema = {
        "type": "object",
        "properties": {
            "need_references": { "type": "string" },
            "reason": {"type": "string"},
            "refs_to_provide": { "type": "array", "items": { "type": "string" } },
        },
        "required": ["need_references", "reason", "refs_to_provide"],
    }
    resp = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=[prompt, image],
        config={'response_mime_type': "application/json", 'response_schema': schema}
    )
    print(f"RESP: {resp.text}")
    return json.loads(resp.text).get('refs_to_provide', [])

def generate_clip_interpolation(start_path: Path, meta: dict, index: int):
    """
    Генерирует видео через интерполяцию (Start Frame -> End Frame).
    """
    # 1. Сначала определяем имя выходного файла
    clip_id = start_path.stem.replace('_start', '') # получаем, например, "001_01"
    out_name = f"clip_{clip_id}.mp4"
    out_path = OUT_DIR / out_name

    # 2. ПРОВЕРКА: Если файл уже есть и он не пустой — пропускаем
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[{index:02d}] ⏭️  Skipping: {out_name} already exists.")
        return

    # Если файла нет — начинаем тратить квоту
    motion_prompt = meta.get('motion_prompt', 'Cinematic movement')
    prompt = (
        f"Cinematic shot. {meta}. "
        "Smooth transition, high temporal consistency."
        "Style: Hyper-realistic cinematic photography, shot on Arri Alexa Mini LF with 50mm lens."
    )

    print(f"[{index:02d}] 🎥 Interpolating: {start_path.name}")
    print(f"       Prompt: {motion_prompt[:50]}...")

    img_start = upload_image(start_path)

    end_path = Path(f"{clip_id}_end.png")
    img_end = None
    if end_path.exists():
        img_end = upload_image(start_path)

    if not img_start:
        print(f"[{index:02d}] ❌ Error: Missing start or end image file.")
        return

    need_chars = need_references(meta, Image.open(start_path))
    ref_images = []
    for name in need_chars:
        name = name.title()
        print([name, name in CHARACTER_IMAGES]);
        if name in CHARACTER_IMAGES:
            path = CHARACTER_IMAGES[name]
            try:
                img = Image.open(path)
                ref_images.append({'image': img, 'reference_type': 'asset'})
            except Exception as e:
                raise e

    config = {
        'duration_seconds': 4,
        'aspect_ratio': "16:9",
        'resolution': DEFAULT_RESOLUTION,
    }

    dialogue_len = len(meta.get('dialogue').split(' '))

    if need_chars or dialogue_len > 15:
        # add references or extend time to fit dialogue
        config['duration_seconds'] = 8
        if ref_images:
            config['reference_images'] = ref_images

    elif dialogue_len > 10:
        # make a bit longer
        config['duration_seconds'] = 6

    else:
        # short action, no dialogue
        config['duration_seconds'] = 4

    if img_end:
        config.pop('reference_images', [])
        config['duration'] = 8
        config['last_frame'] = img_end

    try:
        print(config)
        if config.get('reference_images'):
            formatted_refs = []
            config['reference_images'] = [{'image': Image.open(start_path)}] + config['reference_images']
            for item in config['reference_images']:
                pil_img = item['image']
                b = BytesIO()
                pil_img.save(b, format="PNG")
                formatted_refs.append(types.VideoGenerationReferenceImage(
                        image=types.Image(image_bytes=b.getvalue(), mime_type='image/png'),
                        reference_type="asset"
                    )
                )

            config = types.GenerateVideosConfig(
                duration_seconds=8,
                aspect_ratio="16:9",
                resolution=DEFAULT_RESOLUTION,
                reference_images=formatted_refs
            )

            operation = client.models.generate_videos(
                model=MODEL,
                prompt=prompt,
                config=config,
            )
        else:
            operation = client.models.generate_videos(
                model=MODEL,
                prompt=prompt,
                image=img_start,
                config=config,
            )


        while not operation.done:
            print(f"[{index:02d}] ... generating (8s interpolation)")
            time.sleep(10)
            operation = client.operations.get(operation)

        if operation.error:
            raise RuntimeError(f"API Error: {operation.error}")

        if not operation.response.generated_videos:
            print(f"[{index:02d}] ⚠️ No video returned.")
            return

        video = operation.response.generated_videos[0]

        # Скачиваем и сохраняем
        video_bytes = client.files.download(file=video)
        with open(out_path, 'wb') as f:
            f.write(video_bytes)

        print(f"[{index:02d}] ✅ Saved: {out_path}")

    except exceptions.ResourceExhausted:
        print(f"\n[{index:02d}] 🛑 QUOTA EXHAUSTED (429).")
        print("       Лимит запросов исчерпан. Остановите скрипт и запустите завтра.")
        print("       Благодаря проверке файлов, завтра он продолжит с этого места.")
        import sys; sys.exit(0) # Жесткий выход, чтобы не спамить ошибками

    except Exception as e:
        print(f"[{index:02d}] ❌ Exception: {e}")

def main():
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY not set!")

    metadata = load_metadata()
    start_files = sorted(PANELS_DIR.glob("*_static.png"))

    if not start_files:
        start_files = sorted(PANELS_DIR.glob("*_start.png"))

    if not start_files:
        print(f"No *_start.png files found in {PANELS_DIR}")
        return

    print(f"Found {len(start_files)} pairs to animate.")
    print(f"Checking existing clips in {OUT_DIR}...\n")

    for i, start_path in enumerate(start_files):
        # Ключ: 001_01
        key = "_".join(start_path.stem.split("_")[:2])
        panel_meta = metadata.get(key, {})

        generate_clip_interpolation(start_path, panel_meta, i)

    print(f"\n{'='*30}\nAll done! Check {OUT_DIR}")

if __name__ == "__main__":
    main()
