from __future__ import annotations

import json
import sys
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable
from uuid import uuid4

try:
    import keyboard
except ImportError:  # pragma: no cover - shown in the GUI at runtime.
    keyboard = None

try:
    import mouse
except ImportError:  # pragma: no cover - shown in the GUI at runtime.
    mouse = None


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
CONFIG_PATH = APP_DIR / "mappings.json"

MODIFIER_ORDER = {
    "ctrl": 0,
    "left ctrl": 0,
    "right ctrl": 0,
    "shift": 1,
    "left shift": 1,
    "right shift": 1,
    "alt": 2,
    "left alt": 2,
    "right alt": 2,
    "windows": 3,
    "left windows": 3,
    "right windows": 3,
    "cmd": 3,
}

DISPLAY_NAMES = {
    "space": "Space",
    "enter": "Enter",
    "esc": "Esc",
    "escape": "Esc",
    "ctrl": "Ctrl",
    "left ctrl": "Left Ctrl",
    "right ctrl": "Right Ctrl",
    "shift": "Shift",
    "left shift": "Left Shift",
    "right shift": "Right Shift",
    "alt": "Alt",
    "left alt": "Left Alt",
    "right alt": "Right Alt",
    "tab": "Tab",
    "backspace": "Backspace",
    "delete": "Delete",
    "windows": "Win",
    "left windows": "Left Win",
    "right windows": "Right Win",
    "plus": "+",
    "minus": "-",
}

MOUSE_BUTTON_ALIASES = {
    "left": "left",
    "left click": "left",
    "mouse left": "left",
    "right": "right",
    "right click": "right",
    "mouse right": "right",
    "middle": "middle",
    "middle click": "middle",
    "mouse middle": "middle",
    "wheel": "middle",
    "x": "x",
    "x1": "x",
    "x2": "x2",
}

MOUSE_DISPLAY_NAMES = {
    "left": "鼠标左键",
    "right": "鼠标右键",
    "middle": "鼠标中键",
    "x": "鼠标侧键 1",
    "x2": "鼠标侧键 2",
}

WHEEL_DISPLAY_NAMES = {
    "up": "滚轮上滚",
    "down": "滚轮下滚",
}


@dataclass
class KeyMapping:
    id: str
    source: str
    target: str
    enabled: bool = True


class ToggleSwitch(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        variable: tk.BooleanVar,
        command: Callable[[], None] | None = None,
        *,
        width: int = 58,
        height: int = 30,
        background: str = "#f5f6f8",
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=background,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.variable = variable
        self.command = command
        self.width = width
        self.height = height
        self.bind("<Button-1>", self._toggle)
        self.variable.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _toggle(self, _event: object | None = None) -> None:
        self.variable.set(not self.variable.get())
        if self.command is not None:
            self.command()

    def _draw(self) -> None:
        self.delete("all")
        is_on = self.variable.get()
        radius = self.height // 2
        track_color = "#1f7a4d" if is_on else "#b8bec8"
        knob_x = self.width - self.height + 3 if is_on else 3

        self.create_oval(1, 1, self.height - 1, self.height - 1, fill=track_color, outline=track_color)
        self.create_oval(self.width - self.height + 1, 1, self.width - 1, self.height - 1, fill=track_color, outline=track_color)
        self.create_rectangle(radius, 1, self.width - radius, self.height - 1, fill=track_color, outline=track_color)
        self.create_oval(knob_x, 3, knob_x + self.height - 6, self.height - 3, fill="#ffffff", outline="#ffffff")


def normalize_key_name(name: str | None) -> str:
    if not name:
        return ""
    raw = name.lower()
    if raw == " ":
        return "space"
    cleaned = " ".join(name.strip().lower().split())
    aliases = {
        "spacebar": "space",
        "+": "plus",
        "-": "minus",
        "control": "ctrl",
        "left control": "left ctrl",
        "right control": "right ctrl",
        "return": "enter",
        "escape": "esc",
        "win": "windows",
        "left win": "left windows",
        "right win": "right windows",
    }
    return aliases.get(cleaned, cleaned)


def normalize_input_token(value: str | None) -> str:
    if not value:
        return ""
    raw = value.lower()
    if raw == " ":
        return "space"
    cleaned = " ".join(value.strip().lower().split())
    if cleaned.startswith("key:"):
        return normalize_key_name(cleaned.split(":", 1)[1])
    if cleaned.startswith("mouse:"):
        button = MOUSE_BUTTON_ALIASES.get(cleaned.split(":", 1)[1], cleaned.split(":", 1)[1])
        return f"mouse:{button}"
    if cleaned.startswith("wheel:"):
        direction = cleaned.split(":", 1)[1]
        return f"wheel:{'down' if direction in {'down', '-1'} else 'up'}"
    if cleaned in MOUSE_BUTTON_ALIASES:
        return f"mouse:{MOUSE_BUTTON_ALIASES[cleaned]}"
    if cleaned in {"wheel up", "scroll up", "滚轮上滚"}:
        return "wheel:up"
    if cleaned in {"wheel down", "scroll down", "滚轮下滚"}:
        return "wheel:down"
    return normalize_key_name(cleaned)


def split_action(action: str) -> list[str]:
    return [normalize_input_token(part) for part in action.split("+") if normalize_input_token(part)]


def is_mouse_button_token(token: str) -> bool:
    return token.startswith("mouse:")


def is_wheel_token(token: str) -> bool:
    return token.startswith("wheel:")


def is_keyboard_token(token: str) -> bool:
    return bool(token) and not is_mouse_button_token(token) and not is_wheel_token(token)


def is_modifier_token(token: str) -> bool:
    return is_keyboard_token(token) and token in MODIFIER_ORDER


def display_input(token: str) -> str:
    token = normalize_input_token(token)
    if is_mouse_button_token(token):
        return MOUSE_DISPLAY_NAMES.get(token.split(":", 1)[1], token)
    if is_wheel_token(token):
        return WHEEL_DISPLAY_NAMES.get(token.split(":", 1)[1], token)
    return DISPLAY_NAMES.get(token, token.upper() if len(token) == 1 else token.title())


def action_to_display(action: str) -> str:
    return " + ".join(display_input(part) for part in split_action(action))


def action_order(token: str, index: int) -> tuple[int, int]:
    if is_mouse_button_token(token) or is_wheel_token(token):
        return (100, index)
    return (MODIFIER_ORDER.get(token, 50), index)


def ordered_action(tokens: list[str]) -> str:
    indexed = list(enumerate(normalize_input_token(token) for token in tokens if normalize_input_token(token)))
    indexed.sort(key=lambda item: action_order(item[1], item[0]))
    return "+".join(token for _, token in indexed)


class PossibleKeyApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PossibleKey")
        self.geometry("920x640")
        self.minsize(800, 540)

        self.mappings: list[KeyMapping] = []
        self.active_keyboard_hooks: dict[str, object] = {}
        self.active_mouse_hooks: dict[str, object] = {}
        self.capture_keyboard_hook: object | None = None
        self.capture_mouse_hook: object | None = None
        self.capture_kind: str | None = None
        self.hooks_suspended_for_capture = False
        self.target_capture_tokens: list[str] = []
        self.target_pressed_tokens: set[str] = set()
        self.pressed_sources: set[str] = set()
        self.capture_lock = threading.Lock()
        self.firing_lock = threading.Lock()
        self.is_firing = False

        self.source_key = tk.StringVar(value="")
        self.target_combo = tk.StringVar(value="")
        self.source_text = tk.StringVar(value="点击捕获源输入")
        self.target_text = tk.StringVar(value="点击捕获目标动作")
        self.status_text = tk.StringVar(value="准备就绪")
        self.global_enabled = tk.BooleanVar(value=True)
        self.global_state_text = tk.StringVar(value="开启")

        self._setup_style()
        self._build_ui()
        self._load_mappings()
        self._render_mappings()
        self._refresh_hooks()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        missing = []
        if keyboard is None:
            missing.append("keyboard")
        if mouse is None:
            missing.append("mouse")
        if missing:
            messagebox.showerror("缺少依赖", f"请先运行：pip install -r requirements.txt\n缺少：{', '.join(missing)}")
            self.status_text.set("缺少依赖，无法监听输入")

    def _setup_style(self) -> None:
        self.configure(bg="#f5f6f8")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f6f8")
        style.configure("Panel.TFrame", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("TLabel", background="#f5f6f8", foreground="#20242a", font=("Microsoft YaHei UI", 10))
        style.configure("Panel.TLabel", background="#ffffff", foreground="#20242a", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background="#f5f6f8", foreground="#15181d", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("Subtle.TLabel", background="#f5f6f8", foreground="#69707a", font=("Microsoft YaHei UI", 9))
        style.configure("Capture.TButton", font=("Microsoft YaHei UI", 13, "bold"), padding=(20, 22))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(14, 10))
        style.configure("Danger.TButton", foreground="#b3261e")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="PossibleKey", style="Title.TLabel").pack(side="left")

        global_wrap = ttk.Frame(header)
        global_wrap.pack(side="right")
        ttk.Label(global_wrap, text="全部映射", style="Subtle.TLabel").pack(side="left", padx=(0, 8))
        ToggleSwitch(global_wrap, self.global_enabled, self._on_global_toggle, background="#f5f6f8").pack(side="left")
        ttk.Label(global_wrap, textvariable=self.global_state_text, style="Subtle.TLabel", width=4).pack(side="left", padx=(8, 0))

        capture_area = ttk.Frame(outer)
        capture_area.pack(fill="x")
        capture_area.columnconfigure(0, weight=1)
        capture_area.columnconfigure(1, weight=1)

        left = ttk.Frame(capture_area, style="Panel.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(left, text="要设置的输入", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(left, text="点击后按一个键，或点击鼠标左键/右键/中键", style="Panel.TLabel").pack(anchor="w", pady=(4, 14))
        self.source_button = ttk.Button(
            left,
            textvariable=self.source_text,
            style="Capture.TButton",
            command=self._begin_source_capture,
            takefocus=False,
        )
        self.source_button.pack(fill="x", expand=True)
        ttk.Button(left, text="清空左侧", command=self._clear_source_input).pack(anchor="e", pady=(12, 0))

        right = ttk.Frame(capture_area, style="Panel.TFrame", padding=18)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ttk.Label(right, text="映射的目标动作", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(right, text="录完目标动作后点击确认目标；重复动作需松开再按", style="Panel.TLabel").pack(anchor="w", pady=(4, 14))
        self.target_button = ttk.Button(
            right,
            textvariable=self.target_text,
            style="Capture.TButton",
            command=self._begin_target_capture,
            takefocus=False,
        )
        self.target_button.pack(fill="x", expand=True)
        right_actions = ttk.Frame(right, style="Panel.TFrame")
        right_actions.pack(anchor="e", pady=(12, 0))
        self.confirm_target_button = ttk.Button(
            right_actions,
            text="确认目标",
            command=self._confirm_target_capture,
            state="disabled",
            takefocus=False,
        )
        self.confirm_target_button.pack(side="left", padx=(0, 8))
        ttk.Button(right_actions, text="清空右侧", command=self._clear_target_input).pack(side="left")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=18)
        ttk.Button(actions, text="添加映射", style="Accent.TButton", command=self._add_mapping).pack(side="left")
        ttk.Button(actions, text="清空全部输入", command=self._clear_inputs).pack(side="left", padx=(10, 0))
        ttk.Label(actions, textvariable=self.status_text, style="Subtle.TLabel").pack(side="right")

        list_header = ttk.Frame(outer)
        list_header.pack(fill="x", pady=(4, 8))
        ttk.Label(list_header, text="映射列表", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")

        self.list_frame = ttk.Frame(outer)
        self.list_frame.pack(fill="both", expand=True)

    def _load_mappings(self) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.mappings = [
                KeyMapping(
                    id=str(item.get("id") or uuid4()),
                    source=normalize_input_token(item.get("source")),
                    target=ordered_action(split_action(str(item.get("target", "")))),
                    enabled=bool(item.get("enabled", True)),
                )
                for item in payload
                if item.get("source") and item.get("target")
            ]
        except (OSError, json.JSONDecodeError):
            messagebox.showwarning("配置读取失败", "mappings.json 无法读取，已使用空配置启动。")
            self.mappings = []

    def _save_mappings(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps([asdict(mapping) for mapping in self.mappings], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _begin_source_capture(self) -> None:
        if not self._input_ready():
            return
        self._stop_capture()
        self._suspend_hooks_for_capture()
        self.focus_force()
        self.capture_kind = "source"
        self.status_text.set("正在捕获源输入...")
        self.source_text.set("请按键或点击鼠标")
        self.source_button.state(["disabled"])
        self.capture_keyboard_hook = keyboard.hook(self._handle_keyboard_capture_event, suppress=False)
        self.capture_mouse_hook = mouse.hook(self._handle_mouse_capture_event)

    def _begin_target_capture(self) -> None:
        if not self._input_ready():
            return
        self._stop_capture()
        self._suspend_hooks_for_capture()
        self.focus_force()
        with self.capture_lock:
            self.target_capture_tokens = []
            self.target_pressed_tokens = set()
        self.capture_kind = "target"
        self.status_text.set("正在捕获目标动作，点击确认目标完成")
        self.target_text.set("输入目标动作后点击确认目标")
        self.target_button.state(["disabled"])
        self.confirm_target_button.state(["!disabled"])
        self.capture_keyboard_hook = keyboard.hook(self._handle_keyboard_capture_event, suppress=False)
        self.capture_mouse_hook = mouse.hook(self._handle_mouse_capture_event)

    def _handle_keyboard_capture_event(self, event: object) -> None:
        event_type = getattr(event, "event_type", "")
        token = normalize_input_token(getattr(event, "name", ""))
        if not token:
            return
        if event_type == "up":
            if self.capture_kind == "target":
                with self.capture_lock:
                    self.target_pressed_tokens.discard(token)
            return
        if event_type != "down":
            return

        if self.capture_kind == "source":
            self.after(0, lambda: self._finish_source_capture(token))
            return

        if self.capture_kind == "target":
            with self.capture_lock:
                if token in self.target_pressed_tokens:
                    return
                self.target_pressed_tokens.add(token)
                self.target_capture_tokens.append(token)
                preview = action_to_display(ordered_action(self.target_capture_tokens))
            self.after(0, lambda: self.target_text.set(preview))

    def _handle_mouse_capture_event(self, event: object) -> None:
        token = self._mouse_event_to_token(event)
        if not token:
            return
        if self.capture_kind == "source":
            self.after(0, lambda: self._finish_source_capture(token))
            return
        if self.capture_kind == "target":
            if self._is_target_confirm_button_click(token):
                return
            with self.capture_lock:
                self.target_capture_tokens.append(token)
                preview = action_to_display(ordered_action(self.target_capture_tokens))
            self.after(0, lambda: self.target_text.set(preview))

    def _is_target_confirm_button_click(self, token: str) -> bool:
        if normalize_input_token(token) != "mouse:left":
            return False
        return self._is_pointer_over_widget(self.confirm_target_button)

    def _is_pointer_over_widget(self, widget: tk.Widget) -> bool:
        if mouse is None:
            return False
        try:
            x, y = mouse.get_position()
            left = widget.winfo_rootx()
            top = widget.winfo_rooty()
            return widget.winfo_ismapped() and left <= x <= left + widget.winfo_width() and top <= y <= top + widget.winfo_height()
        except (AttributeError, tk.TclError):
            return False

    def _mouse_event_to_token(self, event: object) -> str:
        if mouse is None:
            return ""
        if isinstance(event, mouse.ButtonEvent) and event.event_type == "down":
            return f"mouse:{event.button}"
        if isinstance(event, mouse.WheelEvent):
            return "wheel:up" if event.delta > 0 else "wheel:down"
        return ""

    def _finish_source_capture(self, token: str) -> None:
        self._stop_capture()
        self.source_key.set(token)
        self.source_text.set(display_input(token))
        self.status_text.set(f"源输入已设置为 {display_input(token)}")

    def _finish_target_capture(self, preset_combo: str | None = None) -> None:
        with self.capture_lock:
            combo = preset_combo or ordered_action(self.target_capture_tokens)
        self._stop_capture()
        if not combo:
            self.target_combo.set("")
            self.target_text.set("点击捕获目标动作")
            self.status_text.set("没有捕获到目标动作")
            return
        self.target_combo.set(combo)
        self.target_text.set(action_to_display(combo))
        self.status_text.set(f"目标动作已设置为 {action_to_display(combo)}")

    def _confirm_target_capture(self) -> None:
        if self.capture_kind != "target":
            return
        self._finish_target_capture()

    def _stop_capture(self, restore_hooks: bool = True) -> None:
        if self.capture_keyboard_hook is not None and keyboard is not None:
            try:
                keyboard.unhook(self.capture_keyboard_hook)
            except (KeyError, ValueError):
                pass
        if self.capture_mouse_hook is not None and mouse is not None:
            try:
                mouse.unhook(self.capture_mouse_hook)
            except ValueError:
                pass
        self.capture_keyboard_hook = None
        self.capture_mouse_hook = None
        self.capture_kind = None
        self.confirm_target_button.state(["disabled"])
        self.after(120, self._enable_capture_buttons_if_idle)
        if restore_hooks and self.hooks_suspended_for_capture:
            self.hooks_suspended_for_capture = False
            self._refresh_hooks()

    def _enable_capture_buttons_if_idle(self) -> None:
        if self.capture_kind is not None:
            return
        try:
            self.source_button.state(["!disabled"])
            self.target_button.state(["!disabled"])
        except tk.TclError:
            pass

    def _suspend_hooks_for_capture(self) -> None:
        if self.hooks_suspended_for_capture:
            return
        self._clear_active_hooks()
        self.hooks_suspended_for_capture = True

    def _add_mapping(self) -> None:
        source = normalize_input_token(self.source_key.get())
        target = ordered_action(split_action(self.target_combo.get()))
        if not source or not target:
            messagebox.showinfo("还差一步", "请先配置左侧源输入和右侧目标动作。")
            return
        if source in split_action(target):
            if not messagebox.askyesno("确认映射", "源输入也出现在目标动作里，可能产生重复触发。仍然添加吗？"):
                return

        existing = next((mapping for mapping in self.mappings if mapping.source == source), None)
        if existing:
            existing.target = target
            existing.enabled = True
            self.status_text.set(f"已更新 {display_input(source)} 的映射")
        else:
            self.mappings.append(KeyMapping(id=str(uuid4()), source=source, target=target, enabled=True))
            self.status_text.set("映射添加成功")

        self._save_mappings()
        self._render_mappings()
        self._refresh_hooks()
        self._clear_inputs()

    def _clear_source_input(self) -> None:
        self._stop_capture()
        self.source_key.set("")
        self.source_text.set("点击捕获源输入")
        self.status_text.set("左侧已清空")

    def _clear_target_input(self) -> None:
        self._stop_capture()
        self.target_combo.set("")
        self.target_text.set("点击捕获目标动作")
        with self.capture_lock:
            self.target_capture_tokens = []
            self.target_pressed_tokens = set()
        self.confirm_target_button.state(["disabled"])
        self.status_text.set("右侧已清空")

    def _clear_inputs(self) -> None:
        self._clear_source_input()
        self._clear_target_input()
        self.status_text.set("输入已清空")

    def _render_mappings(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        if not self.mappings:
            empty = ttk.Frame(self.list_frame, style="Panel.TFrame", padding=26)
            empty.pack(fill="x")
            ttk.Label(empty, text="还没有映射，先在上方添加一个。", style="Panel.TLabel").pack()
            return

        for mapping in self.mappings:
            row = ttk.Frame(self.list_frame, style="Panel.TFrame", padding=(14, 12))
            row.pack(fill="x", pady=(0, 10))
            row.columnconfigure(2, weight=1)

            enabled_var = tk.BooleanVar(value=mapping.enabled)
            ToggleSwitch(
                row,
                enabled_var,
                lambda item=mapping, var=enabled_var: self._set_mapping_enabled(item, var.get()),
                width=52,
                height=28,
                background="#ffffff",
            ).grid(row=0, column=0, padx=(0, 10))

            state_text = "开启" if mapping.enabled else "关闭"
            ttk.Label(row, text=state_text, style="Panel.TLabel", width=4).grid(row=0, column=1, padx=(0, 12))

            text = f"{display_input(mapping.source)}  ->  {action_to_display(mapping.target)}"
            ttk.Label(row, text=text, style="Panel.TLabel", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=2, sticky="w")

            ttk.Button(row, text="删除", style="Danger.TButton", command=lambda item=mapping: self._delete_mapping(item)).grid(row=0, column=3, padx=(12, 0))

    def _set_mapping_enabled(self, mapping: KeyMapping, enabled: bool) -> None:
        mapping.enabled = enabled
        self._save_mappings()
        self._render_mappings()
        self._refresh_hooks()
        state = "开启" if enabled else "关闭"
        self.status_text.set(f"已{state} {display_input(mapping.source)}")

    def _delete_mapping(self, mapping: KeyMapping) -> None:
        self.mappings = [item for item in self.mappings if item.id != mapping.id]
        self._save_mappings()
        self._render_mappings()
        self._refresh_hooks()
        self.status_text.set("映射已删除")

    def _on_global_toggle(self) -> None:
        self.global_state_text.set("开启" if self.global_enabled.get() else "关闭")
        self._refresh_hooks()

    def _clear_active_hooks(self) -> None:
        if keyboard is not None:
            for hook in self.active_keyboard_hooks.values():
                try:
                    keyboard.unhook(hook)
                except (KeyError, ValueError):
                    pass
        if mouse is not None:
            for hook in self.active_mouse_hooks.values():
                try:
                    mouse.unhook(hook)
                except ValueError:
                    pass
        self.active_keyboard_hooks.clear()
        self.active_mouse_hooks.clear()
        self.pressed_sources.clear()

    def _refresh_hooks(self) -> None:
        if keyboard is None or mouse is None:
            return
        self._clear_active_hooks()

        self.global_state_text.set("开启" if self.global_enabled.get() else "关闭")
        if self.capture_kind is not None:
            return
        if not self.global_enabled.get():
            self.status_text.set("全部映射已关闭")
            return

        enabled_count = 0
        for mapping in self.mappings:
            if not mapping.enabled:
                continue
            if self._register_mapping_hook(mapping):
                enabled_count += 1

        if enabled_count:
            self.status_text.set(f"已启用 {enabled_count} 条映射")
        elif self.mappings:
            self.status_text.set("当前没有开启的映射")

    def _register_mapping_hook(self, mapping: KeyMapping) -> bool:
        source = normalize_input_token(mapping.source)
        try:
            if is_keyboard_token(source):
                hook = keyboard.hook_key(source, lambda event, item=mapping: self._handle_keyboard_mapping_event(item, event), suppress=True)
                self.active_keyboard_hooks[mapping.id] = hook
                return True

            hook = mouse.hook(lambda event, item=mapping: self._handle_mouse_mapping_event(item, event))
            self.active_mouse_hooks[mapping.id] = hook
            return True
        except (ValueError, OSError) as exc:
            self.status_text.set(f"{display_input(source)} 监听失败：{exc}")
            return False

    def _handle_keyboard_mapping_event(self, mapping: KeyMapping, event: object) -> bool:
        if self.capture_kind is not None:
            return True
        source = normalize_input_token(mapping.source)
        event_type = getattr(event, "event_type", "")
        if event_type == "up":
            self.pressed_sources.discard(source)
            return True
        if event_type != "down":
            return True
        if source in self.pressed_sources:
            return False
        self.pressed_sources.add(source)
        self._queue_fire_mapping(mapping)
        return False

    def _handle_mouse_mapping_event(self, mapping: KeyMapping, event: object) -> None:
        if self.capture_kind is not None:
            return
        if self._is_replaying():
            return
        token = self._mouse_event_to_token(event)
        if token and token == normalize_input_token(mapping.source):
            self._queue_fire_mapping(mapping)

    def _queue_fire_mapping(self, mapping: KeyMapping) -> None:
        threading.Thread(target=self._delayed_fire_mapping, args=(mapping,), daemon=True).start()

    def _delayed_fire_mapping(self, mapping: KeyMapping) -> None:
        time.sleep(0.03)
        self._fire_mapping(mapping)

    def _fire_mapping(self, mapping: KeyMapping) -> None:
        if keyboard is None or mouse is None:
            return
        if self.capture_kind is not None:
            return
        with self.firing_lock:
            if self.is_firing:
                return
            self.is_firing = True
        try:
            self._send_action(mapping.target)
            self.after(0, lambda: self.status_text.set(f"已触发 {display_input(mapping.source)} -> {action_to_display(mapping.target)}"))
        finally:
            with self.firing_lock:
                self.is_firing = False

    def _send_action(self, action: str) -> None:
        tokens = split_action(action)
        pressed_modifiers: list[str] = []
        try:
            for token in tokens:
                if is_modifier_token(token):
                    if token not in pressed_modifiers:
                        keyboard.press(token)
                        pressed_modifiers.append(token)
                    continue
                if is_keyboard_token(token):
                    keyboard.press_and_release(token)
                    continue
                if is_mouse_button_token(token) or is_wheel_token(token):
                    self._send_mouse_token(token)
        finally:
            for key in reversed(pressed_modifiers):
                keyboard.release(key)

    def _send_mouse_token(self, token: str) -> None:
        if is_mouse_button_token(token):
            mouse.click(token.split(":", 1)[1])
            return
        if is_wheel_token(token):
            direction = token.split(":", 1)[1]
            mouse.wheel(1 if direction == "up" else -1)

    def _is_replaying(self) -> bool:
        with self.firing_lock:
            return self.is_firing

    def _input_ready(self) -> bool:
        missing = []
        if keyboard is None:
            missing.append("keyboard")
        if mouse is None:
            missing.append("mouse")
        if not missing:
            return True
        messagebox.showerror("缺少依赖", f"请先运行：pip install -r requirements.txt\n缺少：{', '.join(missing)}")
        return False

    def _on_close(self) -> None:
        self._stop_capture(restore_hooks=False)
        self._clear_active_hooks()
        self.destroy()


def main() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = PossibleKeyApp()
    app.mainloop()
