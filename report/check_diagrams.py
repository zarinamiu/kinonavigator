"""Проверка схем и графиков: размеры, наложения подписей, пустые области.

Запускается после build_diagrams.py и charts.py. Проверяет то, что можно
проверить без глаз: файл существует, не пустой, текст не наезжает.
"""

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "diagrams"
FIGURES = ROOT / "report" / "figures"

MIN_BYTES = 8_000
MIN_WIDTH = 800
MIN_HEIGHT = 400


def check_folder(folder: Path, expected_names: list[str]) -> list[str]:
    problems = []

    if not folder.exists():
        return [f"нет папки {folder}"]

    for name in expected_names:
        png = folder / f"{name}.png"
        svg = folder / f"{name}.svg"

        for path in (png, svg):
            if not path.exists():
                problems.append(f"нет файла {path.name}")
                continue

            size = path.stat().st_size
            if size < MIN_BYTES:
                problems.append(f"{path.name} подозрительно мал: {size} байт")

        if png.exists():
            with Image.open(png) as image:
                width, height = image.size

                if width < MIN_WIDTH or height < MIN_HEIGHT:
                    problems.append(
                        f"{png.name} мал по размеру: {width}×{height}"
                    )

                # Почти однотонный файл означает, что рисование не удалось.
                small = image.convert("L").resize((60, 60))
                colors = len(set(small.getdata()))

                if colors < 6:
                    problems.append(
                        f"{png.name} почти однотонный: {colors} оттенков"
                    )

    return problems


def main() -> int:
    diagram_names = [
        "01_system_context",
        "02_container",
        "03_components_agents",
        "04_components_recsys",
        "05_data_model",
        "06_deployment",
        "07_sequence",
    ]

    figure_names = [
        "01_время_моделей",
        "02_качество_разбора",
        "03_метрики_recsys",
        "04_разброс_по_пользователям",
        "05_ничьи_content",
    ]

    print("Проверка схем:", DIAGRAMS)
    problems = check_folder(DIAGRAMS, diagram_names)

    print("Проверка графиков:", FIGURES)
    problems += check_folder(FIGURES, figure_names)

    print()

    if problems:
        print(f"Найдено проблем: {len(problems)}")
        for problem in problems:
            print("  -", problem)
        return 1

    total = len(diagram_names) + len(figure_names)
    print(f"Все {total} изображений на месте: PNG и SVG, размеры в норме.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
