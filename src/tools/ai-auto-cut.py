import os
import json
import argparse
import subprocess
import time
import logging
from pathlib import Path
import google.generativeai as genai
from google.api_core import exceptions

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- JSON SCHEMA ---
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "start_time": {"type": "number", "description": "Start trim point in seconds"},
        "end_time": {"type": "number", "description": "End trim point in seconds"},
        "is_usable": {"type": "boolean", "description": "Whether the clip is high quality and matches script"},
        "edit_notes": {"type": "string", "description": "Detailed explanation of why this cut was chosen and sync points found"},
        "fidelity_score": {"type": "integer", "description": "How well the video matches metadata (1-10)"}
    },
    "required": ["start_time", "end_time", "is_usable", "edit_notes", "fidelity_score"]
}

def safe_generate(model, content, max_retries=3):
    """Генерация контента с защитой от Rate Limit (429)."""
    for i in range(max_retries):
        try:
            return model.generate_content(content)
        except exceptions.ResourceExhausted:
            wait = (i + 1) * 10
            logger.warning(f"Лимит запросов! Ждем {wait} сек...")
            time.sleep(wait)
    return None

def ffmpeg_cut(input_p, output_p, start, end):
    """Высокоточная обрезка видео."""
    duration = max(0.1, end - start)
    cmd = [
        'ffmpeg', '-y', '-ss', str(start), '-i', str(input_p),
        '-t', str(duration), '-c:v', 'libx264', '-preset', 'fast',
        '-crf', '18', '-c:a', 'aac', '-b:a', '192k', str(output_p)
    ]
    subprocess.run(cmd, capture_output=True)

def get_gemini_analysis(video_path, panel):
    """Анализ видео с глубоким учетом метаданных."""
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": ANALYSIS_SCHEMA
        }
    )

    # Загрузка
    video_file = genai.upload_file(path=video_path)
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    # Промпт, учитывающий всё: движение, свет, звук, кадры
    prompt = f"""
    You are a lead editor for a sci-fi movie. Analyze this AI video clip against the technical script.

    ### SCRIPT METADATA:
    - VISUAL START: {panel.get('visual_start')}
    - VISUAL END: {panel.get('visual_end')}
    - MOTION: {panel.get('motion_prompt')}
    - LIGHTING/CAMERA: {panel.get('lights_and_camera')}
    - SOUND/DIALOGUE (SFX): {panel.get('dialogue')}

    ### YOUR GOALS:
    1. Synchronize 'start_time' with the core action (e.g., impact, flash, or movement).
    2. Ensure the lighting changes described are captured.
    3. Cut the video BEFORE the AI begins to 'hallucinate' (limbs melting, background warping).
    4. If the video is a static image or misses the main object (e.g. harpoon), set 'is_usable' to false.

    Provide technical edit notes in 'edit_notes'.
    """

    try:
        response = safe_generate(model, [video_file, prompt])
        return json.loads(response.text) if response else None
    finally:
        genai.delete_file(video_file.name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="Путь к animate_27.json")
    parser.add_argument("--clips-dir", required=True, help="Папка с исходниками")
    parser.add_argument("--cut-clips-dir", required=True, help="Папка для результата")
    args = parser.parse_args()

    os.makedirs(args.cut_clips_dir, exist_ok=True)

    with open(args.json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for scene in data.get("scenes", []):
        s_id = scene['scene_id']
        for panel in scene.get("panels", []):
            p_idx = panel['panel_index']
            # Гибкий поиск файла (поиск clip_27_005 или clip_27_5)
            pattern = f"clip_{s_id}_{p_idx:03d}.mp4"
            input_path = Path(args.clips_dir) / pattern

            if not input_path.exists():
                logger.warning(f"Файл {pattern} не найден. Пропуск.")
                continue

            logger.info(f">>> Анализ {pattern}...")
            analysis = get_gemini_analysis(input_path, panel)

            if not analysis:
                continue

            output_stem = f"clip_{s_id}_{p_idx:03d}_cut"
            output_video = Path(args.cut_clips_dir) / f"{output_stem}.mp4"
            output_json = Path(args.cut_clips_dir) / f"{output_stem}.json"

            if analysis['is_usable'] and analysis['fidelity_score'] > 3:
                ffmpeg_cut(input_path, output_video, analysis['start_time'], analysis['end_time'])
                with open(output_json, 'w', encoding='utf-8') as f_out:
                    json.dump(analysis, f_out, indent=2, ensure_ascii=False)
                logger.info(f"✅ Готово: {output_video.name}. Причина: {analysis['edit_notes']}")
            else:
                logger.error(f"❌ Брак: {pattern}. Заметки: {analysis['edit_notes']}")

if __name__ == "__main__":
    main()
