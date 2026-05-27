"""Модуль визуального представления радиоэлектронных схем.

В учебном проекте этот модуль решает две задачи: хранит библиотеку условных
графических обозначений и формирует SVG-файл схемы без сторонних зависимостей.
Данные схемы сохраняются в SQLite через таблицы scheme_nodes и scheme_wires.
"""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping

from .app_config import EXPORT_DIR
from .database import now


SYMBOL_LIBRARY: dict[str, dict[str, str]] = {
    "resistor": {"title": "Резистор", "prefix": "R"},
    "capacitor": {"title": "Конденсатор", "prefix": "C"},
    "diode": {"title": "Диод", "prefix": "D"},
    "transistor": {"title": "Транзистор", "prefix": "VT"},
    "ic": {"title": "Микросхема", "prefix": "U"},
    "connector": {"title": "Разъем", "prefix": "X"},
    "inductor": {"title": "Катушка индуктивности", "prefix": "L"},
    "power": {"title": "Источник питания", "prefix": "V"},
    "ground": {"title": "Общий провод", "prefix": "GND"},
    "generic": {"title": "Блок", "prefix": "E"},
}


CATEGORY_TO_SYMBOL: tuple[tuple[str, str], ...] = (
    ("резист", "resistor"),
    ("конден", "capacitor"),
    ("диод", "diode"),
    ("транз", "transistor"),
    ("микросх", "ic"),
    ("разъем", "connector"),
    ("катуш", "inductor"),
    ("индук", "inductor"),
    ("питан", "power"),
)


def symbol_from_category(category: str | None) -> str:
    """Подбирает условное обозначение по категории компонента."""
    text = (category or "").casefold()
    for needle, symbol in CATEGORY_TO_SYMBOL:
        if needle in text:
            return symbol
    return "generic"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_node(node: Mapping[str, Any]) -> dict[str, Any]:
    """Приводит узел схемы к единому формату перед сохранением/экспортом."""
    symbol_type = str(node.get("symbol_type") or "generic")
    if symbol_type not in SYMBOL_LIBRARY:
        symbol_type = "generic"
    refdes = str(node.get("refdes") or "").strip()
    label = str(node.get("label") or "").strip()
    return {
        "id": node.get("id"),
        "node_key": str(node.get("node_key") or "").strip(),
        "scheme_id": node.get("scheme_id"),
        "component_id": node.get("component_id"),
        "symbol_type": symbol_type,
        "refdes": refdes,
        "label": label,
        "x": safe_float(node.get("x"), 100.0),
        "y": safe_float(node.get("y"), 100.0),
        "rotation": safe_int(node.get("rotation"), 0),
    }


def normalize_wire(wire: Mapping[str, Any]) -> dict[str, Any]:
    """Приводит проводник к единому формату."""
    return {
        "id": wire.get("id"),
        "scheme_id": wire.get("scheme_id"),
        "wire_key": str(wire.get("wire_key") or "").strip(),
        "net_name": str(wire.get("net_name") or "").strip(),
        "x1": safe_float(wire.get("x1"), 0.0),
        "y1": safe_float(wire.get("y1"), 0.0),
        "x2": safe_float(wire.get("x2"), 0.0),
        "y2": safe_float(wire.get("y2"), 0.0),
    }


def _text(x: float, y: float, content: str, anchor: str = "middle", size: int = 12) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}" font-family="Arial, sans-serif">{escape(content)}</text>'


def _line(x1: float, y1: float, x2: float, y2: float, width: int = 2) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="black" stroke-width="{width}" fill="none" />'


def _circle(cx: float, cy: float, r: float) -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" stroke="black" stroke-width="2" fill="white" />'


def _rect(x: float, y: float, w: float, h: float) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" stroke="black" stroke-width="2" fill="white" />'


def render_symbol_svg(node: Mapping[str, Any]) -> str:
    """Рисует один элемент схемы в SVG."""
    item = normalize_node(node)
    x = item["x"]
    y = item["y"]
    symbol_type = item["symbol_type"]
    refdes = item["refdes"] or SYMBOL_LIBRARY[symbol_type]["prefix"]
    label = item["label"] or SYMBOL_LIBRARY[symbol_type]["title"]
    parts: list[str] = [f'<g id="node-{escape(str(item.get("node_key") or item.get("id") or refdes))}">']

    if symbol_type == "resistor":
        parts.extend([
            _line(x - 60, y, x - 34, y),
            f'<polyline points="{x-34:.1f},{y:.1f} {x-24:.1f},{y-14:.1f} {x-12:.1f},{y+14:.1f} {x:.1f},{y-14:.1f} {x+12:.1f},{y+14:.1f} {x+24:.1f},{y-14:.1f} {x+34:.1f},{y:.1f}" stroke="black" stroke-width="2" fill="none" />',
            _line(x + 34, y, x + 60, y),
        ])
    elif symbol_type == "capacitor":
        parts.extend([
            _line(x - 60, y, x - 10, y),
            _line(x - 10, y - 24, x - 10, y + 24),
            _line(x + 10, y - 24, x + 10, y + 24),
            _line(x + 10, y, x + 60, y),
        ])
    elif symbol_type == "diode":
        parts.extend([
            _line(x - 60, y, x - 26, y),
            f'<polygon points="{x-26:.1f},{y-22:.1f} {x-26:.1f},{y+22:.1f} {x+22:.1f},{y:.1f}" stroke="black" stroke-width="2" fill="white" />',
            _line(x + 24, y - 24, x + 24, y + 24),
            _line(x + 24, y, x + 60, y),
        ])
    elif symbol_type == "inductor":
        parts.append(_line(x - 60, y, x - 35, y))
        for offset in (-30, -10, 10, 30):
            parts.append(f'<path d="M {x+offset-10:.1f} {y:.1f} A 10 10 0 0 1 {x+offset+10:.1f} {y:.1f}" stroke="black" stroke-width="2" fill="none" />')
        parts.append(_line(x + 40, y, x + 60, y))
    elif symbol_type == "power":
        parts.extend([
            _line(x - 60, y, x - 30, y),
            _circle(x, y, 30),
            _line(x + 30, y, x + 60, y),
            _text(x, y - 4, "+", size=16),
            _text(x, y + 18, "−", size=16),
        ])
    elif symbol_type == "ground":
        parts.extend([
            _line(x, y - 42, x, y - 15),
            _line(x - 28, y - 15, x + 28, y - 15),
            _line(x - 18, y - 5, x + 18, y - 5),
            _line(x - 8, y + 5, x + 8, y + 5),
        ])
    elif symbol_type == "ic":
        parts.append(_rect(x - 45, y - 35, 90, 70))
        for py in (y - 22, y, y + 22):
            parts.append(_line(x - 65, py, x - 45, py))
            parts.append(_line(x + 45, py, x + 65, py))
    elif symbol_type == "connector":
        parts.append(_rect(x - 40, y - 28, 80, 56))
        for py in (y - 16, y, y + 16):
            parts.append(_circle(x - 15, py, 4))
            parts.append(_circle(x + 15, py, 4))
    elif symbol_type == "transistor":
        parts.extend([
            _circle(x, y, 32),
            _line(x - 60, y, x - 22, y),
            _line(x - 10, y - 12, x + 35, y - 42),
            _line(x - 10, y + 12, x + 35, y + 42),
            f'<polygon points="{x+24:.1f},{y+32:.1f} {x+33:.1f},{y+41:.1f} {x+18:.1f},{y+43:.1f}" fill="black" />',
        ])
    else:
        parts.append(_rect(x - 45, y - 28, 90, 56))
        parts.append(_line(x - 65, y, x - 45, y))
        parts.append(_line(x + 45, y, x + 65, y))

    parts.append(_text(x, y - 45, refdes, size=12))
    if label:
        parts.append(_text(x, y + 56, label[:42], size=11))
    parts.append("</g>")
    return "\n".join(parts)


def build_schematic_svg(
    scheme: Mapping[str, Any],
    nodes: list[Mapping[str, Any]],
    wires: list[Mapping[str, Any]],
    width: int = 1200,
    height: int = 800,
) -> str:
    """Формирует SVG-документ схемы."""
    title = f"{scheme.get('code', '')} — {scheme.get('title', 'Схема')}".strip(" —")
    created = now()
    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="white" />',
        _text(width / 2, 34, title, size=18),
        _text(width / 2, height - 18, f"Экспортировано: {created}", size=10),
    ]

    # Сетка облегчает демонстрацию, что схема строится не как картинка, а как набор объектов.
    for x in range(40, width, 40):
        svg.append(f'<line x1="{x}" y1="60" x2="{x}" y2="{height-50}" stroke="#eeeeee" stroke-width="1" />')
    for y in range(80, height - 50, 40):
        svg.append(f'<line x1="30" y1="{y}" x2="{width-30}" y2="{y}" stroke="#eeeeee" stroke-width="1" />')

    for wire in wires:
        item = normalize_wire(wire)
        svg.append(_line(item["x1"], item["y1"], item["x2"], item["y2"], 2))
        if item["net_name"]:
            svg.append(_text((item["x1"] + item["x2"]) / 2, (item["y1"] + item["y2"]) / 2 - 6, item["net_name"], size=10))
    for node in nodes:
        svg.append(render_symbol_svg(node))
    svg.append("</svg>")
    return "\n".join(svg)


def export_schematic_svg(
    scheme: Mapping[str, Any],
    nodes: list[Mapping[str, Any]],
    wires: list[Mapping[str, Any]],
    export_dir: str | Path = EXPORT_DIR,
) -> Path:
    """Сохраняет схему в SVG-файл и возвращает путь."""
    output_dir = Path(export_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    code = str(scheme.get("code") or "scheme").replace("/", "_").replace("\\", "_")
    path = output_dir / f"schematic_{code}_{now().replace(':', '-').replace(' ', '_')}.svg"
    path.write_text(build_schematic_svg(scheme, nodes, wires), encoding="utf-8")
    return path
