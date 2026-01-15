"""
Compare Refinement - Создание сравнительных изображений original vs refined

Генерирует side-by-side сравнение для визуальной оценки качества refinement.

Usage:
    python compare_refinement.py --scene 1                  # Вся сцена 1
    python compare_refinement.py --scene 1 --panel 3       # Только панель 3
    python compare_refinement.py --all                      # Весь проект
"""

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple

OUTPUT_DIR = Path("cinematic_render")
PANELS_DIR = OUTPUT_DIR / "panels"
REFINED_DIR = OUTPUT_DIR / "refined"
COMPARISON_DIR = OUTPUT_DIR / "comparisons"

COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

def find_refined_panels(scene_id: int = None, panel_id: int = None) -> List[Tuple[Path, Path]]:
    """
    Находит пары original-refined
    Returns: [(original_path, refined_path), ...]
    """
    pairs = []
    
    # Сканируем refined панели
    for refined_file in REFINED_DIR.glob("*_refined.png"):
        # Парсим имя: 001_03_start_refined.png
        parts = refined_file.stem.replace('_refined', '').split('_')
        
        if len(parts) != 3:
            continue
        
        try:
            s_id = int(parts[0])
            p_id = int(parts[1])
            frame = parts[2]
        except ValueError:
            continue
        
        # Фильтрация
        if scene_id and s_id != scene_id:
            continue
        if panel_id and p_id != panel_id:
            continue
        
        # Ищем оригинал
        original_name = f"{s_id:03d}_{p_id:02d}_{frame}.png"
        original_path = PANELS_DIR / original_name
        
        if original_path.exists():
            pairs.append((original_path, refined_file))
    
    return sorted(pairs)

def create_comparison(original_path: Path, refined_path: Path, output_path: Path):
    """Создаёт side-by-side сравнение"""
    
    # Загрузка изображений
    img_orig = Image.open(original_path)
    img_refined = Image.open(refined_path)
    
    # Размеры
    w, h = img_orig.size
    
    # Создание холста (side-by-side + заголовки)
    header_height = 60
    canvas_width = w * 2 + 40  # 2 изображения + отступы
    canvas_height = h + header_height + 20
    
    canvas = Image.new('RGB', (canvas_width, canvas_height), color=(30, 30, 30))
    draw = ImageDraw.Draw(canvas)
    
    # Шрифт
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Заголовок
    title = original_path.stem.replace('_', ' ').upper()
    title_bbox = draw.textbbox((0, 0), title, font=font_large)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(((canvas_width - title_width) // 2, 10), title, fill=(255, 255, 255), font=font_large)
    
    # Размещение изображений
    y_offset = header_height
    
    # Оригинал слева
    canvas.paste(img_orig, (10, y_offset))
    label_orig_bbox = draw.textbbox((0, 0), "ORIGINAL", font=font_small)
    label_orig_width = label_orig_bbox[2] - label_orig_bbox[0]
    draw.text((10 + (w - label_orig_width) // 2, y_offset + h + 5), 
              "ORIGINAL", fill=(255, 200, 200), font=font_small)
    
    # Refined справа
    canvas.paste(img_refined, (w + 30, y_offset))
    label_ref_bbox = draw.textbbox((0, 0), "REFINED", font=font_small)
    label_ref_width = label_ref_bbox[2] - label_ref_bbox[0]
    draw.text((w + 30 + (w - label_ref_width) // 2, y_offset + h + 5), 
              "REFINED", fill=(200, 255, 200), font=font_small)
    
    # Разделительная линия
    draw.line([(w + 20, y_offset), (w + 20, y_offset + h)], fill=(100, 100, 100), width=2)
    
    # Сохранение
    canvas.save(output_path, quality=95)
    print(f"✅ {output_path.name}")

def create_grid_comparison(pairs: List[Tuple[Path, Path]], output_path: Path, max_per_row: int = 3):
    """Создаёт grid сравнение для множества панелей"""
    
    if not pairs:
        return
    
    # Параметры
    padding = 20
    header_h = 40
    
    # Загрузка первого для размеров
    sample = Image.open(pairs[0][0])
    panel_w, panel_h = sample.size
    comparison_w = panel_w * 2 + padding
    
    # Вычисляем размеры grid
    num_comparisons = len(pairs)
    cols = min(max_per_row, num_comparisons)
    rows = (num_comparisons + cols - 1) // cols
    
    # Размеры холста
    canvas_w = cols * comparison_w + (cols + 1) * padding
    canvas_h = rows * (panel_h + header_h + padding) + padding
    
    canvas = Image.new('RGB', (canvas_w, canvas_h), color=(40, 40, 40))
    draw = ImageDraw.Draw(canvas)
    
    # Шрифт
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font = ImageFont.load_default()
    
    # Размещение сравнений
    for idx, (orig_path, ref_path) in enumerate(pairs):
        row = idx // cols
        col = idx % cols
        
        x = padding + col * (comparison_w + padding)
        y = padding + row * (panel_h + header_h + padding)
        
        # Заголовок
        name = orig_path.stem
        draw.text((x, y), name, fill=(200, 200, 200), font=font)
        
        # Изображения
        y_img = y + header_h
        
        orig = Image.open(orig_path).resize((panel_w, panel_h))
        canvas.paste(orig, (x, y_img))
        
        ref = Image.open(ref_path).resize((panel_w, panel_h))
        canvas.paste(ref, (x + panel_w + padding // 2, y_img))
        
        # Разделитель
        draw.line([(x + panel_w + padding // 4, y_img), 
                   (x + panel_w + padding // 4, y_img + panel_h)], 
                  fill=(80, 80, 80), width=2)
    
    # Сохранение
    canvas.save(output_path, quality=90)
    print(f"✅ Grid сравнение: {output_path.name}")

def create_diff_heatmap(original_path: Path, refined_path: Path, output_path: Path):
    """Создаёт тепловую карту различий"""
    import numpy as np
    
    # Загрузка
    img_orig = Image.open(original_path).convert('RGB')
    img_refined = Image.open(refined_path).convert('RGB')
    
    # Конвертация в numpy
    arr_orig = np.array(img_orig, dtype=np.float32)
    arr_refined = np.array(img_refined, dtype=np.float32)
    
    # Вычисление разности
    diff = np.abs(arr_orig - arr_refined).mean(axis=2)  # Усреднение по RGB
    
    # Нормализация для визуализации
    diff_norm = (diff / diff.max() * 255).astype(np.uint8)
    
    # Создание heatmap (grayscale -> color)
    heatmap = Image.fromarray(diff_norm, mode='L')
    heatmap = heatmap.convert('RGB')
    
    # Применение color map (красный = большая разница)
    pixels = np.array(heatmap)
    colored = np.zeros_like(arr_orig, dtype=np.uint8)
    
    # Gradient: черный -> синий -> зеленый -> желтый -> красный
    intensity = pixels[:, :, 0]
    colored[:, :, 0] = intensity  # Red channel
    colored[:, :, 1] = 255 - intensity  # Green channel (inverse)
    colored[:, :, 2] = np.clip(255 - intensity * 2, 0, 255)  # Blue channel
    
    heatmap_colored = Image.fromarray(colored)
    
    # Создание финального сравнения
    w, h = img_orig.size
    canvas = Image.new('RGB', (w * 3 + 80, h + 100), color=(30, 30, 30))
    draw = ImageDraw.Draw(canvas)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # Заголовки
    draw.text((w // 2 - 50, 10), "ORIGINAL", fill=(255, 255, 255), font=font)
    draw.text((w + 40 + w // 2 - 40, 10), "REFINED", fill=(255, 255, 255), font=font)
    draw.text((w * 2 + 80 + w // 2 - 70, 10), "DIFF HEATMAP", fill=(255, 255, 255), font=font)
    
    # Изображения
    canvas.paste(img_orig, (10, 50))
    canvas.paste(img_refined, (w + 40, 50))
    canvas.paste(heatmap_colored, (w * 2 + 70, 50))
    
    # Статистика
    avg_diff = diff.mean()
    max_diff = diff.max()
    stats = f"Avg diff: {avg_diff:.1f} | Max diff: {max_diff:.1f}"
    draw.text((10, h + 60), stats, fill=(200, 200, 200), font=font)
    
    canvas.save(output_path, quality=90)
    print(f"✅ Diff heatmap: {output_path.name}")

def main():
    parser = argparse.ArgumentParser(
        description='Создание сравнительных изображений original vs refined'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--scene', type=int, help='Сцена для сравнения')
    group.add_argument('--all', action='store_true', help='Все сцены')
    
    parser.add_argument('--panel', type=int, help='Конкретная панель (требует --scene)')
    parser.add_argument('--mode', choices=['individual', 'grid', 'diff'], 
                       default='individual',
                       help='Режим сравнения: individual (по одному), grid (сетка), diff (heatmap)')
    parser.add_argument('--max-per-row', type=int, default=3,
                       help='Максимум сравнений в ряд для grid режима')
    
    args = parser.parse_args()
    
    print("="*60)
    print("📊 REFINEMENT COMPARISON GENERATOR")
    print("="*60)
    
    # Проверка директорий
    if not REFINED_DIR.exists() or not list(REFINED_DIR.glob("*_refined.png")):
        print("❌ Не найдено refined панелей")
        print(f"   Сначала запустите: python batch_refinement.py --scene {args.scene or 'ALL'}")
        exit(1)
    
    # Поиск пар
    if args.all:
        pairs = find_refined_panels()
        print(f"📁 Найдено {len(pairs)} refined панелей во всех сценах")
    else:
        pairs = find_refined_panels(scene_id=args.scene, panel_id=args.panel)
        if args.panel:
            print(f"📁 Найдено {len(pairs)} refined версий панели {args.panel} сцены {args.scene}")
        else:
            print(f"📁 Найдено {len(pairs)} refined панелей в сцене {args.scene}")
    
    if not pairs:
        print("❌ Не найдено пар для сравнения")
        exit(1)
    
    print(f"🎨 Режим: {args.mode}")
    print()
    
    # Генерация сравнений
    if args.mode == 'individual':
        # Создание отдельных сравнений
        for orig_path, ref_path in pairs:
            output_name = ref_path.stem.replace('_refined', '_comparison') + '.png'
            output_path = COMPARISON_DIR / output_name
            create_comparison(orig_path, ref_path, output_path)
    
    elif args.mode == 'grid':
        # Создание grid сравнения
        if args.all:
            output_name = "all_scenes_comparison_grid.png"
        elif args.panel:
            output_name = f"scene_{args.scene:03d}_panel_{args.panel:02d}_grid.png"
        else:
            output_name = f"scene_{args.scene:03d}_comparison_grid.png"
        
        output_path = COMPARISON_DIR / output_name
        create_grid_comparison(pairs, output_path, max_per_row=args.max_per_row)
    
    elif args.mode == 'diff':
        # Создание diff heatmaps
        for orig_path, ref_path in pairs:
            output_name = ref_path.stem.replace('_refined', '_diff') + '.png'
            output_path = COMPARISON_DIR / output_name
            create_diff_heatmap(orig_path, ref_path, output_path)
    
    print()
    print("="*60)
    print(f"✅ Сравнения сохранены в: {COMPARISON_DIR}")
    print("="*60)

if __name__ == "__main__":
    main()
