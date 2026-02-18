#!/usr/bin/env python3
"""
Grid Quality Gate — мультимодальный аудит сгенерированных гридов.

Берёт scene_*_grid_combined.png, нарезает на панели, сравнивает каждую
панель с референсами персонажей/локаций через Gemini 2.5 Flash и выдаёт
JSON-отчёт с оценкой fidelity и промптами для перегенерации.

Usage:
    python 05_grid_quality_gate.py                         # все сцены
    python 05_grid_quality_gate.py --scene 16              # одна сцена
    python 05_grid_quality_gate.py --scene 16 --panel 1 5  # конкретные панели
    python 05_grid_quality_gate.py --threshold 6           # порог fidelity (дефолт 5)
    python 05_grid_quality_gate.py --ref-dir ref_thriller  # папка с референсами

Requires:
    pip install google-genai Pillow

Environment:
    GOOGLE_API_KEY or IMG_AI_API_KEY
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from google import genai
from PIL import Image

# ─────────────────────────────────────────────
# Конфигурация
# ─────────────────────────────────────────────
ANALYSIS_MODEL = os.getenv("AI_QA_MODEL", "gemini-2.5-flash")
MAX_WORKERS = int(os.getenv("AI_QA_CONCURRENCY", "20"))
MAX_REFS_PER_PANEL = int(os.getenv("AI_QA_MAX_REFS", "6"))

OUTPUT_DIR = Path("cinematic_render")
META_FILE = OUTPUT_DIR / "animation_metadata.json"
REPORT_FILE = OUTPUT_DIR / "quality_report.json"

logging.basicConfig(
    level=os.getenv("AI_LOG_LEVEL", "INFO"),
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# API клиент
# ─────────────────────────────────────────────
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("IMG_AI_API_KEY", "")
if not api_key:
    logger.error("❌ Не задан GOOGLE_API_KEY или IMG_AI_API_KEY")
    sys.exit(1)

client = genai.Client(api_key=api_key)

SAFETY = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# ─────────────────────────────────────────────
# Rate limiter (переиспользуем паттерн из 01_)
# ─────────────────────────────────────────────
class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.tokens = float(rpm)
        self.max_tokens = float(rpm)
        self.last_update = time.time()
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * (self.rpm / 60.0))
            self.last_update = now
            if self.tokens < 1:
                wait = (1 - self.tokens) * (60.0 / self.rpm)
                time.sleep(wait)
                self.tokens = 0
            else:
                self.tokens -= 1


rate_limiter = RateLimiter(rpm=30)

# ─────────────────────────────────────────────
# JSON-схема ответа Gemini
# ─────────────────────────────────────────────
PANEL_QA_SCHEMA = {
    "type": "object",
    "properties": {
        "fidelity": {
            "type": "integer",
            "description": (
                "Overall visual fidelity score 0-10. "
                "10 = perfect match to references and description. "
                "0 = completely wrong."
            ),
        },
        "character_consistency": {
            "type": "integer",
            "description": (
                "How well characters match their reference images 0-10. "
                "Evaluate face, hair, build, clothing, helmet design. "
                "0 if no characters expected. 10 = identical to reference."
            ),
        },
        "composition_match": {
            "type": "integer",
            "description": (
                "How well the panel matches the requested shot type, "
                "camera angle, and framing 0-10."
            ),
        },
        "artifacts": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "List of specific visual artifacts or errors found: "
                "extra fingers, melted faces, wrong number of people, "
                "text/watermarks, broken geometry, etc."
            ),
        },
        "needs_refinement": {
            "type": "boolean",
            "description": "True if the panel should be regenerated or refined.",
        },
        "refinement_prompt": {
            "type": "string",
            "description": (
                "If needs_refinement is true: a precise prompt describing "
                "WHAT to fix. Reference specific issues. "
                "If false: empty string."
            ),
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of the scores.",
        },
    },
    "required": [
        "fidelity",
        "character_consistency",
        "composition_match",
        "artifacts",
        "needs_refinement",
        "refinement_prompt",
        "reasoning",
    ],
}

# ─────────────────────────────────────────────
# Загрузка данных
# ─────────────────────────────────────────────

def load_metadata(meta_path: Path) -> Dict:
    if not meta_path.exists():
        logger.error(f"❌ Метаданные не найдены: {meta_path}")
        sys.exit(1)
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ref_catalog(ref_dir: Path) -> Dict[str, Dict]:
    """
    Сканирует ref_dir и строит каталог:
    { "Eckels": { "json": {...}, "img_path": Path, "video_visual_desc": "..." }, ... }
    """
    catalog: Dict[str, Dict] = {}
    if not ref_dir.exists():
        logger.warning(f"⚠️  Папка референсов не найдена: {ref_dir}")
        return catalog

    for json_file in ref_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        name = data.get("name", json_file.stem)
        img_path = json_file.with_suffix(".png")

        entry: Dict[str, Any] = {
            "json": data,
            "img_path": img_path if img_path.exists() else None,
            "visual_desc": data.get("visual_desc", ""),
            "video_visual_desc": data.get("video_visual_desc", ""),
            "type": data.get("type", "unknown"),
        }
        catalog[name] = entry

        # Дублируем по нормализованному имени для fuzzy-поиска
        norm = name.lower().replace(" ", "_").replace("-", "_")
        if norm != name:
            catalog[norm] = entry

    logger.info(f"📂 Загружено {len(set(id(v) for v in catalog.values()))} референсов из {ref_dir}")
    return catalog


def find_ref(name: str, catalog: Dict[str, Dict]) -> Optional[Dict]:
    """Ищет референс по имени с fuzzy-нормализацией."""
    if name in catalog:
        return catalog[name]
    norm = name.lower().replace(" ", "_").replace("-", "_").replace("'", "").replace('"', "")
    if norm in catalog:
        return catalog[norm]
    # Пробуем Title Case
    title = name.replace("-", " ").replace("_", " ").title().replace(" ", "_")
    if title in catalog:
        return catalog[title]
    return None


# ─────────────────────────────────────────────
# Нарезка грида на панели
# ─────────────────────────────────────────────

def slice_grid(grid_path: Path, panels_count: int, is_dual: bool) -> List[Image.Image]:
    """
    Нарезает combined grid на отдельные панели.
    Для single_grid: 3x3 = 9 панелей.
    Для dual_grid: верхняя половина = START, нижняя = END (берём только START).
    """
    img = Image.open(grid_path)
    w, h = img.size

    if panels_count == 9:
        cols, rows = 3, 3
    elif panels_count == 6:
        cols, rows = 3, 2
    elif panels_count == 4:
        cols, rows = 2, 2
    else:
        cols = 3
        rows = (panels_count + 2) // 3

    if is_dual:
        half_h = h // 2
        pw, ph = w // cols, half_h // rows
        # Берём START-фреймы (верхняя половина)
        panels = []
        for r in range(rows):
            for c in range(cols):
                box = (c * pw, r * ph, (c + 1) * pw, (r + 1) * ph)
                panels.append(img.crop(box))
        return panels
    else:
        pw, ph = w // cols, h // rows
        panels = []
        for r in range(rows):
            for c in range(cols):
                if len(panels) >= panels_count:
                    break
                box = (c * pw, r * ph, (c + 1) * pw, (r + 1) * ph)
                panels.append(img.crop(box))
        return panels


# ─────────────────────────────────────────────
# Анализ одной панели через Gemini
# ─────────────────────────────────────────────

def analyze_panel(
    panel_img: Image.Image,
    panel_meta: Dict,
    scene_meta: Dict,
    ref_catalog: Dict[str, Dict],
    scene_id: int,
    panel_id: int,
    threshold: int,
) -> Dict:
    """Отправляет панель + референсы в Gemini Flash для QA."""

    # Собираем референсы для этой панели
    ref_names = panel_meta.get("references", [])
    ref_images_content: List[Any] = []
    ref_descriptions: List[str] = []
    loaded_refs: List[str] = []

    for rname in ref_names[:MAX_REFS_PER_PANEL]:
        ref = find_ref(rname, ref_catalog)
        if ref and ref.get("img_path"):
            try:
                rimg = Image.open(ref["img_path"])
                desc = ref.get("video_visual_desc") or ref.get("visual_desc", "")
                ref_images_content.append(f'Reference "{rname}" ({ref.get("type", "?")}):\n{desc}')
                ref_images_content.append(rimg)
                ref_descriptions.append(f"- {rname}: {desc[:200]}")
                loaded_refs.append(rname)
            except Exception as e:
                logger.warning(f"  ⚠️  Не удалось загрузить референс {rname}: {e}")

    # Формируем промпт
    visual_desc = panel_meta.get("visual_start", "")
    if not visual_desc:
        visual_desc = panel_meta.get("visual_end", "")

    prev_panels = [{'panel_index': p['panel_index'], 'visual_desc': p['visual_end']} for p in scene_meta.get('panels') if p['panel_index'] < panel_meta['panel_index']]
    prompt = f"""You are a QA supervisor for an AI film production pipeline.

## TASK
Analyze this PANEL IMAGE against its script description and character references.
Score the visual fidelity and decide if the panel needs regeneration.

## SCENE CONTEXT
Scene ID: {scene_meta.get('scene_id')}
Location: {scene_meta.get('location', 'N/A')}
Setup: {scene_meta.get('pre_action_description', '')}

## PREVIOUS PANELS - FOR CONTEXT AND CONSISTENCY CHECKS
<PREV_PANELS>{json.dumps(prev_panels, ensure_ascii=False, indent=2)}</PREV_PANELS>


## ANALYZED PANEL {panel_id} DESCRIPTION
Visual: {visual_desc}
Camera/Lighting: {panel_meta.get('lights_and_camera', '')}
Motion intent: {panel_meta.get('motion_prompt', '')[:300]}
Expected characters/objects: {', '.join(ref_names) if ref_names else 'None specified'}

## SCORING CRITERIA
- **fidelity** (0-10): Overall match to the description above.
- **character_consistency** (0-10): Do characters match the reference images?
  Check: face shape, hair color/style, age, build, clothing, helmet design.
  If the same character appears different from their reference, score LOW.
  Score 0 if no character references were expected for this panel.
- **composition_match** (0-10): Does the shot type, angle, framing match?
- **artifacts**: List ALL visual problems (extra limbs, wrong face, melted features,
  text overlays, wrong number of people, missing objects, etc.)
- **needs_refinement**: True if fidelity < {threshold} OR character_consistency < {threshold}
  OR critical artifacts exist.
- **refinement_prompt**: If needs_refinement, describe EXACTLY what to fix.
  Be specific: "Eckels' face does not match reference — wrong jaw shape, hair should
  be silver not brown. Helmet has circular viewport but should be fully transparent sphere."

## IMPORTANT
- Compare character faces CAREFULLY against reference images.
- Even small differences (hair color, eye color, facial structure) matter.
- A panel with beautiful composition but WRONG character face scores LOW on character_consistency.
- Panels without character references (landscapes, objects) can score 0 on character_consistency
  without needing refinement for that reason.
- Check narrative continuity 

"""

    contents: List[Any] = []

    # Референсы первыми
    if ref_images_content:
        contents.append("# CHARACTER/OBJECT REFERENCE IMAGES\n")
        contents.extend(ref_images_content)

    # Панель для анализа
    contents.append(f"\n# PANEL {panel_id} TO ANALYZE\n")
    contents.append(panel_img)

    # Промпт последним
    contents.append(prompt)

    # Вызов API
    rate_limiter.acquire()
    try:
        resp = client.models.generate_content(
            model=ANALYSIS_MODEL,
            contents=contents,
            config={
                "safety_settings": SAFETY,
                "response_mime_type": "application/json",
                "response_schema": PANEL_QA_SCHEMA,
                "temperature": 0.2,
                "max_output_tokens": 32048,
            },
        )
        result = json.loads(resp.text)
    except Exception as e:
        logger.error(f"  ❌ Gemini error scene {scene_id} panel {panel_id}: {e}")
        result = {
            "fidelity": 0,
            "character_consistency": 0,
            "composition_match": 0,
            "artifacts": [f"API_ERROR: {str(e)[:200]}"],
            "needs_refinement": True,
            "refinement_prompt": "API call failed, manual review required.",
            "reasoning": f"Error: {e}",
        }

    # Обогащаем результат метаданными
    result["scene_id"] = scene_id
    result["panel_id"] = panel_id
    result["references_expected"] = ref_names
    result["references_loaded"] = loaded_refs

    return result


# ─────────────────────────────────────────────
# Обработка одной сцены
# ─────────────────────────────────────────────

def process_scene(
    scene: Dict,
    ref_catalog: Dict[str, Dict],
    grid_format: str,
    panels_per_scene: int,
    threshold: int,
    panel_filter: Optional[List[int]] = None,
) -> List[Dict]:
    """Анализирует все панели одной сцены."""
    scene_id = scene["scene_id"]

    # Ищем grid файл
    grid_path = OUTPUT_DIR / f"scene_{scene_id:03d}_grid_combined.png"
    if not grid_path.exists():
        logger.warning(f"⏭️  Грид не найден: {grid_path}")
        return []

    is_dual = "dual" in grid_format
    panel_images = slice_grid(grid_path, panels_per_scene, is_dual)

    panels = sorted(scene.get("panels", []), key=lambda p: p["panel_index"])
    results = []

    for panel_meta in panels:
        pid = panel_meta["panel_index"]

        if panel_filter and pid not in panel_filter:
            continue

        if pid < 1 or pid > len(panel_images):
            logger.warning(f"  ⚠️  Panel {pid} out of range (have {len(panel_images)} images)")
            continue

        scene_id = scene['scene_id']
        panel_img = panel_images[pid - 1]

        logger.info(f"  🔍 Scene {scene_id}, Panel {pid} "
                     f"(refs: {panel_meta.get('references', [])})")

        result = analyze_panel(
            panel_img=panel_img,
            panel_meta=panel_meta,
            scene_meta=scene,
            ref_catalog=ref_catalog,
            scene_id=scene_id,
            panel_id=pid,
            threshold=threshold,
        )
        results.append(result)

        # Логирование
        fid = result["fidelity"]
        cc = result["character_consistency"]
        need = "🔴 NEEDS FIX" if result["needs_refinement"] else "🟢 OK"
        logger.info(f"    → fidelity={fid}/10  char_consistency={cc}/10  {need}")

        if result["artifacts"]:
            for art in result["artifacts"][:3]:
                logger.info(f"       ⚠️  {art}")

    return results


# ─────────────────────────────────────────────
# Генерация сводного отчёта
# ─────────────────────────────────────────────

def print_summary(results: List[Dict], threshold: int):
    """Печатает таблицу-сводку."""
    if not results:
        logger.info("Нет результатов для отображения.")
        return

    total = len(results)
    needs_fix = sum(1 for r in results if r["needs_refinement"])
    avg_fid = sum(r["fidelity"] for r in results) / total
    avg_cc = sum(r["character_consistency"] for r in results) / total

    print(f"\n{'=' * 72}")
    print(f"{'QUALITY GATE REPORT':^72}")
    print(f"{'=' * 72}")
    print(f"  Panels analyzed:      {total}")
    print(f"  Average fidelity:     {avg_fid:.1f}/10")
    print(f"  Average char cons.:   {avg_cc:.1f}/10")
    print(f"  Threshold:            {threshold}")
    print(f"  🟢 Passed:            {total - needs_fix}")
    print(f"  🔴 Needs refinement:  {needs_fix}")
    print(f"{'=' * 72}\n")

    if needs_fix:
        print("PANELS REQUIRING ATTENTION:\n")
        print(f"  {'Scene':>5}  {'Panel':>5}  {'Fid':>4}  {'Char':>4}  {'Artifacts'}")
        print(f"  {'─' * 5}  {'─' * 5}  {'─' * 4}  {'─' * 4}  {'─' * 40}")

        for r in sorted(results, key=lambda x: x["fidelity"]):
            if not r["needs_refinement"]:
                continue
            arts = "; ".join(r["artifacts"][:2]) if r["artifacts"] else "—"
            if len(arts) > 50:
                arts = arts[:47] + "..."
            print(
                f"  {r['scene_id']:>5}  {r['panel_id']:>5}  "
                f"{r['fidelity']:>4}  {r['character_consistency']:>4}  {arts}"
            )

        print()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Grid Quality Gate — мультимодальный аудит панелей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python 05_grid_quality_gate.py                          # все сцены
  python 05_grid_quality_gate.py --scene 16               # одна сцена
  python 05_grid_quality_gate.py --scene 16 --panel 1 5 7 # конкретные панели
  python 05_grid_quality_gate.py --threshold 6            # строже
  python 05_grid_quality_gate.py --ref-dir ref_scifi      # другой проект
        """,
    )

    parser.add_argument("--scene", type=int, nargs="+", help="ID сцен для проверки")
    parser.add_argument("--panel", type=int, nargs="+", help="ID панелей (требует --scene с одной сценой)")
    parser.add_argument("--threshold", type=int, default=5, help="Порог fidelity для refinement (дефолт: 5)")
    parser.add_argument("--ref-dir", type=str, default="ref_thriller", help="Папка с референсами")
    parser.add_argument("--meta", type=str, default=str(META_FILE), help="Путь к animation_metadata.json")
    parser.add_argument("--output", type=str, default=str(REPORT_FILE), help="Путь для JSON-отчёта")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Параллельные запросы к API")

    args = parser.parse_args()

    if args.panel and (not args.scene or len(args.scene) != 1):
        parser.error("--panel требует ровно одну сцену в --scene")

    # ── Загрузка ──
    ref_dir = Path(args.ref_dir)
    meta_path = Path(args.meta)

    logger.info("=" * 60)
    logger.info("🎬 GRID QUALITY GATE")
    logger.info("=" * 60)

    metadata = load_metadata(meta_path)
    ref_catalog = load_ref_catalog(ref_dir)

    # Определяем формат из конфига (если есть) или дефолт
    config = metadata.get("config", {})
    grid_format = config.get("format", {}).get("type", "single_grid_animation")
    panels_per_scene = config.get("format", {}).get("panels_per_scene", 9)

    # Если конфиг не встроен в metadata, пробуем custom_prompts/config.json
    if not config:
        for cfg_path in [Path("custom_prompts/config.json"), Path("prompts/config.json")]:
            if cfg_path.exists():
                config = json.loads(cfg_path.read_text(encoding="utf-8"))
                grid_format = config.get("format", {}).get("type", grid_format)
                panels_per_scene = config.get("format", {}).get("panels_per_scene", panels_per_scene)
                break

    logger.info(f"  Format: {grid_format}")
    logger.info(f"  Panels/scene: {panels_per_scene}")
    logger.info(f"  Threshold: {args.threshold}")
    logger.info(f"  References: {len(set(id(v) for v in ref_catalog.values()))} loaded")

    # ── Фильтрация сцен ──
    scenes = metadata.get("scenes", [])
    if args.scene:
        scenes = [s for s in scenes if s["scene_id"] in args.scene]
        if not scenes:
            logger.error(f"❌ Сцены {args.scene} не найдены в метаданных")
            sys.exit(1)

    logger.info(f"  Scenes to analyze: {[s['scene_id'] for s in scenes]}\n")

    # ── Обработка ──
    all_results: List[Dict] = []

    if args.workers > 1 and len(scenes) > 1 and not args.panel:
        # Параллельная обработка по сценам
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    process_scene,
                    scene,
                    ref_catalog,
                    grid_format,
                    panels_per_scene,
                    args.threshold,
                    None,
                ): scene["scene_id"]
                for scene in scenes
            }
            for future in as_completed(futures):
                sid = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сцены {sid}: {e}")
    else:
        # Последовательная обработка
        for scene in scenes:
            results = process_scene(
                scene,
                ref_catalog,
                grid_format,
                panels_per_scene,
                args.threshold,
                args.panel,
            )
            all_results.extend(results)

    # ── Сортировка и сохранение ──
    all_results.sort(key=lambda r: (r["scene_id"], r["panel_id"]))

    # Сохраняем полный отчёт
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "model": ANALYSIS_MODEL,
        "threshold": args.threshold,
        "total_panels": len(all_results),
        "needs_refinement": sum(1 for r in all_results if r["needs_refinement"]),
        "avg_fidelity": round(sum(r["fidelity"] for r in all_results) / max(len(all_results), 1), 2),
        "panels": all_results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"📄 Отчёт сохранён: {output_path}")

    # ── Сводка ──
    print_summary(all_results, args.threshold)

    # Exit code: 1 если есть панели для refinement (для CI/CD)
    if report["needs_refinement"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
