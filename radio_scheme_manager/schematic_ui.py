"""Графический редактор схем для Tkinter-клиента."""
from __future__ import annotations

import uuid
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Mapping

from .api_client import ApiClientError
from .schematics import SYMBOL_LIBRARY, symbol_from_category

GRID_STEP = 20
CANVAS_WIDTH = 1100
CANVAS_HEIGHT = 620


class SchemeDesignerFrame(ttk.Frame):
    """Окно, где схема собирается из графических элементов и проводников."""

    def __init__(self, app: Any) -> None:
        super().__init__(app.content, padding=12)
        self.app = app
        self.scheme_id_var = tk.StringVar(value="1")
        self.status_var = tk.StringVar(value="")
        self.symbol_var = tk.StringVar(value="resistor")
        self.bom_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="Выбор/перемещение")
        self.scheme: dict[str, Any] = {}
        self.nodes: list[dict[str, Any]] = []
        self.wires: list[dict[str, Any]] = []
        self.bom: list[dict[str, Any]] = []
        self.selected_node_key: str | None = None
        self.selected_wire_key: str | None = None
        self.drag_start: tuple[float, float] | None = None
        self.drag_node_origin: tuple[float, float] | None = None
        self.wire_start: tuple[float, float] | None = None
        self.is_editable = bool(self.app.can("scheme_nodes", "update") and self.app.can("scheme_wires", "update"))
        self.can_export = bool(self.app.can("scheme_nodes", "export") and self.app.can("scheme_wires", "export"))
        self._build()
        self.load_schematic()

    def _build(self) -> None:
        ttk.Label(self, text="Визуальный редактор радиоэлектронной схемы", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text="Элементы схемы сохраняются в базе данных как узлы и проводники. Инженер редактирует схему, руководитель и контролер могут просматривать и экспортировать.",
            wraplength=980,
        ).pack(anchor="w", pady=(2, 8))

        top = ttk.Frame(self)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="ID схемы:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.scheme_id_var, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Загрузить", command=self.load_schematic).pack(side=tk.LEFT, padx=4)
        self.save_button = ttk.Button(top, text="Сохранить схему", command=self.save_schematic)
        self.save_button.pack(side=tk.LEFT, padx=4)
        self.export_button = ttk.Button(top, text="Экспорт SVG", command=self.export_svg)
        self.export_button.pack(side=tk.LEFT, padx=4)
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT, padx=(14, 0))
        if not self.is_editable:
            self.save_button.configure(state="disabled")
        if not self.can_export:
            self.export_button.configure(state="disabled")

        tools = ttk.Frame(self)
        tools.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(tools, text="Тип:").pack(side=tk.LEFT)
        symbol_combo = ttk.Combobox(tools, textvariable=self.symbol_var, values=list(SYMBOL_LIBRARY.keys()), width=15, state="readonly")
        symbol_combo.pack(side=tk.LEFT, padx=4)
        self.add_symbol_button = ttk.Button(tools, text="Добавить символ", command=self.add_symbol)
        self.add_symbol_button.pack(side=tk.LEFT, padx=4)

        ttk.Label(tools, text="Из BOM:").pack(side=tk.LEFT, padx=(14, 4))
        self.bom_combo = ttk.Combobox(tools, textvariable=self.bom_var, values=[], width=46, state="readonly")
        self.bom_combo.pack(side=tk.LEFT, padx=4)
        self.add_bom_button = ttk.Button(tools, text="Добавить из BOM", command=self.add_from_bom)
        self.add_bom_button.pack(side=tk.LEFT, padx=4)

        self.wire_button = ttk.Button(tools, text="Провод", command=self.enable_wire_mode)
        self.wire_button.pack(side=tk.LEFT, padx=(14, 4))
        self.select_button = ttk.Button(tools, text="Выбор", command=self.enable_select_mode)
        self.select_button.pack(side=tk.LEFT, padx=4)
        self.delete_button = ttk.Button(tools, text="Удалить выбранное", command=self.delete_selected)
        self.delete_button.pack(side=tk.LEFT, padx=4)
        if not self.is_editable:
            for button in (self.add_symbol_button, self.add_bom_button, self.wire_button, self.delete_button):
                button.configure(state="disabled")

        ttk.Label(self, textvariable=self.mode_var).pack(anchor="w", pady=(0, 4))
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="white", scrollregion=(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT))
        x_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        y_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-1>", self.rename_selected)

    def load_schematic(self) -> None:
        try:
            scheme_id = int(self.scheme_id_var.get() or 1)
            data = self.app.client.get_schematic(scheme_id)
            self.scheme = data.get("scheme") or {}
            self.nodes = [self._client_node(row) for row in data.get("nodes", [])]
            self.wires = [self._client_wire(row) for row in data.get("wires", [])]
            self.bom = list(data.get("bom", []))
            self._fill_bom_combo()
            self.selected_node_key = None
            self.selected_wire_key = None
            self.wire_start = None
            self.draw_all()
            title = self.scheme.get("title", "")
            self.status_var.set(f"Загружена схема: {self.scheme.get('code', scheme_id)} {title}")
        except (ValueError, ApiClientError) as exc:
            messagebox.showerror("Ошибка загрузки схемы", str(exc), parent=self)

    def save_schematic(self) -> None:
        if not self.is_editable:
            return
        try:
            scheme_id = int(self.scheme_id_var.get() or 1)
            payload = {"nodes": self.nodes, "wires": self.wires}
            result = self.app.client.save_schematic(scheme_id, payload)
            self.status_var.set(result.get("message", "Схема сохранена"))
            self.load_schematic()
        except (ValueError, ApiClientError) as exc:
            messagebox.showerror("Ошибка сохранения схемы", str(exc), parent=self)

    def export_svg(self) -> None:
        if not self.can_export:
            return
        try:
            scheme_id = int(self.scheme_id_var.get() or 1)
            result = self.app.client.export_schematic(scheme_id)
            messagebox.showinfo("Экспорт схемы", result.get("path", ""), parent=self)
        except (ValueError, ApiClientError) as exc:
            messagebox.showerror("Ошибка экспорта", str(exc), parent=self)

    def _fill_bom_combo(self) -> None:
        values: list[str] = []
        for index, item in enumerate(self.bom, start=1):
            refdes = item.get("refdes") or f"E{index}"
            name = item.get("component_name") or item.get("part_number") or "Компонент"
            nominal = item.get("nominal") or ""
            values.append(f"{refdes} — {name} {nominal}".strip())
        self.bom_combo.configure(values=values)
        self.bom_var.set(values[0] if values else "")

    def add_symbol(self) -> None:
        if not self.is_editable:
            return
        symbol_type = self.symbol_var.get() or "generic"
        prefix = SYMBOL_LIBRARY.get(symbol_type, SYMBOL_LIBRARY["generic"])["prefix"]
        count = sum(1 for node in self.nodes if node.get("symbol_type") == symbol_type) + 1
        self.nodes.append(
            {
                "node_key": uuid.uuid4().hex,
                "scheme_id": int(self.scheme_id_var.get() or 1),
                "component_id": None,
                "symbol_type": symbol_type,
                "refdes": f"{prefix}{count}",
                "label": SYMBOL_LIBRARY.get(symbol_type, SYMBOL_LIBRARY["generic"])["title"],
                "x": 140 + (count % 6) * 120,
                "y": 140 + (count // 6) * 90,
                "rotation": 0,
            }
        )
        self.draw_all()

    def add_from_bom(self) -> None:
        if not self.is_editable or not self.bom:
            return
        selected = self.bom_var.get()
        try:
            index = [self.bom_combo["values"][i] for i in range(len(self.bom_combo["values"]))].index(selected)
        except ValueError:
            index = 0
        item = self.bom[index]
        symbol_type = symbol_from_category(str(item.get("category") or ""))
        label = " ".join(str(part) for part in (item.get("component_name"), item.get("nominal")) if part)
        self.nodes.append(
            {
                "node_key": uuid.uuid4().hex,
                "scheme_id": int(self.scheme_id_var.get() or 1),
                "component_id": item.get("component_id"),
                "symbol_type": symbol_type,
                "refdes": item.get("refdes") or SYMBOL_LIBRARY.get(symbol_type, SYMBOL_LIBRARY["generic"])["prefix"],
                "label": label[:80],
                "x": 140 + (len(self.nodes) % 6) * 140,
                "y": 160 + (len(self.nodes) // 6) * 100,
                "rotation": 0,
            }
        )
        self.draw_all()

    def enable_wire_mode(self) -> None:
        if not self.is_editable:
            return
        self.wire_start = None
        self.mode_var.set("Режим: провод. Щелкните начальную и конечную точки проводника.")

    def enable_select_mode(self) -> None:
        self.wire_start = None
        self.mode_var.set("Режим: выбор/перемещение")

    def on_click(self, event: tk.Event) -> None:
        x = self._snap(self.canvas.canvasx(event.x))
        y = self._snap(self.canvas.canvasy(event.y))
        if self.mode_var.get().startswith("Режим: провод"):
            if not self.is_editable:
                return
            if self.wire_start is None:
                self.wire_start = (x, y)
                self.mode_var.set(f"Режим: провод. Начало: {int(x)}, {int(y)}. Выберите конец.")
            else:
                x1, y1 = self.wire_start
                self.wires.append(
                    {
                        "wire_key": uuid.uuid4().hex,
                        "scheme_id": int(self.scheme_id_var.get() or 1),
                        "net_name": "",
                        "x1": x1,
                        "y1": y1,
                        "x2": x,
                        "y2": y,
                    }
                )
                self.wire_start = None
                self.draw_all()
                self.mode_var.set("Режим: провод. Можно добавить следующий проводник или перейти в выбор.")
            return

        self.selected_node_key = self._node_key_at(event.x, event.y)
        self.selected_wire_key = None if self.selected_node_key else self._wire_key_at(event.x, event.y)
        if self.selected_node_key:
            node = self._find_node(self.selected_node_key)
            if node:
                self.drag_start = (x, y)
                self.drag_node_origin = (float(node.get("x", 0)), float(node.get("y", 0)))
        self.draw_all()

    def on_drag(self, event: tk.Event) -> None:
        if not self.is_editable or not self.selected_node_key or not self.drag_start or not self.drag_node_origin:
            return
        node = self._find_node(self.selected_node_key)
        if not node:
            return
        x = self._snap(self.canvas.canvasx(event.x))
        y = self._snap(self.canvas.canvasy(event.y))
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        node["x"] = self._snap(self.drag_node_origin[0] + dx)
        node["y"] = self._snap(self.drag_node_origin[1] + dy)
        self.draw_all()

    def on_release(self, _event: tk.Event) -> None:
        self.drag_start = None
        self.drag_node_origin = None

    def delete_selected(self) -> None:
        if not self.is_editable:
            return
        if self.selected_node_key:
            self.nodes = [node for node in self.nodes if node.get("node_key") != self.selected_node_key]
            self.selected_node_key = None
        elif self.selected_wire_key:
            self.wires = [wire for wire in self.wires if wire.get("wire_key") != self.selected_wire_key]
            self.selected_wire_key = None
        self.draw_all()

    def rename_selected(self, _event: tk.Event) -> None:
        if not self.is_editable or not self.selected_node_key:
            return
        node = self._find_node(self.selected_node_key)
        if not node:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Подпись элемента")
        dialog.transient(self)
        dialog.grab_set()
        refdes_var = tk.StringVar(value=str(node.get("refdes") or ""))
        label_var = tk.StringVar(value=str(node.get("label") or ""))
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Обозначение").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=refdes_var, width=35).grid(row=0, column=1, pady=4)
        ttk.Label(frame, text="Подпись").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=label_var, width=35).grid(row=1, column=1, pady=4)

        def save() -> None:
            node["refdes"] = refdes_var.get().strip()
            node["label"] = label_var.get().strip()
            dialog.destroy()
            self.draw_all()

        ttk.Button(frame, text="Сохранить", command=save).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        dialog.wait_window(dialog)

    def draw_all(self) -> None:
        self.canvas.delete("all")
        self._draw_grid()
        for wire in self.wires:
            self._draw_wire(wire)
        for node in self.nodes:
            self._draw_node(node)
        if self.wire_start is not None:
            x, y = self.wire_start
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, width=2)

    def _draw_grid(self) -> None:
        for x in range(0, CANVAS_WIDTH + 1, GRID_STEP):
            self.canvas.create_line(x, 0, x, CANVAS_HEIGHT, fill="#eeeeee")
        for y in range(0, CANVAS_HEIGHT + 1, GRID_STEP):
            self.canvas.create_line(0, y, CANVAS_WIDTH, y, fill="#eeeeee")
        title = f"{self.scheme.get('code', '')} — {self.scheme.get('title', '')}".strip(" —")
        self.canvas.create_text(CANVAS_WIDTH // 2, 22, text=title, font=("Segoe UI", 12, "bold"))

    def _draw_wire(self, wire: Mapping[str, Any]) -> None:
        key = str(wire.get("wire_key") or wire.get("id") or uuid.uuid4().hex)
        width = 3 if key == self.selected_wire_key else 2
        self.canvas.create_line(
            float(wire.get("x1", 0)),
            float(wire.get("y1", 0)),
            float(wire.get("x2", 0)),
            float(wire.get("y2", 0)),
            width=width,
            tags=(f"wire:{key}",),
        )
        if wire.get("net_name"):
            self.canvas.create_text(
                (float(wire.get("x1", 0)) + float(wire.get("x2", 0))) / 2,
                (float(wire.get("y1", 0)) + float(wire.get("y2", 0))) / 2 - 8,
                text=str(wire.get("net_name")),
                font=("Segoe UI", 8),
            )

    def _draw_node(self, node: Mapping[str, Any]) -> None:
        key = str(node.get("node_key") or node.get("id") or uuid.uuid4().hex)
        x = float(node.get("x", 100))
        y = float(node.get("y", 100))
        symbol = str(node.get("symbol_type") or "generic")
        tags = (f"node:{key}", "node")
        width = 3 if key == self.selected_node_key else 2

        def line(x1: float, y1: float, x2: float, y2: float) -> None:
            self.canvas.create_line(x1, y1, x2, y2, width=width, tags=tags)

        if symbol == "resistor":
            line(x - 60, y, x - 34, y)
            self.canvas.create_line(x - 34, y, x - 24, y - 14, x - 12, y + 14, x, y - 14, x + 12, y + 14, x + 24, y - 14, x + 34, y, width=width, tags=tags)
            line(x + 34, y, x + 60, y)
        elif symbol == "capacitor":
            line(x - 60, y, x - 10, y)
            line(x - 10, y - 24, x - 10, y + 24)
            line(x + 10, y - 24, x + 10, y + 24)
            line(x + 10, y, x + 60, y)
        elif symbol == "diode":
            line(x - 60, y, x - 26, y)
            self.canvas.create_polygon(x - 26, y - 22, x - 26, y + 22, x + 22, y, outline="black", fill="white", width=width, tags=tags)
            line(x + 24, y - 24, x + 24, y + 24)
            line(x + 24, y, x + 60, y)
        elif symbol == "inductor":
            line(x - 60, y, x - 35, y)
            for offset in (-30, -10, 10, 30):
                self.canvas.create_arc(x + offset - 10, y - 10, x + offset + 10, y + 10, start=0, extent=180, style=tk.ARC, width=width, tags=tags)
            line(x + 40, y, x + 60, y)
        elif symbol == "power":
            line(x - 60, y, x - 30, y)
            self.canvas.create_oval(x - 30, y - 30, x + 30, y + 30, width=width, tags=tags)
            line(x + 30, y, x + 60, y)
            self.canvas.create_text(x, y - 5, text="+", font=("Segoe UI", 12, "bold"), tags=tags)
            self.canvas.create_text(x, y + 16, text="−", font=("Segoe UI", 12, "bold"), tags=tags)
        elif symbol == "ground":
            line(x, y - 42, x, y - 15)
            line(x - 28, y - 15, x + 28, y - 15)
            line(x - 18, y - 5, x + 18, y - 5)
            line(x - 8, y + 5, x + 8, y + 5)
        elif symbol == "ic":
            self.canvas.create_rectangle(x - 45, y - 35, x + 45, y + 35, width=width, tags=tags)
            for py in (y - 22, y, y + 22):
                line(x - 65, py, x - 45, py)
                line(x + 45, py, x + 65, py)
        elif symbol == "connector":
            self.canvas.create_rectangle(x - 40, y - 28, x + 40, y + 28, width=width, tags=tags)
            for py in (y - 16, y, y + 16):
                self.canvas.create_oval(x - 19, py - 4, x - 11, py + 4, width=width, tags=tags)
                self.canvas.create_oval(x + 11, py - 4, x + 19, py + 4, width=width, tags=tags)
        elif symbol == "transistor":
            self.canvas.create_oval(x - 32, y - 32, x + 32, y + 32, width=width, tags=tags)
            line(x - 60, y, x - 22, y)
            line(x - 10, y - 12, x + 35, y - 42)
            line(x - 10, y + 12, x + 35, y + 42)
            self.canvas.create_polygon(x + 24, y + 32, x + 33, y + 41, x + 18, y + 43, fill="black", tags=tags)
        else:
            self.canvas.create_rectangle(x - 45, y - 28, x + 45, y + 28, width=width, tags=tags)
            line(x - 65, y, x - 45, y)
            line(x + 45, y, x + 65, y)

        self.canvas.create_text(x, y - 45, text=str(node.get("refdes") or ""), font=("Segoe UI", 9, "bold"), tags=tags)
        label = str(node.get("label") or "")[:36]
        self.canvas.create_text(x, y + 54, text=label, font=("Segoe UI", 8), tags=tags)

    def _node_key_at(self, canvas_x: float, canvas_y: float) -> str | None:
        item = self.canvas.find_closest(self.canvas.canvasx(canvas_x), self.canvas.canvasy(canvas_y))
        if not item:
            return None
        for tag in self.canvas.gettags(item[0]):
            if tag.startswith("node:"):
                return tag.split(":", 1)[1]
        return None

    def _wire_key_at(self, canvas_x: float, canvas_y: float) -> str | None:
        item = self.canvas.find_closest(self.canvas.canvasx(canvas_x), self.canvas.canvasy(canvas_y))
        if not item:
            return None
        for tag in self.canvas.gettags(item[0]):
            if tag.startswith("wire:"):
                return tag.split(":", 1)[1]
        return None

    def _find_node(self, key: str) -> dict[str, Any] | None:
        for node in self.nodes:
            if str(node.get("node_key")) == key:
                return node
        return None

    def _client_node(self, row: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["node_key"] = str(data.get("node_key") or data.get("id") or uuid.uuid4().hex)
        data["x"] = float(data.get("x") or 100)
        data["y"] = float(data.get("y") or 100)
        return data

    def _client_wire(self, row: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["wire_key"] = str(data.get("wire_key") or data.get("id") or uuid.uuid4().hex)
        for field in ("x1", "y1", "x2", "y2"):
            data[field] = float(data.get(field) or 0)
        return data

    @staticmethod
    def _snap(value: float) -> float:
        return round(value / GRID_STEP) * GRID_STEP
