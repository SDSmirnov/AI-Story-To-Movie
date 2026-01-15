"""
Reference Validator - Проверка наличия референсов для refinement

Анализирует метаданные и проверяет наличие всех необходимых референсов
для успешного refinement процесса.

Usage:
    python validate_references.py                    # Проверить все
    python validate_references.py --scene 1          # Только сцена 1
    python validate_references.py --fix-missing      # Создать заглушки для отсутствующих
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("cinematic_render")
REF_DIR = Path("ref_thriller")
PANELS_DIR = OUTPUT_DIR / "panels"

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def load_metadata():
    """Загружает метаданные"""
    metadata_path = OUTPUT_DIR / "animation_metadata.json"
    if not metadata_path.exists():
        print(f"{Colors.RED}❌ Не найден файл метаданных: {metadata_path}{Colors.RESET}")
        exit(1)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def collect_all_references(metadata, scene_ids=None) -> Dict[str, List[Tuple[int, int]]]:
    """
    Собирает все референсы из метаданных
    Returns: {ref_name: [(scene_id, panel_id), ...]}
    """
    references = defaultdict(list)
    
    for scene in metadata.get('scenes', []):
        scene_id = scene['scene_id']
        
        # Фильтр по сценам
        if scene_ids and scene_id not in scene_ids:
            continue
        
        for panel in scene.get('panels', []):
            panel_id = panel['panel_index']
            refs = panel.get('references', [])
            
            for ref in refs:
                references[ref].append((scene_id, panel_id))
    
    return dict(references)

def check_reference_files(ref_name: str) -> Dict[str, bool]:
    """
    Проверяет наличие файлов референса
    Returns: {'png': bool, 'json': bool, 'valid_json': bool}
    """
    result = {
        'png': False,
        'json': False,
        'valid_json': False,
        'png_path': None,
        'json_path': None
    }
    
    # Варианты имени файла
    possible_names = [
        ref_name,
        ref_name.lower().replace(' ', '_'),
        ref_name.title().replace(' ', '_'),
        ref_name.replace(' ', '_'),
    ]
    
    for name in possible_names:
        png_path = REF_DIR / f"{name}.png"
        json_path = REF_DIR / f"{name}.json"
        
        if png_path.exists():
            result['png'] = True
            result['png_path'] = png_path
            
            # Проверка валидности JSON
            if json_path.exists():
                result['json'] = True
                result['json_path'] = json_path
                
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Проверка обязательных полей
                        if 'visual_desc' in data:
                            result['valid_json'] = True
                except:
                    result['valid_json'] = False
            
            break  # Нашли файлы, прекращаем поиск
    
    return result

def print_reference_report(references: Dict[str, List], verbose=False):
    """Выводит отчёт о состоянии референсов"""
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}REFERENCE VALIDATION REPORT{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")
    
    total_refs = len(references)
    refs_with_png = 0
    refs_with_json = 0
    refs_complete = 0
    missing_refs = []
    incomplete_refs = []
    
    for ref_name, usages in sorted(references.items()):
        status = check_reference_files(ref_name)
        
        # Статистика
        if status['png']:
            refs_with_png += 1
        if status['json']:
            refs_with_json += 1
        if status['png'] and status['valid_json']:
            refs_complete += 1
        
        # Классификация проблем
        if not status['png']:
            missing_refs.append((ref_name, usages))
        elif not status['valid_json']:
            incomplete_refs.append((ref_name, usages, status))
        
        # Вывод деталей
        if verbose or not (status['png'] and status['valid_json']):
            print(f"📎 {Colors.BOLD}{ref_name}{Colors.RESET}")
            print(f"   Используется в {len(usages)} панелях: {usages[:3]}{'...' if len(usages) > 3 else ''}")
            
            # PNG
            if status['png']:
                print(f"   ✅ PNG: {Colors.GREEN}найден{Colors.RESET} ({status['png_path'].name})")
            else:
                print(f"   ❌ PNG: {Colors.RED}НЕ НАЙДЕН{Colors.RESET}")
            
            # JSON
            if status['json']:
                if status['valid_json']:
                    print(f"   ✅ JSON: {Colors.GREEN}найден и валиден{Colors.RESET}")
                else:
                    print(f"   ⚠️  JSON: {Colors.YELLOW}найден, но невалиден{Colors.RESET}")
            else:
                print(f"   ❌ JSON: {Colors.RED}НЕ НАЙДЕН{Colors.RESET}")
            
            print()
    
    # Сводная статистика
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}SUMMARY{Colors.RESET}\n")
    print(f"Всего уникальных референсов: {total_refs}")
    print(f"{'✅ Полностью готовы:':<30} {Colors.GREEN}{refs_complete}{Colors.RESET} ({refs_complete/total_refs*100:.1f}%)")
    print(f"{'📷 Есть PNG:':<30} {refs_with_png} ({refs_with_png/total_refs*100:.1f}%)")
    print(f"{'📄 Есть JSON:':<30} {refs_with_json} ({refs_with_json/total_refs*100:.1f}%)")
    print(f"{'❌ Полностью отсутствуют:':<30} {Colors.RED}{len(missing_refs)}{Colors.RESET}")
    print(f"{'⚠️  Неполные (нет JSON):':<30} {Colors.YELLOW}{len(incomplete_refs)}{Colors.RESET}")
    
    # Критичные проблемы
    if missing_refs:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  КРИТИЧНО: Отсутствующие референсы{Colors.RESET}")
        print(f"{Colors.RED}Эти референсы блокируют refinement:{Colors.RESET}\n")
        for ref_name, usages in missing_refs[:10]:
            print(f"  • {ref_name} (используется в {len(usages)} панелях)")
        if len(missing_refs) > 10:
            print(f"  ... и ещё {len(missing_refs) - 10}")
    
    if incomplete_refs:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Неполные референсы{Colors.RESET}")
        print(f"{Colors.YELLOW}У этих референсов нет описаний:{Colors.RESET}\n")
        for ref_name, usages, status in incomplete_refs[:10]:
            print(f"  • {ref_name} (есть PNG, нет валидного JSON)")
        if len(incomplete_refs) > 10:
            print(f"  ... и ещё {len(incomplete_refs) - 10}")
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}\n")
    
    return {
        'total': total_refs,
        'complete': refs_complete,
        'missing': missing_refs,
        'incomplete': incomplete_refs
    }

def create_placeholder_reference(ref_name: str, description: str = None):
    """Создаёт заглушку для отсутствующего референса"""
    # Создаём PNG заглушку
    img = Image.new('RGB', (1024, 1024), color=(200, 200, 200))
    draw = ImageDraw.Draw(img)
    
    # Текст
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    text = f"PLACEHOLDER\n{ref_name}\n\nCreate proper reference!"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (1024 - text_width) // 2
    y = (1024 - text_height) // 2
    
    draw.text((x, y), text, fill=(100, 100, 100), font=font, align='center')
    
    # Сохраняем PNG
    filename = ref_name.lower().replace(' ', '_')
    png_path = REF_DIR / f"{filename}.png"
    img.save(png_path)
    
    # Создаём JSON
    json_data = {
        "name": ref_name,
        "visual_desc": description or f"PLACEHOLDER for {ref_name}. Replace with actual description.",
        "type": "unknown",
        "style_reference": filename,
        "placeholder": True
    }
    
    json_path = REF_DIR / f"{filename}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Создана заглушка: {png_path.name} + {json_path.name}")

def check_panels_coverage(metadata, scene_ids=None):
    """Проверяет какие панели готовы к refinement"""
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}PANELS READINESS CHECK{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")
    
    total_panels = 0
    ready_panels = 0
    blocked_panels = []
    
    for scene in metadata.get('scenes', []):
        scene_id = scene['scene_id']
        
        if scene_ids and scene_id not in scene_ids:
            continue
        
        for panel in scene.get('panels', []):
            panel_id = panel['panel_index']
            refs = panel.get('references', [])
            
            total_panels += 1
            
            if not refs:
                # Нет референсов - пропустится при refinement
                continue
            
            # Проверяем все референсы
            all_ready = True
            missing = []
            
            for ref in refs:
                status = check_reference_files(ref)
                if not status['png']:
                    all_ready = False
                    missing.append(ref)
            
            if all_ready:
                ready_panels += 1
            else:
                blocked_panels.append({
                    'scene': scene_id,
                    'panel': panel_id,
                    'missing': missing
                })
    
    print(f"Всего панелей: {total_panels}")
    print(f"{'✅ Готовы к refinement:':<30} {Colors.GREEN}{ready_panels}{Colors.RESET} ({ready_panels/total_panels*100:.1f}%)")
    print(f"{'❌ Заблокированы:':<30} {Colors.RED}{len(blocked_panels)}{Colors.RESET}")
    
    if blocked_panels[:5]:
        print(f"\n{Colors.RED}Примеры заблокированных панелей:{Colors.RESET}\n")
        for bp in blocked_panels[:5]:
            print(f"  Scene {bp['scene']}, Panel {bp['panel']}: отсутствуют {bp['missing']}")
        if len(blocked_panels) > 5:
            print(f"  ... и ещё {len(blocked_panels) - 5}")
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description='Проверка наличия референсов для refinement'
    )
    
    parser.add_argument('--scene', type=int, nargs='+', help='Проверить только указанные сцены')
    parser.add_argument('--verbose', action='store_true', help='Показать детали по всем референсам')
    parser.add_argument('--fix-missing', action='store_true', 
                       help='Создать заглушки для отсутствующих референсов')
    parser.add_argument('--check-panels', action='store_true',
                       help='Проверить готовность панелей к refinement')
    
    args = parser.parse_args()
    
    # Проверка директорий
    if not OUTPUT_DIR.exists():
        print(f"{Colors.RED}❌ Не найдена папка: {OUTPUT_DIR}{Colors.RESET}")
        exit(1)
    
    REF_DIR.mkdir(exist_ok=True)
    
    # Загрузка данных
    metadata = load_metadata()
    
    # Сбор референсов
    references = collect_all_references(metadata, scene_ids=args.scene)
    
    if not references:
        print(f"{Colors.YELLOW}⚠️  Не найдено ни одного референса в метаданных{Colors.RESET}")
        return
    
    # Отчёт
    stats = print_reference_report(references, verbose=args.verbose)
    
    # Проверка готовности панелей
    if args.check_panels:
        check_panels_coverage(metadata, scene_ids=args.scene)
    
    # Создание заглушек
    if args.fix_missing and stats['missing']:
        print(f"\n{Colors.YELLOW}🔧 Создание заглушек для отсутствующих референсов...{Colors.RESET}\n")
        
        confirm = input(f"Создать {len(stats['missing'])} заглушек? (y/n): ")
        if confirm.lower() == 'y':
            for ref_name, usages in stats['missing']:
                create_placeholder_reference(ref_name)
            print(f"\n{Colors.GREEN}✅ Заглушки созданы. Замените их реальными референсами!{Colors.RESET}")
        else:
            print("Отменено.")
    
    # Рекомендации
    if stats['missing'] or stats['incomplete']:
        print(f"\n{Colors.BOLD}💡 РЕКОМЕНДАЦИИ:{Colors.RESET}\n")
        
        if stats['missing']:
            print(f"1. Создайте отсутствующие референсы в {REF_DIR}/")
            print(f"   Или используйте: python validate_references.py --fix-missing")
        
        if stats['incomplete']:
            print(f"2. Добавьте JSON описания для референсов:")
            for ref_name, _, status in stats['incomplete'][:3]:
                filename = status['png_path'].stem
                print(f"   • {filename}.json")

if __name__ == "__main__":
    main()
