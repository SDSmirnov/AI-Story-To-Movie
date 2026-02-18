"""
Batch Panel Refinement - Массовое уточнение панелей

Usage:
    python batch_refinement.py --scene 1           # Вся сцена 1
    python batch_refinement.py --scene 1 2 3       # Сцены 1, 2, 3
    python batch_refinement.py --all               # Все сцены
    python batch_refinement.py --scene 1 --panels 1 2 3  # Только панели 1,2,3 из сцены 1
"""

import argparse
import subprocess
import json
from pathlib import Path
from typing import List, Set

OUTPUT_DIR = Path("cinematic_render")
PANELS_DIR = OUTPUT_DIR / "panels"

def load_metadata():
    """Загружает метаданные"""
    metadata_path = OUTPUT_DIR / "animation_metadata.json"
    if not metadata_path.exists():
        print(f"❌ Не найден файл метаданных: {metadata_path}")
        exit(1)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_all_scene_ids(metadata) -> List[int]:
    """Получает список всех scene_id"""
    return [scene['scene_id'] for scene in metadata.get('scenes', [])]

def get_panel_ids_for_scene(metadata, scene_id: int) -> List[int]:
    """Получает список panel_id для сцены"""
    for scene in metadata.get('scenes', []):
        if scene['scene_id'] == scene_id:
            return [p['panel_index'] for p in scene.get('panels', [])]
    return []

def get_existing_panels() -> Set[tuple]:
    """
    Сканирует папку panels и возвращает set из (scene_id, panel_id, frame_type)
    """
    if not PANELS_DIR.exists():
        return set()
    
    panels = set()
    for file in PANELS_DIR.glob("*.png"):
        # Формат: 001_01_start.png или 001_01_end.png
        parts = file.stem.split('_')
        if len(parts) == 3:
            try:
                scene_id = int(parts[0])
                panel_id = int(parts[1])
                frame_type = parts[2]
                panels.add((scene_id, panel_id, frame_type))
            except ValueError:
                continue
    
    return panels

def run_refinement(scene_id: int, panel_id: int, frame_type: str, custom_prompts: bool = False):
    """Запускает panel_refinement.py для одной панели"""
    cmd = [
        'python', 'panel_refinement.py',
        str(scene_id),
        str(panel_id),
        '--frame', frame_type
    ]
    
    if custom_prompts:
        cmd.append('--custom-prompts')
    
    print(f"\n{'='*60}")
    print(f"🔧 Обработка: Scene {scene_id}, Panel {panel_id}, Frame {frame_type}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(
        description='Массовое уточнение панелей по референсам'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--scene', type=int, nargs='+', help='ID сцен для обработки')
    group.add_argument('--all', action='store_true', help='Обработать все сцены')
    
    parser.add_argument('--panels', type=int, nargs='+', help='Конкретные панели (требует --scene с одной сценой)')
    parser.add_argument('--frame', choices=['start', 'static', 'end', 'both'], default='both',
                       help='Какие фреймы обрабатывать')
    parser.add_argument('--custom-prompts', action='store_true',
                       help='Использовать custom_prompts/')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Пропускать уже обработанные панели')
    
    args = parser.parse_args()
    
    # Проверка аргументов
    if args.panels and (not args.scene or len(args.scene) != 1):
        parser.error("--panels требует ровно одну сцену в --scene")
    
    print("="*60)
    print("🎬 BATCH PANEL REFINEMENT")
    print("="*60)
    
    # Загрузка метаданных
    metadata = load_metadata()
    
    # Определяем сцены для обработки
    if args.all:
        scene_ids = get_all_scene_ids(metadata)
        print(f"📋 Обработка всех сцен: {scene_ids}")
    else:
        scene_ids = args.scene
        print(f"📋 Обработка сцен: {scene_ids}")
    
    # Получаем существующие refined панели если нужно
    refined_dir = OUTPUT_DIR / "refined"
    existing_refined = set()
    if args.skip_existing and refined_dir.exists():
        for file in refined_dir.glob("*_refined.png"):
            parts = file.stem.replace('_refined', '').split('_')
            if len(parts) == 3:
                try:
                    existing_refined.add((int(parts[0]), int(parts[1]), parts[2]))
                except ValueError:
                    continue
        print(f"⏭️  Пропуск {len(existing_refined)} уже обработанных панелей")
    
    # Подсчет задач
    total_tasks = 0
    successful = 0
    skipped = 0
    failed = 0
    
    # Обработка сцен
    for scene_id in scene_ids:
        # Определяем панели
        if args.panels:
            panel_ids = args.panels
        else:
            panel_ids = get_panel_ids_for_scene(metadata, scene_id)
        
        if not panel_ids:
            print(f"⚠️  Сцена {scene_id}: панели не найдены")
            continue
        
        print(f"\n{'#'*60}")
        print(f"# SCENE {scene_id}: {len(panel_ids)} панелей")
        print(f"{'#'*60}")
        
        # Определяем фреймы
        if args.frame == 'both':
            frame_types = ['start', 'end']
        else:
            frame_types = [args.frame]
        
        # Обработка панелей
        for panel_id in panel_ids:
            for frame_type in frame_types:
                total_tasks += 1
                
                # Проверка существования оригинала
                original = PANELS_DIR / f"{scene_id:03d}_{panel_id:02d}_{frame_type}.png"
                if not original.exists():
                    print(f"⏭️  Пропуск {scene_id}/{panel_id}/{frame_type}: нет оригинала")
                    skipped += 1
                    continue
                
                # Проверка на пропуск уже обработанных
                if args.skip_existing and (scene_id, panel_id, frame_type) in existing_refined:
                    print(f"⏭️  Пропуск {scene_id}/{panel_id}/{frame_type}: уже обработано")
                    skipped += 1
                    continue
                
                # Запуск refinement
                success = run_refinement(scene_id, panel_id, frame_type, args.custom_prompts)
                
                if success:
                    successful += 1
                else:
                    failed += 1
                    print(f"❌ Ошибка при обработке {scene_id}/{panel_id}/{frame_type}")
    
    # Итоговая статистика
    print("\n" + "="*60)
    print("📊 СТАТИСТИКА")
    print("="*60)
    print(f"Всего задач:     {total_tasks}")
    print(f"✅ Успешно:      {successful}")
    print(f"⏭️  Пропущено:    {skipped}")
    print(f"❌ Ошибок:       {failed}")
    print("="*60)
    
    if successful > 0:
        print(f"\n✅ Результаты сохранены в: {refined_dir}")

if __name__ == "__main__":
    main()
