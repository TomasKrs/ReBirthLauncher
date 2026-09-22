import os
import sys
import glob
import time
import winreg
import ctypes
import math
import struct
import random
import json
import wave
import base64
import shutil
import threading
import subprocess
import webbrowser
import urllib.request
import zipfile
import copy
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from learning_center_steps import REBIRTH_TUTORIAL_STEPS

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

DOCUMENT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tif", ".tiff"}
DOCUMENT_TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".log", ".rtf", ".xml", ".ini", ".cfg"}
DOCUMENT_HTML_EXTENSIONS = {".html", ".htm"}
DOCUMENT_PREVIEW_SIZE = (140, 96)
DOCUMENT_EXT_COLORS = {
    ".pdf": "#FF453A",
    ".txt": "#A0A5C0",
    ".md": "#00E5FF",
    ".html": "#FF9500",
    ".htm": "#FF9500",
    ".json": "#00FF66",
    ".csv": "#8A2BE2",
    ".xml": "#FF9500",
    ".png": "#00E5FF",
    ".jpg": "#00E5FF",
    ".jpeg": "#00E5FF",
    ".gif": "#00FF66",
    ".bmp": "#00E5FF",
    ".webp": "#00E5FF",
}
PATTERN_BANK_FORMAT = "rebirth-toolbox-pattern-bank"
PATTERN_BANK_VERSION = 1

# --- PORTABLEAPPS & DIRECTORY SETUP ---
def get_base_dir():
    # Returns absolute path to launcher root directory
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
os.chdir(BASE_DIR)

EXE_NAME = "Rebirth.exe"
EXE_PATH = os.path.join(BASE_DIR, EXE_NAME)

def is_rebirth_exe_ready():
    return os.path.exists(EXE_PATH)

def is_iso_ready(config=None):
    return bool(find_iso_file(config))

def is_setup_wizard_only(config=None):
    return not is_rebirth_exe_ready() and not is_iso_ready(config)

CONFIG_FILE = os.path.join(BASE_DIR, "ReBirthToolBox.json")
LEGACY_CONFIG_FILE = os.path.join(BASE_DIR, "rebirth_toolbox_config.json")
DEFAULT_SONGS_DIR = os.path.join(BASE_DIR, "Default Songs")
SONGS_DIR = os.path.join(BASE_DIR, "Songs")
DOCUMENTS_DIR = os.path.join(BASE_DIR, "Documents")
MODS_DIR = os.path.join(BASE_DIR, "Mods")
MOD_TAB_LABEL = "RBM DB"
MOD_GALLERY_IMG_WIDTH = 320
MOD_GALLERY_IMG_HEIGHT = 172
MOD_GALLERY_LEFT_WIDTH = MOD_GALLERY_IMG_WIDTH + 16
MOD_GALLERY_ROW_HEIGHT = 210
MOD_GALLERY_VIEW_BUFFER = 5
MOD_RECENT_MAX = 12
MOD_FILTER_LABELS = ("All mods", "★ Favorites", "🕐 Recent")
TUTORIAL_TAB_LABEL = "💡 Tips And Tricks"
SUPER_RACK_WIDTH = 800
SUPER_RACK_HEIGHT = 620
SUPER_RACK_LABEL = "Super Rack"
# Typical ReBirth rack content size (song window before MDI maximize).
SUPER_RACK_CLIENT_W = 640
SUPER_RACK_CLIENT_H = 486
# Sharp display modes (no magnifier — that made pixels mushy).
SUPER_RACK_DISPLAY_CHOICES = (
    ("Fit height (sharp, side bezel)", "fit_height"),
    ("Keep desktop", "desktop"),
)
SUPER_RACK_DISPLAY_LABELS = [c[0] for c in SUPER_RACK_DISPLAY_CHOICES]
SUPER_RACK_DISPLAY_BY_LABEL = {c[0]: c[1] for c in SUPER_RACK_DISPLAY_CHOICES}
# Legacy zoom combo → map into display modes
SUPER_RACK_SCALE_CHOICES = SUPER_RACK_DISPLAY_CHOICES  # alias for older UI refs
_SUPER_RACK_MENU_BACKUP = {}
_SUPER_RACK_STYLE_BACKUP = {}
_SUPER_RACK_HIDDEN_CHROME = {}  # main_hwnd -> [(child_hwnd, was_visible), ...]
_SUPER_RACK_SIZE_CACHE = {}  # main_hwnd -> (client_w, client_h) natural rack size
_SUPER_RACK_MAG_READY = False
_SUPER_RACK_TASKBAR_HIDDEN = False
_SUPER_RACK_TASKBAR_HWNDS = []


def super_rack_display_label_for_value(value):
    """Accept legacy float zoom or new mode id / label."""
    if isinstance(value, str):
        if value in SUPER_RACK_DISPLAY_BY_LABEL:
            return value
        if value in SUPER_RACK_DISPLAY_BY_LABEL.values():
            for label, mode in SUPER_RACK_DISPLAY_CHOICES:
                if mode == value:
                    return label
        # legacy labels like "125%"
        if "100%" in value or value.lower() == "desktop":
            return SUPER_RACK_DISPLAY_CHOICES[1][0]
        return SUPER_RACK_DISPLAY_CHOICES[0][0]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return SUPER_RACK_DISPLAY_CHOICES[0][0]
    # Old zoom: 1.0 kept desktop; anything larger meant "bigger" → fit height
    if v <= 1.01:
        return SUPER_RACK_DISPLAY_CHOICES[1][0]
    return SUPER_RACK_DISPLAY_CHOICES[0][0]


def resolve_super_rack_display(label_or_value=None, config=None):
    if label_or_value is not None:
        if isinstance(label_or_value, str):
            if label_or_value in SUPER_RACK_DISPLAY_BY_LABEL:
                return SUPER_RACK_DISPLAY_BY_LABEL[label_or_value]
            if label_or_value in ("fit_height", "desktop"):
                return label_or_value
            label = super_rack_display_label_for_value(label_or_value)
            return SUPER_RACK_DISPLAY_BY_LABEL.get(label, "fit_height")
        try:
            return "desktop" if float(label_or_value) <= 1.01 else "fit_height"
        except (TypeError, ValueError):
            pass
    if config is not None:
        raw = config.get("rebirth_super_rack_display")
        if raw:
            return resolve_super_rack_display(raw)
        return resolve_super_rack_display(config.get("rebirth_super_rack_scale", 1.25))
    return "fit_height"


# Back-compat helpers used by older call sites
def super_rack_scale_label_for_value(value):
    return super_rack_display_label_for_value(value)


def resolve_super_rack_scale(label_or_value=None, config=None):
    mode = resolve_super_rack_display(label_or_value, config)
    return 1.0 if mode == "desktop" else 1.25
_MOD_SCREENSHOT_INDEX_CACHE = {"key": None, "index": {}}
RBM_SAMPLE_CACHE_DIR = os.path.join(MODS_DIR, ".sample_cache_v7")
RB20FUL_SIZE = 134217984
RB20FUL_FILENAME = "RB20FUL.DAT"
RB20FUL_URL = "https://azopsoft.com/data/RB20FUL.DAT"
_RB20FUL_BYTES = None
_TK_IMAGE_CACHE = {}
PATTERN_BANKS_DIR = os.path.join(BASE_DIR, "PatternBanks")
TOOLBOX_CACHE_DIR = os.path.join(BASE_DIR, ".toolbox_cache")
LIBRARY_CACHE_FILE = os.path.join(TOOLBOX_CACHE_DIR, "library_index.json")
LIBRARY_CACHE_VERSION = 1
MOD_CATALOG_FILE = os.path.join(BASE_DIR, "Mods", "mod-catalog.json")
GENERIC_MOD_NAMES = {
    "template mod",
    "template",
    "new mod",
    "custom mod",
    "mod",
    "untitled",
    "rebirth mod",
    "default mod",
    "standard rebirth",
    "custom rebirth mod skin pack",
}
DEFAULT_DOWNLOAD_CATALOG = {
    "iso": {
        "title": "ReBirth 2.01 CD-ROM Image (2001 version)",
        "filename": "Rebirth 2.01 (2001 version).iso",
        "url": "",
        "hint": "Mount this ISO when ReBirth asks for the original CD (mnx2010 mirror).",
    },
    "installer": {
        "title": "ReBirth RB-338 2.0.1 Installer",
        "filename": "ReBirth RB-338 2.0.1 Installer.exe",
        "url": "",
        "hint": "ReBirth 2.0.1 setup from the Mooglala archive bundle on Archive.org.",
    },
}
DEFAULT_DIRECTORY_PATHS = {
    "songs": "Songs",
    "documents": "Documents",
    "default_songs": "Default Songs",
    "downloads": "Downloads",
    "mods": "Mods",
}
DEFAULT_THEME_COLORS = {
    "bg_root": "#12131A",
    "bg_header": "#191B24",
    "bg_panel": "#1A1C27",
    "bg_card": "#12131A",
    "bg_input": "#1A1C27",
    "bg_elevated": "#242736",
    "border": "#282B3C",
    "border_soft": "#242736",
    "fg_primary": "#FFFFFF",
    "fg_muted": "#A0A5C0",
    "fg_dim": "#6C7293",
    "accent_cyan": "#00E5FF",
    "accent_green": "#00FF66",
    "accent_orange": "#FF9500",
    "accent_purple": "#8A2BE2",
    "accent_red": "#FF453A",
    "btn_primary": "#00A86B",
    "btn_primary_hover": "#00C880",
    "btn_secondary": "#242736",
    "btn_danger_bg": "#2D1A21",
    "select_bg": "#242736",
    "select_color": "#1F2230",
    "progress": "#00FF66",
    "header_screw": "#3A3D52",
    "header_wave": "#00FF66",
    "header_outline": "#2A2D3E",
    "header_scope_bg": "#08140B",
    "header_scope_border": "#1A3B20",
}

def make_theme(label, **overrides):
    colors = dict(DEFAULT_THEME_COLORS)
    colors.update(overrides)
    return {"label": label, "colors": colors}

DEFAULT_THEMES = {
    "midnight_studio": make_theme("Midnight Studio"),
    "rebirth_classic": make_theme(
        "ReBirth Classic",
        accent_cyan="#39FF14",
        accent_green="#39FF14",
        accent_orange="#FF6600",
        btn_primary="#2E8B2E",
        progress="#39FF14",
        header_wave="#39FF14",
    ),
    "acid_lime": make_theme(
        "Acid Lime",
        bg_root="#0E1408",
        bg_panel="#141C0D",
        bg_card="#101808",
        accent_cyan="#B8FF00",
        accent_green="#CCFF00",
        accent_orange="#E6FF66",
        btn_primary="#7CB518",
        progress="#CCFF00",
        header_wave="#CCFF00",
        header_scope_bg="#101808",
        header_scope_border="#3A5A10",
    ),
    "purple_haze": make_theme(
        "Purple Haze",
        bg_root="#140F1E",
        bg_panel="#1B1428",
        bg_card="#161022",
        accent_cyan="#C77DFF",
        accent_green="#B388FF",
        accent_purple="#9D4EDD",
        btn_primary="#7B2CBF",
        progress="#C77DFF",
        header_wave="#B388FF",
    ),
    "copper_analog": make_theme(
        "Copper Analog",
        bg_root="#17120E",
        bg_panel="#211812",
        bg_card="#1A1510",
        accent_cyan="#FFB347",
        accent_green="#D4A574",
        accent_orange="#E67E22",
        btn_primary="#B87333",
        progress="#FFB347",
        header_wave="#E67E22",
    ),
    "ice_blue": make_theme(
        "Ice Blue",
        bg_root="#0B1218",
        bg_panel="#101A24",
        bg_card="#0E1620",
        accent_cyan="#7FDBFF",
        accent_green="#92E0FF",
        accent_orange="#A8D8FF",
        btn_primary="#2E86AB",
        progress="#7FDBFF",
        header_wave="#92E0FF",
    ),
    "blood_moon": make_theme(
        "Blood Moon",
        bg_root="#160C0C",
        bg_panel="#221010",
        bg_card="#1A0E0E",
        accent_cyan="#FF6B6B",
        accent_green="#FF8787",
        accent_red="#FF2D55",
        btn_primary="#C0392B",
        progress="#FF6B6B",
        header_wave="#FF6B6B",
    ),
    "matrix_terminal": make_theme(
        "Matrix Terminal",
        bg_root="#020802",
        bg_panel="#041004",
        bg_card="#030A03",
        bg_input="#020802",
        bg_elevated="#0A1A0A",
        accent_cyan="#00FF41",
        accent_green="#00FF41",
        accent_orange="#66FF66",
        btn_primary="#008F11",
        progress="#00FF41",
        header_wave="#00FF41",
        header_scope_bg="#020802",
        header_scope_border="#0A3D0A",
    ),
    "sunset_vapor": make_theme(
        "Sunset Vapor",
        bg_root="#1A0F24",
        bg_panel="#24142E",
        bg_card="#1E1230",
        accent_cyan="#FF71CE",
        accent_green="#FF9EE2",
        accent_orange="#FFB347",
        accent_purple="#B967FF",
        btn_primary="#FF6B9D",
        progress="#FF71CE",
        header_wave="#FF71CE",
    ),
    "ocean_depth": make_theme(
        "Ocean Depth",
        bg_root="#071018",
        bg_panel="#0C1824",
        bg_card="#091420",
        accent_cyan="#20B2AA",
        accent_green="#48D1CC",
        accent_orange="#5FD4D4",
        btn_primary="#117A8B",
        progress="#20B2AA",
        header_wave="#48D1CC",
    ),
    "amber_tube": make_theme(
        "Amber Tube",
        bg_root="#141008",
        bg_panel="#1C160C",
        bg_card="#18120A",
        accent_cyan="#FFB000",
        accent_green="#FFC857",
        accent_orange="#FF9500",
        btn_primary="#CC8400",
        progress="#FFB000",
        header_wave="#FFB000",
        header_scope_bg="#181008",
        header_scope_border="#664400",
    ),
    "neon_tokyo": make_theme(
        "Neon Tokyo",
        bg_root="#120818",
        bg_panel="#1A0C24",
        bg_card="#150A20",
        accent_cyan="#00F5FF",
        accent_green="#00F5FF",
        accent_orange="#FF007F",
        accent_purple="#FF007F",
        btn_primary="#D100D1",
        progress="#00F5FF",
        header_wave="#00F5FF",
    ),
    "forest_night": make_theme(
        "Forest Night",
        bg_root="#0A120C",
        bg_panel="#101A12",
        bg_card="#0D1610",
        accent_cyan="#6BCB77",
        accent_green="#4D9E53",
        accent_orange="#8FD694",
        btn_primary="#2D6A4F",
        progress="#6BCB77",
        header_wave="#6BCB77",
    ),
    "slate_minimal": make_theme(
        "Slate Minimal",
        bg_root="#15171C",
        bg_panel="#1C1F26",
        bg_card="#181A20",
        accent_cyan="#C8CDD8",
        accent_green="#A8B0C0",
        accent_orange="#9098A8",
        btn_primary="#5C6370",
        progress="#A8B0C0",
        header_wave="#C8CDD8",
    ),
    "candy_pop": make_theme(
        "Candy Pop",
        bg_root="#18121A",
        bg_panel="#221824",
        bg_card="#1D1520",
        accent_cyan="#FF6AD5",
        accent_green="#C774E8",
        accent_orange="#FFD166",
        accent_purple="#FF6AD5",
        btn_primary="#E056A0",
        progress="#FF6AD5",
        header_wave="#FF6AD5",
    ),
    "retro_amber": make_theme(
        "Retro Amber CRT",
        bg_root="#120E00",
        bg_panel="#1A1400",
        bg_card="#161000",
        accent_cyan="#FFBF00",
        accent_green="#FFD966",
        accent_orange="#FF9500",
        btn_primary="#B8860B",
        progress="#FFBF00",
        header_wave="#FFBF00",
        fg_primary="#FFE8A3",
        fg_muted="#D4B86A",
        header_scope_bg="#120E00",
        header_scope_border="#665500",
    ),
    "cyber_punk": make_theme(
        "Cyber Punk",
        bg_root="#100812",
        bg_panel="#180C1C",
        bg_card="#140A18",
        accent_cyan="#FCEE09",
        accent_green="#FCEE09",
        accent_orange="#FF005C",
        accent_purple="#FF005C",
        btn_primary="#FF005C",
        progress="#FCEE09",
        header_wave="#FCEE09",
    ),
    "silver_studio": make_theme(
        "Silver Studio",
        bg_root="#121418",
        bg_panel="#181C22",
        bg_card="#141820",
        accent_cyan="#AEC6CF",
        accent_green="#8FD3E8",
        accent_orange="#B0C4DE",
        btn_primary="#607D8B",
        progress="#8FD3E8",
        header_wave="#AEC6CF",
    ),
    "wine_cellar": make_theme(
        "Wine Cellar",
        bg_root="#140A10",
        bg_panel="#1C1018",
        bg_card="#180C14",
        accent_cyan="#E8A0BF",
        accent_green="#D98880",
        accent_orange="#C98474",
        btn_primary="#8B1538",
        progress="#E8A0BF",
        header_wave="#D98880",
    ),
    "arctic_dawn": make_theme(
        "Arctic Dawn",
        bg_root="#101620",
        bg_panel="#162030",
        bg_card="#121A28",
        accent_cyan="#E0F7FA",
        accent_green="#B2EBF2",
        accent_orange="#80DEEA",
        btn_primary="#4DD0E1",
        progress="#B2EBF2",
        header_wave="#E0F7FA",
    ),
}

def get_default_themes():
    return copy.deepcopy(DEFAULT_THEMES)

def merge_config_themes(cfg):
    cfg.setdefault("theme", "midnight_studio")
    cfg.setdefault("themes", {})
    for theme_id, theme_def in DEFAULT_THEMES.items():
        if theme_id not in cfg["themes"]:
            cfg["themes"][theme_id] = copy.deepcopy(theme_def)
            continue
        stored = cfg["themes"][theme_id]
        stored.setdefault("label", theme_def["label"])
        stored.setdefault("colors", {})
        for color_key, color_val in theme_def["colors"].items():
            stored["colors"].setdefault(color_key, color_val)
    if cfg["theme"] not in cfg["themes"]:
        cfg["theme"] = "midnight_studio"
    return cfg

def get_active_theme_palette(cfg):
    themes = (cfg or {}).get("themes") or DEFAULT_THEMES
    theme_id = (cfg or {}).get("theme") or "midnight_studio"
    if theme_id not in themes:
        theme_id = "midnight_studio"
    colors = themes.get(theme_id, {}).get("colors") or DEFAULT_THEME_COLORS
    merged = dict(DEFAULT_THEME_COLORS)
    merged.update(colors)
    return merged

def get_build_palette():
    return dict(DEFAULT_THEME_COLORS)

def get_theme_choices(cfg):
    themes = (cfg or {}).get("themes") or DEFAULT_THEMES
    theme_ids = sorted(themes.keys(), key=lambda tid: (themes[tid].get("label") or tid).lower())
    labels = [themes[tid].get("label") or tid for tid in theme_ids]
    return theme_ids, labels

def remap_theme_color(color, old_palette, new_palette):
    if not isinstance(color, str) or not color.startswith("#"):
        return color
    norm = color.upper()
    for key, old_val in old_palette.items():
        if isinstance(old_val, str) and old_val.upper() == norm:
            return new_palette.get(key, color)
    return color

def apply_theme_colors_to_widget(widget, old_palette, new_palette):
    for prop in (
        "bg",
        "fg",
        "activebackground",
        "activeforeground",
        "highlightbackground",
        "highlightcolor",
        "selectcolor",
        "insertbackground",
        "disabledforeground",
    ):
        try:
            current = widget.cget(prop)
        except tk.TclError:
            continue
        if not isinstance(current, str):
            continue
        new_val = remap_theme_color(current, old_palette, new_palette)
        if new_val != current:
            try:
                widget.configure(**{prop: new_val})
            except tk.TclError:
                pass
    try:
        children = widget.winfo_children()
    except tk.TclError:
        return
    for child in children:
        apply_theme_colors_to_widget(child, old_palette, new_palette)
DEFAULT_SONG_OPTIONS = [
    ("Silent Default Song (Total Silence)", "Silent Default Song.rbs"),
    ("ReBirth 1.0 Default Song", "ReBirth 1.0 Default Song.rbs"),
]

# Base64 encoded 32x32 studio synth icon
APP_ICON_BASE64 = (
    "R0lGODlhIAAgAPMAAMwAAAD/AP///0BAQIyMAMzMM8zM/93d3b29vdzc3LW1tbW1/8z//2Zm"
    "ZgAAAAAAAAAAACH5BAEAAAEALAAAAAAgACAAAASOMMiJqp134807/2AohkRZmlzpnmu6vnAs"
    "z3Rt33qu73zv/8CgcEgsGo/IpHLJbDqf0Kh0Sq1ar9is9osNj8lkbrmMXq/YrHaLXWq/4LB4"
    "SCyaz+ijup0+u+PxeUp7e3+AfYGGh26Ki4yNj4+RkJKSkpOWl5iZmpucnZ6foKGio6Slpqeo"
    "qaqrrK2ur7CxgREAOw=="
)

DEFAULT_SCREENSHOT = os.path.join(BASE_DIR, "Mods", "Screenshots", "default.png")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "Downloads")
REBIRTH_DOWNLOAD_PAGE = "https://archive.org/details/rebirthrb338forwin7810"
REBIRTH_EXTRACT_DIR = os.path.join(DOWNLOADS_DIR, "ReBirthPortable")

def normalize_portable_relative_path(relative_path):
    rel = (relative_path or "").strip().replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.strip("/")
    if not rel or rel.startswith("..") or "/.." in f"/{rel}/":
        return None
    return rel

def is_path_inside_base(path):
    if not path:
        return False
    try:
        base = os.path.abspath(BASE_DIR)
        target = os.path.abspath(path)
        return os.path.commonpath([base, target]) == base
    except ValueError:
        return False

def resolve_portable_path(relative_path, config=None):
    rel = normalize_portable_relative_path(relative_path)
    if not rel:
        return None
    resolved = os.path.abspath(os.path.join(BASE_DIR, rel))
    if not is_path_inside_base(resolved):
        return None
    return resolved

def ensure_config_directory(dir_key, rel_path, config=None):
    rel = normalize_portable_relative_path(rel_path)
    if not rel:
        return False, None, "Empty or invalid relative path"
    abs_path = resolve_portable_path(rel, config)
    if not abs_path:
        return False, None, "Path must stay inside the ReBirth ToolBox folder"
    try:
        os.makedirs(abs_path, exist_ok=True)
        return True, abs_path, ""
    except OSError as exc:
        return False, abs_path, str(exc)
    except Exception as exc:
        return False, abs_path, str(exc)

def ensure_all_config_directories(config):
    results = {}
    dirs = (config or {}).get("directories") or {}
    for dir_key, default_rel in DEFAULT_DIRECTORY_PATHS.items():
        rel = dirs.get(dir_key, default_rel)
        ok, path, err = ensure_config_directory(dir_key, rel, config)
        results[dir_key] = {
            "ok": ok,
            "path": path,
            "error": err,
            "rel": normalize_portable_relative_path(rel) or default_rel,
        }
    return results

def apply_config_paths(config):
    global DEFAULT_SONGS_DIR, DOWNLOADS_DIR, SONGS_DIR, DOCUMENTS_DIR, MODS_DIR, REBIRTH_EXTRACT_DIR
    results = ensure_all_config_directories(config)
    mapping = {
        "default_songs": "DEFAULT_SONGS_DIR",
        "downloads": "DOWNLOADS_DIR",
        "songs": "SONGS_DIR",
        "documents": "DOCUMENTS_DIR",
        "mods": "MODS_DIR",
    }
    for dir_key, global_name in mapping.items():
        info = results.get(dir_key) or {}
        if info.get("ok") and info.get("path"):
            globals()[global_name] = info["path"]
    downloads_path = results.get("downloads", {}).get("path") or DOWNLOADS_DIR
    REBIRTH_EXTRACT_DIR = os.path.join(downloads_path, "ReBirthPortable")
    return results

def get_download_catalog(config=None):
    catalog = {}
    saved = (config or {}).get("download_urls") or {}
    for key, defaults in DEFAULT_DOWNLOAD_CATALOG.items():
        merged = dict(defaults)
        merged.update(saved.get(key) or {})
        catalog[key] = merged
    return catalog

def get_download_file_info(config, file_key):
    return get_download_catalog(config).get(file_key) or {}

def get_rebirth_download_path(file_key, config=None):
    info = get_download_file_info(config or {}, file_key)
    filename = (info.get("filename") or "").strip()
    if not filename:
        return None
    downloads_dir = resolve_portable_path(
        ((config or {}).get("directories") or {}).get("downloads", DEFAULT_DIRECTORY_PATHS["downloads"]),
        config,
    ) or DOWNLOADS_DIR
    return os.path.join(downloads_dir, filename)

def scan_rebirth_download_status(config=None):
    config = config or {}
    iso_path = get_rebirth_download_path("iso", config)
    installer_path = get_rebirth_download_path("installer", config)
    return {
        "iso_ready": bool(iso_path and os.path.exists(iso_path)),
        "installer_ready": bool(installer_path and os.path.exists(installer_path)),
        "iso_path": iso_path if iso_path and os.path.exists(iso_path) else None,
        "installer_path": installer_path if installer_path and os.path.exists(installer_path) else None,
    }

def validate_https_download_url(url):
    value = (url or "").strip()
    if not value:
        return True, ""
    if not value.lower().startswith("https://"):
        return False, "URL must start with https://"
    return True, value

def find_rebirth_exe_in_dir(base_dir):
    if not base_dir or not os.path.isdir(base_dir):
        return None
    direct = os.path.join(base_dir, EXE_NAME)
    if os.path.exists(direct):
        return os.path.abspath(direct)
    for root, _, files in os.walk(base_dir):
        for filename in files:
            if filename.lower() == EXE_NAME.lower():
                return os.path.abspath(os.path.join(root, filename))
    return None

def find_seven_zip_executable():
    for candidate in (
        os.path.join(BASE_DIR, "7z.exe"),
        os.path.join(BASE_DIR, "7-Zip", "7z.exe"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    return None

def normalize_mod_name_key(name):
    return (name or "Standard ReBirth").strip().lower()

def resolve_config_directory(config, key, default_rel):
    rel = ((config or {}).get("directories") or {}).get(key, default_rel)
    if not rel:
        rel = default_rel
    if os.path.isabs(rel):
        return os.path.abspath(rel)
    return os.path.abspath(os.path.join(BASE_DIR, rel))

def get_toolbox_backup_sources(config=None):
    config = config or load_config()
    sources = []
    for key, default_rel in DEFAULT_DIRECTORY_PATHS.items():
        path = resolve_config_directory(config, key, default_rel)
        if os.path.isdir(path):
            sources.append(path)
    if os.path.isdir(PATTERN_BANKS_DIR):
        sources.append(os.path.abspath(PATTERN_BANKS_DIR))
    return sources

def create_toolbox_backup_7z(output_path, config=None):
    config = config or load_config()
    seven_zip = find_seven_zip_executable()
    if not seven_zip:
        return False, (
            "7-Zip (7z.exe) was not found.\n\n"
            "Install 7-Zip or copy 7z.exe into the ToolBox folder, then try again."
        )
    sources = get_toolbox_backup_sources(config)
    if not sources and not os.path.isfile(CONFIG_FILE):
        return False, "Nothing to back up — no configured folders found."

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = [seven_zip, "a", "-t7z", "-mx=5", "-y", output_path]
    for folder in sources:
        cmd.append(folder + ("" if folder.endswith(os.sep) else os.sep))
    if os.path.isfile(CONFIG_FILE):
        cmd.append(CONFIG_FILE)
    if os.path.isfile(os.path.join(BASE_DIR, "ReBirthToolBox.json")):
        cmd.append(os.path.join(BASE_DIR, "ReBirthToolBox.json"))
    for pattern in (
        r"*.previews\*",
        r"*.sample_cache*\*",
        r".toolbox_cache\*",
        r"*\__pycache__\*",
        r"*\LaunchCache\*",
    ):
        cmd.append(f"-xr!{pattern}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        creationflags=get_subprocess_creationflags(),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail or f"7-Zip failed with exit code {result.returncode}."
    if not os.path.isfile(output_path):
        return False, "7-Zip reported success but the archive file was not created."
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    return True, f"Backup saved ({size_mb:.1f} MB):\n{output_path}"

def scale_pcm_buffer(pcm_data, gain=1.0):
    if not pcm_data:
        return pcm_data
    if gain >= 0.999:
        return pcm_data
    if gain <= 0.0:
        return b"\x00" * len(pcm_data)
    out = bytearray()
    for index in range(0, len(pcm_data), 2):
        sample = struct.unpack("<h", pcm_data[index:index + 2])[0]
        scaled = int(max(-32767, min(32767, round(sample * gain))))
        out.extend(struct.pack("<h", scaled))
    return bytes(out)

def _promote_rebirth_tree_to_dir(rebirth_exe, dest_dir):
    """
    If 7-Zip unpacked ReBirth into a nested folder, lift that folder's contents
    into dest_dir so Rebirth.exe sits next to the ToolBox.
    """
    if not rebirth_exe or not os.path.isfile(rebirth_exe):
        return None
    dest_dir = os.path.abspath(dest_dir)
    exe_dir = os.path.abspath(os.path.dirname(rebirth_exe))
    if exe_dir == dest_dir:
        return os.path.abspath(rebirth_exe)

    for name in os.listdir(exe_dir):
        src = os.path.join(exe_dir, name)
        dst = os.path.join(dest_dir, name)
        if os.path.abspath(src) == os.path.abspath(dst):
            continue
        try:
            if os.path.exists(dst):
                if os.path.isdir(dst) and not os.path.islink(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                else:
                    os.remove(dst)
            shutil.move(src, dst)
        except Exception:
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            except Exception:
                pass

    try:
        if exe_dir.startswith(dest_dir) and exe_dir != dest_dir and not os.listdir(exe_dir):
            os.rmdir(exe_dir)
    except Exception:
        pass

    promoted = os.path.join(dest_dir, EXE_NAME)
    if os.path.isfile(promoted):
        return os.path.abspath(promoted)
    return find_rebirth_exe_in_dir(dest_dir)

def extract_rebirth_installer(installer_path, dest_dir):
    """
    Unpack the RB-338 installer EXE with 7-Zip into dest_dir.
    Does NOT run the installer — unzip only, into the ToolBox folder.
    """
    os.makedirs(dest_dir, exist_ok=True)
    seven_zip = find_seven_zip_executable()
    if not seven_zip:
        return False, None, (
            "7-Zip (7z.exe) was not found.\n\n"
            "Install 7-Zip from https://www.7-zip.org/ or copy 7z.exe into the ToolBox folder,\n"
            "then click Extract again. The installer EXE is only unpacked — never launched."
        )

    kwargs = {
        "args": [seven_zip, "x", installer_path, f"-o{dest_dir}", "-y", "-aoa"],
        "capture_output": True,
        "text": True,
    }
    creationflags = get_subprocess_creationflags()
    if creationflags:
        kwargs["creationflags"] = creationflags
    result = subprocess.run(**kwargs)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, None, detail or "7-Zip could not unpack the installer EXE."

    rebirth_exe = find_rebirth_exe_in_dir(dest_dir)
    if not rebirth_exe:
        return False, None, (
            "7-Zip finished, but Rebirth.exe was not found in the unpacked files.\n"
            f"Checked folder:\n{dest_dir}"
        )

    rebirth_exe = _promote_rebirth_tree_to_dir(rebirth_exe, dest_dir) or rebirth_exe
    if rebirth_exe and os.path.isfile(rebirth_exe):
        return True, rebirth_exe, "extracted_with_7zip"
    return False, None, "Unpack succeeded but Rebirth.exe could not be placed into the ToolBox folder."

LAUNCHER_MAIN_FILE = "ReBirthToolBox.py"
MOD_SCREENSHOTS_REL = os.path.join("Mods", "Screenshots")
SCREENSHOT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")

def deploy_launcher_to_directory(source_base, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    deployed = []

    launcher_src = os.path.join(source_base, LAUNCHER_MAIN_FILE)
    if os.path.isfile(launcher_src):
        shutil.copy2(launcher_src, os.path.join(target_dir, LAUNCHER_MAIN_FILE))
        deployed.append(LAUNCHER_MAIN_FILE)

    screenshots_src = os.path.join(source_base, MOD_SCREENSHOTS_REL)
    if os.path.isdir(screenshots_src):
        screenshots_dst = os.path.join(target_dir, MOD_SCREENSHOTS_REL)
        os.makedirs(screenshots_dst, exist_ok=True)
        image_count = 0
        for name in os.listdir(screenshots_src):
            src_file = os.path.join(screenshots_src, name)
            if os.path.isfile(src_file) and name.lower().endswith(SCREENSHOT_EXTENSIONS):
                shutil.copy2(src_file, os.path.join(screenshots_dst, name))
                image_count += 1
        if image_count:
            deployed.append(f"{MOD_SCREENSHOTS_REL}\\ ({image_count} images)")

    iso_path = get_rebirth_download_path("iso")
    if iso_path and os.path.exists(iso_path):
        iso_dst = os.path.join(target_dir, os.path.basename(iso_path))
        if os.path.abspath(iso_path) != os.path.abspath(iso_dst):
            shutil.copy2(iso_path, iso_dst)
            deployed.append(os.path.basename(iso_path))

    return deployed

def get_configured_install_dir(config=None):
    configured = ((config or {}).get("rebirth_install_dir") or "").strip()
    if configured and os.path.isdir(configured):
        return os.path.abspath(configured)
    return os.path.abspath(BASE_DIR)

def resolve_rebirth_install_root(config=None):
    install_dir = get_configured_install_dir(config)
    rebirth_exe = find_rebirth_exe_in_dir(install_dir)
    if rebirth_exe:
        return os.path.dirname(rebirth_exe), rebirth_exe
    if os.path.exists(EXE_PATH):
        return BASE_DIR, EXE_PATH
    return install_dir, None

def get_launcher_shortcut_target(launcher_py_path):
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    py_exe = get_gui_python_executable()
    if py_exe.lower().endswith("pythonw.exe"):
        return py_exe, f'"{launcher_py_path}"'
    return py_exe, f'"{launcher_py_path}"'

def create_windows_shortcut(shortcut_path, target_path, arguments="", working_dir="", description=""):
    def ps_escape(value):
        return value.replace("'", "''")

    ps = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{ps_escape(shortcut_path)}'); "
        f"$s.TargetPath = '{ps_escape(target_path)}'; "
        f"$s.Arguments = '{ps_escape(arguments)}'; "
        f"$s.WorkingDirectory = '{ps_escape(working_dir)}'; "
        f"$s.Description = '{ps_escape(description)}'; "
        f"$s.Save()"
    )
    result = run_powershell(ps, capture_output=True, text=True)
    return result.returncode == 0

def create_launcher_shortcuts(launcher_py_path, desktop=True, start_menu=True):
    created = []
    target_path, arguments = get_launcher_shortcut_target(launcher_py_path)
    working_dir = os.path.dirname(launcher_py_path)
    label = "ReBirth ToolBox"

    if desktop:
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.isdir(desktop_dir):
            shortcut_path = os.path.join(desktop_dir, f"{label}.lnk")
            if create_windows_shortcut(shortcut_path, target_path, arguments, working_dir, label):
                created.append(shortcut_path)

    if start_menu:
        programs_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
        if os.path.isdir(programs_dir):
            shortcut_path = os.path.join(programs_dir, f"{label}.lnk")
            if create_windows_shortcut(shortcut_path, target_path, arguments, working_dir, label):
                created.append(shortcut_path)

    return created

def format_bytes(num_bytes):
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num_bytes} B"

def download_file_with_progress(url, dest_path, progress_callback=None, timeout=600):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ReBirthStudioToolBox/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0) or 0)
        downloaded = 0
        chunk_size = 1024 * 256
        with open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)
    return dest_path

_sample_play_lock = threading.Lock()

def play_audio_file(wav_path):
    if not wav_path or not os.path.exists(wav_path):
        return False

    def worker():
        play_wav_sync(wav_path)

    threading.Thread(target=worker, daemon=True).start()
    return True

def normalize_pcm16le_bytes(pcm_le, target_peak=23000):
    """Scale PCM to a sane peak level (same idea as rb338packer audioManager gain)."""
    if not pcm_le or len(pcm_le) < 2:
        return pcm_le
    peak = 0
    for i in range(0, len(pcm_le), 2):
        sample = abs(struct.unpack("<h", pcm_le[i : i + 2])[0])
        if sample > peak:
            peak = sample
    if peak <= 0:
        return pcm_le
    if peak < 500:
        scale = min(target_peak / peak, 8.0)
    elif peak <= target_peak:
        return pcm_le
    else:
        scale = target_peak / peak
    out = bytearray()
    for i in range(0, len(pcm_le), 2):
        value = struct.unpack("<h", pcm_le[i : i + 2])[0]
        scaled = int(max(-32767, min(32767, round(value * scale))))
        out.extend(struct.pack("<h", scaled))
    return bytes(out)

def wav_path_to_playback_bytes(wav_path):
    """Read a mono 16-bit WAV and return normalized in-memory WAV bytes."""
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if not frames:
        raise ValueError("empty wav")
    if channels == 1 and sample_width == 2:
        pcm = frames
    elif channels == 2 and sample_width == 2:
        pcm = bytearray()
        for i in range(0, len(frames), 4):
            left = struct.unpack("<h", frames[i : i + 2])[0]
            right = struct.unpack("<h", frames[i + 2 : i + 4])[0]
            pcm.extend(struct.pack("<h", (left + right) // 2))
        pcm = bytes(pcm)
    else:
        raise ValueError(f"unsupported wav format: {channels}x{sample_width * 8}")
    pcm = normalize_pcm16le_bytes(pcm)
    return pcm16le_to_wav_bytes(pcm, sample_rate, channels=1)

def play_wav_sync(wav_path):
    if not wav_path or not os.path.exists(wav_path):
        return False
    if HAS_WINSOUND:
        try:
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            return True
        except Exception:
            pass
    try:
        ps_path = wav_path.replace("'", "''")
        run_powershell(f"(New-Object Media.SoundPlayer '{ps_path}').PlaySync()", capture_output=False, text=False)
        return True
    except Exception:
        return False

def stop_wav_playback():
    if HAS_WINSOUND:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
    try:
        run_powershell("try { (New-Object Media.SoundPlayer).Stop() } catch { }", capture_output=False, text=False)
    except Exception:
        pass

def sanitize_tk_text(value, limit=1200):
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r", " ").strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text

def make_tk_image_from_png(image_path, max_w, max_h):
    if not HAS_PIL or not image_path or not os.path.exists(image_path):
        return None
    try:
        mtime = int(os.path.getmtime(image_path))
    except OSError:
        mtime = 0
    cache_key = (os.path.normcase(os.path.abspath(image_path)), mtime, max_w, max_h)
    cached = _TK_IMAGE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        img = Image.open(image_path)
        ratio = min(max_w / img.size[0], max_h / img.size[1])
        new_size = (max(1, int(img.size[0] * ratio)), max(1, int(img.size[1] * ratio)))
        resample_filter = getattr(getattr(Image, "Resampling", Image), "BILINEAR", getattr(Image, "BILINEAR", 2))
        img = img.resize(new_size, resample_filter)
        photo = ImageTk.PhotoImage(img)
        if len(_TK_IMAGE_CACHE) > 512:
            _TK_IMAGE_CACHE.clear()
        _TK_IMAGE_CACHE[cache_key] = photo
        return photo
    except Exception:
        return None

def _hex_to_rgb(color):
    color = (color or "#242736").lstrip("#")
    if len(color) != 6:
        return (36, 39, 54)
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

def _blend_rgb(base, accent, ratio=0.18):
    return tuple(int(base[i] + (accent[i] - base[i]) * ratio) for i in range(3))

def _document_ext_color(ext):
    ext = (ext or "").lower()
    mapped = DOCUMENT_EXT_COLORS.get(ext)
    if isinstance(mapped, str) and mapped.startswith("."):
        mapped = DOCUMENT_EXT_COLORS.get(mapped, "#00E5FF")
    return mapped or "#00E5FF"

def _draw_document_card_shell(draw, max_w, max_h, accent="#00E5FF", header_label="DOC"):
    bg = "#181A24"
    body = "#242736"
    border = "#35384C"
    accent_rgb = _hex_to_rgb(accent)
    body_rgb = _hex_to_rgb(body)
    draw.rectangle((0, 0, max_w - 1, max_h - 1), fill=bg, outline=border, width=1)
    draw.rectangle((1, 1, max_w - 2, 18), fill=accent)
    draw.rectangle((1, 19, max_w - 2, max_h - 2), fill=body)
    font = ImageFont.load_default()
    label = (header_label or "DOC").strip(".").upper()[:10] or "DOC"
    draw.text((8, 4), label, fill="#FFFFFF", font=font)
    for y in range(24, max_h - 8, 5):
        shade = _blend_rgb(body_rgb, accent_rgb, 0.08 if (y // 5) % 2 else 0.03)
        draw.line((8, y, max_w - 8, y), fill=shade, width=1)

def make_extension_badge_photo(ext_label, max_w, max_h, bg="#242736", fg="#00E5FF"):
    if not HAS_PIL:
        return None
    try:
        ext = (ext_label or "?").strip().lower()
        accent = _document_ext_color(ext if ext.startswith(".") else f".{ext}")
        img = Image.new("RGB", (max_w, max_h), color=bg)
        draw = ImageDraw.Draw(img)
        _draw_document_card_shell(draw, max_w, max_h, accent=accent, header_label=document_type_label(ext_label))
        label = document_type_label(ext_label if (ext_label or "").startswith(".") else f".{ext_label or 'file'}")
        font = ImageFont.load_default()
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = draw.textsize(label, font=font)
        draw.text(((max_w - tw) / 2, 24 + (max_h - 24 - th) / 2), label, fill=fg, font=font)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

def make_document_image_preview(image_path, max_w, max_h, ext=""):
    if not HAS_PIL or not image_path or not os.path.exists(image_path):
        return None
    try:
        accent = _document_ext_color(ext)
        img = Image.new("RGB", (max_w, max_h), color="#181A24")
        draw = ImageDraw.Draw(img)
        _draw_document_card_shell(draw, max_w, max_h, accent=accent, header_label=ext or "IMG")
        inner_w = max_w - 16
        inner_h = max_h - 30
        source = Image.open(image_path)
        if source.mode not in ("RGB", "RGBA"):
            source = source.convert("RGBA")
        ratio = min(inner_w / source.size[0], inner_h / source.size[1])
        new_size = (max(1, int(source.size[0] * ratio)), max(1, int(source.size[1] * ratio)))
        resample_filter = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "LANCZOS", 1))
        thumb = source.resize(new_size, resample_filter)
        offset_x = 8 + (inner_w - new_size[0]) // 2
        offset_y = 22 + (inner_h - new_size[1]) // 2
        if thumb.mode == "RGBA":
            img.paste(thumb, (offset_x, offset_y), thumb)
        else:
            img.paste(thumb, (offset_x, offset_y))
        return ImageTk.PhotoImage(img)
    except Exception:
        return make_tk_image_from_png(image_path, max_w, max_h)

def strip_html_for_preview(text):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text or "")
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def document_type_label(ext):
    ext = (ext or "").lower()
    labels = {
        ".pdf": "PDF",
        ".html": "HTML",
        ".htm": "HTML",
        ".txt": "TEXT",
        ".md": "MARKDOWN",
        ".json": "JSON",
        ".csv": "CSV",
        ".xml": "XML",
        ".rtf": "RTF",
        ".png": "IMAGE",
        ".jpg": "IMAGE",
        ".jpeg": "IMAGE",
        ".gif": "IMAGE",
        ".bmp": "IMAGE",
        ".webp": "IMAGE",
    }
    return labels.get(ext, ext.strip(".").upper()[:8] or "FILE")

def _draw_text_lines_on_document_card(draw, max_w, max_h, lines, accent, ext_label, fg="#A0A5C0"):
    _draw_document_card_shell(draw, max_w, max_h, accent=accent, header_label=ext_label)
    font = ImageFont.load_default()
    y = 26
    for line in lines[:6]:
        draw.text((10, y), line, fill=fg, font=font)
        y += 12
        if y > max_h - 8:
            break

def make_html_preview_photo(file_path, max_w, max_h, bg="#242736", fg="#A0A5C0", ext=".html"):
    if not HAS_PIL or not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            snippet = strip_html_for_preview(handle.read(4000))
        if not snippet:
            snippet = "(empty HTML)"
        lines = []
        for raw_line in snippet.split(". "):
            line = raw_line.strip()
            if not line:
                continue
            while len(line) > 30:
                lines.append(line[:30])
                line = line[30:]
            if line:
                lines.append(line)
            if len(lines) >= 6:
                break
        if not lines:
            lines = ["(empty HTML)"]
        accent = _document_ext_color(ext)
        img = Image.new("RGB", (max_w, max_h), color=bg)
        draw = ImageDraw.Draw(img)
        _draw_text_lines_on_document_card(draw, max_w, max_h, lines, accent, document_type_label(ext))
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

def make_text_preview_photo(file_path, max_w, max_h, bg="#242736", fg="#A0A5C0", ext=""):
    if not HAS_PIL or not file_path or not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            snippet = handle.read(700)
        snippet = snippet.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not snippet:
            snippet = "(empty file)"
        lines = []
        for raw_line in snippet.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            while len(line) > 30:
                lines.append(line[:30])
                line = line[30:]
            if line:
                lines.append(line)
            if len(lines) >= 6:
                break
        if not lines:
            lines = ["(empty file)"]
        accent = _document_ext_color(ext or os.path.splitext(file_path)[1])
        img = Image.new("RGB", (max_w, max_h), color=bg)
        draw = ImageDraw.Draw(img)
        _draw_text_lines_on_document_card(
            draw,
            max_w,
            max_h,
            lines,
            accent,
            document_type_label(ext or os.path.splitext(file_path)[1]),
            fg=fg,
        )
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

def scan_documents_folder(documents_dir=None):
    root_dir = documents_dir or DOCUMENTS_DIR
    if not root_dir or not os.path.isdir(root_dir):
        return []
    files = []
    for current_root, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if filename.startswith("."):
                continue
            full_path = os.path.join(current_root, filename)
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
            files.append(
                {
                    "path": full_path,
                    "rel_path": rel_path,
                    "name": filename,
                    "ext": os.path.splitext(filename)[1].lower(),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )
    files.sort(key=lambda item: (-item["modified"], item["rel_path"].lower()))
    return files

def format_file_size(num_bytes):
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"

DEFAULT_CLEAN_RBS_B64 = "UklGRpAAAAAAV0FWRS" + "A" * 120 + "A=="

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_char * 32), ("dmSpecVersion", ctypes.c_ushort),
        ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort),
        ("dmDriverExtra", ctypes.c_ushort), ("dmFields", ctypes.c_ulong),
        ("dmOrientation", ctypes.c_short), ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short), ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short), ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short), ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTttOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_char * 32),
        ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong), ("dmPelsHeight", ctypes.c_ulong),
        ("dmDisplayFlags", ctypes.c_ulong), ("dmDisplayFrequency", ctypes.c_ulong),
    ]


RESOLUTIONS = [
    ("Current Resolution (Desktop / No Change)", None, None),
    ("640 x 480 (4:3 Retro VGA)", 640, 480),
    ("800 x 600 (4:3 Retro SVGA)", 800, 600),
    ("1024 x 768 (4:3 XGA)", 1024, 768),
    ("1152 x 864 (4:3 CRT Preferred)", 1152, 864),
    ("1280 x 720 (16:9 HD Ready)", 1280, 720),
    ("1280 x 960 (4:3 Retro Optimal)", 1280, 960),
    ("1280 x 1024 (5:4 SXGA)", 1280, 1024),
    ("1366 x 768 (16:9 WXGA)", 1366, 768),
    ("1440 x 900 (16:10 WXGA+)", 1440, 900),
    ("1600 x 900 (16:9 HD+)", 1600, 900),
    ("1600 x 1200 (4:3 UXGA)", 1600, 1200),
    ("1920 x 1080 (16:9 Full HD)", 1920, 1080),
    ("1920 x 1200 (16:10 WUXGA)", 1920, 1200),
    ("2560 x 1080 (21:9 UltraWide)", 2560, 1080),
    ("2560 x 1440 (16:9 QHD / 2K)", 2560, 1440),
    ("3440 x 1440 (21:9 UWQHD)", 3440, 1440),
    ("3840 x 2160 (16:9 4K Ultra HD)", 3840, 2160)
]

SCALES = {
    "Pentatonic Minor": [0, 3, 5, 7, 10],
    "Phrygian Acid": [0, 1, 3, 5, 7, 8, 10],
    "Blues Scale": [0, 3, 5, 6, 7, 10],
    "Japanese Insen": [0, 1, 5, 7, 10],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Minor Natural": [0, 2, 3, 5, 7, 8, 10],
    "Major Harmonic": [0, 2, 4, 5, 7, 8, 11],
    "Chromatic (All Notes)": list(range(12))
}

def load_config():
    if os.path.exists(LEGACY_CONFIG_FILE) and not os.path.exists(CONFIG_FILE):
        try:
            shutil.copy2(LEGACY_CONFIG_FILE, CONFIG_FILE)
        except Exception:
            pass

    defaults = {
        "favorites": [],
        "launch_resolution_index": 6,
        "rebirth_maximized": True,
        "rebirth_super_rack": False,
        "rebirth_super_rack_scale": 1.25,
        "rebirth_super_rack_display": "fit_height",
        "cpu_affinity": True,
        "theme": "midnight_studio",
        "themes": get_default_themes(),
        "rebirth_install_dir": BASE_DIR,
        "directories": dict(DEFAULT_DIRECTORY_PATHS),
        "download_urls": {
            key: {"url": "", "filename": info.get("filename", "")}
            for key, info in DEFAULT_DOWNLOAD_CATALOG.items()
        },
        "tutorial_completed_steps": [],
        "tutorial_last_step_id": "welcome",
        "mod_favorites": [],
        "mod_recent": [],
        "acid_mix_levels": {"303_1": 85, "303_2": 85, "drums": 90},
    }
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            pass

    for key, val in defaults.items():
        if key not in cfg:
            cfg[key] = val if not isinstance(val, dict) else dict(val)
    if not (cfg.get("rebirth_install_dir") or "").strip():
        cfg["rebirth_install_dir"] = BASE_DIR
    cfg.setdefault("directories", {})
    for dir_key, dir_val in DEFAULT_DIRECTORY_PATHS.items():
        cfg["directories"].setdefault(dir_key, dir_val)
    cfg.setdefault("download_urls", {})
    for dl_key, dl_info in DEFAULT_DOWNLOAD_CATALOG.items():
        cfg["download_urls"].setdefault(dl_key, {})
        cfg["download_urls"][dl_key].setdefault("url", "")
        cfg["download_urls"][dl_key].setdefault("filename", dl_info.get("filename", ""))

    # Drop removed audio/MIDI keys from older configs.
    for obsolete in ("audio_output", "midi_input", "disable_midi_input", "x64_package"):
        cfg.pop(obsolete, None)
    if "download_urls" in cfg:
        cfg["download_urls"].pop("x64_package", None)
    cfg.setdefault("cpu_affinity", True)
    merge_config_themes(cfg)
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_wchar * 32),
        ("dwSupport", ctypes.c_ulong),
    ]

class WAVEOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_wchar * 32),
        ("dwFormats", ctypes.c_ulong),
        ("wChannels", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("dwSupport", ctypes.c_ulong),
    ]

def detect_midi_input_devices():
    devices = ["None (disable MIDI input)"]
    try:
        winmm = ctypes.windll.winmm
        num_devs = winmm.midiInGetNumDevs()
        caps = MIDIINCAPSW()
        for i in range(num_devs):
            if winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                name = caps.szPname.strip()
                if name and name not in devices:
                    devices.append(name)
    except Exception:
        pass
    return devices

def detect_wave_out_devices():
    devices = []
    try:
        winmm = ctypes.windll.winmm
        num_devs = winmm.waveOutGetNumDevs()
        caps = WAVEOUTCAPSW()
        for i in range(num_devs):
            if winmm.waveOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                name = caps.szPname.strip()
                if name:
                    devices.append(name)
    except Exception:
        pass
    if not devices:
        devices = ["Primary Sound Driver"]
    return devices

def wave_out_index_for_name(device_name):
    devices = detect_wave_out_devices()
    target = (device_name or "").strip()
    if not target:
        return 0
    for i, name in enumerate(devices):
        if name == target:
            return i
    target_l = target.lower()
    for i, name in enumerate(devices):
        nl = name.lower()
        if target_l in nl or nl in target_l:
            return i
    return 0

REBIRTH_PRF_SIZE = 320
REBIRTH_PRF_DEVICE_INDEX_OFFSET = 24
REBIRTH_PRF_DEVICE_NAME_OFFSET = 53
REBIRTH_PRF_NAMES = ("ReBirth RB-338.prf", "ReBirth RB-338 2.prf")

def rebirth_prf_device_index(wave_out_index):
    """ReBirth stores waveOut selection as 1-based index in .prf (1 = first device)."""
    return int(wave_out_index) + 1

def create_rebirth_prf_blob(audio_device_index=0, audio_device_name="Primary Sound Driver"):
    body = bytearray(REBIRTH_PRF_SIZE)
    body[0:4] = b"PREF"
    struct.pack_into("<I", body, 4, 0)
    body[8:13] = b".prf\x00"
    body[13:24] = b"ReBirth Pre"
    for i in range(1, 7):
        struct.pack_into("<I", body, REBIRTH_PRF_DEVICE_INDEX_OFFSET + i * 4, 1)
    struct.pack_into("<I", body, REBIRTH_PRF_DEVICE_INDEX_OFFSET, rebirth_prf_device_index(audio_device_index))
    name_bytes = (audio_device_name or "Primary Sound Driver").encode("latin-1", errors="ignore")
    name_room = REBIRTH_PRF_SIZE - REBIRTH_PRF_DEVICE_NAME_OFFSET
    encoded = name_bytes[: name_room - 1] + b"\x00"
    body[REBIRTH_PRF_DEVICE_NAME_OFFSET:REBIRTH_PRF_DEVICE_NAME_OFFSET + len(encoded)] = encoded
    return bytes(body)

def patch_rebirth_prf_audio(data, audio_device_index, audio_device_name):
    if not data or len(data) < REBIRTH_PRF_DEVICE_NAME_OFFSET:
        return create_rebirth_prf_blob(audio_device_index, audio_device_name)
    patched = bytearray(data[:REBIRTH_PRF_SIZE].ljust(REBIRTH_PRF_SIZE, b"\x00"))
    if patched[0:4] != b"PREF":
        return create_rebirth_prf_blob(audio_device_index, audio_device_name)
    struct.pack_into("<I", patched, REBIRTH_PRF_DEVICE_INDEX_OFFSET, rebirth_prf_device_index(audio_device_index))
    name_bytes = (audio_device_name or "").encode("latin-1", errors="ignore")
    name_room = REBIRTH_PRF_SIZE - REBIRTH_PRF_DEVICE_NAME_OFFSET
    patched[REBIRTH_PRF_DEVICE_NAME_OFFSET:REBIRTH_PRF_SIZE] = b"\x00" * name_room
    encoded = name_bytes[: name_room - 1] + b"\x00"
    patched[REBIRTH_PRF_DEVICE_NAME_OFFSET:REBIRTH_PRF_DEVICE_NAME_OFFSET + len(encoded)] = encoded
    return bytes(patched)

def apply_rebirth_audio_preferences(config=None):
    config = config or {}
    audio_name = (config.get("audio_output") or "").strip()
    if not audio_name:
        return False
    device_index = wave_out_index_for_name(audio_name)
    applied = False
    for prf_name in REBIRTH_PRF_NAMES:
        prf_path = os.path.join(BASE_DIR, prf_name)
        try:
            if os.path.exists(prf_path):
                with open(prf_path, "rb") as f:
                    existing = f.read()
                payload = patch_rebirth_prf_audio(existing, device_index, audio_name)
            else:
                payload = create_rebirth_prf_blob(device_index, audio_name)
            with open(prf_path, "wb") as f:
                f.write(payload)
            applied = True
        except Exception:
            pass
    return applied

def ensure_rebirth_preferences(config=None):
    return

def is_303_step_active(note_val, flags):
    if flags == 0x10 and note_val == 0:
        return False
    if flags & 0x10 and note_val > 0:
        return True
    if (flags & 0x10) == 0 and (note_val > 0 or (flags & 0x0F)):
        return True
    return False

def set_window_icon(window):
    try:
        icon_img = tk.PhotoImage(data=APP_ICON_BASE64)
        window.iconphoto(True, icon_img)
        window._app_icon_ref = icon_img
    except Exception:
        pass

def change_resolution(width, height):
    try:
        user32 = ctypes.windll.user32
        devmode = DEVMODE()
        devmode.dmSize = ctypes.sizeof(DEVMODE)
        devmode.dmFields = 0x00080000 | 0x00100000
        devmode.dmPelsWidth = int(width)
        devmode.dmPelsHeight = int(height)
        return user32.ChangeDisplaySettingsA(ctypes.byref(devmode), 4) == 0
    except Exception:
        return False

def restore_resolution():
    try:
        ctypes.windll.user32.ChangeDisplaySettingsA(None, 0)
    except Exception:
        pass

def enum_display_modes():
    """Unique (width, height, refresh) modes the adapter reports."""
    user32 = ctypes.windll.user32
    modes = []
    seen = set()
    i = 0
    while True:
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        ok = user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm))
        if not ok:
            break
        w, h = int(dm.dmPelsWidth), int(dm.dmPelsHeight)
        hz = int(dm.dmDisplayFrequency or 0)
        key = (w, h)
        if w >= 640 and h >= 400 and key not in seen:
            seen.add(key)
            modes.append((w, h, hz))
        i += 1
        if i > 512:
            break
    return modes

def pick_super_rack_resolution(need_w, need_h):
    """
    Pick a sharp display mode so the rack fills nearly top→bottom,
    with leftover width as left/right bezel. No digital magnifier.
    """
    need_w = int(need_w or SUPER_RACK_CLIENT_W)
    need_h = int(need_h or SUPER_RACK_CLIENT_H)
    # Allow a few pixels of slack either side of perfect height match.
    modes = enum_display_modes()
    if not modes:
        # Fallback candidates commonly available on Win10/11
        modes = [(800, 600, 60), (1024, 768, 60), (1280, 720, 60), (1280, 1024, 60)]

    scored = []
    for w, h, hz in modes:
        if w < need_w - 8:
            continue
        # Prefer height within ±16 of the window; still accept nearest.
        dh = abs(h - need_h)
        # Side bezel bonus: wider is better (but not huge empty letterbox height)
        side = max(0, w - need_w)
        # Penalize modes much taller than the rack (big empty top/bottom)
        tall_pen = max(0, h - need_h - 16) * 40
        short_pen = max(0, need_h - h) * 200  # never crop the rack hard
        score = dh * 100 + tall_pen + short_pen - min(side, 800) * 0.5 - (hz or 0) * 0.01
        scored.append((score, w, h, hz))

    if not scored:
        # Last resort: any mode with height closest to need_h
        for w, h, hz in modes:
            scored.append((abs(h - need_h) * 100, w, h, hz))

    scored.sort(key=lambda t: t[0])
    _score, w, h, _hz = scored[0]
    return int(w), int(h)

def estimate_super_rack_outer_size():
    return compute_super_rack_outer_size(
        None,
        preferred_client=(SUPER_RACK_CLIENT_W, SUPER_RACK_CLIENT_H),
        has_menu=True,
    )

def apply_super_rack_fit_resolution():
    """Change display so rack height fills the screen; returns (ok, w, h)."""
    ow, oh = estimate_super_rack_outer_size()
    tw, th = pick_super_rack_resolution(ow, oh)
    sw, sh = get_primary_screen_size()
    if sw == tw and sh == th:
        return True, tw, th
    if change_resolution(tw, th):
        time.sleep(0.35)
        return True, tw, th
    return False, sw, sh

def minimize_other_windows(exclude_hwnds=None):
    """Minimize every other top-level app window before Super Rack."""
    user32 = ctypes.windll.user32
    SW_MINIMIZE = 6
    GW_OWNER = 4
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    exclude = {int(h) for h in (exclude_hwnds or []) if h}
    skip_classes = {
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Progman",
        "WorkerW",
        "DV2ControlHost",
        "NotifyIconOverflowWindow",
        "Windows.UI.Core.CoreWindow",
        "ForegroundStaging",
    }

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        try:
            hwnd_i = int(hwnd)
            if hwnd_i in exclude:
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.IsIconic(hwnd):
                return True
            if user32.GetWindow(hwnd, GW_OWNER):
                return True
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, buf, 64)
            if buf.value in skip_classes:
                return True
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex & WS_EX_TOOLWINDOW and not (ex & WS_EX_APPWINDOW):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(enum_proc, 0)
    except Exception:
        pass

def _find_taskbar_hwnds():
    """Primary + secondary taskbars (Win10/11 multi-monitor)."""
    user32 = ctypes.windll.user32
    found = []
    primary = user32.FindWindowW("Shell_TrayWnd", None)
    if primary:
        found.append(int(primary))

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        if buf.value in ("Shell_SecondaryTrayWnd", "Shell_TrayWnd"):
            h = int(hwnd)
            if h not in found:
                found.append(h)
        return True

    try:
        user32.EnumWindows(enum_proc, 0)
    except Exception:
        pass
    return found

def hide_taskbar_for_super_rack():
    """Hide the Windows taskbar for a full emulator-style Super Rack view."""
    global _SUPER_RACK_TASKBAR_HIDDEN, _SUPER_RACK_TASKBAR_HWNDS
    if _SUPER_RACK_TASKBAR_HIDDEN:
        return True
    user32 = ctypes.windll.user32
    SW_HIDE = 0
    hwnds = _find_taskbar_hwnds()
    hidden = []
    for hwnd in hwnds:
        try:
            if user32.IsWindow(hwnd):
                user32.ShowWindow(hwnd, SW_HIDE)
                hidden.append(hwnd)
        except Exception:
            pass
    _SUPER_RACK_TASKBAR_HWNDS = hidden or hwnds
    _SUPER_RACK_TASKBAR_HIDDEN = bool(_SUPER_RACK_TASKBAR_HWNDS)
    return _SUPER_RACK_TASKBAR_HIDDEN

def show_taskbar_after_super_rack():
    """Restore the taskbar after Super Rack ends."""
    global _SUPER_RACK_TASKBAR_HIDDEN, _SUPER_RACK_TASKBAR_HWNDS
    if not _SUPER_RACK_TASKBAR_HIDDEN and not _SUPER_RACK_TASKBAR_HWNDS:
        # Still try to show primary tray in case a previous run crashed mid-session.
        pass
    user32 = ctypes.windll.user32
    SW_SHOW = 5
    hwnds = list(_SUPER_RACK_TASKBAR_HWNDS) or _find_taskbar_hwnds()
    for hwnd in hwnds:
        try:
            if user32.IsWindow(hwnd):
                user32.ShowWindow(hwnd, SW_SHOW)
                user32.UpdateWindow(hwnd)
        except Exception:
            pass
    try:
        tray = user32.FindWindowW("Shell_TrayWnd", None)
        if tray:
            user32.ShowWindow(tray, SW_SHOW)
            user32.UpdateWindow(tray)
    except Exception:
        pass
    _SUPER_RACK_TASKBAR_HWNDS = []
    _SUPER_RACK_TASKBAR_HIDDEN = False

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def hide_console_window():
    try:
        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if console_hwnd:
            ctypes.windll.user32.ShowWindow(console_hwnd, 0)
    except Exception:
        pass
    minimize_powershell_windows()

def get_subprocess_creationflags():
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags |= subprocess.CREATE_NO_WINDOW
    return flags or None

def minimize_powershell_windows():
    try:
        user32 = ctypes.windll.user32
        markers = (
            "windows powershell",
            "powershell",
            "administrator: windows powershell",
            "administrator: powershell",
        )

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd) + 1
            buf = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buf, length)
            title_l = buf.value.lower()
            if any(marker in title_l for marker in markers):
                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            return True

        user32.EnumWindows(enum_proc, 0)
    except Exception:
        pass

def run_powershell(command, capture_output=True, text=True, timeout=None):
    kwargs = {
        "args": ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
        "capture_output": capture_output,
    }
    if text:
        kwargs["text"] = True
    creationflags = get_subprocess_creationflags()
    if creationflags:
        kwargs["creationflags"] = creationflags
    try:
        return subprocess.run(**kwargs, timeout=timeout)
    finally:
        minimize_powershell_windows()

def get_gui_python_executable():
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        pyw_exe = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw_exe):
            return pyw_exe
    return exe

def ensure_admin_elevation():
    if not is_admin():
        try:
            if getattr(sys, 'frozen', False):
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, None, None, 1)
            else:
                python_exe = get_gui_python_executable()
                script_path = f'"{os.path.abspath(__file__)}"'
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", python_exe, script_path, None, 0)
            if int(ret) > 32:
                sys.exit(0)
        except Exception:
            pass

def get_short_path_name(long_name):
    if not long_name or not os.path.exists(long_name):
        return long_name
    try:
        buffer_size = ctypes.windll.kernel32.GetShortPathNameW(long_name, None, 0)
        if buffer_size == 0:
            return long_name
        buffer = ctypes.create_unicode_buffer(buffer_size)
        if ctypes.windll.kernel32.GetShortPathNameW(long_name, buffer, buffer_size) > 0:
            return buffer.value
    except Exception:
        pass
    return long_name

def format_display_mode(mode):
    if not mode or mode == "Unknown Mode":
        return "Pattern Mode"
    return mode

LEGACY_RB_SYSEX_ID = bytes([0x92, 0x30])
LEGACY_GLOBAL_STATE_TRACK = 1
LEGACY_STATE_BLOB_SIZE = 9304
LEGACY_STATE_HEADER_SIZE = 256
LEGACY_303_CHUNK_SIZE = 1097
LEGACY_808_CHUNK_SIZE = 6238
LEGACY_909_CHUNK_SIZE = 6239
TB303_NOTES_MAP = ["C ", "C#", "D ", "D#", "E ", "F ", "F#", "G ", "G#", "A ", "A#", "B ", "C5"]

def detect_rbs_format(content):
    if not content or len(content) < 4:
        return "unknown"
    if content[:4] == b"MThd":
        return "legacy_midi"
    glob_idx = content.find(b"GLOB")
    if glob_idx != -1 and len(content) >= glob_idx + 8 + 512:
        glob_size = struct.unpack(">I", content[glob_idx + 4 : glob_idx + 8])[0]
        if glob_size == 512:
            return "iff42"
    if content[:4] == b"FORM" or b"CAT " in content[:512] or b"RB40" in content[:512]:
        return "iff42"
    return "unknown"

def read_midi_var_len(data, offset):
    val = 0
    start = offset
    while offset < len(data):
        b = data[offset]
        offset += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return val, offset - start

def extract_legacy_rebirth_sysex(content):
    if content[:4] != b"MThd" or len(content) < 14:
        return None
    pos = 14
    try:
        _, ntrks, _ = struct.unpack(">HHH", content[8:14])
    except struct.error:
        return None
    for _ in range(ntrks):
        if pos + 8 > len(content) or content[pos : pos + 4] != b"MTrk":
            break
        sz = struct.unpack(">I", content[pos + 4 : pos + 8])[0]
        trk = content[pos + 8 : pos + 8 + sz]
        pos += 8 + sz
        i = 0
        while i < len(trk):
            b0 = trk[i]
            if b0 == 0xF0:
                ln = trk[i + 1]
                pl = trk[i + 2 : i + 2 + ln]
                if len(pl) >= 2 and pl[:2] == LEGACY_RB_SYSEX_ID:
                    return pl
                i += 2 + ln
            elif b0 == 0xFF:
                ln = trk[i + 2]
                i += 3 + ln
            elif b0 & 0x80:
                i += 2 if (b0 & 0xF0) in (0xC0, 0xD0) else 3
            else:
                i += 1
    return None

def legacy_total_bars_from_sysex(syx):
    if not syx or len(syx) <= 32:
        return 0
    return syx[28] + (syx[32] << 4)

def legacy_loop_end_from_sysex(syx):
    if not syx or len(syx) <= 28:
        return 0
    return syx[28]

def parse_legacy_midi_tracks(content):
    if content[:4] != b"MThd" or len(content) < 14:
        return []
    _, ntrks, division = struct.unpack(">HHH", content[8:14])
    track_labels = ["Header/Meta", "Global State", "Mixer/FX", "303 #1 Sequence", "303 #2 Sequence", "Drum Sequence"]
    pos = 14
    tracks = []
    for idx in range(ntrks):
        if pos + 8 > len(content) or content[pos : pos + 4] != b"MTrk":
            break
        size = struct.unpack(">I", content[pos + 4 : pos + 8])[0]
        label = track_labels[idx] if idx < len(track_labels) else f"Track {idx + 1}"
        tracks.append(
            {
                "index": idx,
                "label": label,
                "data": content[pos + 8 : pos + 8 + size],
                "size": size,
                "division": division,
            }
        )
        pos += 8 + size
    return tracks

def parse_legacy_running_events(track_data):
    events = []
    i = 0
    tick = 0
    while i < len(track_data):
        delta, consumed = read_midi_var_len(track_data, i)
        tick += delta
        i += consumed
        if i >= len(track_data):
            break
        b0 = track_data[i]
        if b0 == 0xFF:
            meta_type = track_data[i + 1]
            ln = track_data[i + 2]
            payload = track_data[i + 3 : i + 3 + ln]
            events.append({"tick": tick, "type": "meta", "meta": meta_type, "data": payload})
            i += 3 + ln
        elif b0 in (0xF0, 0xF7):
            ln = track_data[i + 1]
            payload = track_data[i + 2 : i + 2 + ln]
            events.append({"tick": tick, "type": "sysex", "data": payload})
            i += 2 + ln
        elif b0 & 0x80:
            cmd = b0 & 0xF0
            if cmd in (0xC0, 0xD0):
                events.append({"tick": tick, "type": "midi", "status": b0, "data": track_data[i + 1 : i + 2]})
                i += 2
            else:
                events.append({"tick": tick, "type": "midi", "status": b0, "data": track_data[i + 1 : i + 3]})
                i += 3
        else:
            events.append({"tick": tick, "type": "run", "value": b0})
            i += 1
    return events

def extract_legacy_midi_track_blob(track_data):
    """Legacy v3.x stores a fixed binary device block as running-status bytes in a MIDI track."""
    blob = bytearray()
    i = 0
    while i < len(track_data):
        _, consumed = read_midi_var_len(track_data, i)
        i += consumed
        if i >= len(track_data):
            break
        b0 = track_data[i]
        if b0 == 0xF0:
            ln = track_data[i + 1]
            i += 2 + ln
        elif b0 == 0xFF:
            i += 3 + track_data[i + 2]
        elif b0 & 0x80:
            i += 2 if (b0 & 0xF0) in (0xC0, 0xD0) else 3
        else:
            blob.append(b0)
            i += 1
    return bytes(blob)

def parse_303_patterns_from_chunk_data(chunk_data, notes_map=None):
    notes_map = notes_map or TB303_NOTES_MAP
    patterns = []
    if not chunk_data or len(chunk_data) < 9 + 34:
        return patterns
    for p in range(32):
        bank_char = chr(65 + (p // 8))
        pat_num = (p % 8) + 1
        pat_name = f"{bank_char}{pat_num}"
        pat_bytes = chunk_data[9 + p * 34 : 9 + (p + 1) * 34]
        steps_data = []
        has_notes = False
        for s in range(16):
            note_val = pat_bytes[2 + s * 2]
            flags = pat_bytes[2 + s * 2 + 1]
            note_str = notes_map[note_val] if note_val < len(notes_map) else "? "
            slide = "S" if (flags & 0x01) else "-"
            accent = "A" if (flags & 0x02) else "-"
            up = "^" if (flags & 0x04) else ("v" if (flags & 0x08) else "-")
            active = is_303_step_active(note_val, flags)
            if active:
                has_notes = True
                steps_data.append({"note": note_str.strip(), "up": up, "accent": accent, "slide": slide, "active": True})
            else:
                steps_data.append({"note": "--", "up": "-", "accent": "-", "slide": "-", "active": False})
        if has_notes:
            patterns.append({"name": pat_name, "steps": steps_data})
    return patterns

def parse_drum_patterns_from_chunk_data(chunk_data, is_909=False):
    patterns = []
    chunk_size = LEGACY_909_CHUNK_SIZE if is_909 else LEGACY_808_CHUNK_SIZE
    if not chunk_data or len(chunk_data) < chunk_size:
        return patterns
    inst_labels = INST_LABELS_909 if is_909 else INST_LABELS_808
    drum_offset = get_drum_pattern_data_offset(is_909)
    for p in range(32):
        bank_char = chr(65 + (p // 8))
        pat_num = (p % 8) + 1
        pat_name = f"{bank_char}{pat_num}"
        pat_bytes = chunk_data[drum_offset + p * 194 : drum_offset + (p + 1) * 194]
        matrix = {lbl: [] for lbl in inst_labels}
        has_hits = False
        for s in range(16):
            step_offset = 2 + s * 12
            for inst_i, lbl in enumerate(inst_labels):
                val = pat_bytes[step_offset + inst_i] if (step_offset + inst_i) < len(pat_bytes) else 0
                if val > 0:
                    has_hits = True
                    matrix[lbl].append("x")
                else:
                    matrix[lbl].append(".")
        if has_hits:
            patterns.append({"name": pat_name, "matrix": matrix})
    return patterns

def parse_legacy_device_state_blob(blob):
    """Legacy v3.x global state: 256 B header + TB-303 + TB-303 + TR-808 (no TR-909 bank)."""
    header = LEGACY_STATE_HEADER_SIZE
    need = header + (2 * LEGACY_303_CHUNK_SIZE) + LEGACY_808_CHUNK_SIZE
    if not blob or len(blob) < need:
        return {"303_1": [], "303_2": [], "808": [], "909": []}
    offset = header
    chunk_303_1 = blob[offset : offset + LEGACY_303_CHUNK_SIZE]
    offset += LEGACY_303_CHUNK_SIZE
    chunk_303_2 = blob[offset : offset + LEGACY_303_CHUNK_SIZE]
    offset += LEGACY_303_CHUNK_SIZE
    chunk_808 = blob[offset : offset + LEGACY_808_CHUNK_SIZE]
    return {
        "303_1": parse_303_patterns_from_chunk_data(chunk_303_1),
        "303_2": parse_303_patterns_from_chunk_data(chunk_303_2),
        "808": parse_drum_patterns_from_chunk_data(chunk_808, is_909=False),
        "909": [],
    }

def deconstruct_legacy_rbs_song(rbs_path, content):
    result = {
        "303_1": [],
        "303_2": [],
        "808": [],
        "909": [],
        "legacy": True,
        "legacy_info": {},
        "legacy_tracks": [],
        "legacy_arrangement": [],
    }
    meta = parse_legacy_midi_rbs_metadata(rbs_path, content)
    syx = extract_legacy_rebirth_sysex(content)
    total_bars = legacy_total_bars_from_sysex(syx)
    result["legacy_info"] = {
        "meta": meta,
        "total_bars": total_bars,
        "loop_end_bar": legacy_loop_end_from_sysex(syx),
        "extension_bars": (syx[32] << 4) if syx and len(syx) > 32 else 0,
        "sysex_id": syx[14:18].decode("latin-1", errors="ignore") if syx and len(syx) >= 18 else "",
        "has_tr909": False,
        "pattern_source": "",
    }
    tracks = parse_legacy_midi_tracks(content)
    max_end = 0
    for tr in tracks:
        events = parse_legacy_running_events(tr["data"])
        end_tick = max((ev["tick"] for ev in events), default=0)
        max_end = max(max_end, end_tick)
        result["legacy_tracks"].append(
            {
                "index": tr["index"],
                "label": tr["label"],
                "size": tr["size"],
                "event_count": len(events),
                "end_tick": end_tick,
            }
        )
    if len(tracks) > 3:
        result["legacy_arrangement"] = parse_legacy_running_events(tracks[3]["data"])
    if len(tracks) > LEGACY_GLOBAL_STATE_TRACK:
        state_blob = extract_legacy_midi_track_blob(tracks[LEGACY_GLOBAL_STATE_TRACK]["data"])
        result["legacy_info"]["state_blob_size"] = len(state_blob)
        if len(state_blob) >= LEGACY_STATE_BLOB_SIZE:
            parsed = parse_legacy_device_state_blob(state_blob)
            result["303_1"] = parsed["303_1"]
            result["303_2"] = parsed["303_2"]
            result["808"] = parsed["808"]
            result["909"] = parsed["909"]
            result["legacy_info"]["pattern_source"] = "midi_global_state_blob"
            active = len(result["303_1"]) + len(result["303_2"]) + len(result["808"])
            result["legacy_info"]["active_patterns"] = active
            meta["active_patterns"] = active
            meta["pattern_breakdown"] = (
                f"Legacy v3.x | 303 #1: {len(result['303_1'])} | "
                f"303 #2: {len(result['303_2'])} | 808: {len(result['808'])} | 909: 0"
            )
    result["legacy_info"]["max_tick"] = max_end
    result["legacy_info"]["ticks_per_bar"] = round(max_end / total_bars, 2) if total_bars > 0 and max_end > 0 else 0
    return result

def parse_legacy_midi_rbs_metadata(rbs_path, content):
    info = {
        "bpm": None,
        "mode": "Unknown Mode",
        "title": os.path.splitext(os.path.basename(rbs_path))[0],
        "comments": "Legacy ReBirth song (MIDI-based .RBS format, v3.x).",
        "mod_name": "Standard ReBirth",
        "sound_engine": "ReBirth v3.x (Legacy MIDI)",
        "active_patterns": 0,
        "pattern_breakdown": "Legacy v3.x format",
        "web": "",
        "loop_start": 1,
        "loop_end": 0,
        "total_bars": 0,
        "duration_str": "N/A",
        "format": "legacy_midi",
        "format_version": "3.x",
    }
    try:
        pos = 14
        if len(content) >= pos + 8 and content[pos : pos + 4] == b"MTrk":
            sz = struct.unpack(">I", content[pos + 4 : pos + 8])[0]
            trk0 = content[pos + 8 : pos + 8 + sz]
            i = 0
            while i < len(trk0):
                delta, consumed = read_midi_var_len(trk0, i)
                i += consumed
                if i >= len(trk0):
                    break
                if trk0[i] == 0xFF:
                    meta_type = trk0[i + 1]
                    ln = trk0[i + 2]
                    payload = trk0[i + 3 : i + 3 + ln]
                    if meta_type == 0x51 and ln == 3:
                        us_per_beat = struct.unpack(">I", bytes([0]) + payload)[0]
                        if us_per_beat > 0:
                            info["bpm"] = round(60000000.0 / us_per_beat, 1)
                    elif meta_type == 0x02 and payload:
                        version_text = payload.decode("latin-1", errors="ignore").strip()
                        if "3.1" in version_text:
                            info["format_version"] = "3.1"
                        if version_text:
                            info["comments"] = version_text
                    i += 3 + ln
                elif trk0[i] == 0xF0:
                    ln = trk0[i + 1]
                    i += 2 + ln
                elif trk0[i] & 0x80:
                    i += 2 if (trk0[i] & 0xF0) in (0xC0, 0xD0) else 3
                else:
                    i += 1

        syx = extract_legacy_rebirth_sysex(content)
        if syx and len(syx) > 32:
            loop_end = legacy_loop_end_from_sysex(syx)
            total_bars = legacy_total_bars_from_sysex(syx)
            extension_bars = syx[32] << 4
            info["loop_end"] = total_bars
            info["total_bars"] = total_bars
            info["pattern_breakdown"] = (
                f"Legacy v3.x | loop {loop_end} + ext {extension_bars} = {total_bars} bars"
                if extension_bars
                else f"Legacy v3.x | {total_bars} bars"
            )
            if total_bars <= 1:
                info["mode"] = "Pattern Mode"
                info["duration_str"] = "Looping Pattern"
            else:
                info["mode"] = "Song Mode"
                if info["bpm"] and info["bpm"] > 0:
                    total_sec = total_bars * (240.0 / info["bpm"])
                    mins = int(total_sec // 60)
                    secs = int(total_sec % 60)
                    info["duration_str"] = f"~{mins:02d}:{secs:02d} ({total_bars} Bars)"
                else:
                    info["duration_str"] = f"{total_bars} Bars"
        elif info["bpm"]:
            info["mode"] = "Pattern Mode"
            info["duration_str"] = "Looping Pattern"
    except Exception:
        pass
    return info

def parse_iff42_rbs_metadata(rbs_path, content, include_patterns=True):
    info = {
        "bpm": None,
        "mode": "Unknown Mode",
        "title": "Untitled Song",
        "comments": "No description available.",
        "mod_name": "Standard ReBirth",
        "sound_engine": "ReBirth 2.0 Sound",
        "active_patterns": 0,
        "pattern_breakdown": "303 #1: 0 | 303 #2: 0 | 808: 0 | 909: 0",
        "web": "",
        "loop_start": 1,
        "loop_end": 0,
        "total_bars": 0,
        "duration_str": "N/A",
        "format": "iff42",
        "format_version": "4.2",
    }

    glob_idx = find_rbs_chunk(content, b"GLOB")
    if glob_idx != -1 and len(content) >= glob_idx + 8 + 512:
        glob_data = content[glob_idx + 8 : glob_idx + 8 + 512]
        mode_byte = glob_data[0]
        info["mode"] = "Song Mode" if mode_byte == 1 else "Pattern Mode"

        tempo_raw = struct.unpack(">I", glob_data[2:6])[0]
        if tempo_raw > 0:
            info["bpm"] = round(tempo_raw / 1000.0, 1) if tempo_raw >= 1000 else float(tempo_raw)

        l_start_raw = struct.unpack(">I", glob_data[6:10])[0]
        l_end_raw = struct.unpack(">I", glob_data[10:14])[0]
        info["loop_start"] = max(1, (l_start_raw // 768) + 1)
        info["loop_end"] = l_end_raw // 768

        mod_raw = glob_data[15:80].split(b"\x00")[0]
        mod_str = mod_raw.decode("latin-1", errors="ignore").strip()
        if mod_str:
            info["mod_name"] = mod_str

        if len(glob_data) > 482:
            v_mode = glob_data[482]
            info["sound_engine"] = "Vintage 1.5 Sound" if v_mode == 1 else "ReBirth 2.0 Sound"

    usri_idx = find_rbs_chunk(content, b"USRI")
    if usri_idx != -1 and len(content) >= usri_idx + 8 + 512:
        usri_data = content[usri_idx + 8 : usri_idx + 8 + 512]
        title_raw = usri_data[0:41].split(b"\x00")[0]
        title_str = title_raw.decode("latin-1", errors="ignore").strip()
        if title_str:
            info["title"] = title_str

        comm_raw = usri_data[41:242].split(b"\x00")[0]
        comm_str = comm_raw.decode("latin-1", errors="ignore").replace("\r", "\n").strip()
        if comm_str:
            info["comments"] = comm_str

    if include_patterns:
        deconstructed = deconstruct_rbs_song(rbs_path)
        c_303_1 = len(deconstructed.get("303_1", []))
        c_303_2 = len(deconstructed.get("303_2", []))
        c_808 = len(deconstructed.get("808", []))
        c_909 = len(deconstructed.get("909", []))
        total_active = c_303_1 + c_303_2 + c_808 + c_909
        info["active_patterns"] = total_active
        info["pattern_breakdown"] = f"303 #1: {c_303_1} | 303 #2: {c_303_2} | 808: {c_808} | 909: {c_909}"
    else:
        info["active_patterns"] = 0
        info["pattern_breakdown"] = "—"

    max_trak_ticks = 0
    trak_pos = 0
    while True:
        t_idx = content.find(b"TRAK", trak_pos)
        if t_idx == -1:
            break
        trak_pos = t_idx + 4
        if len(content) >= t_idx + 12:
            try:
                num_events = struct.unpack(">I", content[t_idx + 4 : t_idx + 8])[0]
                ev_offset = t_idx + 8
                accum = 0
                for _ in range(min(num_events, 3000)):
                    if ev_offset >= len(content):
                        break
                    val = 0
                    while ev_offset < len(content):
                        b = content[ev_offset]
                        ev_offset += 1
                        val = (val << 7) | (b & 0x7F)
                        if not (b & 0x80):
                            break
                    accum += val
                    ev_offset += 2
                max_trak_ticks = max(max_trak_ticks, accum)
            except Exception:
                pass

    trak_bars = math.ceil(max_trak_ticks / 768) if max_trak_ticks > 0 else 0
    total_bars = max(info["loop_end"], trak_bars)
    info["total_bars"] = total_bars

    if info["bpm"] and info["bpm"] > 0 and total_bars > 0:
        total_sec = total_bars * (240.0 / info["bpm"])
        mins = int(total_sec // 60)
        secs = int(total_sec % 60)
        info["duration_str"] = f"~{mins:02d}:{secs:02d} ({total_bars} Bars)"
    elif info["mode"] == "Pattern Mode":
        info["duration_str"] = "Looping Pattern"
    else:
        info["duration_str"] = "N/A"

    return info

def set_cpu_affinity_core_0(pid):
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x0200, False, pid)
        if handle:
            ctypes.windll.kernel32.SetProcessAffinityMask(handle, 1)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass

class WINRECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

def find_main_window_for_pid(pid):
    user32 = ctypes.windll.user32
    exclude_title = (
        "compact disc", "cd drive", "autoplay", "audio cd", "explore ",
        "explorer", "volume", "rb-338 cd", "rebirth cd", "program manager",
    )
    candidates = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        # Prefer top-level owned windows (skip child chrome)
        try:
            if user32.GetWindow(hwnd, 4):  # GW_OWNER
                return True
        except Exception:
            pass
        proc_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value != pid:
            return True

        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        title = buf.value.strip()
        title_l = title.lower()
        if any(token in title_l for token in exclude_title):
            return True

        rect = WINRECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = max(0, rect.right - rect.left)
        height = max(0, rect.bottom - rect.top)
        # Untitled splash / early frames: still accept if large enough
        if width < 280 or height < 160:
            return True
        if not title and (width < 400 or height < 280):
            return True

        score = width * height
        if any(token in title_l for token in ("rebirth", "rb-338", "rb338", "propellerhead")):
            score += 10_000_000
        elif title:
            score += 50_000
        candidates.append((score, hwnd))
        return True

    user32.EnumWindows(enum_proc, 0)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]

def dismiss_mounted_cd_windows(drive_letter):
    if not drive_letter:
        return
    user32 = ctypes.windll.user32
    drive = drive_letter.strip().upper().rstrip(":")
    if not drive:
        return
    markers = (f"({drive}:", f"{drive}:", f"{drive} )", f"drive ({drive}")

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        title_l = buf.value.lower()
        if any(marker.lower() in title_l for marker in markers) or "compact disc" in title_l:
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        return True

    user32.EnumWindows(enum_proc, 0)

def _force_maximize_hwnd(hwnd):
    """Maximize a Win32 HWND; ReBirth often resets size after first ShowWindow."""
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    SW_MAXIMIZE = 3
    WM_SYSCOMMAND = 0x0112
    SC_MAXIMIZE = 0xF030
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.05)
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_MAXIMIZE, 0)
        try:
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return True
    except Exception:
        return False

def maximize_window_for_pid(pid, timeout=35.0):
    """Find ReBirth's main window and keep re-applying maximize while it settles."""
    deadline = time.time() + timeout
    found = False
    hold_until = 0.0
    while time.time() < deadline:
        hwnd = find_main_window_for_pid(pid)
        if hwnd:
            _force_maximize_hwnd(hwnd)
            if not found:
                found = True
                # ReBirth redraws / loads song and often undoes maximize — keep pressing.
                hold_until = time.time() + 8.0
            elif time.time() >= hold_until:
                return True
        time.sleep(0.4 if found else 0.25)
    return found

def get_primary_screen_size():
    user32 = ctypes.windll.user32
    try:
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        return 1920, 1080

def _window_rect(hwnd):
    user32 = ctypes.windll.user32
    rect = WINRECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom

def _client_size(hwnd):
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    rect = WINRECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    return max(0, rect.right - rect.left), max(0, rect.bottom - rect.top)

def find_mdi_client_hwnd(main_hwnd):
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        if buf.value == "MDIClient":
            found.append(hwnd)
            return False
        return True

    user32.EnumChildWindows(main_hwnd, enum_proc, 0)
    return found[0] if found else None

def find_rebirth_rack_child(main_hwnd):
    """Find the MDI song/rack child window inside ReBirth's workspace."""
    user32 = ctypes.windll.user32
    mdi = find_mdi_client_hwnd(main_hwnd)
    parent = mdi or main_hwnd
    candidates = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        cls = buf.value
        if cls in ("MDIClient", "msctls_statusbar32", "ToolbarWindow32", "#32770"):
            return True
        rect = _window_rect(hwnd)
        if not rect:
            return True
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if w < 200 or h < 160:
            return True
        title_len = user32.GetWindowTextLengthW(hwnd) + 1
        title_buf = ctypes.create_unicode_buffer(title_len)
        user32.GetWindowTextW(hwnd, title_buf, title_len)
        score = w * h
        title_l = title_buf.value.lower()
        if any(tok in title_l for tok in (".rbs", "song", "rebirth", "default", "silent", "mod")):
            score += 5_000_000
        candidates.append((score, hwnd, w, h, title_buf.value))
        return True

    user32.EnumChildWindows(parent, enum_proc, 0)
    if not candidates and mdi:
        user32.EnumChildWindows(main_hwnd, enum_proc, 0)
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _score, hwnd, w, h, _title = candidates[0]
    return hwnd, w, h

def maximize_mdi_rack_child(main_hwnd, child_hwnd=None):
    """Maximize the song document inside the MDI client so the rack fills the workspace."""
    user32 = ctypes.windll.user32
    WM_MDIMAXIMIZE = 0x0225
    SW_MAXIMIZE = 3
    mdi = find_mdi_client_hwnd(main_hwnd)
    child = child_hwnd
    if not child:
        child, _w, _h = find_rebirth_rack_child(main_hwnd)
    if not child:
        return False
    try:
        if mdi:
            user32.SendMessageW(mdi, WM_MDIMAXIMIZE, child, 0)
        user32.ShowWindow(child, SW_MAXIMIZE)
        return True
    except Exception:
        return False

def restore_mdi_rack_child(main_hwnd, child_hwnd=None):
    """Restore song window to its natural size so we can measure the real rack."""
    user32 = ctypes.windll.user32
    WM_MDIRESTORE = 0x0223
    SW_RESTORE = 9
    mdi = find_mdi_client_hwnd(main_hwnd)
    child = child_hwnd
    if not child:
        child, _w, _h = find_rebirth_rack_child(main_hwnd)
    if not child:
        return None, None, None
    try:
        if mdi:
            user32.SendMessageW(mdi, WM_MDIRESTORE, child, 0)
        user32.ShowWindow(child, SW_RESTORE)
    except Exception:
        pass
    return find_rebirth_rack_child(main_hwnd)

def _enum_super_rack_extra_chrome(main_hwnd):
    """Status bars / toolbars that steal space and leave gray strips around the rack."""
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        cls = buf.value
        if cls in ("msctls_statusbar32", "ToolbarWindow32"):
            found.append(hwnd)
        return True

    try:
        user32.EnumChildWindows(main_hwnd, enum_proc, 0)
    except Exception:
        pass
    return found

def compute_super_rack_outer_size(main_hwnd=None, preferred_client=None, has_menu=True):
    """
    Outer window size that wraps tightly around the rack (no oversized gray MDI void).
    Keeps the menu bar; sizes from the natural (non-maximized) rack when possible.
    """
    user32 = ctypes.windll.user32
    client_w, client_h = SUPER_RACK_CLIENT_W, SUPER_RACK_CLIENT_H
    if preferred_client:
        pw, ph = preferred_client
        if pw and ph:
            # Prefer natural rack size; ignore maximized "fills whole MDI" measurements.
            if pw <= SUPER_RACK_WIDTH - 20 and ph <= SUPER_RACK_HEIGHT - 40:
                client_w, client_h = int(pw), int(ph)
    elif main_hwnd:
        child, cw, ch = find_rebirth_rack_child(main_hwnd)
        if child and cw and ch and cw <= SUPER_RACK_WIDTH - 20 and ch <= SUPER_RACK_HEIGHT - 40:
            client_w, client_h = int(cw), int(ch)

    client_w = max(560, min(int(client_w), SUPER_RACK_WIDTH - 16))
    client_h = max(400, min(int(client_h), SUPER_RACK_HEIGHT - 48))

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = RECT(0, 0, int(client_w), int(client_h))
    style = 0x00CF0000  # typical overlapped: CAPTION|SYSMENU|THICKFRAME|MINIMIZE|MAXIMIZE
    ex_style = 0
    menu_flag = bool(has_menu)
    if main_hwnd:
        try:
            style = user32.GetWindowLongW(main_hwnd, -16)
            ex_style = user32.GetWindowLongW(main_hwnd, -20)
            menu_flag = bool(user32.GetMenu(main_hwnd)) or bool(has_menu)
        except Exception:
            pass
    try:
        user32.AdjustWindowRectEx(ctypes.byref(rect), int(style), bool(menu_flag), int(ex_style))
    except Exception:
        try:
            user32.AdjustWindowRect(ctypes.byref(rect), int(style), bool(menu_flag))
        except Exception:
            pass
    outer_w = max(400, rect.right - rect.left)
    outer_h = max(300, rect.bottom - rect.top)
    sw, sh = get_primary_screen_size()
    outer_w = min(max(outer_w, 580), SUPER_RACK_WIDTH, sw - 16)
    outer_h = min(max(outer_h, 440), SUPER_RACK_HEIGHT, sh - 16)
    return int(outer_w), int(outer_h)

def compute_super_rack_geometry(main_hwnd=None, max_w=SUPER_RACK_WIDTH, max_h=SUPER_RACK_HEIGHT, has_menu=True):
    """Centered outer window that hugs the rack (≤800×620) with room for the menu."""
    sw, sh = get_primary_screen_size()
    w, h = compute_super_rack_outer_size(main_hwnd, has_menu=has_menu)
    w = min(int(w), int(max_w), max(320, sw - 16))
    h = min(int(h), int(max_h), max(240, sh - 16))
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2)
    return x, y, w, h, sw, sh

def strip_super_rack_chrome(hwnd):
    """
    Super Rack chrome: keep File/Edit/Mods menu + title (for drag/minimize),
    hide status/toolbars that leave gray strips, lock resize.
    """
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    GWL_STYLE = -16
    WS_THICKFRAME = 0x00040000
    WS_MAXIMIZEBOX = 0x00010000
    key = int(hwnd)
    try:
        if key not in _SUPER_RACK_STYLE_BACKUP:
            _SUPER_RACK_STYLE_BACKUP[key] = user32.GetWindowLongW(hwnd, GWL_STYLE)
        # Ensure menu stays (restore if a previous run cleared it)
        if key in _SUPER_RACK_MENU_BACKUP and _SUPER_RACK_MENU_BACKUP[key]:
            user32.SetMenu(hwnd, _SUPER_RACK_MENU_BACKUP[key])
        elif key not in _SUPER_RACK_MENU_BACKUP:
            _SUPER_RACK_MENU_BACKUP[key] = user32.GetMenu(hwnd)

        # Hide status bar / toolbars once
        if key not in _SUPER_RACK_HIDDEN_CHROME:
            hidden = []
            for child in _enum_super_rack_extra_chrome(hwnd):
                was = bool(user32.IsWindowVisible(child))
                if was:
                    user32.ShowWindow(child, 0)  # SW_HIDE
                hidden.append((int(child), was))
            _SUPER_RACK_HIDDEN_CHROME[key] = hidden

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(WS_THICKFRAME | WS_MAXIMIZEBOX)
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0020 | 0x0040)
        return True
    except Exception:
        return False

def restore_super_rack_chrome(hwnd):
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    key = int(hwnd)
    try:
        style = _SUPER_RACK_STYLE_BACKUP.pop(key, None)
        if style is not None:
            user32.SetWindowLongW(hwnd, -16, style)
        menu = _SUPER_RACK_MENU_BACKUP.pop(key, None)
        if menu:
            user32.SetMenu(hwnd, menu)
        for child, was in _SUPER_RACK_HIDDEN_CHROME.pop(key, []):
            try:
                if was:
                    user32.ShowWindow(child, 5)  # SW_SHOW
            except Exception:
                pass
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0020 | 0x0040)
    except Exception:
        pass

def _mag_api():
    try:
        mag = ctypes.WinDLL("Magnification")
        mag.MagInitialize.restype = ctypes.c_bool
        mag.MagUninitialize.restype = ctypes.c_bool
        mag.MagSetFullscreenTransform.argtypes = [ctypes.c_float, ctypes.c_int, ctypes.c_int]
        mag.MagSetFullscreenTransform.restype = ctypes.c_bool
        try:
            mag.MagShowSystemCursor.argtypes = [ctypes.c_bool]
            mag.MagShowSystemCursor.restype = ctypes.c_bool
        except Exception:
            pass
        return mag
    except Exception:
        return None

def super_rack_magnifier_start():
    global _SUPER_RACK_MAG_READY
    mag = _mag_api()
    if not mag:
        return False
    try:
        if not _SUPER_RACK_MAG_READY:
            if not mag.MagInitialize():
                return False
            _SUPER_RACK_MAG_READY = True
            try:
                mag.MagShowSystemCursor(True)
            except Exception:
                pass
        return True
    except Exception:
        return False

def super_rack_magnifier_stop():
    global _SUPER_RACK_MAG_READY
    mag = _mag_api()
    if not mag:
        _SUPER_RACK_MAG_READY = False
        return
    try:
        mag.MagSetFullscreenTransform(ctypes.c_float(1.0), 0, 0)
    except Exception:
        pass
    try:
        if _SUPER_RACK_MAG_READY:
            mag.MagUninitialize()
    except Exception:
        pass
    _SUPER_RACK_MAG_READY = False

def super_rack_apply_zoom(scale, focus_hwnd=None):
    """Fullscreen magnifier zoom centered on the ReBirth rack (mouse still works)."""
    try:
        scale = float(scale or 1.0)
    except (TypeError, ValueError):
        scale = 1.0
    if scale <= 1.01:
        try:
            mag = _mag_api()
            if mag and _SUPER_RACK_MAG_READY:
                mag.MagSetFullscreenTransform(ctypes.c_float(1.0), 0, 0)
        except Exception:
            pass
        return False
    if not super_rack_magnifier_start():
        return False
    mag = _mag_api()
    sw, sh = get_primary_screen_size()
    cx, cy = sw / 2.0, sh / 2.0
    if focus_hwnd:
        rect = _window_rect(focus_hwnd)
        if rect:
            cx = (rect[0] + rect[2]) / 2.0
            cy = (rect[1] + rect[3]) / 2.0
    # Visible unmagnified area is screen/scale; place focus at its center.
    x_offset = int(round(cx - (sw / scale) / 2.0))
    y_offset = int(round(cy - (sh / scale) / 2.0))
    x_offset = max(0, min(x_offset, max(0, sw - int(sw / scale))))
    y_offset = max(0, min(y_offset, max(0, sh - int(sh / scale))))
    try:
        return bool(mag.MagSetFullscreenTransform(ctypes.c_float(scale), int(x_offset), int(y_offset)))
    except Exception:
        return False

def apply_super_rack_to_hwnd(hwnd, strip_chrome=True, scale=1.0, fill_height=False):
    """
    Super Rack:
    1) restore main window
    2) measure natural rack size (not maximized MDI gray void)
    3) keep menu + title; hide status/toolbars
    4) shrink window tightly around the rack and center it
       (fill_height: y≈0 / almost top→bottom on the fitted resolution)
    5) maximize rack into that tight workspace
    Note: no digital magnifier — use display resolution for sharp scaling.
    """
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    HWND_TOP = 0
    SWP_SHOWWINDOW = 0x0040
    SWP_FRAMECHANGED = 0x0020
    SWP_NOCOPYBITS = 0x0100
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        if user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)

        child = None
        child_w = child_h = None
        key = int(hwnd)
        if key in _SUPER_RACK_SIZE_CACHE:
            child_w, child_h = _SUPER_RACK_SIZE_CACHE[key]
            child, _cw, _ch = find_rebirth_rack_child(hwnd)
        else:
            child, child_w, child_h = restore_mdi_rack_child(hwnd)
            if not child:
                child, child_w, child_h = find_rebirth_rack_child(hwnd)
            if child_w and child_h and child_w <= SUPER_RACK_WIDTH - 20 and child_h <= SUPER_RACK_HEIGHT - 40:
                _SUPER_RACK_SIZE_CACHE[key] = (int(child_w), int(child_h))

        if strip_chrome:
            strip_super_rack_chrome(hwnd)

        preferred = _SUPER_RACK_SIZE_CACHE.get(key) or (
            (child_w, child_h) if child_w and child_h else None
        )
        ow, oh = compute_super_rack_outer_size(hwnd, preferred_client=preferred, has_menu=True)
        sw, sh = get_primary_screen_size()
        w = min(ow, SUPER_RACK_WIDTH, max(320, sw - 8))
        h = min(oh, SUPER_RACK_HEIGHT, max(240, sh - 4))
        # Resolution was pre-fitted to ≈ h, so this lands nearly top→bottom with side bezels.
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)

        user32.SetWindowPos(
            hwnd,
            HWND_TOP,
            int(x),
            int(y),
            int(w),
            int(h),
            SWP_SHOWWINDOW | SWP_FRAMECHANGED | SWP_NOCOPYBITS,
        )
        maximize_mdi_rack_child(hwnd, child)
        # Never use MagSetFullscreenTransform here — it block-scales and looks muddy.
        try:
            super_rack_magnifier_stop()
        except Exception:
            pass
        try:
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return True
    except Exception:
        return False

def apply_super_rack_for_pid(pid, scale=1.0, fill_height=False):
    hwnd = find_main_window_for_pid(pid)
    if not hwnd:
        return False
    return apply_super_rack_to_hwnd(hwnd, strip_chrome=True, scale=scale, fill_height=fill_height)

def super_rack_window_for_pid(pid, timeout=40.0, hold_seconds=12.0, tick_callback=None, scale=1.0, fill_height=False):
    """Keep re-applying Super Rack geometry while ReBirth settles."""
    deadline = time.time() + timeout
    found = False
    hold_until = 0.0
    while time.time() < deadline:
        if apply_super_rack_for_pid(pid, scale=scale, fill_height=fill_height):
            if not found:
                found = True
                hold_until = time.time() + hold_seconds
            elif time.time() >= hold_until:
                return True
        if tick_callback:
            try:
                tick_callback()
            except Exception:
                pass
        time.sleep(0.35 if found else 0.2)
    return found

def cleanup_super_rack_session(pid=None):
    """Restore chrome, taskbar + cancel magnifier when Super Rack ends."""
    super_rack_magnifier_stop()
    try:
        show_taskbar_after_super_rack()
    except Exception:
        pass
    hwnd = find_main_window_for_pid(pid) if pid else None
    if hwnd:
        restore_super_rack_chrome(hwnd)
        _SUPER_RACK_SIZE_CACHE.pop(int(hwnd), None)
    for key in list(_SUPER_RACK_STYLE_BACKUP.keys()) + list(_SUPER_RACK_HIDDEN_CHROME.keys()):
        try:
            restore_super_rack_chrome(key)
        except Exception:
            _SUPER_RACK_MENU_BACKUP.pop(key, None)
            _SUPER_RACK_STYLE_BACKUP.pop(key, None)
            _SUPER_RACK_HIDDEN_CHROME.pop(key, None)
        _SUPER_RACK_SIZE_CACHE.pop(key, None)

def find_iso_file(config=None):
    if config:
        status = scan_rebirth_download_status(config)
        if status.get("iso_path"):
            return status["iso_path"]
    iso_files = glob.glob(os.path.join(BASE_DIR, "*.iso"))
    if iso_files:
        return os.path.abspath(iso_files[0])
    return None

def mount_iso(iso_path):
    try:
        ps_command = (
            f"$vol = (Mount-DiskImage -ImagePath '{iso_path}' -PassThru | Get-Volume).DriveLetter; "
            f"Start-Sleep -Milliseconds 400; "
            f"(New-Object -ComObject Shell.Application).Windows() | Where-Object {{ $_.LocationURL -like \"*$vol*\" }} | ForEach-Object {{ $_.Quit() }}; "
            f"Write-Output $vol"
        )
        result = run_powershell(ps_command, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return None

def dismount_iso(iso_path):
    try:
        ps_command = f"Dismount-DiskImage -ImagePath '{iso_path}'"
        run_powershell(ps_command, capture_output=True, text=False)
    except Exception:
        pass

def is_process_running(process_name):
    try:
        cmd = f'tasklist /FI "IMAGENAME eq {process_name}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return process_name.lower() in result.stdout.lower()
    except Exception:
        return False

def kill_zombie_process():
    try:
        cmd = f'taskkill /F /IM "{EXE_NAME}"'
        subprocess.run(cmd, shell=True, capture_output=True)
    except Exception:
        pass

def force_retro_compatibility():
    reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppNameCompatFlags\Layers"
    compat_flags = "~ RUNASADMIN GDIDPISCALE DPIUNAWARE"
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, EXE_PATH, 0, winreg.REG_SZ, compat_flags)
        winreg.CloseKey(key)
    except Exception:
        pass

def stabilize_rebirth_environment(game_folder, drive_letter, song_path=None):
    folder_with_slash = game_folder + "\\"
    cd_path = f"{drive_letter}:\\" if drive_letter else folder_with_slash
    short_song = get_short_path_name(song_path) if song_path else None

    REG_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Propellerhead Software\ReBirth"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Propellerhead Software\ReBirth"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Propellerhead Software\ReBirth"),
        (winreg.HKEY_CURRENT_USER, r"Software\VirtualStore\Machine\Software\Wow6432Node\Propellerhead Software\ReBirth")
    ]
    
    for root_key, path in REG_KEYS:
        try:
            key = winreg.CreateKeyEx(root_key, path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "CDPath", 0, winreg.REG_SZ, cd_path)
            winreg.SetValueEx(key, "SourcePath", 0, winreg.REG_SZ, folder_with_slash)
            winreg.SetValueEx(key, "InstallationPath", 0, winreg.REG_SZ, folder_with_slash)
            if song_path:
                winreg.SetValueEx(key, "LastSong", 0, winreg.REG_SZ, short_song or song_path)
                winreg.SetValueEx(key, "DefaultSong", 0, winreg.REG_SZ, short_song or song_path)
            winreg.CloseKey(key)
        except Exception:
            pass

def parse_rbs_metadata(rbs_path, include_patterns=True):
    info = {
        "bpm": None,
        "mode": "Unknown Mode",
        "title": "Untitled Song",
        "comments": "No description available.",
        "mod_name": "Standard ReBirth",
        "sound_engine": "ReBirth 2.0 Sound",
        "active_patterns": 0,
        "pattern_breakdown": "303 #1: 0 | 303 #2: 0 | 808: 0 | 909: 0",
        "web": "",
        "loop_start": 1,
        "loop_end": 0,
        "total_bars": 0,
        "duration_str": "N/A",
        "format": "unknown",
        "format_version": "",
    }
    if not rbs_path or not os.path.exists(rbs_path):
        return info

    try:
        with open(rbs_path, "rb") as f:
            content = f.read()

        fmt = detect_rbs_format(content)
        if fmt == "legacy_midi":
            return parse_legacy_midi_rbs_metadata(rbs_path, content)
        if fmt == "iff42":
            return parse_iff42_rbs_metadata(rbs_path, content, include_patterns=include_patterns)
    except Exception:
        pass

    return info

RBS_CHUNK_SIZES = {
    b"HEAD": 256,
    b"GLOB": 512,
    b"USRI": 712,
    b"MIXR": 64,
    b"DELY": 8,
    b"PCF ": 12,
    b"DIST": 8,
    b"COMP": 8,
    b"303 ": 1097,
    b"808 ": 6238,
    b"909 ": 6239,
}

def find_rbs_chunk(content, tag, occurrence=0):
    expected_size = RBS_CHUNK_SIZES.get(tag)
    pos = 0
    found = 0
    tag_len = len(tag)
    while True:
        idx = content.find(tag, pos)
        if idx == -1:
            return -1
        if len(content) >= idx + 8:
            size = struct.unpack(">I", content[idx + 4 : idx + 8])[0]
            if expected_size is None or size == expected_size:
                if len(content) >= idx + 8 + size:
                    if found == occurrence:
                        return idx
                    found += 1
        pos = idx + tag_len
    return -1

DRUM_PATTERN_DATA_OFFSET = {"808": 30, "909": 31}

def get_drum_pattern_data_offset(is_909=True):
    return DRUM_PATTERN_DATA_OFFSET["909" if is_909 else "808"]

def deconstruct_rbs_song(rbs_path):
    notes_map = ["C ", "C#", "D ", "D#", "E ", "F ", "F#", "G ", "G#", "A ", "A#", "B ", "C5"]
    result = {"303_1": [], "303_2": [], "808": [], "909": []}
    if not rbs_path or not os.path.exists(rbs_path):
        return result

    try:
        with open(rbs_path, "rb") as f:
            content = f.read()

        if detect_rbs_format(content) == "legacy_midi":
            return deconstruct_legacy_rbs_song(rbs_path, content)

        tb303_indices = []
        for occurrence in range(2):
            idx = find_rbs_chunk(content, b"303 ", occurrence=occurrence)
            if idx == -1:
                break
            tb303_indices.append(idx)

        for dev_i, idx in enumerate(tb303_indices[:2]):
            key = "303_1" if dev_i == 0 else "303_2"
            if len(content) >= idx + 8 + 1097:
                chunk_data = content[idx + 8 : idx + 8 + 1097]
                for p in range(32):
                    bank_char = chr(65 + (p // 8))
                    pat_num = (p % 8) + 1
                    pat_name = f"{bank_char}{pat_num}"
                    pat_bytes = chunk_data[9 + p*34 : 9 + (p+1)*34]
                    steps_data = []
                    has_notes = False
                    
                    for s in range(16):
                        note_val = pat_bytes[2 + s*2]
                        flags = pat_bytes[2 + s*2 + 1]
                        
                        note_str = notes_map[note_val] if note_val < len(notes_map) else "? "
                        slide = "S" if (flags & 0x01) else "-"
                        accent = "A" if (flags & 0x02) else "-"
                        up = "^" if (flags & 0x04) else ("v" if (flags & 0x08) else "-")
                        active = is_303_step_active(note_val, flags)
                        
                        if active:
                            has_notes = True
                            step_data = {"note": note_str.strip(), "up": up, "accent": accent, "slide": slide, "active": True}
                        else:
                            step_data = {"note": "--", "up": "-", "accent": "-", "slide": "-", "active": False}
                        steps_data.append(step_data)

                    if has_notes:
                        result[key].append({"name": pat_name, "steps": steps_data})

        # Parse TR-808
        idx_808 = find_rbs_chunk(content, b"808 ")
        if idx_808 != -1 and len(content) >= idx_808 + 8 + 6238:
            chunk_data = content[idx_808 + 8 : idx_808 + 8 + 6238]
            inst_labels = ["AC", "BD", "SD", "LT", "MT", "HT", "RS", "CP", "CB", "CY", "OH", "CH"]
            drum_offset = get_drum_pattern_data_offset(False)
            for p in range(32):
                bank_char = chr(65 + (p // 8))
                pat_num = (p % 8) + 1
                pat_name = f"{bank_char}{pat_num}"
                pat_bytes = chunk_data[drum_offset + p * 194 : drum_offset + (p + 1) * 194]
                matrix = {lbl: [] for lbl in inst_labels}
                has_hits = False
                for s in range(16):
                    step_offset = 2 + s * 12
                    for inst_i, lbl in enumerate(inst_labels):
                        val = pat_bytes[step_offset + inst_i] if (step_offset + inst_i) < len(pat_bytes) else 0
                        if val > 0:
                            has_hits = True
                            matrix[lbl].append("x")
                        else:
                            matrix[lbl].append(".")
                if has_hits:
                    result["808"].append({"name": pat_name, "matrix": matrix})

        # Parse TR-909
        idx_909 = find_rbs_chunk(content, b"909 ")
        if idx_909 != -1 and len(content) >= idx_909 + 8 + 6239:
            chunk_data = content[idx_909 + 8 : idx_909 + 8 + 6239]
            inst_labels_909 = ["AC", "BD", "SD", "LT", "MT", "HT", "RS", "CP", "CH", "OH", "CC", "RC"]
            drum_offset = get_drum_pattern_data_offset(True)
            for p in range(32):
                bank_char = chr(65 + (p // 8))
                pat_num = (p % 8) + 1
                pat_name = f"{bank_char}{pat_num}"
                pat_bytes = chunk_data[drum_offset + p * 194 : drum_offset + (p + 1) * 194]
                matrix = {lbl: [] for lbl in inst_labels_909}
                has_hits = False
                for s in range(16):
                    step_offset = 2 + s * 12
                    for inst_i, lbl in enumerate(inst_labels_909):
                        val = pat_bytes[step_offset + inst_i] if (step_offset + inst_i) < len(pat_bytes) else 0
                        if val == 1:
                            has_hits = True
                            matrix[lbl].append("x")
                        elif val == 2:
                            has_hits = True
                            matrix[lbl].append("A")
                        elif val == 3:
                            has_hits = True
                            matrix[lbl].append("F")
                        else:
                            matrix[lbl].append(".")
                if has_hits:
                    result["909"].append({"name": pat_name, "matrix": matrix})
    except Exception:
        pass

    return result

NOTE_NAME_TO_303_VAL = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
    "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11, "C5": 12
}
VAL_TO_NOTE_NAME = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B", "C5"]
ACID_PIANO_ROWS = ("C5", "B", "A#", "A", "G#", "G", "F#", "F", "E", "D#", "D", "C#", "C")

def empty_303_steps():
    return [{"note": "--", "up": "-", "accent": "-", "slide": "-", "active": False} for _ in range(16)]

def normalize_303_steps(steps):
    normalized = empty_303_steps()
    if not steps:
        return normalized
    for i in range(min(16, len(steps))):
        src = steps[i] or {}
        if src.get("active") and src.get("note") in NOTE_NAME_TO_303_VAL:
            normalized[i] = {
                "note": src["note"],
                "up": src.get("up") if src.get("up") in ("^", "v") else "-",
                "accent": "A" if src.get("accent") == "A" else "-",
                "slide": "S" if src.get("slide") == "S" else "-",
                "active": True,
            }
    return normalized

def pattern_slot_to_index(slot_code):
    if not slot_code or len(slot_code) < 2:
        return None
    bank = slot_code[0].upper()
    if bank not in "ABCD":
        return None
    try:
        num = int(slot_code[1:])
    except ValueError:
        return None
    if num < 1 or num > 8:
        return None
    return (ord(bank) - ord("A")) * 8 + (num - 1)

def pattern_slot_sort_key(slot_code):
    idx = pattern_slot_to_index(slot_code)
    return idx if idx is not None else 999

INST_LABELS_808 = ["AC", "BD", "SD", "LT", "MT", "HT", "RS", "CP", "CB", "CY", "OH", "CH"]
INST_LABELS_909 = ["AC", "BD", "SD", "LT", "MT", "HT", "RS", "CP", "CH", "OH", "CC", "RC"]

def acid_note_index_from_degree(semitone, octave_band):
    base = semitone % 12
    if octave_band >= 2:
        return min(12, base + 7)
    if octave_band <= 0:
        return max(0, base - 5)
    return base

def generate_melodic_acid_steps(slot_code, scale_intervals, density, accent_p, slide_p, octave_spread=0.55, variation_seed=0, unit_index=0):
    slot_idx = pattern_slot_to_index(slot_code) or 0
    unit_bias = unit_index * 2_137_000_000
    if unit_index == 1:
        rotate = (slot_idx + 5) % max(1, len(scale_intervals))
        density = min(0.98, max(0.12, density * 0.88 + 0.08))
        accent_p = min(1.0, accent_p * 1.12)
        slide_p = min(1.0, slide_p * 0.82)
        octave_spread = min(1.0, octave_spread * 1.18)
    else:
        rotate = slot_idx % max(1, len(scale_intervals))
    rng = random.Random(
        slot_idx * 9001
        + sum(scale_intervals)
        + int(density * 1000)
        + int(octave_spread * 100)
        + int(variation_seed)
        + unit_bias
        + unit_index * 17_003
    )

    rotated = scale_intervals[rotate:] + scale_intervals[:rotate]

    if octave_spread < 0.35:
        allowed_bands = {1}
    elif octave_spread < 0.7:
        allowed_bands = {0, 1, 2}
    else:
        allowed_bands = {0, 1, 2}

    pool = []
    for band in sorted(allowed_bands):
        for interval in rotated:
            note_idx = acid_note_index_from_degree(interval, band)
            pool.append(note_idx)
    pool = sorted(set(pool))
    if not pool:
        pool = [acid_note_index_from_degree(rotated[0], 1)]

    pos = slot_idx % len(pool)
    prev_pos = None
    prev_active = False
    consecutive_slides = 0
    steps = empty_303_steps()

    for step_idx in range(16):
        on_beat = step_idx % 4 == 0
        rest_chance = max(0.08, 1.0 - density)
        if on_beat:
            rest_chance *= 0.45
        if step_idx in (0, 8):
            rest_chance *= 0.25

        if rng.random() < rest_chance and step_idx != 0:
            prev_pos = None
            prev_active = False
            consecutive_slides = 0
            continue

        if prev_pos is not None and rng.random() < 0.72:
            move = rng.choice([-2, -1, -1, 0, 1, 1, 2])
            pos = max(0, min(len(pool) - 1, prev_pos + move))
        else:
            pos = rng.randrange(len(pool))

        note_idx = pool[pos]
        note_name = VAL_TO_NOTE_NAME[note_idx]

        slide = "-"
        semitone_gap = abs(pool[pos] - pool[prev_pos]) if prev_pos is not None else 99
        if (
            prev_active
            and step_idx > 0
            and consecutive_slides < 2
            and semitone_gap <= 2
            and rng.random() < min(slide_p, 0.22)
        ):
            slide = "S"
            consecutive_slides += 1
        else:
            consecutive_slides = 0

        accent = "-"
        accent_chance = min(1.0, accent_p * (1.35 if on_beat else 1.0))
        if not prev_active:
            accent_chance = min(1.0, accent_chance * 1.15)
        if rng.random() < accent_chance:
            accent = "A"

        steps[step_idx] = {
            "note": note_name,
            "up": "-",
            "accent": accent,
            "slide": slide,
            "active": True,
        }
        prev_pos = pos
        prev_active = True

    return steps

def get_acid_launch_path():
    return os.path.join(BASE_DIR, "_AcidGen_Launch.rbs")

def is_rebirth_running():
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return EXE_NAME.lower() in (result.stdout or "").lower()
    except Exception:
        return False

def empty_drum_matrix(is_909=True):
    labels = INST_LABELS_909 if is_909 else INST_LABELS_808
    return {lbl: ["."] * 16 for lbl in labels}

def generate_acid_drum_matrix(slot_code, is_909=True, variation_seed=0):
    matrix = empty_drum_matrix(is_909)
    slot_idx = pattern_slot_to_index(slot_code) or 0
    rng = random.Random(slot_idx * 7919 + sum(ord(c) for c in slot_code) + int(variation_seed))

    for s in (0, 4, 8, 12):
        if rng.random() > 0.1:
            matrix["BD"][s] = "x"

    for s in (4, 12):
        if rng.random() > 0.22:
            matrix["SD"][s] = "A" if rng.random() < 0.35 else "x"

    hat_density = 0.5 + (slot_idx % 6) * 0.07
    for s in range(16):
        if s % 2 == 1 and rng.random() < hat_density:
            matrix["CH"][s] = "x"
        elif rng.random() < hat_density * 0.2:
            matrix["CH"][s] = "x"

    for s in (6, 14, 2, 10):
        if rng.random() < 0.38:
            matrix["OH"][s] = "x"

    if is_909:
        for s in range(16):
            if s not in (4, 12) and rng.random() < 0.1:
                matrix["CP"][s] = "x"
        if rng.random() < 0.55:
            for s in (1, 9):
                matrix["RS"][s] = "x"
    else:
        for s in (7, 15):
            if rng.random() < 0.35:
                matrix["CB"][s] = "x"
        if rng.random() < 0.45:
            matrix["CY"][s] = "x"

    return matrix

def encode_drum_pattern(matrix, is_909=True):
    labels = INST_LABELS_909 if is_909 else INST_LABELS_808
    pat = bytearray(194)
    pat[0] = 0
    pat[1] = 16
    for s in range(16):
        step_offset = 2 + s * 12
        for inst_i, lbl in enumerate(labels):
            hits = matrix.get(lbl, ["."] * 16)
            hit = hits[s] if s < len(hits) else "."
            if is_909:
                val = 1 if hit == "x" else (2 if hit == "A" else (3 if hit == "F" else 0))
            else:
                val = 1 if hit in ("x", "A", "F") else 0
            pat[step_offset + inst_i] = val
    return pat

def encode_303_step(step):
    if not step.get("active"):
        return 0, 0x10
    note_val = NOTE_NAME_TO_303_VAL.get(step.get("note", "C"), 0)
    flags = 0
    if step.get("slide") == "S":
        flags |= 0x01
    if step.get("accent") == "A":
        flags |= 0x02
    if step.get("up") == "^":
        flags |= 0x04
    elif step.get("up") == "v":
        flags |= 0x08
    if flags == 0 and note_val == 0:
        flags = 0x02
    return note_val, flags

def encode_303_pattern(steps):
    steps = normalize_303_steps(steps)
    pat = bytearray(34)
    pat[0] = 0
    pat[1] = 16
    for s in range(16):
        step = steps[s]
        note_val, flags = encode_303_step(step)
        pat[2 + s * 2] = note_val
        pat[2 + s * 2 + 1] = flags
    return pat

def discover_builtin_default_songs():
    songs = []
    for label, filename in DEFAULT_SONG_OPTIONS:
        path = os.path.join(DEFAULT_SONGS_DIR, filename)
        if os.path.exists(path):
            songs.append((label, os.path.abspath(path)))
    return songs

def is_under_default_songs(path):
    if not path:
        return False
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(DEFAULT_SONGS_DIR)]) == os.path.abspath(DEFAULT_SONGS_DIR)
    except ValueError:
        return False

def find_template_rbs(prefer_silent=True):
    builtins = discover_builtin_default_songs()
    if not builtins:
        return None
    if prefer_silent:
        for _, path in builtins:
            if "silent" in os.path.basename(path).lower():
                return path
    return builtins[0][1]

def apply_acid_launch_defaults(content, active_slot_code, drum_machine="909", enable_303_2=False, active_slot_303_2=None):
    slot_idx = pattern_slot_to_index(active_slot_code)
    if slot_idx is None:
        slot_idx = 0
    slot_idx_2 = pattern_slot_to_index(active_slot_303_2) if active_slot_303_2 else slot_idx
    if slot_idx_2 is None:
        slot_idx_2 = slot_idx

    glob_idx = find_rbs_chunk(content, b"GLOB")
    if glob_idx != -1 and len(content) >= glob_idx + 8 + 512:
        glob_base = glob_idx + 8
        content[glob_base] = 0
        content[glob_base + 1] = 0

    mix_idx = find_rbs_chunk(content, b"MIXR")
    if mix_idx != -1 and len(content) >= mix_idx + 8 + 64:
        mix_base = mix_idx + 8
        content[mix_base + 16] = 1
        content[mix_base + 28] = 0
        content[mix_base + 40] = 1 if drum_machine == "808" else 0
        content[mix_base + 41] = 0x7f if drum_machine == "808" else 0
        content[mix_base + 52] = 1 if drum_machine != "808" else 0
        content[mix_base + 53] = 0x7f if drum_machine != "808" else 0

    for occurrence in range(2):
        idx_303 = find_rbs_chunk(content, b"303 ", occurrence=occurrence)
        if idx_303 == -1 or len(content) < idx_303 + 8 + 1097:
            break
        base = idx_303 + 8
        if occurrence == 0:
            enabled = True
            active_idx = slot_idx
        else:
            enabled = bool(enable_303_2)
            active_idx = slot_idx_2 if enabled else 0
        content[base] = 1 if enabled else 0
        content[base + 1] = active_idx if enabled else 0
        if enabled:
            content[base + 3] = max(content[base + 3], 72)
            content[base + 4] = max(content[base + 4], 32)
            content[base + 6] = max(content[base + 6], 52)
            content[base + 7] = max(content[base + 7], 72)

    for machine, tag in (("808", b"808 "), ("909", b"909 ")):
        idx_drum = find_rbs_chunk(content, tag)
        if idx_drum == -1 or len(content) <= idx_drum + 10:
            continue
        drum_base = idx_drum + 8
        enabled = drum_machine == machine
        content[drum_base] = 1 if enabled else 0
        content[drum_base + 1] = slot_idx if enabled else 0

    return content

def write_303_patterns_to_chunk(content, occurrence, generated_patterns, active_slot_code=None, clear_unwritten_slots=False):
    if not generated_patterns:
        return 0
    idx_303 = find_rbs_chunk(content, b"303 ", occurrence=occurrence)
    if idx_303 == -1 or len(content) < idx_303 + 8 + 1097:
        return 0

    chunk_base = idx_303 + 8
    empty_pat = encode_303_pattern(empty_303_steps())
    written = 0
    written_slots = set()
    for slot_code, steps in generated_patterns.items():
        pat_index = pattern_slot_to_index(slot_code)
        if pat_index is None:
            continue
        pat_bytes = encode_303_pattern(steps)
        offset = chunk_base + 9 + pat_index * 34
        content[offset:offset + 34] = pat_bytes
        written += 1
        written_slots.add(pat_index)

    if clear_unwritten_slots:
        for pat_index in range(32):
            if pat_index not in written_slots:
                offset = chunk_base + 9 + pat_index * 34
                content[offset:offset + 34] = empty_pat

    if written:
        content[chunk_base] = 1
        if active_slot_code is not None:
            active_idx = pattern_slot_to_index(active_slot_code)
            if active_idx is not None:
                content[chunk_base + 1] = active_idx
    return written

def write_drum_patterns_to_chunk(content, drum_tag, is_909, drum_patterns, active_slot_code):
    if not drum_patterns:
        return 0
    idx_drum = find_rbs_chunk(content, drum_tag)
    if idx_drum == -1:
        return 0
    drum_base = idx_drum + 8
    written = 0
    for slot_code, matrix in drum_patterns.items():
        pat_index = pattern_slot_to_index(slot_code)
        if pat_index is None:
            continue
        pat_bytes = encode_drum_pattern(matrix, is_909=is_909)
        drum_offset = get_drum_pattern_data_offset(is_909)
        offset = drum_base + drum_offset + pat_index * 194
        if offset + 194 <= len(content):
            content[offset:offset + 194] = pat_bytes
            written += 1
    if written:
        content[drum_base] = 1
        active_idx = pattern_slot_to_index(active_slot_code)
        if active_idx is not None:
            content[drum_base + 1] = active_idx
    return written

def write_acid_patterns_to_rbs(output_path, generated_patterns, source_rbs_path=None, song_title="Acid Bank Generated", generated_drum_patterns=None, drum_machine="909", active_slot_code=None, clear_unwritten_slots=False, generated_patterns_303_2=None, generated_drum_patterns_808=None, generated_drum_patterns_909=None):
    drum_808 = generated_drum_patterns_808
    drum_909 = generated_drum_patterns_909
    if drum_808 is None and drum_machine == "808":
        drum_808 = generated_drum_patterns
    if drum_909 is None and drum_machine != "808":
        drum_909 = generated_drum_patterns
    if not generated_patterns and not generated_patterns_303_2 and not drum_808 and not drum_909:
        return False
    template_path = source_rbs_path or find_template_rbs()
    if not template_path or not os.path.exists(template_path):
        return False

    if active_slot_code is None:
        all_keys = []
        for store in (generated_patterns, generated_patterns_303_2, drum_808, drum_909):
            if store:
                all_keys.extend(store.keys())
        active_slot_code = min(all_keys, key=pattern_slot_sort_key) if all_keys else "A1"

    try:
        with open(template_path, "rb") as f:
            content = bytearray(f.read())

        written = write_303_patterns_to_chunk(
            content,
            0,
            generated_patterns or {},
            active_slot_code=active_slot_code,
            clear_unwritten_slots=clear_unwritten_slots,
        )
        written_2 = write_303_patterns_to_chunk(
            content,
            1,
            generated_patterns_303_2 or {},
            active_slot_code=active_slot_code,
            clear_unwritten_slots=clear_unwritten_slots and bool(generated_patterns_303_2),
        )

        drum_written_808 = write_drum_patterns_to_chunk(content, b"808 ", False, drum_808 or {}, active_slot_code)
        drum_written_909 = write_drum_patterns_to_chunk(content, b"909 ", True, drum_909 or {}, active_slot_code)
        drum_written = drum_written_808 + drum_written_909

        if written == 0 and written_2 == 0 and drum_written == 0:
            return False

        apply_acid_launch_defaults(
            content,
            active_slot_code,
            drum_machine=drum_machine,
            enable_303_2=bool(written_2),
            active_slot_303_2=active_slot_code,
        )

        usri_idx = find_rbs_chunk(content, b"USRI")
        if usri_idx != -1 and len(content) >= usri_idx + 8 + 442:
            title_bytes = song_title.encode("latin-1", errors="ignore")[:40].ljust(41, b"\x00")
            content[usri_idx + 8:usri_idx + 8 + 41] = title_bytes
            comment = (
                f"Generated acid ({written} TB-303 #1 slots, {written_2} TB-303 #2 slots, "
                f"{drum_written_808} TR-808 + {drum_written_909} TR-909 drum slots) via ReBirth ToolBox."
            )
            comment_bytes = comment.encode("latin-1", errors="ignore")[:401].ljust(401, b"\x00")
            content[usri_idx + 8 + 41:usri_idx + 8 + 442] = comment_bytes

        with open(output_path, "wb") as f:
            f.write(content)
        return True
    except Exception:
        return False

def generated_patterns_to_deconstructed(generated_patterns, generated_drum_patterns=None, drum_machine="909", slot_code=None):
    acid_source = generated_patterns or {}
    drum_source = generated_drum_patterns or {}
    if slot_code and slot_code in acid_source:
        acid_source = {slot_code: acid_source[slot_code]}
    if slot_code and slot_code in drum_source:
        drum_source = {slot_code: drum_source[slot_code]}

    patterns = []
    for slot, steps in sorted(acid_source.items(), key=lambda item: pattern_slot_sort_key(item[0])):
        patterns.append({"name": slot, "steps": steps})
    drum_patterns = []
    for slot, matrix in sorted(drum_source.items(), key=lambda item: pattern_slot_sort_key(item[0])):
        drum_patterns.append({"name": slot, "matrix": matrix})
    result = {"303_1": patterns, "303_2": [], "808": [], "909": []}
    if drum_machine == "808":
        result["808"] = drum_patterns
    else:
        result["909"] = drum_patterns
    return result

def normalize_mod_lookup_key(name):
    if not name:
        return ""
    key = str(name).strip().lower()
    key = "".join(ch if ch.isalnum() else " " for ch in key)
    return " ".join(key.split())

def get_mod_screenshot_search_dirs(mod_path=None):
    search_dirs = [os.path.join(BASE_DIR, "Mods", "Screenshots")]
    if mod_path and os.path.exists(mod_path):
        mods_dir = os.path.dirname(mod_path)
        search_dirs.extend([
            os.path.join(mods_dir, "Screenshots"),
            mods_dir,
        ])
    unique_dirs = []
    seen = set()
    for folder in search_dirs:
        norm = os.path.normcase(os.path.abspath(folder))
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.isdir(folder):
            unique_dirs.append(folder)
    return unique_dirs

def build_mod_screenshot_index(search_dirs=None):
    index = {}
    for folder in search_dirs or get_mod_screenshot_search_dirs():
        try:
            for filename in os.listdir(folder):
                stem, ext = os.path.splitext(filename)
                if ext.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
                    continue
                full_path = os.path.join(folder, filename)
                key = normalize_mod_lookup_key(stem)
                if key and key not in index:
                    index[key] = full_path
        except OSError:
            continue
    return index

def get_cached_mod_screenshot_index(search_dirs=None):
    dirs = tuple(search_dirs or get_mod_screenshot_search_dirs())
    cache = _MOD_SCREENSHOT_INDEX_CACHE
    if cache["key"] == dirs:
        return cache["index"]
    cache["index"] = build_mod_screenshot_index(list(dirs))
    cache["key"] = dirs
    return cache["index"]

def invalidate_mod_screenshot_index_cache():
    _MOD_SCREENSHOT_INDEX_CACHE["key"] = None
    _MOD_SCREENSHOT_INDEX_CACHE["index"] = {}

def find_mod_screenshot_path_fast(mod_path=None, mod_name=None, screenshot_index=None, search_dirs=None):
    internal_name = (mod_name or "").strip()
    file_stem = os.path.splitext(os.path.basename(mod_path))[0] if mod_path else ""
    search_dirs = search_dirs or get_mod_screenshot_search_dirs(mod_path)
    if screenshot_index is None:
        screenshot_index = get_cached_mod_screenshot_index(search_dirs)

    lookup_keys = []
    for candidate in (internal_name, file_stem, mod_name):
        norm = normalize_mod_lookup_key(candidate)
        if norm and norm not in lookup_keys:
            lookup_keys.append(norm)

    aliases = get_mod_screenshot_aliases()
    for key in lookup_keys:
        alias_name = aliases.get(key)
        if not alias_name:
            continue
        if os.path.isabs(alias_name) and os.path.exists(alias_name):
            return alias_name
        for folder in search_dirs:
            direct = os.path.join(folder, alias_name)
            if os.path.exists(direct):
                return direct
            stem = os.path.splitext(alias_name)[0]
            for try_ext in (".png", ".jpg", ".jpeg", ".bmp"):
                candidate = os.path.join(folder, stem + try_ext)
                if os.path.exists(candidate):
                    return candidate

    for key in lookup_keys:
        hit = screenshot_index.get(key)
        if hit and os.path.exists(hit):
            return hit

    for key in lookup_keys:
        for idx_key, candidate in screenshot_index.items():
            if key == idx_key or key in idx_key or idx_key in key:
                if os.path.exists(candidate):
                    return candidate

    for stem in filter(None, {internal_name, file_stem, mod_name}):
        for folder in search_dirs:
            for ext in (".png", ".jpg", ".jpeg", ".bmp"):
                candidate = os.path.join(folder, stem + ext)
                if os.path.exists(candidate):
                    return candidate

    if internal_name and "standard" in internal_name.lower():
        return DEFAULT_SCREENSHOT if os.path.exists(DEFAULT_SCREENSHOT) else None
    if mod_name and "standard" in mod_name.lower():
        return DEFAULT_SCREENSHOT if os.path.exists(DEFAULT_SCREENSHOT) else None
    return DEFAULT_SCREENSHOT if os.path.exists(DEFAULT_SCREENSHOT) else None

def get_mod_screenshot_aliases():
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    aliases = (cfg or {}).get("mod_screenshot_map") or {}
    normalized = {}
    for mod_key, screenshot_name in aliases.items():
        norm_key = normalize_mod_lookup_key(mod_key)
        if norm_key and screenshot_name:
            normalized[norm_key] = str(screenshot_name).strip()
    return normalized

def find_mod_screenshot_path(mod_path=None, mod_name=None):
    internal_name = (mod_name or "").strip()
    file_stem = ""
    if mod_path and os.path.exists(mod_path):
        info = extract_rmb_mod_info(mod_path)
        parsed_name = (info.get("name") or "").strip()
        if parsed_name:
            internal_name = parsed_name
        file_stem = os.path.splitext(os.path.basename(mod_path))[0]

    lookup_keys = []
    for candidate in (internal_name, file_stem, mod_name):
        norm = normalize_mod_lookup_key(candidate)
        if norm and norm not in lookup_keys:
            lookup_keys.append(norm)

    search_dirs = get_mod_screenshot_search_dirs(mod_path)
    screenshot_index = build_mod_screenshot_index(search_dirs)
    aliases = get_mod_screenshot_aliases()

    for key in lookup_keys:
        alias_name = aliases.get(key)
        if not alias_name:
            continue
        if os.path.isabs(alias_name) and os.path.exists(alias_name):
            return alias_name
        for folder in search_dirs:
            direct = os.path.join(folder, alias_name)
            if os.path.exists(direct):
                return direct
            stem = os.path.splitext(alias_name)[0]
            for try_ext in (".png", ".jpg", ".jpeg", ".bmp"):
                candidate = os.path.join(folder, stem + try_ext)
                if os.path.exists(candidate):
                    return candidate

    for key in lookup_keys:
        hit = screenshot_index.get(key)
        if hit and os.path.exists(hit):
            return hit

    for key in lookup_keys:
        for idx_key, candidate in screenshot_index.items():
            if key == idx_key or key in idx_key or idx_key in key:
                if os.path.exists(candidate):
                    return candidate

    for stem in filter(None, {internal_name, file_stem, mod_name}):
        for folder in search_dirs:
            for ext in (".png", ".jpg", ".jpeg", ".bmp"):
                candidate = os.path.join(folder, stem + ext)
                if os.path.exists(candidate):
                    return candidate

    if internal_name and "standard" in internal_name.lower():
        return DEFAULT_SCREENSHOT if os.path.exists(DEFAULT_SCREENSHOT) else None
    if mod_name and "standard" in mod_name.lower():
        return DEFAULT_SCREENSHOT if os.path.exists(DEFAULT_SCREENSHOT) else None
    return DEFAULT_SCREENSHOT if os.path.exists(DEFAULT_SCREENSHOT) else None

def synthesize_303_pattern_pcm(steps, bpm=125, sample_rate=44100):
    note_freqs = {
        "C": 130.81, "C#": 138.59, "D": 146.83, "D#": 155.56, "E": 164.81, "F": 174.61,
        "F#": 185.00, "G": 196.00, "G#": 207.65, "A": 220.00, "A#": 233.08, "B": 246.94, "C5": 261.63
    }
    step_duration = 60.0 / bpm / 4.0
    num_samples_per_step = max(1, int(sample_rate * step_duration))
    pcm_samples = bytearray()

    step_info = []
    for step in steps:
        if step.get("active") and step.get("note") in note_freqs:
            freq = note_freqs[step["note"]]
            if step.get("up") == "^":
                freq *= 2.0
            elif step.get("up") == "v":
                freq *= 0.5
            step_info.append({
                "active": True,
                "freq": freq,
                "accent": step.get("accent") == "A",
                "slide": step.get("slide") == "S",
            })
        else:
            step_info.append({"active": False, "freq": 0.0, "accent": False, "slide": False})

    phase = 0.0
    filter_low = 0.0
    last_freq = 130.81
    current_freq = 130.81

    for step_idx, info in enumerate(step_info):
        target_freq = info["freq"] if info["active"] else 0.0
        slide_from_prev = (
            info["active"]
            and info["slide"]
            and step_idx > 0
            and step_info[step_idx - 1]["active"]
        )
        glide_start = last_freq if slide_from_prev else target_freq

        if info["active"]:
            if not slide_from_prev:
                phase = 0.0
                filter_low = 0.0
            last_freq = target_freq

        for i in range(num_samples_per_step):
            t = i / float(num_samples_per_step)

            if info["active"]:
                if slide_from_prev and t < 0.65:
                    glide = t / 0.65
                    current_freq = glide_start + (target_freq - glide_start) * glide
                else:
                    current_freq = target_freq
            elif slide_from_prev and t < 0.25:
                current_freq = glide_start * (1.0 - t / 0.25)
            else:
                pcm_samples.extend(struct.pack("<h", 0))
                continue

            phase += (2.0 * math.pi * current_freq) / sample_rate
            saw = 2.0 * ((phase / (2.0 * math.pi)) % 1.0) - 1.0

            cutoff_peak = min(9000.0, current_freq * 5.5 + (2200.0 if info["accent"] else 900.0))
            cutoff_now = cutoff_peak * (0.35 + 0.65 * math.exp(-t * (4.0 if info["accent"] else 6.5)))
            f_norm = min(0.35, cutoff_now / sample_rate)
            filter_low += f_norm * (saw - filter_low)

            env = math.exp(-t * (3.0 if info["accent"] else 5.0))
            amp = 12000 if info["accent"] else 8500
            sample_val = int(filter_low * env * amp)
            sample_val = max(-32767, min(32767, sample_val))
            pcm_samples.extend(struct.pack("<h", sample_val))

    return pcm_samples

def synthesize_303_pattern_audio(steps, bpm=125, sample_rate=44100):
    pcm_samples = synthesize_303_pattern_pcm(steps, bpm=bpm, sample_rate=sample_rate)
    temp_path = os.path.join(os.environ.get("TEMP", BASE_DIR), "acid_303_audition.wav")
    try:
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_samples)
        return temp_path
    except Exception:
        return None

def synthesize_303_step_audition_wav(step, bpm=125, sample_rate=44100):
    if not step or not step.get("active"):
        return None
    steps = empty_303_steps()
    steps[0] = step
    temp_path = os.path.join(os.environ.get("TEMP", BASE_DIR), "acid_303_step_audition.wav")
    try:
        pcm_samples = synthesize_303_pattern_pcm(steps, bpm=bpm, sample_rate=sample_rate)
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_samples)
        return temp_path
    except Exception:
        return None

def synthesize_drum_hit_audition_wav(inst_label, accent=False, is_909=True, bpm=125, sample_rate=44100):
    if not inst_label:
        return None
    matrix = empty_drum_matrix(is_909)
    if inst_label not in matrix:
        return None
    step_duration = 60.0 / bpm / 4.0
    num_samples = max(1, int(sample_rate * step_duration * 2))
    voice = DRUM_VOICE_MAP.get(inst_label, "snare")
    temp_path = os.path.join(os.environ.get("TEMP", BASE_DIR), "acid_drum_hit_audition.wav")
    try:
        voice_samples = synthesize_drum_voice(
            voice,
            num_samples,
            sample_rate,
            accent=accent if accent else False,
            seed=len(inst_label) * 1.7,
        )
        peak = max((abs(v) for v in voice_samples), default=1.0)
        if peak > 30000.0:
            scale = 30000.0 / peak
            voice_samples = [v * scale for v in voice_samples]
        pcm_samples = b"".join(
            struct.pack("<h", int(max(-32767, min(32767, v)))) for v in voice_samples
        )
        pcm_samples = normalize_pcm16le_bytes(pcm_samples)
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_samples)
        return temp_path
    except Exception:
        return None

def play_audition_wav(wav_path):
    if not wav_path or not os.path.exists(wav_path):
        return False
    if HAS_WINSOUND:
        try:
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        except Exception:
            pass
    return play_audio_file(wav_path)

def stop_sample_playback():
    stop_wav_playback()

def play_mod_sample_wav(wav_path):
    """Play a cached drum-sample WAV synchronously from disk (best for short hits)."""
    if not wav_path or not os.path.exists(wav_path):
        return False
    stop_wav_playback()

    def worker():
        with _sample_play_lock:
            play_wav_sync(wav_path)

    threading.Thread(target=worker, daemon=True).start()
    return True

def _pseudo_noise(index, seed=0.0):
    return (math.sin((index + 1) * 12.9898 + seed * 78.233) * 43758.5453) % 1.0 * 2.0 - 1.0

def synthesize_drum_voice(voice, num_samples, sample_rate, accent=False, seed=0.0):
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        if voice in ("kick", "kick_low", "kick_mid", "kick_high"):
            base = {"kick": 58.0, "kick_low": 42.0, "kick_mid": 68.0, "kick_high": 88.0}[voice]
            freq = base * (1.0 + 4.5 * math.exp(-t * 38.0))
            env = math.exp(-t * (9.0 if accent else 13.0))
            val = math.sin(2.0 * math.pi * freq * t) * env * (14000.0 if accent else 11000.0)
        elif voice in ("snare", "clap"):
            env = math.exp(-t * (13.0 if voice == "snare" else 17.0))
            noise = _pseudo_noise(i, seed)
            tone = math.sin(2.0 * math.pi * 180.0 * t) * math.exp(-t * 22.0)
            val = (noise * 0.78 + tone * 0.22) * env * (10500.0 if accent else 8200.0)
        elif voice == "rim":
            env = math.exp(-t * 32.0)
            val = math.sin(2.0 * math.pi * 330.0 * t) * env * 6200.0
        elif voice == "hihat_closed":
            env = math.exp(-t * 42.0)
            val = _pseudo_noise(i, seed + 1.7) * env * 4800.0
        elif voice == "hihat_open":
            env = math.exp(-t * 11.0)
            val = _pseudo_noise(i, seed + 3.1) * env * 5800.0
        elif voice in ("crash", "ride", "cowbell"):
            env = math.exp(-t * (8.0 if voice == "crash" else 12.0))
            freq = 420.0 if voice == "cowbell" else (320.0 if voice == "ride" else 260.0)
            val = (_pseudo_noise(i, seed) * 0.65 + math.sin(2.0 * math.pi * freq * t) * 0.35) * env * 7000.0
        else:
            env = math.exp(-t * 20.0)
            val = _pseudo_noise(i, seed) * env * 5000.0
        samples.append(val)
    return samples

DRUM_VOICE_MAP = {
    "BD": "kick", "LT": "kick_low", "MT": "kick_mid", "HT": "kick_high",
    "SD": "snare", "RS": "rim", "CP": "clap", "AC": "clap",
    "CH": "hihat_closed", "OH": "hihat_open", "CY": "crash", "CC": "crash", "CB": "cowbell", "RC": "ride",
}

def synthesize_drum_pattern_pcm(matrix, bpm=125, sample_rate=44100):
    step_duration = 60.0 / bpm / 4.0
    num_samples_per_step = max(1, int(sample_rate * step_duration))
    total_samples = num_samples_per_step * 16
    mix = [0.0] * total_samples

    for s in range(16):
        step_start = s * num_samples_per_step
        for lbl, hits in matrix.items():
            hit = hits[s] if s < len(hits) else "."
            if hit not in ("x", "A", "F"):
                continue
            accent = hit == "A"
            voice = DRUM_VOICE_MAP.get(lbl, "snare")
            voice_samples = synthesize_drum_voice(voice, num_samples_per_step, sample_rate, accent=accent, seed=s * 1.9 + len(lbl))
            for i, val in enumerate(voice_samples):
                idx = step_start + i
                if idx < total_samples:
                    mix[idx] += val

    peak = max((abs(v) for v in mix), default=1.0)
    if peak > 30000.0:
        scale = 30000.0 / peak
        mix = [v * scale for v in mix]
    return b"".join(struct.pack("<h", int(max(-32767, min(32767, v)))) for v in mix)

def mix_pcm_buffers(pcm_a, pcm_b, gain_a=0.82, gain_b=0.95):
    count_a = len(pcm_a) // 2
    count_b = len(pcm_b) // 2
    total = max(count_a, count_b)
    mixed = bytearray()
    for i in range(total):
        sa = 0
        sb = 0
        if i < count_a:
            sa = struct.unpack("<h", pcm_a[i * 2:i * 2 + 2])[0]
        if i < count_b:
            sb = struct.unpack("<h", pcm_b[i * 2:i * 2 + 2])[0]
        val = int(sa * gain_a + sb * gain_b)
        mixed.extend(struct.pack("<h", max(-32767, min(32767, val))))
    return mixed

def synthesize_acid_preview_audio(steps, drum_matrix=None, bpm=128, sample_rate=44100):
    pcm_303 = synthesize_303_pattern_pcm(steps, bpm=bpm, sample_rate=sample_rate)
    if drum_matrix:
        pcm_drums = synthesize_drum_pattern_pcm(drum_matrix, bpm=bpm, sample_rate=sample_rate)
        pcm_data = mix_pcm_buffers(pcm_303, pcm_drums)
    else:
        pcm_data = pcm_303
    temp_path = os.path.join(os.environ.get("TEMP", BASE_DIR), "acid_full_preview.wav")
    try:
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return temp_path
    except Exception:
        return None

def write_var_len(val):
    buf = bytearray()
    buf.append(val & 0x7F)
    val >>= 7
    while val > 0:
        buf.insert(0, (val & 0x7F) | 0x80)
        val >>= 7
    return buf

REBIRTH_TICKS_PER_BAR = 768
MIDI_PPQ = 96
MIDI_TICKS_PER_BAR = MIDI_PPQ * 4
MIDI_TICKS_PER_STEP = MIDI_TICKS_PER_BAR // 16

def read_rbs_var_len(data, offset):
    val = 0
    start = offset
    while offset < len(data):
        b = data[offset]
        offset += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return val, offset - start

def pattern_index_to_slot(pat_idx):
    pat_idx = max(0, min(31, int(pat_idx)))
    return f"{chr(65 + pat_idx // 8)}{pat_idx % 8 + 1}"

def parse_rbs_trak_chunks(content):
    tracks = []
    pos = 0
    while True:
        idx = content.find(b"TRAK", pos)
        if idx == -1:
            break
        if len(content) < idx + 8:
            break
        num_events = struct.unpack(">I", content[idx + 4 : idx + 8])[0]
        ev_off = idx + 8
        accum = 0
        events = []
        for _ in range(num_events):
            if ev_off >= len(content):
                break
            delta, consumed = read_rbs_var_len(content, ev_off)
            ev_off += consumed
            if ev_off + 1 >= len(content):
                break
            cid = content[ev_off]
            cval = content[ev_off + 1]
            ev_off += 2
            accum += delta
            events.append((accum, cid, cval))
        tracks.append(events)
        pos = idx + 4
    return tracks

def get_device_selected_patterns(content):
    defaults = {"303_1": 0, "303_2": 0, "808": 0, "909": 0}
    for key, tag, occ in (
        ("303_1", b"303 ", 0),
        ("303_2", b"303 ", 1),
        ("808", b"808 ", 0),
        ("909", b"909 ", 0),
    ):
        cidx = find_rbs_chunk(content, tag, occurrence=occ)
        if cidx != -1 and len(content) > cidx + 9:
            defaults[key] = content[cidx + 8 + 1]
    return defaults

def build_pattern_timeline(trak_events, total_rebirth_ticks, default_pattern=0):
    changes = [(0, default_pattern)]
    for pos, cid, cval in trak_events:
        if cid == 0x01:
            changes.append((pos, cval))
    changes.sort(key=lambda item: item[0])
    deduped = []
    for pos, pat in changes:
        if deduped and deduped[-1][0] == pos:
            deduped[-1] = (pos, pat)
        else:
            deduped.append((pos, pat))
    timeline = []
    for i, (start, pat_idx) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else total_rebirth_ticks
        if end > start:
            timeline.append((start, end, pat_idx))
    return timeline

def rebirth_pos_to_midi_tick(rebirth_pos):
    return int(rebirth_pos * MIDI_TICKS_PER_BAR / REBIRTH_TICKS_PER_BAR)

def pattern_lookup_from_deconstructed(deconstructed):
    lookup = {"303_1": {}, "303_2": {}, "808": {}, "909": {}}
    for key in lookup:
        for pat in deconstructed.get(key, []):
            lookup[key][pat["name"]] = pat
    return lookup

def resolve_pattern_data(lookup, device_key, pat_idx):
    slot = pattern_index_to_slot(pat_idx)
    pat = lookup.get(device_key, {}).get(slot)
    if pat:
        return pat
    items = list(lookup.get(device_key, {}).values())
    return items[0] if items else None

def export_rbs_to_midi(rbs_path, midi_out_path, deconstructed=None, bpm=None):
    meta = parse_rbs_metadata(rbs_path) if rbs_path else {}
    if deconstructed is None:
        deconstructed = deconstruct_rbs_song(rbs_path)
    if bpm is None:
        bpm = meta.get("bpm") or 120.0
    bpm = max(20.0, min(999.0, float(bpm)))

    step_ticks = MIDI_TICKS_PER_STEP
    note_pitch_map = {"C": 48, "C#": 49, "D": 50, "D#": 51, "E": 52, "F": 53, "F#": 54, "G": 55, "G#": 56, "A": 57, "A#": 58, "B": 59, "C5": 60}
    drum_gm_map = {"BD": 36, "SD": 38, "LT": 43, "MT": 47, "HT": 50, "RS": 37, "CP": 39, "CB": 56, "CY": 49, "OH": 46, "CH": 42, "CC": 49, "RC": 51}
    timed_events = []

    def add_event(tick, msg_bytes):
        timed_events.append((tick, msg_bytes))

    us_per_beat = int(60000000 / bpm)
    add_event(0, b"\xFF\x51\x03" + struct.pack(">I", us_per_beat)[1:])
    add_event(0, bytes([0xC0, 81]))
    add_event(0, bytes([0xC1, 81]))
    add_event(0, bytes([0xC9, 0]))

    def emit_303_steps(steps, channel_idx, start_tick):
        tick = start_tick
        for s in steps:
            if s["active"] and s["note"] in note_pitch_map:
                base_p = note_pitch_map[s["note"]]
                if s["up"] == "^":
                    base_p += 12
                elif s["up"] == "v":
                    base_p -= 12
                vel = 127 if s["accent"] == "A" else 96
                dur = min(step_ticks * 2 if s["slide"] == "S" else int(step_ticks * 0.85), step_ticks - 1)
                dur = max(1, dur)
                add_event(tick, bytes([0x90 | channel_idx, base_p, vel]))
                add_event(tick + dur, bytes([0x80 | channel_idx, base_p, 0]))
            tick += step_ticks

    def emit_drum_matrix(matrix, start_tick):
        tick = start_tick
        note_dur = max(1, step_ticks // 2)
        for s_idx in range(16):
            hits = []
            for inst_lbl, inst_hits in matrix.items():
                h = inst_hits[s_idx]
                if h in ("x", "A", "F") and inst_lbl in drum_gm_map:
                    vel = 127 if h == "A" else 96
                    hits.append((drum_gm_map[inst_lbl], vel))
            for note_p, vel in hits:
                add_event(tick, bytes([0x99, note_p, vel]))
                add_event(tick + note_dur, bytes([0x89, note_p, 0]))
            tick += step_ticks

    def emit_pattern_bar(device_key, pat_data, bar_rebirth_pos):
        if not pat_data:
            return
        midi_tick = rebirth_pos_to_midi_tick(bar_rebirth_pos)
        if device_key.startswith("303"):
            channel_idx = 0 if device_key == "303_1" else 1
            emit_303_steps(pat_data["steps"], channel_idx, midi_tick)
        else:
            emit_drum_matrix(pat_data["matrix"], midi_tick)

    lookup = pattern_lookup_from_deconstructed(deconstructed)

    if not rbs_path:
        bar_tick = 0
        for pat in deconstructed.get("303_1", []):
            emit_303_steps(pat["steps"], 0, bar_tick)
            bar_tick += MIDI_TICKS_PER_BAR
        for pat in deconstructed.get("303_2", []):
            emit_303_steps(pat["steps"], 1, bar_tick)
            bar_tick += MIDI_TICKS_PER_BAR
        drum_patterns = deconstructed.get("808") or deconstructed.get("909") or []
        for pat in drum_patterns:
            emit_drum_matrix(pat["matrix"], bar_tick)
            bar_tick += MIDI_TICKS_PER_BAR
    else:
        content = b""
        with open(rbs_path, "rb") as f:
            content = f.read()

        total_bars = meta.get("total_bars") or 0
        loop_end = meta.get("loop_end") or 0
        loop_start = max(1, meta.get("loop_start") or 1)
        if meta.get("mode") == "Song Mode" and loop_end >= loop_start:
            export_bars = loop_end - loop_start + 1
            start_bar = loop_start - 1
        elif total_bars > 0:
            export_bars = total_bars
            start_bar = 0
        else:
            export_bars = 4
            start_bar = 0

        total_rebirth_ticks = export_bars * REBIRTH_TICKS_PER_BAR
        start_rebirth = start_bar * REBIRTH_TICKS_PER_BAR
        end_rebirth = start_rebirth + total_rebirth_ticks

        trak_tracks = parse_rbs_trak_chunks(content)
        device_defaults = get_device_selected_patterns(content)
        device_trak_index = {"303_1": 1, "303_2": 2, "808": 3, "909": 4}

        for device_key, trak_idx in device_trak_index.items():
            if not lookup.get(device_key):
                continue
            trak_events = trak_tracks[trak_idx] if trak_idx < len(trak_tracks) else []
            timeline = build_pattern_timeline(
                trak_events,
                end_rebirth,
                device_defaults.get(device_key, 0),
            )
            if not timeline:
                timeline = [(start_rebirth, end_rebirth, device_defaults.get(device_key, 0))]

            for seg_start, seg_end, pat_idx in timeline:
                seg_start = max(seg_start, start_rebirth)
                seg_end = min(seg_end, end_rebirth)
                if seg_end <= seg_start:
                    continue
                bar = (seg_start // REBIRTH_TICKS_PER_BAR) * REBIRTH_TICKS_PER_BAR
                if bar < start_rebirth:
                    bar += REBIRTH_TICKS_PER_BAR
                pat_data = resolve_pattern_data(lookup, device_key, pat_idx)
                while bar < seg_end:
                    emit_pattern_bar(device_key, pat_data, bar)
                    bar += REBIRTH_TICKS_PER_BAR

    note_events = [ev for ev in timed_events if not ev[1].startswith(b"\xFF")]
    if not note_events:
        return False

    timed_events.sort(key=lambda item: (item[0], 0 if (item[1][0] & 0xF0) != 0x80 else 1))
    track_name = f"ReBirth @ {bpm:g} BPM".encode("latin-1", errors="ignore")[:127]
    track = bytearray()
    track.extend(write_var_len(0) + b"\xFF\x03" + bytes([len(track_name)]) + track_name)
    last_tick = 0
    for tick, msg in timed_events:
        delta = max(0, tick - last_tick)
        track.extend(write_var_len(delta))
        track.extend(msg)
        last_tick = tick
    track.extend(write_var_len(0) + b"\xFF\x2F\x00")

    hdr = bytearray(b"MThd\x00\x00\x00\x06\x00\x00")
    hdr.extend(struct.pack(">H", 1))
    hdr.extend(struct.pack(">H", MIDI_PPQ))

    with open(midi_out_path, "wb") as f:
        f.write(hdr)
        f.write(b"MTrk" + struct.pack(">I", len(track)) + track)
    return True

def export_html_cheatsheet(song_path, html_out_path):
    meta = parse_rbs_metadata(song_path)
    deconstructed = deconstruct_rbs_song(song_path)
    title = meta["title"] or os.path.basename(song_path)
    bpm_val = str(meta["bpm"]) if meta["bpm"] else "N/A"

    lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<title>ReBirth ToolBox Cheat Sheet - {title}</title>",
        "<style>",
        "body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #12131A; color: #E0E0E0; margin: 20px; }",
        "h1 { color: #00E5FF; border-bottom: 2px solid #00E5FF; padding-bottom: 5px; }",
        ".meta-box { background: #1A1C27; padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; border: 1px solid #282B3C; }",
        "table { border-collapse: collapse; width: 100%; margin-bottom: 25px; background: #1A1C27; font-family: monospace; font-size: 13px; }",
        "th, td { border: 1px solid #282B3C; padding: 6px 8px; text-align: center; }",
        "th { background: #242736; color: #00FF66; }",
        ".active-step { background: #003311; color: #00FF66; font-weight: bold; }",
        ".drum-hit { background: #4A2800; color: #FF9500; font-weight: bold; }",
        "@media print { body { background: white; color: black; } table, th, td { border-color: #666; } th { background: #eee; color: black; } .active-step { background: #ddffdd; color: black; } .drum-hit { background: #ffeedd; color: black; } }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>Studio Cheat Sheet: {title}</h1>",
        "<div class='meta-box'>",
        f"  <strong>Tempo:</strong> {bpm_val} BPM | <strong>Mode:</strong> {meta['mode']} | <strong>Mod Skin:</strong> {meta['mod_name']}<br>",
        f"  <strong>Active Patterns:</strong> {meta['active_patterns']} total ({meta['pattern_breakdown']})<br>",
        f"  <strong>Comments:</strong> {meta['comments']}",
        "</div>"
    ]

    for dev_k, dev_name in [("303_1", "TB-303 #1"), ("303_2", "TB-303 #2")]:
        pats = deconstructed.get(dev_k, [])
        if pats:
            lines.append(f"<h2>{dev_name} Patterns</h2>")
            for p in pats:
                step_headers = "".join([f"<th>{i+1:02d}</th>" for i in range(16)])
                lines.append(f"<h3>Pattern {p['name']}</h3><table><tr><th>Attr / Step</th>{step_headers}</tr>")
                notes_row = "".join([f"<td class='active-step'>{s['note']}</td>" if s['active'] else "<td>--</td>" for s in p['steps']])
                lines.append(f"<tr><td><strong>Note Pitch</strong></td>{notes_row}</tr>")
                attrs_row = "".join([f"<td>{s['up']}{s['accent']}{s['slide']}</td>" for s in p['steps']])
                lines.append(f"<tr><td><strong>Octave / Accent / Slide</strong></td>{attrs_row}</tr></table>")

    for drum_k, drum_name in [("808", "TR-808 Drums"), ("909", "TR-909 Drums")]:
        pats = deconstructed.get(drum_k, [])
        if pats:
            lines.append(f"<h2>{drum_name} Patterns</h2>")
            for p in pats:
                step_headers = "".join([f"<th>{i+1:02d}</th>" for i in range(16)])
                lines.append(f"<h3>Pattern {p['name']}</h3><table><tr><th>Inst / Step</th>{step_headers}</tr>")
                for inst_lbl, hits in p['matrix'].items():
                    hits_row = "".join([f"<td class='drum-hit'>{h}</td>" if h != "." else "<td>.</td>" for h in hits])
                    lines.append(f"<tr><td><strong>{inst_lbl}</strong></td>{hits_row}</tr>")
                lines.append("</table>")

    lines.append("<p><small>Exported via ReBirth ToolBox</small></p></body></html>")
    with open(html_out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return True

def generate_mod_rbs(mod_name, output_path, source_rbs_path=None):
    try:
        if source_rbs_path and os.path.exists(source_rbs_path):
            with open(source_rbs_path, "rb") as f:
                content = bytearray(f.read())
        else:
            content = bytearray(base64.b64decode(DEFAULT_CLEAN_RBS_B64))

        return patch_rbs_mod_name_bytes(content, mod_name, output_path)
    except Exception:
        return False

def patch_rbs_mod_name_bytes(content, mod_name, output_path):
    glob_idx = find_rbs_chunk(content, b"GLOB")
    if glob_idx == -1:
        glob_idx = content.find(b"GLOB")
    if glob_idx == -1 or len(content) < glob_idx + 8 + 80:
        return False
    mod_bytes = (mod_name or "Standard ReBirth").encode("latin-1", errors="ignore")[:64]
    content[glob_idx + 8 + 15 : glob_idx + 8 + 80] = mod_bytes.ljust(65, b"\x00")
    with open(output_path, "wb") as f:
        f.write(content)
    return True

def patch_rbs_mod_name(source_path, mod_name, output_path=None):
    if not source_path or not os.path.exists(source_path):
        return False
    output_path = output_path or source_path
    try:
        with open(source_path, "rb") as f:
            content = bytearray(f.read())
        return patch_rbs_mod_name_bytes(content, mod_name, output_path)
    except Exception:
        return False

def extract_prbm_info_fields(data):
    """
    PRBM/.rbm files store the ReBirth-visible mod name in a trailing INFO chunk
    (1280 bytes payload). Short title sits at a fixed offset; long blurb at the start.
    Example: file afx-1.rbm → INFO name \"AFX 1\" (what ReBirth lists / requires).
    """
    title = ""
    comments = ""
    if not data or len(data) < 64:
        return title, comments
    info_idx = -1
    # Prefer INFO near EOF with classic 0x0500 payload size
    search_from = max(0, len(data) - 4096)
    pos = search_from
    while True:
        idx = data.find(b"INFO", pos)
        if idx == -1:
            break
        if idx + 8 <= len(data):
            size = struct.unpack(">I", data[idx + 4 : idx + 8])[0]
            if size in (0x500, 1280) and idx + 8 + size <= len(data):
                info_idx = idx
        pos = idx + 4
    if info_idx == -1:
        # Fallback: name often sits 277 bytes before EOF in stock PRBM packs
        name_off = len(data) - 277
        if name_off > 0:
            raw = data[name_off : name_off + 64].split(b"\x00")[0]
            try:
                title = raw.decode("latin-1", errors="ignore").strip()
            except Exception:
                title = ""
        return title, comments

    payload = data[info_idx + 8 : info_idx + 8 + 1280]
    comments = payload[:240].split(b"\x00")[0].decode("latin-1", errors="ignore").strip()
    # Short name at offset 1003 within INFO payload (verified across AFX / 707 / CHEZIO)
    if len(payload) >= 1003 + 4:
        title = payload[1003 : 1003 + 64].split(b"\x00")[0].decode("latin-1", errors="ignore").strip()
    if not title:
        name_off = len(data) - 277
        if name_off > 0:
            raw = data[name_off : name_off + 64].split(b"\x00")[0]
            title = raw.decode("latin-1", errors="ignore").strip()
    return title, comments

def get_rmb_internal_mod_name(rmb_path):
    if not rmb_path or not os.path.exists(rmb_path):
        return ""
    try:
        with open(rmb_path, "rb") as f:
            data = f.read()
        glob_name = extract_rmb_string_field(data, b"GLOB", 15, 65)
        if glob_name and not is_generic_mod_name(glob_name) and not is_junk_mod_text(glob_name):
            return glob_name
        info_title, _comments = extract_prbm_info_fields(data)
        if info_title and not is_generic_mod_name(info_title) and not is_system_mod_folder_name(info_title):
            return info_title
        return info_title or glob_name or ""
    except Exception:
        return ""

def patch_rmb_internal_mod_name(rmb_path, mod_name):
    if not rmb_path or not os.path.exists(rmb_path):
        return False
    try:
        with open(rmb_path, "rb") as f:
            content = bytearray(f.read())
        glob_idx = find_rbs_chunk(content, b"GLOB")
        if glob_idx == -1:
            glob_idx = content.find(b"GLOB")
        if glob_idx == -1 or len(content) < glob_idx + 8 + 80:
            return False
        mod_bytes = (mod_name or "").encode("latin-1", errors="ignore")[:64]
        content[glob_idx + 8 + 15 : glob_idx + 8 + 80] = mod_bytes.ljust(65, b"\x00")
        with open(rmb_path, "wb") as f:
            f.write(content)
        return True
    except Exception:
        return False

def mod_names_match(required, candidate):
    req = (required or "").strip()
    cand = (candidate or "").strip()
    if not req or not cand:
        return False
    if req.lower() == cand.lower():
        return True
    req_key = normalize_mod_lookup_key(req)
    cand_key = normalize_mod_lookup_key(cand)
    if req_key == cand_key:
        return True
    if req_key in cand_key or cand_key in req_key:
        shorter = min(len(req_key), len(cand_key))
        if shorter >= 8:
            return True
    req_compact = req_key.replace(" ", "")
    cand_compact = cand_key.replace(" ", "")
    if req_compact == cand_compact:
        return True
    return False

def ensure_mod_in_rebirth_mods_folder(mod_path):
    if not mod_path or not os.path.exists(mod_path):
        return mod_path
    mods_root = os.path.abspath(MODS_DIR)
    mod_abs = os.path.abspath(mod_path)
    if os.path.normcase(os.path.dirname(mod_abs)) == os.path.normcase(mods_root):
        return mod_abs
    os.makedirs(mods_root, exist_ok=True)
    dest = os.path.join(mods_root, os.path.basename(mod_path))
    if os.path.normcase(mod_abs) != os.path.normcase(dest):
        if not os.path.exists(dest):
            shutil.copy2(mod_abs, dest)
        return dest
    return mod_abs

def prepare_rebirth_launch_song(song_path, mod_path=None):
    if not song_path or not os.path.exists(song_path):
        return song_path
    if not mod_path or not os.path.exists(mod_path):
        return song_path

    internal_name = resolve_mod_rebirth_name(mod_path)
    if not internal_name:
        return song_path

    meta = parse_rbs_metadata(song_path)
    required_name = (meta.get("mod_name") or "Standard ReBirth").strip()
    if not required_name or required_name == "Standard ReBirth":
        return song_path
    if required_name == internal_name:
        return song_path

    cache_path = _launch_cache_path(song_path, internal_name)
    if patch_rbs_mod_name(song_path, internal_name, cache_path):
        return cache_path
    return song_path

def _launch_cache_path(song_path, mod_name):
    cache_dir = os.path.join(DEFAULT_SONGS_DIR, "_LaunchCache")
    os.makedirs(cache_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(song_path))[0]
    mod_slug = "".join(c if c.isalnum() else "_" for c in mod_name).strip("_")[:40] or "Mod"
    return os.path.join(cache_dir, f"{base}__{mod_slug}.rbs")

def resolve_mod_rebirth_name(mod_path, fallback_name=""):
    internal = get_rmb_internal_mod_name(mod_path) if mod_path else ""
    if internal and not is_generic_mod_name(internal) and not is_system_mod_folder_name(internal):
        return internal
    if fallback_name and not is_system_mod_folder_name(fallback_name) and not is_generic_mod_name(fallback_name):
        return fallback_name
    if mod_path:
        stem = preferred_mod_file_stem(mod_path)
        if stem:
            return stem
    return "Standard ReBirth"

def is_generic_mod_name(name):
    norm = normalize_mod_lookup_key(name)
    if not norm:
        return True
    if norm in GENERIC_MOD_NAMES:
        return True
    return norm.startswith("template mod")

def is_junk_mod_text(text):
    raw = (text or "").strip()
    if not raw:
        return True
    lower = raw.lower()
    if is_generic_mod_name(raw):
        return True
    if re.search(r"\(c\)|copyright|©|all rights reserved|\b19\d{2}\b|\b20\d{2}\b", lower):
        return True
    # Pure punctuation / symbols only (digit-only stems like "707-727" are valid mod names)
    if re.fullmatch(r"[\W_]+", raw):
        return True
    if len(raw) <= 1:
        return True
    return False

def prettify_mod_filename(filename):
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    if not stem:
        return ""
    stem = stem.replace("_", " ").replace("-", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    words = []
    for raw in stem.split(" "):
        token = raw.strip()
        if not token:
            continue
        if token.isupper() and len(token) <= 6:
            words.append(token)
        elif token[:1].isdigit():
            words.append(token)
        else:
            words.append(token[:1].upper() + token[1:])
    return " ".join(words) or stem

def load_mod_catalog_metadata():
    if not os.path.isfile(MOD_CATALOG_FILE):
        return {}
    try:
        with open(MOD_CATALOG_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return {}
    catalog = {}
    entries = payload.get("mods") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return catalog
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        filename = (entry.get("filename") or entry.get("file") or "").strip()
        if not filename:
            continue
        catalog[filename.lower()] = entry
    return catalog

def get_mod_catalog_entry(mod_path):
    if not mod_path:
        return {}
    filename = os.path.basename(mod_path)
    return load_mod_catalog_metadata().get(filename.lower(), {})

def extract_rmb_string_field(data, chunk_tag, offset, max_len):
    idx = find_rbs_chunk(data, chunk_tag) if isinstance(data, (bytes, bytearray)) else -1
    if idx == -1:
        idx = data.find(chunk_tag) if isinstance(data, (bytes, bytearray)) else -1
    if idx == -1:
        return ""
    start = idx + 8 + offset
    end = start + max_len
    if len(data) < end:
        return ""
    raw = data[start:end].split(b"\x00")[0]
    return raw.decode("latin-1", errors="ignore").strip()

def is_system_mod_folder_name(name):
    key = normalize_mod_lookup_key(name)
    return key in {
        "mods", "screenshots", "documents", "songs", "default songs", "demo songs",
        "downloads", "patternbanks", "previews", ".previews", ".sidecar",
        ".sample_cache", ".sample_cache_v2", ".sample_cache_v3", ".sample_cache_v4",
        ".sample_cache_v5", ".sample_cache_v6", ".sample_cache_v7", "toolbox_cache",
    }

def preferred_mod_file_stem(filename):
    """File stem fallback only — prefer INFO/GLOB names from extract_rmb_mod_info."""
    return os.path.splitext(os.path.basename(filename or ""))[0].strip()

def extract_rmb_mod_info(rmb_path):
    info = {"name": "", "rebirth_name": "", "comments": "Custom ReBirth Mod Skin Pack.", "filename": ""}
    if not rmb_path or not os.path.exists(rmb_path):
        return info
    info["filename"] = os.path.basename(rmb_path)
    catalog_entry = get_mod_catalog_entry(rmb_path)
    raw_stem = preferred_mod_file_stem(info["filename"])
    file_title = prettify_mod_filename(info["filename"]) or raw_stem
    try:
        with open(rmb_path, "rb") as f:
            data = f.read()

        glob_name = (extract_rmb_string_field(data, b"GLOB", 15, 65) or "").strip()
        usri_title = (extract_rmb_string_field(data, b"USRI", 0, 41) or "").strip()
        usri_comments = (extract_rmb_string_field(data, b"USRI", 41, 201) or "").strip()
        info_title, info_comments = extract_prbm_info_fields(data)
        parent_raw = os.path.basename(os.path.dirname(rmb_path))
        parent_title = prettify_mod_filename(parent_raw) if not is_system_mod_folder_name(parent_raw) else ""

        # Display name: ReBirth INFO/GLOB titles first (AFX 1, TR 727 & 707), never folder "Mods".
        candidates = []
        for candidate, allow_filename_fallback in (
            (info_title, False),
            ((catalog_entry or {}).get("title"), False),
            (glob_name, False),
            (usri_title, False),
            (file_title, True),
            (raw_stem, True),
            (parent_title, False),
        ):
            clean = (candidate or "").strip()
            if not clean or clean in candidates:
                continue
            if not allow_filename_fallback and is_junk_mod_text(clean):
                continue
            if is_system_mod_folder_name(clean):
                continue
            candidates.append(clean)

        info["name"] = candidates[0] if candidates else (file_title or raw_stem or "Unknown Mod")

        # Launch identity must match what ReBirth lists in its Mods menu.
        if glob_name and not is_generic_mod_name(glob_name) and not is_junk_mod_text(glob_name):
            info["rebirth_name"] = glob_name
        elif info_title and not is_generic_mod_name(info_title) and not is_system_mod_folder_name(info_title):
            info["rebirth_name"] = info_title
        else:
            info["rebirth_name"] = info["name"] or raw_stem

        comment_candidates = [
            (catalog_entry or {}).get("description"),
            info_comments,
            usri_comments,
        ]
        for comment in comment_candidates:
            clean = (comment or "").replace("\r", " ").strip()
            if clean and not is_junk_mod_text(clean) and len(clean) > 8:
                info["comments"] = clean
                break
    except Exception:
        pass

    if not info["name"]:
        info["name"] = file_title or raw_stem or os.path.splitext(info["filename"])[0]
    if not info.get("rebirth_name"):
        info["rebirth_name"] = info["name"] or raw_stem
    return info

def extract_embedded_image_candidates(data):
    candidates = []
    if not data:
        return candidates

    pos = 0
    while pos < len(data):
        idx = data.find(b"BM", pos)
        if idx == -1:
            break
        if idx + 26 <= len(data):
            try:
                file_size = struct.unpack("<I", data[idx + 2 : idx + 6])[0]
                if 128 <= file_size <= len(data) - idx:
                    width = abs(struct.unpack("<i", data[idx + 18 : idx + 22])[0])
                    height = abs(struct.unpack("<i", data[idx + 22 : idx + 26])[0])
                    if 16 <= width <= 4096 and 16 <= height <= 4096:
                        candidates.append((width * height, idx, file_size, "bmp"))
            except Exception:
                pass
        pos = idx + 2

    pos = 0
    while pos < len(data):
        idx = data.find(b"\x89PNG\r\n\x1a\n", pos)
        if idx == -1:
            break
        end = data.find(b"IEND", idx)
        if end != -1:
            end += 8
            if end <= len(data):
                size = end - idx
                if size >= 128:
                    candidates.append((size, idx, size, "png"))
        pos = idx + 8

    pos = 0
    while pos < len(data):
        idx = data.find(b"\xff\xd8\xff", pos)
        if idx == -1:
            break
        end = data.find(b"\xff\xd9", idx + 3)
        if end != -1:
            end += 2
            size = end - idx
            if size >= 128:
                candidates.append((size, idx, size, "jpg"))
        pos = idx + 3

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates

def extract_rmb_preview_image_path(rmb_path):
    if not rmb_path or not os.path.exists(rmb_path) or not HAS_PIL:
        return None
    cache_dir = os.path.join(BASE_DIR, "Mods", ".previews")
    os.makedirs(cache_dir, exist_ok=True)
    source_mtime = os.path.getmtime(rmb_path)
    cache_base = os.path.join(cache_dir, f"{os.path.basename(rmb_path)}.{int(source_mtime)}")
    for ext in (".png", ".bmp", ".jpg"):
        cached = cache_base + ext
        if os.path.exists(cached):
            return cached
    try:
        with open(rmb_path, "rb") as handle:
            data = handle.read()
        candidates = extract_embedded_image_candidates(data)
        if not candidates:
            return None
        _score, offset, size, kind = candidates[0]
        blob = data[offset : offset + size]
        suffix = {"bmp": ".bmp", "png": ".png", "jpg": ".jpg"}.get(kind, ".bin")
        temp_path = cache_base + suffix
        with open(temp_path, "wb") as out:
            out.write(blob)
        if kind == "bmp" and HAS_PIL:
            try:
                with Image.open(temp_path) as img:
                    png_path = cache_base + ".png"
                    img.convert("RGB").save(png_path, format="PNG")
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                return png_path
            except Exception:
                return temp_path
        return temp_path
    except Exception:
        return None

def iff_padded_size(chunk_size):
    return chunk_size + (chunk_size & 1)

def iter_rbm_embf_chunks(rbm_data):
    if not rbm_data or len(rbm_data) < 16 or rbm_data[:4] != b"CAT ":
        return
    cat_size = struct.unpack(">I", rbm_data[4:8])[0]
    cat_end = min(len(rbm_data), 8 + cat_size)
    if rbm_data[8:12] != b"PRBM":
        return
    pos = 12
    slot = 0
    while pos + 8 <= cat_end:
        tag = rbm_data[pos : pos + 4]
        chunk_size = struct.unpack(">I", rbm_data[pos + 4 : pos + 8])[0]
        chunk_end = pos + 8 + iff_padded_size(chunk_size)
        if chunk_size <= 0 or chunk_end > cat_end:
            break
        if tag == b"EMBF":
            body = rbm_data[pos + 8 : pos + 8 + chunk_size]
            yield body, slot
        slot += 1
        pos = chunk_end

def resolve_rb20ful_path():
    candidates = [
        os.path.join(MODS_DIR, RB20FUL_FILENAME),
        os.path.join(BASE_DIR, RB20FUL_FILENAME),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.path.getsize(path) == RB20FUL_SIZE:
            return path
    return candidates[0]

def load_rb20ful_dat():
    global _RB20FUL_BYTES
    if _RB20FUL_BYTES is not None:
        return _RB20FUL_BYTES
    rb20ful_path = resolve_rb20ful_path()
    if not os.path.isfile(rb20ful_path):
        return None
    try:
        if os.path.getsize(rb20ful_path) != RB20FUL_SIZE:
            return None
        with open(rb20ful_path, "rb") as handle:
            _RB20FUL_BYTES = handle.read()
    except OSError:
        return None
    return _RB20FUL_BYTES

def parse_rbm_embf_body(body):
    if not body:
        return None
    scan = min(len(body), 1024)
    zero = -1
    for index in range(scan):
        if body[index] == 0:
            zero = index
            break
    if zero <= 0:
        return None
    name = body[:zero].decode("latin-1", errors="ignore").replace("\0", "").strip()
    name_bytes_len = zero + 1
    payload = bytearray(body[name_bytes_len:])
    return name, name_bytes_len, payload

def build_rbm_decrypt_table(rb20ful, embf_bodies):
    r_acc = 8192
    t_acc = 12288
    for body in embf_bodies:
        chunk = bytearray(1024)
        chunk[:] = bytes([101]) * 1024
        take = min(len(body), 1024)
        chunk[:take] = body[:take]
        h = 0
        f = 0
        m = 0
        for _ in range(128):
            b = (m & 0xFFFF) * 4 % 1024
            h = (h + struct.unpack(">I", chunk[b : b + 4])[0]) & 0xFFFFFFFF
            m += 1
        for _ in range(128):
            b = (m & 0xFFFF) * 4 % 1024
            f = (f + struct.unpack(">I", chunk[b : b + 4])[0]) & 0xFFFFFFFF
            m += 1
        r_acc = (r_acc + h) & 0xFFFFFFFF
        t_acc = (t_acc + f) & 0xFFFFFFFF
    s = 256 + (r_acc % 134215680)
    o = 256 + (t_acc % 134215680)
    table = bytearray(4096)
    table[0:2048] = rb20ful[s : s + 2048]
    table[2048:4096] = rb20ful[o : o + 2048]
    return table

def decrypt_rbm_embf_payload(payload, name_bytes_len, slot, table):
    if not table or len(table) < 4096 or not payload:
        return payload
    total_len = len(payload) + name_bytes_len
    if total_len <= 1024:
        return payload
    start = max(0, 1024 - name_bytes_len)
    if start >= len(payload):
        return payload
    decrypt_count = total_len - 1024
    table_off = 2048 if (slot & 1) else 0
    wrap = (slot * 17) % 1925 + 123
    idx = 0
    end = min(decrypt_count, len(payload) - start)
    for offset in range(end):
        payload[start + offset] = (payload[start + offset] + table[table_off + idx]) & 0xFF
        idx += 1
        if idx == wrap:
            idx = 0
    return payload

def decrypt_rbm_embf_sample(body, slot, table):
    parsed = parse_rbm_embf_body(body)
    if not parsed:
        return None, None
    name, name_bytes_len, payload = parsed
    decrypt_rbm_embf_payload(payload, name_bytes_len, slot, table)
    form_start = payload.find(b"FORM")
    if form_start < 0:
        return name, None
    return name, bytes(payload[form_start:])

def prepare_rbm_decrypt_table(rbm_data):
    rb20ful = load_rb20ful_dat()
    if not rb20ful:
        return None
    embf_bodies = [body for body, _slot in iter_rbm_embf_chunks(rbm_data)]
    if not embf_bodies:
        return None
    try:
        return build_rbm_decrypt_table(rb20ful, embf_bodies)
    except (IndexError, struct.error, ValueError):
        return None

def read_aiff_sample_rate(comm_data):
    if len(comm_data) < 18:
        return 44100
    rate_bytes = comm_data[8:18]
    try:
        exponent = ((127 & rate_bytes[0]) << 8) | rate_bytes[1]
        if exponent == 0:
            return 44100
        mantissa = 0
        for b in rate_bytes[2:10]:
            mantissa = (mantissa << 8) | b
        value = mantissa * (2.0 ** (exponent - 16383 - 63))
        if 8000 <= value <= 96000:
            return int(round(value))
    except Exception:
        pass
    return 44100

def pcm16le_to_wav_bytes(pcm_le, sample_rate, channels=1):
    if not pcm_le:
        return None
    data_size = len(pcm_le)
    block_align = 2 * channels
    byte_rate = sample_rate * block_align
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        16,
        b"data",
        data_size,
    )
    return header + pcm_le

def _dwop_u32(value):
    return value & 0xFFFFFFFF

def _dwop_s32(value):
    value &= 0xFFFFFFFF
    if value & 0x80000000:
        return value - 0x100000000
    return value

def _dwop_z(value):
    signed = _dwop_s32(value)
    if signed >= 0:
        return _dwop_u32(signed)
    return _dwop_u32((~_dwop_u32(-signed)) & 0xFFFFFFFF)

class _DwopBitReader:
    def __init__(self, data):
        self.data = data
        self.nwords = len(data) // 4
        self.pos = 0

    def next(self):
        if self.pos >= self.nwords:
            return 0
        word = struct.unpack(">I", self.data[self.pos * 4 : self.pos * 4 + 4])[0]
        self.pos += 1
        return _dwop_s32(word)

def _dwop_samples_to_pcm16le(samples):
    pcm = bytearray()
    for sample in samples:
        clipped = max(-32768, min(32767, _dwop_s32(sample)))
        pcm.extend(struct.pack("<h", clipped))
    return bytes(pcm)

def _dwop_decode_fold(reader, pred_s, rice_l, rice_m, bit_v, bit_w):
    total = 0
    rice_i = 7
    s_val = _dwop_u32(3 * (pred_s + 12) >> 7)
    u_val = 0
    guard = 0
    while True:
        guard += 1
        if guard > 4096:
            raise ValueError("DWOP: rice decode guard tripped")
        u_val = s_val
        token = _dwop_s32(bit_w)
        bit_v -= 1
        if bit_v < 0:
            token = reader.next()
            bit_v = 31
        s_val = _dwop_u32(2 * token)
        bit_w = s_val
        if token < 0:
            break
        total += u_val
        rice_i -= 1
        if rice_i == 0:
            rice_i = 7
        s_val = _dwop_u32(4 * u_val)
        if rice_i != 0:
            s_val = u_val

    if u_val < rice_m:
        while u_val < (rice_m >> 1):
            rice_l -= 1
            rice_m >>= 1
    else:
        guard = 0
        while True:
            guard += 1
            if guard > 64:
                raise ValueError("DWOP: rice m guard tripped")
            rice_l += 1
            rice_m = _dwop_u32(2 * rice_m)
            if rice_m == 0:
                raise ValueError("DWOP: rice parameter overflow")
            if not (rice_m <= u_val):
                break

    value = 0
    if rice_l != 0:
        shift = (32 - rice_l) & 31
        value = _dwop_u32(s_val >> shift)
        bit_w = _dwop_u32(s_val << (31 & rice_l))
        bit_v -= rice_l
        if bit_v < 0:
            s_val = reader.next()
            bit_v = 32 + bit_v
            value = _dwop_u32(value | (_dwop_u32(s_val) >> (31 & bit_v)))
            bit_w = _dwop_u32(s_val << (31 & (-rice_l)))

    bound = _dwop_u32(rice_m - u_val)
    if _dwop_s32(_dwop_u32(value - bound)) >= 0:
        bit_v -= 1
        if bit_v < 0:
            bit_w = reader.next()
            bit_v = 31
        value = _dwop_u32(2 * value - bound + (_dwop_u32(bit_w) >> 31))
        bit_w = _dwop_u32(2 * _dwop_s32(bit_w))

    value = _dwop_u32(value + total)
    folded = _dwop_u32(~value) if (value & 1) else _dwop_u32(value)
    return folded, rice_l, rice_m, bit_v, bit_w

def dwop_decode_mono(data, sample_count):
    """Decode ReBirth DWOP-compressed mono sample data (rb338packer compatible)."""
    reader = _DwopBitReader(data)
    out = [0] * sample_count
    rice_l = 0
    rice_m = 2
    acc_h = 0
    pred_c = pred_d = pred_f = pred_p = pred_m = 2560
    prev_g = prev_b = prev_y = 0
    bit_v = 0
    bit_w = 0
    pred_s = pred_d
    if pred_c <= pred_d:
        pred_s = pred_c
    mode = 1 if pred_d < pred_c else 0
    if pred_f < pred_s:
        mode = 2
        pred_s = pred_f
    if pred_p < pred_s:
        mode = 3
        pred_s = pred_p
    if pred_m < pred_s:
        mode = 4
        pred_s = pred_m

    for index in range(sample_count):
        folded, rice_l, rice_m, bit_v, bit_w = _dwop_decode_fold(
            reader, pred_s, rice_l, rice_m, bit_v, bit_w
        )
        if mode == 1:
            val_r = _dwop_u32(folded - prev_g)
            val_n = _dwop_u32(val_r - prev_b)
            val_u = _dwop_u32(val_n - prev_y)
            val_t = folded
            acc_h = _dwop_u32(acc_h + folded)
        elif mode == 2:
            val_t = _dwop_u32(prev_g + folded)
            val_u = _dwop_u32(folded - prev_b - prev_y)
            val_r = folded
            acc_h = _dwop_u32(acc_h + prev_g + folded)
            val_n = _dwop_u32(folded - prev_b)
        elif mode == 3:
            val_r = _dwop_u32(prev_b + folded)
            val_t = _dwop_u32(prev_g + val_r)
            val_u = _dwop_u32(folded - prev_y)
            acc_h = _dwop_u32(acc_h + prev_g + val_r)
            val_n = folded
        elif mode == 4:
            val_n = _dwop_u32(prev_y + folded)
            val_r = _dwop_u32(prev_b + val_n)
            val_t = _dwop_u32(prev_g + val_r)
            val_u = folded
            acc_h = _dwop_u32(acc_h + prev_g + val_r)
        else:
            val_t = _dwop_u32(folded - acc_h)
            val_r = _dwop_u32(val_t - prev_g)
            val_n = _dwop_u32(val_r - prev_b)
            val_u = _dwop_u32(val_n - prev_y)

        out[index] = _dwop_s32(acc_h) >> 1

        pred_c = _dwop_u32(pred_c + (_dwop_z(acc_h) - (pred_c >> 5)))
        pred_d = _dwop_u32(pred_d + (_dwop_z(val_t) - (pred_d >> 5)))
        pred_s = pred_d
        if pred_c <= pred_d:
            pred_s = pred_c
        pred_f = _dwop_u32(pred_f + (_dwop_z(val_r) - (pred_f >> 5)))
        mode = 1 if pred_d < pred_c else 0
        if pred_f < pred_s:
            mode = 2
            pred_s = pred_f
        pred_p = _dwop_u32(pred_p + (_dwop_z(val_n) - (pred_p >> 5)))
        if pred_p < pred_s:
            mode = 3
            pred_s = pred_p
        pred_m = _dwop_u32(pred_m + (_dwop_z(val_u) - (pred_m >> 5)))
        prev_g = val_t
        prev_b = val_r
        prev_y = val_n
        if pred_m < pred_s:
            mode = 4
            pred_s = pred_m

    return out

def dwop_decode_stereo(data, sample_count):
    """Decode ReBirth DWOP-compressed stereo sample data; returns mono mix."""
    reader = _DwopBitReader(data)
    left = [0] * sample_count
    right = [0] * sample_count
    rice_l = rice_m = 2
    rice_l2 = rice_m2 = 2
    bit_v = bit_w = 0
    bit_v2 = bit_w2 = 0
    pred_c = pred_d = pred_f = pred_p = pred_m = 2560
    pred_c2 = pred_d2 = pred_f2 = pred_p2 = pred_m2 = 2560
    prev_g = prev_b = prev_y = 0
    prev_g2 = prev_b2 = prev_y2 = 0
    acc_h = acc_e = 0
    pred_s = pred_d
    if pred_c <= pred_d:
        pred_s = pred_c
    mode = 1 if pred_d < pred_c else 0
    if pred_f < pred_s:
        mode = 2
        pred_s = pred_f
    if pred_p < pred_s:
        mode = 3
        pred_s = pred_p
    if pred_m < pred_s:
        mode = 4
        pred_s = pred_m
    pred_s2 = pred_d2 if pred_c2 <= pred_d2 else pred_c2
    mode2 = 1 if pred_d2 < pred_c2 else 0
    if pred_f2 < pred_s2:
        mode2 = 2
        pred_s2 = pred_f2
    if pred_p2 < pred_s2:
        mode2 = 3
        pred_s2 = pred_p2
    if pred_m2 < pred_s2:
        mode2 = 4
        pred_s2 = pred_m2

    for index in range(sample_count):
        folded, rice_l, rice_m, bit_v, bit_w = _dwop_decode_fold(
            reader, pred_s, rice_l, rice_m, bit_v, bit_w
        )
        if mode == 1:
            val_r = _dwop_u32(folded - prev_g)
            val_n = _dwop_u32(val_r - prev_b)
            val_u = _dwop_u32(val_n - prev_y)
            val_t = folded
            acc_h = _dwop_u32(acc_h + folded)
        elif mode == 2:
            val_t = _dwop_u32(prev_g + folded)
            val_u = _dwop_u32(folded - prev_b - prev_y)
            val_r = folded
            acc_h = _dwop_u32(acc_h + prev_g + folded)
            val_n = _dwop_u32(folded - prev_b)
        elif mode == 3:
            val_r = _dwop_u32(prev_b + folded)
            val_t = _dwop_u32(prev_g + val_r)
            val_u = _dwop_u32(folded - prev_y)
            acc_h = _dwop_u32(acc_h + prev_g + val_r)
            val_n = folded
        elif mode == 4:
            val_n = _dwop_u32(prev_y + folded)
            val_r = _dwop_u32(prev_b + val_n)
            val_t = _dwop_u32(prev_g + val_r)
            val_u = folded
            acc_h = _dwop_u32(acc_h + prev_g + val_r)
        else:
            val_t = _dwop_u32(folded - acc_h)
            val_r = _dwop_u32(val_t - prev_g)
            val_n = _dwop_u32(val_r - prev_b)
            val_u = _dwop_u32(val_n - prev_y)
        left[index] = _dwop_s32(acc_h) >> 1

        pred_c = _dwop_u32(pred_c + (_dwop_z(acc_h) - (pred_c >> 5)))
        pred_d = _dwop_u32(pred_d + (_dwop_z(val_t) - (pred_d >> 5)))
        pred_s = pred_d if pred_c > pred_d else pred_c
        mode = 1 if pred_d < pred_c else 0
        pred_f = _dwop_u32(pred_f + (_dwop_z(val_r) - (pred_f >> 5)))
        if pred_f < pred_s:
            mode = 2
            pred_s = pred_f
        pred_p = _dwop_u32(pred_p + (_dwop_z(val_n) - (pred_p >> 5)))
        if pred_p < pred_s:
            mode = 3
            pred_s = pred_p
        pred_m = _dwop_u32(pred_m + (_dwop_z(val_u) - (pred_m >> 5)))
        prev_g, prev_b, prev_y = val_t, val_r, val_n
        if pred_m < pred_s:
            mode = 4
            pred_s = pred_m

        folded2, rice_l2, rice_m2, bit_v2, bit_w2 = _dwop_decode_fold(
            reader, pred_s2, rice_l2, rice_m2, bit_v2, bit_w2
        )
        if mode2 == 1:
            val_r2 = _dwop_u32(folded2 - prev_g2)
            val_n2 = _dwop_u32(val_r2 - prev_b2)
            val_u2 = _dwop_u32(val_n2 - prev_y2)
            val_t2 = folded2
            acc_e = _dwop_u32(acc_e + folded2)
        elif mode2 == 2:
            val_t2 = _dwop_u32(prev_g2 + folded2)
            val_u2 = _dwop_u32(folded2 - prev_b2 - prev_y2)
            val_r2 = folded2
            acc_e = _dwop_u32(acc_e + prev_g2 + folded2)
            val_n2 = _dwop_u32(folded2 - prev_b2)
        elif mode2 == 3:
            val_r2 = _dwop_u32(prev_b2 + folded2)
            val_t2 = _dwop_u32(prev_g2 + val_r2)
            val_u2 = _dwop_u32(folded2 - prev_y2)
            acc_e = _dwop_u32(acc_e + prev_g2 + val_r2)
            val_n2 = folded2
        elif mode2 == 4:
            val_n2 = _dwop_u32(prev_y2 + folded2)
            val_r2 = _dwop_u32(prev_b2 + val_n2)
            val_t2 = _dwop_u32(prev_g2 + val_r2)
            val_u2 = folded2
            acc_e = _dwop_u32(acc_e + prev_g2 + val_r2)
        else:
            val_t2 = _dwop_u32(folded2 - acc_e)
            val_r2 = _dwop_u32(val_t2 - prev_g2)
            val_n2 = _dwop_u32(val_r2 - prev_b2)
            val_u2 = _dwop_u32(val_n2 - prev_y2)
        right[index] = _dwop_s32(_dwop_u32(acc_h + acc_e)) >> 1

        pred_c2 = _dwop_u32(pred_c2 + (_dwop_z(acc_e) - (pred_c2 >> 5)))
        pred_d2 = _dwop_u32(pred_d2 + (_dwop_z(val_t2) - (pred_d2 >> 5)))
        pred_s2 = pred_d2 if pred_c2 > pred_d2 else pred_c2
        mode2 = 1 if pred_d2 < pred_c2 else 0
        pred_f2 = _dwop_u32(pred_f2 + (_dwop_z(val_r2) - (pred_f2 >> 5)))
        if pred_f2 < pred_s2:
            mode2 = 2
            pred_s2 = pred_f2
        pred_p2 = _dwop_u32(pred_p2 + (_dwop_z(val_n2) - (pred_p2 >> 5)))
        if pred_p2 < pred_s2:
            mode2 = 3
            pred_s2 = pred_p2
        pred_m2 = _dwop_u32(pred_m2 + (_dwop_z(val_u2) - (pred_m2 >> 5)))
        prev_g2, prev_b2, prev_y2 = val_t2, val_r2, val_n2
        if pred_m2 < pred_s2:
            mode2 = 4
            pred_s2 = pred_m2

    mixed = []
    for index in range(sample_count):
        mixed.append(max(-32768, min(32767, (left[index] + right[index]) // 2)))
    return mixed

def _try_dwop_decode_pcm16le(pcm_data, frames, channels):
    if frames <= 0 or not pcm_data:
        return None
    try:
        if channels == 1:
            samples = dwop_decode_mono(pcm_data, frames)
        elif channels == 2:
            samples = dwop_decode_stereo(pcm_data, frames)
        else:
            return None
        pcm = _dwop_samples_to_pcm16le(samples)
        return pcm if pcm else None
    except Exception:
        return None

def _pcm16le_looks_valid(pcm_le):
    if not pcm_le or len(pcm_le) < 64:
        return False
    peak = 0
    non_zero = 0
    for index in range(0, min(len(pcm_le), 44100), 2):
        sample = abs(struct.unpack("<h", pcm_le[index : index + 2])[0])
        if sample:
            non_zero += 1
        if sample > peak:
            peak = sample
    return peak >= 64 and non_zero >= 8

def _decode_aiff_pcm16le_frames(pcm, frames, channels, bits, little_endian, compression):
    if frames <= 0 or not pcm:
        return None
    sample_width = max(1, bits // 8)
    frame_bytes = sample_width * channels
    pcm_le = bytearray()
    for frame_idx in range(frames):
        frame_offset = frame_idx * frame_bytes
        if frame_offset >= len(pcm):
            break
        if channels == 1:
            sample_offset = frame_offset
            if sample_offset + sample_width > len(pcm):
                break
            raw = pcm[sample_offset : sample_offset + sample_width]
            value = _aiff_read_sample_value(raw, bits, little_endian, compression)
            pcm_le.extend(struct.pack("<h", value))
        else:
            mix = 0
            count = 0
            for ch in range(channels):
                sample_offset = frame_offset + ch * sample_width
                if sample_offset + sample_width > len(pcm):
                    continue
                raw = pcm[sample_offset : sample_offset + sample_width]
                mix += _aiff_read_sample_value(raw, bits, little_endian, compression)
                count += 1
            if count:
                pcm_le.extend(struct.pack("<h", mix // count))
    if not pcm_le:
        return None
    return bytes(pcm_le)

def _aiff_read_sample_value(raw, bits, little_endian, compression):
    if bits == 8:
        return max(-32768, min(32767, (raw[0] - 128) * 256))
    if bits == 16:
        fmt = "<h" if little_endian else ">h"
        return struct.unpack(fmt, raw)[0]
    if bits == 24:
        b0, b1, b2 = raw
        if little_endian:
            value = b2 << 16 | b1 << 8 | b0
        else:
            value = b0 << 16 | b1 << 8 | b2
        if value & 0x800000:
            value -= 0x1000000
        return max(-32768, min(32767, value >> 8))
    if bits == 32:
        if compression in ("fl32", "fl64", "float"):
            fmt = "<f" if little_endian else ">f"
            fval = struct.unpack(fmt, raw)[0]
            if not math.isfinite(fval):
                return 0
            return max(-32767, min(32767, int(round(fval * 32767))))
        fmt = "<i" if little_endian else ">i"
        value = struct.unpack(fmt, raw)[0]
        return max(-32767, min(32767, int(round(value / 2147483648.0 * 32767))))
    return 0

def decode_aiff_form_to_pcm16le(form_bytes):
    """Decode AIFF/AIFC FORM data using the same rules as rb338packer."""
    if not form_bytes or len(form_bytes) < 12 or form_bytes[:4] != b"FORM":
        return None
    form_type = form_bytes[8:12]
    if form_type not in (b"AIFF", b"AIFC"):
        return None

    channels = 0
    frames = 0
    bits = 0
    sample_rate = 44100
    compression = None
    pcm = None
    pos = 12
    end = len(form_bytes)

    while pos + 8 <= end:
        chunk_id = form_bytes[pos : pos + 4]
        chunk_size = struct.unpack(">I", form_bytes[pos + 4 : pos + 8])[0]
        chunk_data_start = pos + 8
        chunk_data_end = min(end, chunk_data_start + chunk_size)

        if chunk_id == b"COMM" and chunk_size >= 8:
            channels = struct.unpack(">H", form_bytes[chunk_data_start : chunk_data_start + 2])[0] or 1
            frames = struct.unpack(">I", form_bytes[chunk_data_start + 2 : chunk_data_start + 6])[0]
            bits = struct.unpack(">H", form_bytes[chunk_data_start + 6 : chunk_data_start + 8])[0] or 16
            sample_rate = read_aiff_sample_rate(form_bytes[chunk_data_start : chunk_data_start + chunk_size])
            if form_type == b"AIFC" and chunk_size >= 18:
                comp_raw = form_bytes[chunk_data_start + 18 : chunk_data_end]
                compression = comp_raw.split(b"\x00")[0].decode("latin-1", errors="ignore").strip().lower()
        elif chunk_id == b"SSND" and chunk_size >= 8:
            offset = struct.unpack(">I", form_bytes[chunk_data_start : chunk_data_start + 4])[0]
            sound_start = chunk_data_start + 8 + offset
            pcm = form_bytes[sound_start:chunk_data_end]

        pos = chunk_data_start + chunk_size + (chunk_size & 1)

    if not pcm or channels <= 0 or frames <= 0 or bits not in (8, 16, 24, 32):
        return None

    compression = (compression or "").strip().lower()
    allowed_pcm = ("none", "twos", "sowt", "fl32", "fl64", "float", "")
    little_endian = compression == "sowt"
    sample_width = max(1, bits // 8)
    frame_bytes = sample_width * channels
    expected = frames * frame_bytes
    actual_frames = len(pcm) // frame_bytes if frame_bytes else 0

    # ReBirth often stores valid 16-bit PCM but COMM frame count is inflated (~4/3).
    if (
        actual_frames > 0
        and len(pcm) == actual_frames * frame_bytes
        and actual_frames < frames
        and compression in allowed_pcm
    ):
        pcm_from_size = _decode_aiff_pcm16le_frames(
            pcm, actual_frames, channels, bits, little_endian, compression
        )
        if _pcm16le_looks_valid(pcm_from_size):
            return 1, sample_rate, pcm_from_size

    if expected > 0 and len(pcm) >= expected:
        pcm = pcm[:expected]
        pcm_full = _decode_aiff_pcm16le_frames(
            pcm, frames, channels, bits, little_endian, compression
        )
        if _pcm16le_looks_valid(pcm_full):
            return 1, sample_rate, pcm_full

    if compression and compression not in allowed_pcm:
        dwop_pcm = _try_dwop_decode_pcm16le(pcm, frames, channels)
        if dwop_pcm and _pcm16le_looks_valid(dwop_pcm):
            return 1, sample_rate, dwop_pcm
        return None

    # True DWOP compression: SSND shorter and not an exact PCM byte multiple.
    if (
        expected > 0
        and len(pcm) < max(64, int(expected * 0.85))
        and (frame_bytes <= 0 or len(pcm) % frame_bytes != 0)
    ):
        dwop_pcm = _try_dwop_decode_pcm16le(pcm, frames, channels)
        if dwop_pcm and _pcm16le_looks_valid(dwop_pcm):
            return 1, sample_rate, dwop_pcm

    decode_frames = frames
    if actual_frames > 0 and actual_frames < frames:
        decode_frames = actual_frames
    pcm_trim = pcm[: decode_frames * frame_bytes] if frame_bytes else pcm
    pcm_fallback = _decode_aiff_pcm16le_frames(
        pcm_trim, decode_frames, channels, bits, little_endian, compression
    )
    if not pcm_fallback:
        return None
    return 1, sample_rate, pcm_fallback

def decode_mod_voice_sample_wav(mod_path, machine, label):
    """Decode one mapped drum voice directly from an .rbm file (bypasses cache)."""
    if not mod_path or not os.path.exists(mod_path):
        return None
    hints = (RBM_VOICE_HINTS.get(machine) or {}).get(label) or ()
    if not hints:
        return None
    try:
        with open(mod_path, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    best = None
    decrypt_table = prepare_rbm_decrypt_table(data)
    for body, slot in iter_rbm_embf_chunks(data):
        filename = extract_rbm_embf_filename(body) or ""
        stem = normalize_rbm_sample_stem(filename or "")
        if not stem:
            continue
        score = max(rbm_voice_match_score(stem, hint) for hint in hints)
        if score < 0:
            continue
        blob = None
        if decrypt_table is not None:
            _name, blob = decrypt_rbm_embf_sample(body, slot, decrypt_table)
        if not blob:
            blob = body[body.find(b"FORM") :] if b"FORM" in body else body
        if not blob or blob[:4] != b"FORM":
            continue
        if best is None or score > best[0]:
            best = (score, blob)
    if not best:
        return None
    return aiff_blob_to_wav_bytes(best[1])

def aiff_blob_to_wav_bytes(aiff_blob):
    if not aiff_blob:
        return None
    form_start = aiff_blob.find(b"FORM")
    if form_start < 0:
        return None
    decoded = decode_aiff_form_to_pcm16le(aiff_blob[form_start:])
    if not decoded:
        return None
    channels, sample_rate, pcm_le = decoded
    if not pcm_le:
        return None
    return pcm16le_to_wav_bytes(pcm_le, sample_rate, channels=1)

def aiff_file_to_wav_bytes(aiff_path):
    if not aiff_path or not os.path.isfile(aiff_path):
        return None
    try:
        with open(aiff_path, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    if not data:
        return None
    return aiff_blob_to_wav_bytes(data)

def _decoded_pcm_clip_ratio(pcm_le, threshold=30000):
    if not pcm_le or len(pcm_le) < 64:
        return 1.0
    frames = len(pcm_le) // 2
    if frames <= 0:
        return 1.0
    clipped = 0
    for index in range(0, len(pcm_le), 2):
        if abs(struct.unpack("<h", pcm_le[index : index + 2])[0]) >= threshold:
            clipped += 1
    return clipped / frames

def _decoded_pcm_is_suspicious(pcm_le):
    if not pcm_le:
        return True
    clip_ratio = _decoded_pcm_clip_ratio(pcm_le)
    if clip_ratio >= 0.02:
        return True
    return not _pcm16le_looks_valid(pcm_le)

def iter_mod_sidecar_sample_dirs(rbm_path, mod_name=None):
    if not rbm_path:
        return
    stem = os.path.splitext(os.path.basename(rbm_path))[0]
    names = {
        stem,
        stem.lower(),
        (mod_name or "").strip(),
        (mod_name or "").strip().lower(),
    }
    candidates = []
    base_dir = os.path.dirname(os.path.abspath(rbm_path))
    for name in names:
        if not name:
            continue
        candidates.extend([
            os.path.join(base_dir, name),
            os.path.join(MODS_DIR, name),
            os.path.join(MODS_DIR, ".sidecar", name),
            os.path.join(MODS_DIR, ".sidecar", name.lower()),
        ])
    cursor_temp_candidates = []
    temp_env = os.environ.get("TEMP", "")
    if temp_env:
        cursor_temp_candidates.append(temp_env)
        if not temp_env.lower().endswith(os.path.join("", "cursorportabletemp").lower()):
            cursor_temp_candidates.append(os.path.join(temp_env, "CursorPortableTemp"))
    local_temp = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp")
    if local_temp:
        cursor_temp_candidates.append(os.path.join(local_temp, "CursorPortableTemp"))
    seen_temp = set()
    for cursor_temp in cursor_temp_candidates:
        if not cursor_temp:
            continue
        norm_temp = os.path.normcase(os.path.abspath(cursor_temp))
        if norm_temp in seen_temp or not os.path.isdir(cursor_temp):
            continue
        seen_temp.add(norm_temp)
        try:
            has_aif = any(
                entry.lower().endswith((".aif", ".aiff"))
                for entry in os.listdir(cursor_temp)
            )
        except OSError:
            has_aif = False
        if not has_aif:
            continue
        for name in names:
            if name.lower() in ("peffedit", "peff"):
                candidates.insert(0, cursor_temp)
        break
    try:
        config = load_config()
        sidecar_map = config.get("mod_sidecar_dirs") or {}
        for name in names:
            mapped = sidecar_map.get(name) or sidecar_map.get(name.lower())
            if mapped:
                candidates.insert(0, mapped)
    except Exception:
        pass
    seen = set()
    for path in candidates:
        if not path:
            continue
        norm = os.path.normcase(os.path.abspath(path))
        if norm in seen or not os.path.isdir(path):
            continue
        seen.add(norm)
        if any(
            entry.lower().endswith((".aif", ".aiff"))
            for entry in os.listdir(path)
        ):
            yield path

def find_sidecar_aif_path(sidecar_dir, stem):
    if not sidecar_dir or not os.path.isdir(sidecar_dir) or not stem:
        return None
    target = normalize_rbm_sample_stem(stem)
    if not target:
        return None
    best = None
    try:
        entries = os.listdir(sidecar_dir)
    except OSError:
        return None
    for name in entries:
        if not name.lower().endswith((".aif", ".aiff")):
            continue
        score = rbm_voice_match_score(name, target)
        if score >= 0 and (best is None or score > best[0]):
            best = (score, os.path.join(sidecar_dir, name))
    return best[1] if best else None

def resolve_sidecar_aif_for_voice(sidecar_dirs, stem):
    for sidecar_dir in sidecar_dirs:
        sidecar_path = find_sidecar_aif_path(sidecar_dir, stem)
        if sidecar_path:
            return sidecar_path
    return None

RBM_VOICE_HINTS = {
    "808": {
        "AC": ("808ac", "tr808ac"),
        "BD": ("tr808bd", "808bd"),
        "SD": ("tr808sd1", "808sd1", "tr808sd", "808sd"),
        "LT": ("tr808lt", "808lt"),
        "MT": ("tr808mt", "808mt"),
        "HT": ("tr808ht", "808ht"),
        "RS": ("tr808rs", "808rs"),
        "CP": ("tr808cp", "808cp"),
        "CB": ("tr808cb", "808cb", "tr808cl", "808cl"),
        "CY": ("tr808cy", "808cy"),
        "OH": ("tr808oh", "808oh"),
        "CH": ("tr808ch", "808ch", "tr808hc", "808hc"),
    },
    "909": {
        "AC": ("909ac", "tr909ac"),
        "BD": ("tr909bd", "909bd"),
        "SD": ("tr909sd1", "909sd1", "tr909sd", "909sd"),
        "LT": ("tr909lt", "909lt"),
        "MT": ("tr909mt", "909mt"),
        "HT": ("tr909ht", "909ht"),
        "RS": ("tr909rs", "909rs"),
        "CP": ("tr909cp", "909cp"),
        "CH": ("tr909ch", "909ch"),
        "OH": ("tr909oh", "909oh"),
        "CC": ("tr909cc", "909cc"),
        "RC": ("tr909rc", "909rc", "tr909rcy", "909rcy"),
    },
}

def normalize_rbm_sample_stem(name):
    stem = os.path.splitext(os.path.basename(name or ""))[0].lower()
    return re.sub(r"[^a-z0-9]", "", stem)

def rbm_voice_match_score(stem, hint):
    stem_norm = normalize_rbm_sample_stem(stem)
    hint_norm = re.sub(r"[^a-z0-9]", "", hint.lower())
    if not stem_norm or not hint_norm:
        return -1
    if stem_norm == hint_norm:
        return 100
    if stem_norm.startswith(hint_norm):
        return 80 - len(stem_norm)
    if hint_norm in stem_norm:
        return 60 - len(stem_norm)
    return -1

def map_rbm_sample_stem_to_voice(stem):
    stem_norm = normalize_rbm_sample_stem(stem)
    if not stem_norm or "startup" in stem_norm:
        return None, None
    best = None
    for machine, labels in RBM_VOICE_HINTS.items():
        for label, hints in labels.items():
            for hint in hints:
                score = rbm_voice_match_score(stem_norm, hint)
                if score >= 0 and (best is None or score > best[0]):
                    best = (score, machine, label)
    if best:
        return best[1], best[2]
    return None, None

def extract_rbm_embf_filename(body):
    if not body:
        return ""
    if body[:4] == b"FORM":
        return ""
    zero = body.find(b"\x00")
    if zero <= 0:
        return ""
    return body[:zero].decode("latin-1", errors="ignore").strip()

def extract_rbm_drum_samples(rbm_path, mod_name=None):
    result = {
        "samples": {},
        "voices": {"808": {}, "909": {}},
        "sample_count": 0,
        "error": "",
        "sidecar_dir": "",
    }
    if not rbm_path or not os.path.exists(rbm_path):
        result["error"] = "Mod file not found."
        return result
    try:
        mtime = int(os.path.getmtime(rbm_path))
    except OSError:
        mtime = 0
    cache_dir = os.path.join(
        RBM_SAMPLE_CACHE_DIR,
        f"{os.path.basename(rbm_path)}.{mtime}",
    )
    os.makedirs(cache_dir, exist_ok=True)
    sidecar_dirs = list(iter_mod_sidecar_sample_dirs(rbm_path, mod_name=mod_name))
    try:
        with open(rbm_path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        result["error"] = str(exc)
        return result

    decrypt_table = prepare_rbm_decrypt_table(data)
    if decrypt_table is None:
        result["error"] = f"Missing {RB20FUL_FILENAME} ({RB20FUL_SIZE // (1024 * 1024)} MB) in Mods folder."

    extracted = {}
    embf_samples = {}
    for body, slot in iter_rbm_embf_chunks(data):
        filename = extract_rbm_embf_filename(body) or ""
        blob = None
        if decrypt_table is not None:
            _name, blob = decrypt_rbm_embf_sample(body, slot, decrypt_table)
        if not blob:
            blob = body[body.find(b"FORM") :] if b"FORM" in body else body
        if not blob or blob[:4] != b"FORM" or blob[8:12] not in (b"AIFF", b"AIFC"):
            continue
        stem = normalize_rbm_sample_stem(filename or f"sample{len(embf_samples)+1:02d}")
        if not stem:
            continue
        embf_samples[stem] = (filename, blob)

    for stem, (filename, blob) in embf_samples.items():
        cache_tag = stem
        wav_path = os.path.join(cache_dir, f"{cache_tag}.wav")
        if os.path.isfile(wav_path) and os.path.getsize(wav_path) >= 48:
            extracted[stem] = wav_path
            continue

        wav_bytes = aiff_blob_to_wav_bytes(blob)
        if wav_bytes:
            decoded = decode_aiff_form_to_pcm16le(blob)
            if decoded and _decoded_pcm_is_suspicious(decoded[2]):
                sidecar_path = resolve_sidecar_aif_for_voice(sidecar_dirs, filename or stem)
                retry_bytes = aiff_file_to_wav_bytes(sidecar_path) if sidecar_path else None
                if retry_bytes:
                    wav_bytes = retry_bytes
                    if not result["sidecar_dir"] and sidecar_path:
                        result["sidecar_dir"] = os.path.dirname(os.path.abspath(sidecar_path))
        elif sidecar_dirs:
            sidecar_path = resolve_sidecar_aif_for_voice(sidecar_dirs, filename or stem)
            wav_bytes = aiff_file_to_wav_bytes(sidecar_path) if sidecar_path else None
            if wav_bytes and sidecar_path and not result["sidecar_dir"]:
                result["sidecar_dir"] = os.path.dirname(os.path.abspath(sidecar_path))

        if not wav_bytes:
            continue
        try:
            with open(wav_path, "wb") as out:
                out.write(wav_bytes)
        except OSError:
            continue
        extracted[stem] = wav_path

    result["samples"] = extracted
    result["sample_count"] = len(extracted)
    for stem, wav_path in extracted.items():
        machine, label = map_rbm_sample_stem_to_voice(stem)
        if not machine or not label:
            continue
        score = max(rbm_voice_match_score(stem, hint) for hint in RBM_VOICE_HINTS[machine][label])
        current = result["voices"][machine].get(label)
        if current:
            current_stem = normalize_rbm_sample_stem(os.path.basename(current))
            current_score = max(rbm_voice_match_score(current_stem, hint) for hint in RBM_VOICE_HINTS[machine][label])
            if score <= current_score:
                continue
        result["voices"][machine][label] = wav_path
    return result

def resolve_mod_preview_path(mod_path=None, mod_name=None):
    screenshot = find_mod_screenshot_path(mod_path, mod_name)
    if screenshot and os.path.exists(screenshot):
        default_exists = os.path.exists(DEFAULT_SCREENSHOT)
        if not default_exists or os.path.normcase(screenshot) != os.path.normcase(DEFAULT_SCREENSHOT):
            return screenshot
    if mod_path and os.path.exists(mod_path):
        embedded = extract_rmb_preview_image_path(mod_path)
        if embedded and os.path.exists(embedded):
            return embedded
    if mod_name and "standard" in mod_name.lower() and os.path.exists(DEFAULT_SCREENSHOT):
        return DEFAULT_SCREENSHOT
    return None

class SongDeconstructionWindow(tk.Toplevel):
    def __init__(self, parent, song_path, song_title, meta=None):
        super().__init__(parent)
        self.title(f"Song Deconstruction Inspector - {song_title}")
        self.geometry("880x620")
        self.configure(bg="#12131A")
        self.transient(parent)
        self.grab_set()

        set_window_icon(self)
        self.song_path = song_path
        self.meta = meta or parse_rbs_metadata(song_path)
        self.deconstructed_data = deconstruct_rbs_song(song_path)
        self.is_legacy = bool(self.deconstructed_data.get("legacy"))

        lbl_header = tk.Label(self, text=f"🔬 PATTERN DECONSTRUCTION MATRIX: {song_title}", font=("Segoe UI", 11, "bold"), fg="#00E5FF", bg="#12131A")
        lbl_header.pack(anchor="w", padx=15, pady=(12, 6))

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        if self.is_legacy:
            self.create_legacy_info_tab(notebook, self.deconstructed_data, self.meta)
            self.create_legacy_arrangement_tab(notebook, self.deconstructed_data)

        self.create_303_tab(notebook, "TB-303 #1", self.deconstructed_data["303_1"], legacy_hint=self.is_legacy)
        self.create_303_tab(notebook, "TB-303 #2", self.deconstructed_data["303_2"], legacy_hint=self.is_legacy)
        self.create_drum_tab(notebook, "TR-808 Drums", self.deconstructed_data["808"], legacy_hint=self.is_legacy)
        self.create_drum_tab(notebook, "TR-909 Drums", self.deconstructed_data["909"], legacy_hint=self.is_legacy)

        btn_bar = tk.Frame(self, bg="#12131A")
        btn_bar.pack(fill=tk.X, padx=15, pady=(0, 12))

        tk.Button(btn_bar, text="📋 Copy Report to Clipboard", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#242736", bd=0, cursor="hand2", command=self.copy_to_clipboard).pack(side=tk.LEFT, ipadx=10, ipady=4)
        tk.Button(btn_bar, text="💾 Save to .TXT", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#00A86B", bd=0, cursor="hand2", command=self.save_to_txt).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=4)
        tk.Button(btn_bar, text="📦 Export Pattern Bank", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#3A3D52", bd=0, cursor="hand2", command=self.export_to_pattern_bank).pack(side=tk.LEFT, ipadx=8, ipady=4)
        tk.Button(btn_bar, text="Close", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#3A3D52", bd=0, cursor="hand2", command=self.destroy).pack(side=tk.RIGHT, ipadx=15, ipady=4)

    def create_text_tab(self, notebook, title, text, fg="#00FF66"):
        frame = tk.Frame(notebook, bg="#1A1C27")
        notebook.add(frame, text=title)
        txt = tk.Text(frame, bg="#12131A", fg=fg, font=("Consolas", 9), bd=0, wrap=tk.NONE)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, text)
        txt.config(state=tk.DISABLED)

    def create_legacy_info_tab(self, notebook, data, meta):
        info = data.get("legacy_info", {})
        lines = [
            "=== LEGACY REBIRTH v3.x (MIDI .RBS) ===",
            "",
            f"Title:        {meta.get('title', '--')}",
            f"Tempo:        {meta.get('bpm') or '--'} BPM",
            f"Mode:         {meta.get('mode', '--')}",
            f"Duration:     {meta.get('duration_str', '--')}",
            f"Song Length:  {info.get('total_bars', '--')} bars",
            f"Loop End:     {info.get('loop_end_bar', '--')} bars",
            f"Extension:    +{info.get('extension_bars', 0)} bars  (sysex[32] << 4)",
            f"Song ID:      {info.get('sysex_id', '--')}",
            f"Max Tick:     {info.get('max_tick', '--')}",
            f"Ticks/Bar:    {info.get('ticks_per_bar', '--')}",
            f"State Blob:   {info.get('state_blob_size', '--')} bytes",
            f"Pattern Src:  {info.get('pattern_source') or 'not decoded'}",
            f"303 #1:       {len(data.get('303_1', []))} active patterns",
            f"303 #2:       {len(data.get('303_2', []))} active patterns",
            f"TR-808:       {len(data.get('808', []))} active patterns",
            f"TR-909:       none (legacy v3.x has no 909 bank)",
            "",
            "MIDI Tracks:",
        ]
        for tr in data.get("legacy_tracks", []):
            lines.append(
                f"  [{tr['index']}] {tr['label']}: {tr['size']} bytes, "
                f"{tr['event_count']} events, end tick {tr['end_tick']}"
            )
        lines.extend(
            [
                "",
                "Legacy v3.x stores device/pattern banks in MIDI track 1 (9304-byte blob):",
                "256 B header + TB-303 + TB-303 + TR-808. TR-909 and custom mods are v2.x only.",
                "Use TB-303 / TR-808 tabs for decoded pattern banks, or Arrangement for the song stream.",
            ]
        )
        self.create_text_tab(notebook, "Legacy Info", "\n".join(lines), fg="#00E5FF")

    def create_legacy_arrangement_tab(self, notebook, data):
        info = data.get("legacy_info", {})
        events = data.get("legacy_arrangement", [])
        total_bars = info.get("total_bars") or 0
        tpb = info.get("ticks_per_bar") or 0
        lines = [
            "=== SONG ARRANGEMENT STREAM (303 #1 track) ===",
            f"Bars: {total_bars} | Ticks/Bar: {tpb}",
            "",
            "Bar   Tick     Hex   Dec   Note",
            "----  -------  ----  ----  ----------------",
        ]
        shown = 0
        for ev in events:
            if ev.get("type") != "run":
                continue
            tick = ev["tick"]
            val = ev["value"]
            bar = int(tick / tpb) + 1 if tpb else 0
            note = ""
            if val <= 31:
                bank = chr(65 + (val // 8)) if val < 32 else "?"
                num = (val % 8) + 1
                note = f"pattern? {bank}{num} (idx {val})"
            lines.append(f"{bar:4d}  {tick:7d}  {val:02X}    {val:3d}  {note}")
            shown += 1
            if shown >= 400:
                lines.append("... truncated (400 events shown) ...")
                break
        if shown == 0:
            lines.append("(No running-status events found in arrangement track.)")
        self.create_text_tab(notebook, "Arrangement", "\n".join(lines), fg="#FF9500")

    def create_303_tab(self, notebook, title, patterns, legacy_hint=False):
        frame = tk.Frame(notebook, bg="#1A1C27")
        notebook.add(frame, text=title)
        txt = tk.Text(frame, bg="#12131A", fg="#00FF66", font=("Consolas", 9), bd=0, wrap=tk.NONE)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        if not patterns:
            if legacy_hint:
                txt.insert(
                    tk.END,
                    "Legacy v3.x songs embed pattern data in MIDI tracks, not IFF chunks.\n"
                    "Open the Legacy Info / Arrangement tabs for song structure.\n",
                )
            else:
                txt.insert(tk.END, "No active patterns found.\n")
        else:
            txt.insert(tk.END, f"=== {title} PATTERNS ({len(patterns)} total) ===\n\n")
            for p in patterns:
                txt.insert(tk.END, f"Pattern {p['name']}:\n")
                steps_h = " ".join([f"{i+1:02d}".center(5) for i in range(16)])
                notes_h = " ".join([s['note'].center(5) for s in p['steps']])
                attrs_h = " ".join([f"{s['up']}{s['accent']}{s['slide']}".center(5) for s in p['steps']])
                txt.insert(tk.END, f" Step: {steps_h}\n Note: {notes_h}\n Attr: {attrs_h}\n" + "-"*95 + "\n")
        txt.config(state=tk.DISABLED)

    def create_drum_tab(self, notebook, title, patterns, legacy_hint=False):
        frame = tk.Frame(notebook, bg="#1A1C27")
        notebook.add(frame, text=title)
        txt = tk.Text(frame, bg="#12131A", fg="#FF9500", font=("Consolas", 9), bd=0, wrap=tk.NONE)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        if not patterns:
            if legacy_hint:
                txt.insert(
                    tk.END,
                    "Legacy v3.x songs embed drum data in MIDI tracks, not IFF chunks.\n"
                    "Open the Legacy Info / Arrangement tabs for song structure.\n",
                )
            else:
                txt.insert(tk.END, "No active drum patterns found.\n")
        else:
            txt.insert(tk.END, f"=== {title} PATTERNS ({len(patterns)} total) ===\n\n")
            for p in patterns:
                txt.insert(tk.END, f"Pattern {p['name']}:\n")
                steps_line = " ".join([f"{i+1:02d}" for i in range(16)])
                txt.insert(tk.END, f"     Step: {steps_line}\n")
                for inst_lbl, hits in p['matrix'].items():
                    txt.insert(tk.END, f"     {inst_lbl:4s}: {'  '.join(hits)}\n")
                txt.insert(tk.END, "-"*70 + "\n")
        txt.config(state=tk.DISABLED)

    def copy_to_clipboard(self):
        meta = self.meta if hasattr(self, "meta") else parse_rbs_metadata(self.song_path)
        summary = (
            f"Deconstructed Song: {meta['title']}\n"
            f"Format: {meta.get('format', 'unknown')} {meta.get('format_version', '')}\n"
            f"Tempo: {meta['bpm']} BPM\n"
            f"Mode: {meta['mode']}\n"
            f"Duration: {meta['duration_str']}\n"
        )
        if self.deconstructed_data.get("legacy"):
            info = self.deconstructed_data.get("legacy_info", {})
            summary += f"Legacy Length: {info.get('total_bars')} bars\n"
        self.clipboard_clear()
        self.clipboard_append(summary)
        messagebox.showinfo("Clipboard", "Pattern report summary copied!")

    def save_to_txt(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Deconstruction Report for {self.song_path}\n")
            messagebox.showinfo("Saved", "Report saved successfully!")

    def export_to_pattern_bank(self):
        ensure_pattern_banks_dir()
        default_name = os.path.splitext(os.path.basename(self.song_path))[0] + "_bank.json"
        out_p = filedialog.asksaveasfilename(
            title="Export Song to Pattern Bank",
            defaultextension=".json",
            initialdir=PATTERN_BANKS_DIR,
            initialfile=default_name,
            filetypes=[("Pattern Bank JSON", "*.json"), ("All Files", "*.*")],
        )
        if not out_p:
            return
        try:
            export_song_to_pattern_bank_json(
                self.song_path,
                out_p,
                description=f"Extracted from {os.path.basename(self.song_path)}",
                author="ReBirth ToolBox",
                tags=["song-export"],
            )
            messagebox.showinfo("Export Pattern Bank", f"Pattern bank saved to:\n{out_p}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not export pattern bank:\n{exc}")

def get_library_scan_roots():
    roots = []
    songs_dir = os.path.abspath(SONGS_DIR)
    if os.path.isdir(songs_dir):
        roots.append(songs_dir)
    demo_dir = os.path.abspath(os.path.join(BASE_DIR, "Demo Songs"))
    if os.path.isdir(demo_dir):
        roots.append(demo_dir)
    for rel_path in load_config().get("library_scan_paths", []):
        if not rel_path:
            continue
        scan_path = rel_path if os.path.isabs(rel_path) else os.path.join(BASE_DIR, rel_path)
        scan_path = os.path.abspath(scan_path)
        if os.path.isdir(scan_path) and scan_path not in roots:
            roots.append(scan_path)
    return roots

def load_library_cache_from_disk():
    if not os.path.isfile(LIBRARY_CACHE_FILE):
        return None
    try:
        with open(LIBRARY_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != LIBRARY_CACHE_VERSION:
            return None
        return data
    except Exception:
        return None

def save_library_cache_to_disk(songs, mods, metadata_cache, mod_info_cache):
    try:
        os.makedirs(TOOLBOX_CACHE_DIR, exist_ok=True)
        payload = {
            "version": LIBRARY_CACHE_VERSION,
            "songs": [{"name": name, "path": path} for name, path in songs],
            "mods": [list(entry) for entry in mods],
            "metadata": metadata_cache,
            "mod_info": mod_info_cache,
        }
        with open(LIBRARY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass

def scan_installed_mods(mod_info_cache=None):
    mods = []
    if not os.path.exists(MODS_DIR):
        if mod_info_cache is not None:
            mod_info_cache.clear()
        return mods
    seen_keys = set()
    for root_d, dirnames, files in os.walk(MODS_DIR):
        # Skip cache / preview folders (not real mods)
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in ("screenshots",)]
        for f in files:
            if not f.lower().endswith((".rmb", ".rbm")):
                continue
            full_p = os.path.abspath(os.path.join(root_d, f))
            key = os.path.normcase(full_p)
            seen_keys.add(key)
            try:
                st = os.stat(full_p)
                sig = (st.st_mtime, st.st_size)
            except OSError:
                continue
            if mod_info_cache and key in mod_info_cache:
                cached = mod_info_cache[key]
                if cached.get("mtime") == sig[0] and cached.get("size") == sig[1]:
                    mods.append(tuple(cached["entry"]))
                    continue
            info = extract_rmb_mod_info(full_p)
            entry = (
                info["name"] or os.path.splitext(f)[0],
                full_p,
                info["comments"],
                info.get("rebirth_name") or preferred_mod_file_stem(f) or info["name"],
            )
            mods.append(entry)
            if mod_info_cache is not None:
                mod_info_cache[key] = {"mtime": sig[0], "size": sig[1], "entry": list(entry)}
    if mod_info_cache is not None:
        for stale in [k for k in list(mod_info_cache.keys()) if k not in seen_keys]:
            mod_info_cache.pop(stale, None)
    mods.sort(key=lambda x: x[0].lower())
    return mods

def find_all_rbs_songs(progress_callback=None, max_limit=1000):
    songs = []
    seen_paths = set()
    scan_roots = get_library_scan_roots()
    if not scan_roots:
        scan_roots = [os.path.abspath(BASE_DIR)]

    for scan_root in scan_roots:
        for root, _, files in os.walk(scan_root):
            for file in files:
                if not file.lower().endswith(".rbs"):
                    continue
                full_path = os.path.abspath(os.path.join(root, file))
                if is_under_default_songs(full_path):
                    continue
                key = full_path.lower()
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                songs.append((file, full_path))
                if progress_callback:
                    progress_callback(len(songs))
                if len(songs) >= max_limit:
                    break
            if len(songs) >= max_limit:
                break
        if len(songs) >= max_limit:
            break

    songs.sort(key=lambda x: x[0].lower())
    return songs

def acid_step_key(step):
    if not step or not step.get("active"):
        return ("rest",)
    return (
        step.get("note"),
        step.get("up"),
        step.get("accent"),
        step.get("slide"),
    )

def clone_303_steps(steps):
    return normalize_303_steps(steps)

def clone_drum_matrix(matrix, is_909=True):
    labels = INST_LABELS_909 if is_909 else INST_LABELS_808
    base = empty_drum_matrix(is_909)
    if matrix:
        for lbl in labels:
            src = matrix.get(lbl, ["."] * 16)
            base[lbl] = [(src[s] if s < len(src) else ".") for s in range(16)]
    return base

def pattern_store_has_content(store, kind="303"):
    if kind == "303":
        return any(step.get("active") for step in (store or []))
    matrix = store or {}
    for hits in matrix.values():
        if any(hit not in (".", "-", "", None) for hit in hits):
            return True
    return False

def collect_filled_pattern_slots(patterns_1, patterns_2, drums_808, drums_909):
    filled = set()
    for slot, steps in (patterns_1 or {}).items():
        if pattern_store_has_content(steps, "303"):
            filled.add(str(slot).upper())
    for slot, steps in (patterns_2 or {}).items():
        if pattern_store_has_content(steps, "303"):
            filled.add(str(slot).upper())
    for slot, matrix in (drums_808 or {}).items():
        if pattern_store_has_content(matrix, "drums"):
            filled.add(str(slot).upper())
    for slot, matrix in (drums_909 or {}).items():
        if pattern_store_has_content(matrix, "drums"):
            filled.add(str(slot).upper())
    return filled

def collect_filled_pattern_slots_for_store(store, kind="303"):
    filled = set()
    for slot, payload in (store or {}).items():
        if pattern_store_has_content(payload, kind):
            filled.add(str(slot).upper())
    return filled

def collect_filled_banks(filled_slots):
    banks = set()
    for slot in filled_slots or []:
        if slot and len(slot) >= 1 and slot[0] in "ABCD":
            banks.add(slot[0])
    return banks

class ReBirthPatternSelector(tk.Frame):
    """ReBirth-style bank (A-D) + pattern (1-8) picker."""

    def __init__(self, parent, on_change=None, compact=False, **kwargs):
        super().__init__(parent, bg="#1A1C27", highlightbackground="#404563", highlightthickness=1, **kwargs)
        self.on_change = on_change
        self._bank = "A"
        self._pat = 1
        self._bank_btns = {}
        self._pat_btns = {}
        self._filled_slots = set()
        self._filled_banks = set()
        pad = 2 if compact else 3
        btn_w = 2
        inner = tk.Frame(self, bg="#1A1C27")
        inner.pack(padx=4 if compact else 5, pady=4 if compact else 5)
        tk.Label(inner, text="PATTERN", font=("Segoe UI", 7, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(anchor="w")
        pat_grid = tk.Frame(inner, bg="#1A1C27")
        pat_grid.pack(pady=(2, 6))
        for row in range(2):
            row_frame = tk.Frame(pat_grid, bg="#1A1C27")
            row_frame.pack()
            for col in range(4):
                num = row * 4 + col + 1
                btn = tk.Button(
                    row_frame,
                    text=str(num),
                    width=btn_w,
                    font=("Segoe UI", 8, "bold"),
                    fg="#E8EAF6",
                    bg="#242736",
                    activebackground="#FF3366",
                    bd=0,
                    cursor="hand2",
                    command=lambda n=num: self._select_pat(n),
                )
                btn.pack(side=tk.LEFT, padx=pad, pady=pad, ipady=1)
                self._pat_btns[num] = btn
        tk.Label(inner, text="BANK:", font=("Segoe UI", 7, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(anchor="w")
        bank_row = tk.Frame(inner, bg="#1A1C27")
        bank_row.pack(pady=(2, 0))
        for bank in ("A", "B", "C", "D"):
            btn = tk.Button(
                bank_row,
                text=bank,
                width=btn_w,
                font=("Segoe UI", 8, "bold"),
                fg="#E8EAF6",
                bg="#242736",
                activebackground="#FF3366",
                bd=0,
                cursor="hand2",
                command=lambda b=bank: self._select_bank(b),
            )
            btn.pack(side=tk.LEFT, padx=pad, ipady=1)
            self._bank_btns[bank] = btn
        self._refresh_buttons()

    def _select_bank(self, bank):
        self._bank = bank
        self._refresh_buttons()
        if self.on_change:
            self.on_change(self.get_slot())

    def _select_pat(self, num):
        self._pat = num
        self._refresh_buttons()
        if self.on_change:
            self.on_change(self.get_slot())

    def set_filled_state(self, filled_slots=None):
        filled_slots = filled_slots or set()
        self._filled_slots = {str(slot).upper() for slot in filled_slots if slot}
        self._filled_banks = collect_filled_banks(self._filled_slots)
        self._refresh_buttons()

    def _refresh_buttons(self):
        active_bg, active_fg = "#FF3366", "#FFFFFF"
        idle_bg, idle_fg = "#242736", "#E8EAF6"
        filled_bg, filled_fg = "#1A4028", "#00FF66"
        filled_bank_bg, filled_bank_fg = "#243628", "#7CFFAA"
        for bank, btn in self._bank_btns.items():
            if bank == self._bank:
                btn.config(bg=active_bg, fg=active_fg)
            elif bank in self._filled_banks:
                btn.config(bg=filled_bank_bg, fg=filled_bank_fg)
            else:
                btn.config(bg=idle_bg, fg=idle_fg)
        for num, btn in self._pat_btns.items():
            slot_code = f"{self._bank}{num}"
            if num == self._pat:
                btn.config(bg=active_bg, fg=active_fg)
            elif slot_code in self._filled_slots:
                btn.config(bg=filled_bg, fg=filled_fg)
            else:
                btn.config(bg=idle_bg, fg=idle_fg)

    def get_slot(self):
        return f"{self._bank}{self._pat}"

    def set_slot(self, slot_code):
        if not slot_code or len(slot_code) < 2:
            return
        bank = slot_code[0].upper()
        try:
            num = int(slot_code[1:])
        except ValueError:
            return
        if bank in "ABCD" and 1 <= num <= 8:
            self._bank = bank
            self._pat = num
            self._refresh_buttons()

def import_patterns_from_rbs(rbs_path):
    """Load all pattern banks from an .rbs song into editor stores."""
    data = deconstruct_rbs_song(rbs_path)
    patterns_1 = {}
    patterns_2 = {}
    drums_808 = {}
    drums_909 = {}
    for item in data.get("303_1", []):
        patterns_1[item["name"]] = normalize_303_steps(item.get("steps", []))
    for item in data.get("303_2", []):
        patterns_2[item["name"]] = normalize_303_steps(item.get("steps", []))
    for item in data.get("808", []):
        drums_808[item["name"]] = clone_drum_matrix(item.get("matrix", {}), is_909=False)
    for item in data.get("909", []):
        drums_909[item["name"]] = clone_drum_matrix(item.get("matrix", {}), is_909=True)
    return patterns_1, patterns_2, drums_808, drums_909

def ensure_pattern_banks_dir():
    try:
        os.makedirs(PATTERN_BANKS_DIR, exist_ok=True)
    except OSError:
        pass
    return PATTERN_BANKS_DIR

def list_pattern_bank_files():
    ensure_pattern_banks_dir()
    banks = []
    if not os.path.isdir(PATTERN_BANKS_DIR):
        return banks
    for root, _, filenames in os.walk(PATTERN_BANKS_DIR):
        for filename in filenames:
            lower = filename.lower()
            if not lower.endswith(".json"):
                continue
            if lower in ("community-pack-index.json", "pack-index.json"):
                continue
            full_path = os.path.join(root, filename)
            if os.path.isfile(full_path):
                banks.append(full_path)
    banks.sort(key=lambda path: path.lower())
    return banks

def _pattern_bank_slot_dict(store, normalize_fn):
    result = {}
    if not store:
        return result
    for slot_code, payload in store.items():
        slot = str(slot_code).strip().upper()
        if pattern_slot_to_index(slot) is None:
            continue
        result[slot] = normalize_fn(payload)
    return result

def export_patterns_to_bank_json(
    output_path,
    patterns_1,
    patterns_2,
    drums_808,
    drums_909,
    name="Custom Pattern Bank",
    description="",
    author="",
    tags=None,
    source_song="",
):
    payload = {
        "format": PATTERN_BANK_FORMAT,
        "version": PATTERN_BANK_VERSION,
        "name": name or "Custom Pattern Bank",
        "description": description or "",
        "author": author or "",
        "tags": list(tags or []),
        "source_song": source_song or "",
        "303_1": _pattern_bank_slot_dict(patterns_1, normalize_303_steps),
        "303_2": _pattern_bank_slot_dict(patterns_2, normalize_303_steps),
        "808": _pattern_bank_slot_dict(drums_808, lambda matrix: clone_drum_matrix(matrix, is_909=False)),
        "909": _pattern_bank_slot_dict(drums_909, lambda matrix: clone_drum_matrix(matrix, is_909=True)),
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return True

def import_patterns_from_bank_json(bank_path):
    with open(bank_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("format") != PATTERN_BANK_FORMAT:
        raise ValueError("Unsupported pattern bank format.")
    patterns_1 = {}
    patterns_2 = {}
    drums_808 = {}
    drums_909 = {}
    for slot_code, steps in (payload.get("303_1") or {}).items():
        patterns_1[str(slot_code).upper()] = normalize_303_steps(steps)
    for slot_code, steps in (payload.get("303_2") or {}).items():
        patterns_2[str(slot_code).upper()] = normalize_303_steps(steps)
    for slot_code, matrix in (payload.get("808") or {}).items():
        drums_808[str(slot_code).upper()] = clone_drum_matrix(matrix, is_909=False)
    for slot_code, matrix in (payload.get("909") or {}).items():
        drums_909[str(slot_code).upper()] = clone_drum_matrix(matrix, is_909=True)
    meta = {
        "name": payload.get("name") or os.path.splitext(os.path.basename(bank_path))[0],
        "description": payload.get("description") or "",
        "author": payload.get("author") or "",
        "tags": payload.get("tags") or [],
        "source_song": payload.get("source_song") or "",
        "path": bank_path,
    }
    return patterns_1, patterns_2, drums_808, drums_909, meta

def export_song_to_pattern_bank_json(rbs_path, output_path, description="", author="", tags=None):
    patterns_1, patterns_2, drums_808, drums_909 = import_patterns_from_rbs(rbs_path)
    song_title = os.path.splitext(os.path.basename(rbs_path))[0]
    return export_patterns_to_bank_json(
        output_path,
        patterns_1,
        patterns_2,
        drums_808,
        drums_909,
        name=song_title,
        description=description or f"Patterns extracted from {song_title}",
        author=author,
        tags=tags,
        source_song=os.path.basename(rbs_path),
    )

def concat_pcm_buffers(chunks, gap_samples=0):
    if not chunks:
        return b""
    gap = b"\x00\x00" * gap_samples
    parts = []
    for i, chunk in enumerate(chunks):
        if chunk:
            parts.append(chunk)
            if gap_samples and i < len(chunks) - 1:
                parts.append(gap)
    return b"".join(parts)

def build_acid_mix_pcm(
    steps_303_1,
    steps_303_2,
    drum_matrix=None,
    bpm=128,
    sample_rate=44100,
    mute_303_1=False,
    mute_303_2=False,
    mute_drums=False,
    gain_303_1=1.0,
    gain_303_2=1.0,
    gain_drums=1.0,
):
    silent = [{"active": False}] * 16
    pcm_parts = []
    if not mute_303_1:
        pcm_parts.append(
            scale_pcm_buffer(
                synthesize_303_pattern_pcm(steps_303_1 or silent, bpm=bpm, sample_rate=sample_rate),
                gain_303_1,
            )
        )
    if not mute_303_2:
        pcm_parts.append(
            scale_pcm_buffer(
                synthesize_303_pattern_pcm(steps_303_2 or silent, bpm=bpm, sample_rate=sample_rate),
                gain_303_2,
            )
        )
    pcm_data = b""
    for part in pcm_parts:
        pcm_data = mix_pcm_buffers(pcm_data, part) if pcm_data else part
    if drum_matrix and not mute_drums:
        pcm_drums = scale_pcm_buffer(
            synthesize_drum_pattern_pcm(drum_matrix, bpm=bpm, sample_rate=sample_rate),
            gain_drums,
        )
        pcm_data = mix_pcm_buffers(pcm_data, pcm_drums) if pcm_data else pcm_drums
    return pcm_data

def synthesize_acid_mix_preview(
    steps_303_1,
    steps_303_2,
    drum_matrix=None,
    bpm=128,
    sample_rate=44100,
    mute_303_1=False,
    mute_303_2=False,
    mute_drums=False,
    gain_303_1=1.0,
    gain_303_2=1.0,
    gain_drums=1.0,
):
    pcm_data = build_acid_mix_pcm(
        steps_303_1,
        steps_303_2,
        drum_matrix,
        bpm,
        sample_rate,
        mute_303_1,
        mute_303_2,
        mute_drums,
        gain_303_1,
        gain_303_2,
        gain_drums,
    )
    if not pcm_data:
        silent = [{"active": False}] * 16
        pcm_data = synthesize_303_pattern_pcm(silent, bpm=bpm, sample_rate=sample_rate)
    temp_path = os.path.join(os.environ.get("TEMP", BASE_DIR), "acid_mix_preview.wav")
    try:
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        return temp_path
    except Exception:
        return None

class Acid303PianoRoll(tk.Frame):
    TOOL_SPECS = (
        ("note", "Note", "#00FF66"),
        ("accent", "Accent", "#FF9500"),
        ("slide", "Slide", "#00E5FF"),
        ("up", "Up", "#FF66CC"),
        ("down", "Down", "#8A2BE2"),
        ("erase", "Erase", "#FF453A"),
    )

    def __init__(self, parent, on_change=None, on_randomize=None, on_step_audition=None, **kwargs):
        super().__init__(parent, bg="#12131A", **kwargs)
        self.on_change = on_change
        self.on_randomize = on_randomize
        self.on_step_audition = on_step_audition
        self.steps = empty_303_steps()
        self.ghost_steps = None
        self.playhead_step = None
        self._clipboard_steps = None
        self.active_tool = "note"
        self._undo_stack = []
        self._max_undo = 48
        self._step_w = 22
        self._row_h = 13
        self._left_pad = 22
        self._top_pad = 14
        self._build_toolbar()
        self._build_canvas()
        self.bind("<Configure>", self._on_frame_resize)
        self.canvas.bind("<Control-z>", lambda _e: self.undo())
        self.canvas.bind("<Control-c>", lambda _e: self.copy_steps())
        self.canvas.bind("<Control-v>", lambda _e: self.paste_steps())
        self.canvas.bind("<Delete>", lambda _e: self.set_tool("erase"))

    def _build_toolbar(self):
        bar = tk.Frame(self, bg="#12131A")
        bar.pack(fill=tk.X, padx=2, pady=(0, 2))
        tk.Label(bar, text="Edit Tool:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A").pack(side=tk.LEFT, padx=(0, 6))
        self.tool_buttons = {}
        for tool_id, label, color in self.TOOL_SPECS:
            btn = tk.Button(
                bar,
                text=label,
                font=("Segoe UI", 8, "bold"),
                fg="#FFFFFF",
                bg="#242736",
                activebackground=color,
                bd=0,
                cursor="hand2",
                command=lambda t=tool_id: self.set_tool(t),
            )
            btn.pack(side=tk.LEFT, padx=2, ipadx=6, ipady=2)
            self.tool_buttons[tool_id] = btn
        tk.Button(
            bar,
            text="Clear",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#3A3D52",
            bd=0,
            cursor="hand2",
            command=self.clear_slot,
        ).pack(side=tk.RIGHT, padx=(4, 0), ipadx=8, ipady=2)
        self.set_tool("note")

    def _build_canvas(self):
        self._update_canvas_geometry()
        self.canvas = tk.Canvas(self, width=self._canvas_w, height=self._canvas_h, bg="#12131A", highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.redraw()

    def _update_canvas_geometry(self):
        self._canvas_w = max(360, self._left_pad + self._step_w * 16 + 8)
        toolbar_h = 34
        frame_h = self.winfo_height() if self.winfo_height() > 1 else 0
        if frame_h > toolbar_h + self._top_pad + 40:
            avail_rows = frame_h - toolbar_h - self._top_pad - 10
            self._row_h = max(14, min(28, avail_rows // len(ACID_PIANO_ROWS)))
        self._canvas_h = self._top_pad + self._row_h * len(ACID_PIANO_ROWS) + 8

    def _on_frame_resize(self, event):
        if event.width < 10 or event.height < 10:
            return
        old_row_h = self._row_h
        self._update_canvas_geometry()
        if hasattr(self, "canvas") and self._row_h != old_row_h:
            self.canvas.config(height=self._canvas_h)
            self.redraw()
        elif hasattr(self, "canvas") and self.canvas.winfo_height() != self._canvas_h:
            self.canvas.config(height=self._canvas_h)
            self.redraw()

    def set_tool(self, tool_id):
        self.active_tool = tool_id
        for tid, btn in self.tool_buttons.items():
            color = next(c for t, _, c in self.TOOL_SPECS if t == tid)
            if tid == tool_id:
                btn.config(bg=color, fg="#12131A")
            else:
                btn.config(bg="#242736", fg="#FFFFFF")

    def load_steps(self, steps, ghost_steps=None):
        self.steps = normalize_303_steps(steps)
        self.ghost_steps = normalize_303_steps(ghost_steps) if ghost_steps is not None else None
        self._undo_stack.clear()
        self.redraw()

    def set_playhead(self, step_idx):
        new_step = step_idx if step_idx is None or 0 <= step_idx < 16 else None
        if new_step == self.playhead_step:
            return
        self.playhead_step = new_step
        c = self.canvas
        c.delete("playhead")
        if self.playhead_step is None:
            return
        canvas_h = self._top_pad + self._row_h * len(ACID_PIANO_ROWS) + 8
        px0 = self._left_pad + self.playhead_step * self._step_w
        px1 = px0 + self._step_w - 2
        c.create_rectangle(px0, self._top_pad - 2, px1, canvas_h - 4, outline="#00E5FF", width=2, tags=("playhead",))

    def copy_steps(self):
        self._clipboard_steps = clone_303_steps(self.steps)
        return "break"

    def paste_steps(self):
        if not self._clipboard_steps:
            return "break"
        self._push_undo()
        self.steps = clone_303_steps(self._clipboard_steps)
        self.redraw()
        if self.on_change:
            self.on_change(self.get_steps())
        return "break"

    def get_steps(self):
        return normalize_303_steps(self.steps)

    def _push_undo(self):
        self._undo_stack.append(clone_303_steps(self.steps))
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def undo(self):
        if not self._undo_stack:
            return False
        self.steps = self._undo_stack.pop()
        self.redraw()
        if self.on_change:
            self.on_change(self.get_steps())
        return True

    def clear_slot(self):
        self._push_undo()
        self.steps = empty_303_steps()
        self.redraw()
        if self.on_change:
            self.on_change(self.get_steps())

    def _randomize_slot(self):
        if self.on_randomize:
            self.on_randomize()

    def _step_from_x(self, x):
        idx = int((x - self._left_pad) // self._step_w)
        if 0 <= idx < 16:
            return idx
        return None

    def _note_from_y(self, y):
        row = int((y - self._top_pad) // self._row_h)
        if 0 <= row < len(ACID_PIANO_ROWS):
            return ACID_PIANO_ROWS[row]
        return None

    def _on_canvas_click(self, event):
        step_idx = self._step_from_x(event.x)
        if step_idx is None:
            return
        note_name = self._note_from_y(event.y)
        step = self.steps[step_idx]
        self._push_undo()

        if self.active_tool == "erase":
            self.steps[step_idx] = empty_303_steps()[0]
        elif self.active_tool == "note":
            if note_name is None:
                return
            self.steps[step_idx] = {
                "note": note_name,
                "up": "-",
                "accent": "-",
                "slide": "-",
                "active": True,
            }
        elif self.active_tool in ("accent", "slide", "up", "down"):
            if not step.get("active"):
                return
            if self.active_tool == "accent":
                step["accent"] = "-" if step.get("accent") == "A" else "A"
            elif self.active_tool == "slide":
                step["slide"] = "-" if step.get("slide") == "S" else "S"
            elif self.active_tool == "up":
                if step.get("up") == "^":
                    step["up"] = "-"
                else:
                    step["up"] = "^"
                    step["down"] = "-"
            elif self.active_tool == "down":
                if step.get("up") == "v":
                    step["up"] = "-"
                else:
                    step["up"] = "v"
        else:
            return

        self.redraw()
        if self.on_change:
            self.on_change(self.get_steps())
        if self.on_step_audition and self.active_tool != "erase":
            preview_step = self.steps[step_idx]
            if preview_step.get("active"):
                self.on_step_audition(preview_step)

    def redraw(self):
        c = self.canvas
        c.delete("all")
        canvas_h = self._top_pad + self._row_h * len(ACID_PIANO_ROWS) + 8
        if self.playhead_step is not None:
            px0 = self._left_pad + self.playhead_step * self._step_w
            px1 = px0 + self._step_w - 2
            c.create_rectangle(px0, self._top_pad - 2, px1, canvas_h - 4, outline="#00E5FF", width=2, tags=("playhead",))
        for i in range(16):
            x0 = self._left_pad + i * self._step_w
            x1 = x0 + self._step_w - 2
            c.create_text((x0 + x1) / 2, 10, text=f"{i + 1:02d}", fill="#6C7293", font=("Consolas", 7))
            step = self.steps[i]
            if step.get("active"):
                badges = []
                if step.get("accent") == "A":
                    badges.append("A")
                if step.get("slide") == "S":
                    badges.append("T")
                if step.get("up") == "^":
                    badges.append("^")
                elif step.get("up") == "v":
                    badges.append("v")
                if badges:
                    c.create_text((x0 + x1) / 2, self._top_pad - 8, text="".join(badges), fill="#FFD700", font=("Consolas", 7, "bold"))

        for row_i, note_name in enumerate(ACID_PIANO_ROWS):
            y0 = self._top_pad + row_i * self._row_h
            y1 = y0 + self._row_h - 2
            c.create_text(14, (y0 + y1) / 2, text=note_name, fill="#6C7293", font=("Consolas", 6))
            for step_i in range(16):
                x0 = self._left_pad + step_i * self._step_w
                x1 = x0 + self._step_w - 2
                if self.ghost_steps:
                    ghost = self.ghost_steps[step_i]
                    if ghost.get("active") and ghost.get("note") == note_name and not (
                        self.steps[step_i].get("active") and self.steps[step_i].get("note") == note_name
                    ):
                        c.create_rectangle(
                            x0, y0, x1, y1,
                            fill="#4A3560",
                            outline="#C080FF",
                            width=1,
                            dash=(2, 2),
                        )
                step = self.steps[step_i]
                fill = "#1A1C27"
                outline = "#282B3C"
                if step.get("active") and step.get("note") == note_name:
                    fill = "#0B5D3B" if step.get("accent") != "A" else "#7A4E00"
                    outline = "#00FF66" if step.get("accent") != "A" else "#FF9500"
                    if step.get("slide") == "S":
                        outline = "#00E5FF"
                c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=1, tags=("cell",))

class Acid303DiffStrip(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg="#12131A", **kwargs)
        self.lbl = tk.Label(
            self,
            text="303 #1 vs #2 diff  (magenta step = different)",
            font=("Segoe UI", 8, "bold"),
            fg="#FF66CC",
            bg="#12131A",
            anchor="w",
        )
        self.lbl.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.canvas = tk.Canvas(self, width=620, height=28, bg="#12131A", highlightthickness=0, bd=0)
        self.canvas.pack(padx=2, pady=(0, 2))
        self.steps_a = empty_303_steps()
        self.steps_b = empty_303_steps()

    def load_steps(self, steps_a, steps_b):
        self.steps_a = normalize_303_steps(steps_a)
        self.steps_b = normalize_303_steps(steps_b)
        self.redraw()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        same = diff = only_a = only_b = 0
        for i in range(16):
            x0 = 8 + i * 38
            x1 = x0 + 34
            key_a = acid_step_key(self.steps_a[i])
            key_b = acid_step_key(self.steps_b[i])
            if key_a == key_b:
                fill, outline = "#242736", "#282B3C"
                same += 1
            elif key_a == ("rest",) and key_b != ("rest",):
                fill, outline = "#1B3552", "#00E5FF"
                only_b += 1
            elif key_b == ("rest",) and key_a != ("rest",):
                fill, outline = "#1B4030", "#00FF66"
                only_a += 1
            else:
                fill, outline = "#4A2148", "#FF66CC"
                diff += 1
            c.create_rectangle(x0, 6, x1, 22, fill=fill, outline=outline, width=1)
            c.create_text((x0 + x1) / 2, 14, text=f"{i + 1:02d}", fill="#E8EAF6", font=("Consolas", 7))
        self.lbl.config(
            text=(
                f"303 #1 vs #2  |  same {same}  ·  #1 only {only_a}  ·  #2 only {only_b}  ·  different {diff}"
            )
        )

class AcidDrumStepGrid(tk.Frame):
    HIT_CYCLE_909 = (".", "x", "A")
    HIT_CYCLE_808 = (".", "x")

    def __init__(self, parent, get_is_909=None, on_change=None, on_randomize=None, on_hit_audition=None, **kwargs):
        super().__init__(parent, bg="#12131A", **kwargs)
        self.get_is_909 = get_is_909 or (lambda: True)
        self.on_change = on_change
        self.on_randomize = on_randomize
        self.on_hit_audition = on_hit_audition
        self.matrix = empty_drum_matrix(True)
        self.playhead_step = None
        self._undo_stack = []
        self._max_undo = 48
        self._step_w = 20
        self._row_h = 13
        self._left_pad = 24
        self._top_pad = 14
        self._build_toolbar()
        self._build_canvas()
        self.bind("<Configure>", self._on_frame_resize)
        self.canvas.bind("<Control-z>", lambda _e: self.undo())
        self.canvas.bind("<Delete>", lambda _e: self._erase_at_event)

    def _erase_at_event(self, event):
        step_idx = self._step_from_x(event.x)
        inst = self._inst_from_y(event.y)
        if step_idx is None or inst is None:
            return
        self._push_undo()
        self.matrix.setdefault(inst, ["."] * 16)[step_idx] = "."
        self.redraw()
        if self.on_change:
            self.on_change(self.get_matrix())

    def _build_toolbar(self):
        bar = tk.Frame(self, bg="#12131A")
        bar.pack(fill=tk.X, padx=2, pady=(0, 2))
        self.machine_lbl = tk.Label(
            bar,
            text="TR-909 step grid  (click: empty → hit → accent)",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
        )
        self.machine_lbl.pack(side=tk.LEFT)
        tk.Button(
            bar,
            text="Clear",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#3A3D52",
            bd=0,
            cursor="hand2",
            command=self.clear_slot,
        ).pack(side=tk.RIGHT, padx=(4, 0), ipadx=8, ipady=2)

    def refresh_machine_label(self):
        if self.get_is_909():
            self.machine_lbl.config(text="TR-909 step grid  (click: empty → hit → accent)")
        else:
            self.machine_lbl.config(text="TR-808 step grid  (click: empty → hit)")

    def _build_canvas(self):
        self._update_canvas_geometry()
        self.canvas = tk.Canvas(self, width=self._canvas_w, height=self._canvas_h, bg="#12131A", highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=(0, 2))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.redraw()

    def _update_canvas_geometry(self):
        labels = self._labels()
        self._canvas_w = max(360, self._left_pad + self._step_w * 16 + 8)
        toolbar_h = 34
        frame_h = self.winfo_height() if self.winfo_height() > 1 else 0
        if frame_h > toolbar_h + self._top_pad + 40:
            avail_rows = frame_h - toolbar_h - self._top_pad - 10
            self._row_h = max(14, min(26, avail_rows // max(1, len(labels))))
        self._canvas_h = self._top_pad + self._row_h * len(labels) + 8

    def _on_frame_resize(self, event):
        if event.width < 10 or event.height < 10:
            return
        old_row_h = self._row_h
        self._update_canvas_geometry()
        if hasattr(self, "canvas") and (self._row_h != old_row_h or self.canvas.winfo_height() != self._canvas_h):
            self.canvas.config(height=self._canvas_h)
            self.redraw()

    def _labels(self):
        return INST_LABELS_909 if self.get_is_909() else INST_LABELS_808

    def _cycle_for_hit(self, hit):
        cycle = self.HIT_CYCLE_909 if self.get_is_909() else self.HIT_CYCLE_808
        try:
            idx = cycle.index(hit)
        except ValueError:
            idx = -1
        return cycle[(idx + 1) % len(cycle)]

    def load_matrix(self, matrix=None):
        labels = self._labels()
        base = empty_drum_matrix(self.get_is_909())
        if matrix:
            for lbl in labels:
                src = matrix.get(lbl, ["."] * 16)
                base[lbl] = [src[s] if s < len(src) else "." for s in range(16)]
        self.matrix = base
        self._undo_stack.clear()
        self.refresh_machine_label()
        self.redraw()

    def set_playhead(self, step_idx):
        new_step = step_idx if step_idx is None or 0 <= step_idx < 16 else None
        if new_step == self.playhead_step:
            return
        self.playhead_step = new_step
        c = self.canvas
        c.delete("playhead")
        if self.playhead_step is None:
            return
        labels = self._labels()
        canvas_h = self._top_pad + self._row_h * len(labels) + 8
        px0 = self._left_pad + self.playhead_step * self._step_w
        px1 = px0 + self._step_w - 2
        c.create_rectangle(px0, self._top_pad - 2, px1, canvas_h - 4, outline="#00E5FF", width=2, tags=("playhead",))

    def get_matrix(self):
        labels = self._labels()
        return {lbl: list(self.matrix.get(lbl, ["."] * 16)) for lbl in labels}

    def _push_undo(self):
        self._undo_stack.append(clone_drum_matrix(self.matrix, self.get_is_909()))
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def undo(self):
        if not self._undo_stack:
            return False
        self.matrix = self._undo_stack.pop()
        self.redraw()
        if self.on_change:
            self.on_change(self.get_matrix())
        return True

    def clear_slot(self):
        self._push_undo()
        self.matrix = empty_drum_matrix(self.get_is_909())
        self.redraw()
        if self.on_change:
            self.on_change(self.get_matrix())

    def _randomize_slot(self):
        if self.on_randomize:
            self.on_randomize()

    def _step_from_x(self, x):
        idx = int((x - self._left_pad) // self._step_w)
        if 0 <= idx < 16:
            return idx
        return None

    def _inst_from_y(self, y):
        row = int((y - self._top_pad) // self._row_h)
        labels = self._labels()
        if 0 <= row < len(labels):
            return labels[row]
        return None

    def _on_canvas_click(self, event):
        step_idx = self._step_from_x(event.x)
        inst = self._inst_from_y(event.y)
        if step_idx is None or inst is None:
            return
        self._push_undo()
        hits = self.matrix.setdefault(inst, ["."] * 16)
        hits[step_idx] = self._cycle_for_hit(hits[step_idx])
        new_hit = hits[step_idx]
        self.redraw()
        if self.on_change:
            self.on_change(self.get_matrix())
        if self.on_hit_audition and new_hit in ("x", "A"):
            self.on_hit_audition(inst, new_hit == "A")

    def redraw(self):
        c = self.canvas
        c.delete("all")
        labels = self._labels()
        canvas_h = self._top_pad + self._row_h * len(labels) + 8
        if self.playhead_step is not None:
            px0 = self._left_pad + self.playhead_step * self._step_w
            px1 = px0 + self._step_w - 2
            c.create_rectangle(px0, self._top_pad - 2, px1, canvas_h - 4, outline="#00E5FF", width=2, tags=("playhead",))
        for i in range(16):
            x0 = self._left_pad + i * self._step_w
            x1 = x0 + self._step_w - 2
            c.create_text((x0 + x1) / 2, 10, text=f"{i + 1:02d}", fill="#6C7293", font=("Consolas", 7))

        for row_i, lbl in enumerate(labels):
            y0 = self._top_pad + row_i * self._row_h
            y1 = y0 + self._row_h - 2
            c.create_text(14, (y0 + y1) / 2, text=lbl, fill="#6C7293", font=("Consolas", 6))
            hits = self.matrix.get(lbl, ["."] * 16)
            for step_i in range(16):
                x0 = self._left_pad + step_i * self._step_w
                x1 = x0 + self._step_w - 2
                hit = hits[step_i] if step_i < len(hits) else "."
                if hit == "x":
                    fill, outline = "#FF9500", "#FFB84D"
                elif hit == "A":
                    fill, outline = "#FF453A", "#FF6B61"
                else:
                    fill, outline = "#242736", "#282B3C"
                c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=1)

class ModernRebirthStudioToolBox:
    def __init__(self, root):
        self.root = root
        self.root.title("ReBirth ToolBox")
        self.root.geometry("920x900")
        self.root.minsize(920, 780)
        self.root.resizable(True, True)
        self.root.configure(bg="#12131A")

        set_window_icon(self.root)
        self.config = load_config()
        apply_config_paths(self.config)
        self._build_palette = get_build_palette()
        self._palette = get_active_theme_palette(self.config)
        self._theme_ids = []
        self._theme_labels = []

        self.iso_path = find_iso_file(self.config)
        self.selected_res_index = min(max(0, self.config.get("launch_resolution_index", 6)), len(RESOLUTIONS) - 1)
        self._resolution_sync_source = None
        self.builtin_songs = discover_builtin_default_songs()
        self.rbs_songs = []
        self.installed_mods = []
        self.generated_patterns = {}
        self.generated_patterns_303_2 = {}
        self.generated_drum_patterns_909 = {}
        self.generated_drum_patterns_808 = {}
        self.generated_drum_machine = "909"
        self.acid_active_slots = {"303_1": "A1", "303_2": "A1", "808": "A1", "909": "A1"}
        self.acid_loop_enabled = False
        self._acid_preview_stop = threading.Event()
        self._acid_preview_thread = None
        self._acid_preview_mode = "full"
        self._acid_preview_restart_id = None
        self._playhead_timer_id = None
        self._playhead_running = False
        self.acid_preview_bpm = 128
        self.current_preview_pat = "A1"
        self.selected_startup_song_path = None
        self.browsed_startup_song = None
        self._install_restart_prompted = False
        self.startup_song_tiles = {}
        self.startup_tile_photos = []
        self.mod_songs_index = {}
        self.selected_mod_name = "Standard ReBirth"
        self.selected_mod_path = None
        self.mod_tiles = {}
        self.mod_tile_photos = []
        self.mod_row_widgets = {}
        self._mod_gallery_dirty = True
        self._mod_gallery_built = False
        self._mod_gallery_build_index = 0
        self._mod_gallery_building = False
        self._mod_gallery_reload_pending = False
        self._mod_canvas_rows = {}
        self._mod_gallery_top_y = 0.0
        self._mod_gallery_fallback_win = None
        self._mod_viewport_after = None
        self._mod_sync_after_id = None
        self.mod_filter_mode = "all"
        self._documents_gallery_loaded = False
        self.download_in_progress = False
        self.document_tile_photos = []
        self.document_tiles = {}
        self.document_files = []
        self._metadata_cache = {}
        self._mod_info_cache = {}
        self._library_cache_loaded = False
        self.library_sort_column = "title"
        self.library_sort_reverse = False
        self.library_heading_labels = {
            "fav": "⭐",
            "title": "FileName",
            "bpm": "BPM",
            "mode": "Mode",
            "dur": "Duration",
            "mod_name": "Mod Name",
            "description": "Description",
            "breakdown": "Patterns",
        }

        self.setup_styles()
        self.build_loading_overlay()
        self.show_loading_overlay("Please wait...", "Starting ReBirth ToolBox...")
        self.root.update()
        self.update_loading_overlay("Building interface...", title="Please wait...")
        self.root.update()
        self.build_ui()
        if self._palette != self._build_palette:
            self.apply_theme(self._build_palette)
        else:
            self.apply_theme_extras()
        if not is_setup_wizard_only(self.config):
            self.update_loading_overlay("Loading song library...", title="Please wait...")
            self.root.update()
            self.update_iso_status()
            self.refresh_start_launch_info()
            self.check_zombie_status()
            if self.try_load_library_cache():
                self.lbl_scan_status.config(
                    text="✔ Library loaded from cache — checking for updates...",
                    fg="#FF9500",
                )
                self.update_loading_overlay("Checking for new or changed songs...")
            else:
                self.show_loading_overlay("Please wait...", "Scanning song library and mod skins...")
            self.scan_files_async()
        else:
            self.hide_loading_overlay()
            self.refresh_get_rebirth_ui()

    def palette(self, key, default=None):
        if default is None:
            default = DEFAULT_THEME_COLORS.get(key, "#FFFFFF")
        return self._palette.get(key, default)

    def apply_theme(self, old_palette=None):
        old_palette = old_palette or dict(self._palette)
        self._palette = get_active_theme_palette(self.config)
        apply_theme_colors_to_widget(self.root, old_palette, self._palette)
        self.apply_theme_extras()
        self.refresh_start_launch_info()

    def apply_theme_extras(self):
        p = self._palette
        self.setup_styles()
        if hasattr(self, "btn_launch"):
            self.btn_launch.config(
                bg=p["btn_primary"],
                activebackground=p["btn_primary_hover"],
                fg=p["fg_primary"],
            )
        if hasattr(self, "btn_save_settings"):
            self.btn_save_settings.config(bg=p["btn_primary"], activebackground=p["btn_primary_hover"])
        if hasattr(self, "btn_verify_downloads"):
            self.btn_verify_downloads.config(bg=p["btn_secondary"], activebackground=p["bg_elevated"])
        if hasattr(self, "lbl_footer"):
            self.lbl_footer.config(bg=p["bg_root"], fg=p["fg_dim"])
        if hasattr(self, "header_canvas"):
            self.header_canvas.config(bg=p["bg_root"])
            self.header_canvas.delete("all")
            self.draw_synth_header(self.header_canvas, p)
        if hasattr(self, "start_info_card"):
            self.start_info_card.config(bg=p["bg_card"], highlightbackground=p["border"])
        if hasattr(self, "settings_btn_bar"):
            self.settings_btn_bar.config(bg=p["bg_panel"], highlightbackground=p["border"])

    def on_theme_selected(self, _event=None):
        idx = self.combo_theme_settings.current()
        if idx < 0 or idx >= len(self._theme_ids):
            return
        theme_id = self._theme_ids[idx]
        if theme_id == self.config.get("theme"):
            return
        old_palette = dict(self._palette)
        self.config["theme"] = theme_id
        self._palette = get_active_theme_palette(self.config)
        apply_theme_colors_to_widget(self.root, old_palette, self._palette)
        self.apply_theme_extras()
        save_config(self.config)
        self.refresh_start_launch_info()

    def refresh_start_launch_info(self):
        if not hasattr(self, "lbl_start_iso"):
            return
        p = self._palette
        downloads_rel = (self.config.get("directories") or {}).get("downloads", DEFAULT_DIRECTORY_PATHS["downloads"])
        if is_rebirth_exe_ready():
            self.lbl_start_iso.config(
                text=f"✔ Rebirth.exe ready",
                fg=p.get("accent_green", "#00FF66"),
            )
            self.lbl_start_iso_hint.config(text="", fg=p.get("fg_dim", "#6C7293"))
        else:
            self.lbl_start_iso.config(
                text="✖ Rebirth.exe missing — install via Get ReBirth (RB-338 2.0.1 Installer)",
                fg=p.get("accent_red", "#FF453A"),
            )
            self.lbl_start_iso_hint.config(
                text="Open Get ReBirth → Step 2: extract installer with 7-Zip into this folder.",
                fg=p.get("accent_orange", "#FF9500"),
            )

        if self.iso_path and os.path.exists(self.iso_path):
            iso_line = f"✔ ISO: {os.path.basename(self.iso_path)}"
            if is_rebirth_exe_ready():
                self.lbl_start_iso.config(
                    text=f"{self.lbl_start_iso.cget('text')}  |  {iso_line}",
                    fg=p.get("accent_green", "#00FF66"),
                )
        elif is_rebirth_exe_ready():
            self.lbl_start_iso.config(
                text=f"{self.lbl_start_iso.cget('text')}  |  ✖ ISO missing",
                fg=p.get("accent_orange", "#FF9500"),
            )
            self.lbl_start_iso_hint.config(
                text=f"Settings → CD-ROM / ISO IMAGE, or copy .iso into ToolBox folder or ./{downloads_rel}",
                fg=p.get("accent_orange", "#FF9500"),
            )

        idx = self.get_launch_resolution_index()
        res_name, width, height = RESOLUTIONS[idx]
        cpu_short = "ON (Core 0)" if self.var_cpu_affinity.get() else "OFF"
        if self.var_rebirth_super_rack.get():
            mode = resolve_super_rack_display(self.var_super_rack_scale.get())
            mode_short = "fit height" if mode == "fit_height" else "desktop"
            display_short = f"{SUPER_RACK_LABEL} ({mode_short})"
        elif self.var_rebirth_maximized.get():
            display_short = "Maximize"
        else:
            display_short = "Normal"
        song_path = self.get_selected_song_path()
        song_name = os.path.basename(song_path) if song_path else "(none)"
        mod_name = self.selected_mod_name or "Standard ReBirth"
        res_detail = f"{width}×{height}" if width and height else res_name
        if self.var_rebirth_super_rack.get():
            res_detail = "desktop (kept)"
        self.lbl_start_params.config(
            text=(
                f"Resolution {res_detail}  ·  CPU lock {cpu_short}  ·  Display {display_short}\n"
                f"Song {song_name}  ·  Mod {mod_name}"
            ),
            fg=p.get("fg_muted", "#A0A5C0"),
        )

    def setup_styles(self):
        p = self._palette
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TNotebook", background=p["bg_root"], borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            background=p["bg_panel"],
            foreground=p["fg_muted"],
            padding=[16, 7],
            font=("Segoe UI", 9, "bold"),
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", p["bg_elevated"])],
            foreground=[("selected", p["accent_cyan"])],
        )
        self.style.configure(
            "Dark.TCombobox",
            fieldbackground=p["bg_card"],
            background=p["border"],
            foreground=p["fg_primary"],
            arrowcolor=p["accent_cyan"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            padding=6,
        )
        self.style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", p["bg_card"]), ("disabled", p["bg_panel"])],
            foreground=[("readonly", p["fg_primary"]), ("disabled", p["fg_dim"])],
            background=[("readonly", p["border"]), ("disabled", p["bg_panel"])],
            selectbackground=[("readonly", p["select_bg"])],
            selectforeground=[("readonly", p["accent_cyan"])],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=p["bg_card"],
            background=p["border"],
            foreground=p["fg_primary"],
            arrowcolor=p["accent_cyan"],
            padding=5,
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", p["bg_card"])],
            foreground=[("readonly", p["fg_primary"])],
            background=[("readonly", p["border"])],
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            background=p["progress"],
            troughcolor=p["bg_card"],
            bordercolor=p["border"],
            lightcolor=p["progress"],
            darkcolor=p["progress"],
        )
        self.style.configure(
            "Dark.Treeview",
            background=p["bg_input"],
            fieldbackground=p["bg_input"],
            foreground=p["fg_primary"],
            bordercolor=p["border"],
            lightcolor=p["bg_input"],
            darkcolor=p["bg_input"],
            rowheight=24,
        )
        self.style.configure(
            "Dark.Treeview.Heading",
            background=p["bg_elevated"],
            foreground=p["accent_cyan"],
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        )
        self.style.map(
            "Dark.Treeview",
            background=[("selected", p["select_bg"])],
            foreground=[("selected", p["accent_cyan"])],
        )
        self.style.configure(
            "Dark.Vertical.TScrollbar",
            background=p["bg_elevated"],
            troughcolor=p["bg_card"],
            bordercolor=p["border"],
            arrowcolor=p["accent_cyan"],
        )
        self.style.configure(
            "Dark.Horizontal.TScrollbar",
            background=p["bg_elevated"],
            troughcolor=p["bg_card"],
            bordercolor=p["border"],
            arrowcolor=p["accent_cyan"],
        )
        self.root.option_add("*TCombobox*Listbox.background", p["bg_card"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["fg_primary"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", p["select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", p["accent_cyan"])

    def draw_synth_header(self, canvas, palette=None):
        p = palette or self._palette
        canvas.create_rectangle(0, 0, 920, 110, fill=p["bg_header"], outline=p["header_outline"], width=2)
        screws = [(15, 15), (905, 15), (15, 95), (905, 95)]
        for sx, sy in screws:
            canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=p["header_screw"], outline=p["border"], width=1)
            canvas.create_line(sx - 3, sy - 3, sx + 3, sy + 3, fill=p["bg_root"], width=1.5)

        canvas.create_rectangle(35, 20, 185, 90, fill=p["header_scope_bg"], outline=p["header_scope_border"], width=2)
        wave_pts = [(35, 55), (50, 35), (50, 75), (65, 35), (65, 75), (80, 55), (95, 30), (110, 80), (125, 40), (140, 70), (155, 55), (185, 55)]
        for i in range(len(wave_pts) - 1):
            canvas.create_line(
                wave_pts[i][0],
                wave_pts[i][1],
                wave_pts[i + 1][0],
                wave_pts[i + 1][1],
                fill=p["header_wave"],
                width=2,
            )

        canvas.create_text(400, 38, text="REBIRTH TOOLBOX", font=("Segoe UI", 18, "bold"), fill=p["accent_cyan"])
        canvas.create_text(400, 62, text="LAUNCH · MODS · SONG LIBRARY · INSPIRE ME", font=("Segoe UI", 8, "bold"), fill=p["accent_orange"])
        canvas.create_line(20, 104, 900, 104, fill=p["accent_cyan"], width=1)
        canvas.create_line(20, 106, 900, 106, fill=p["border"], width=1)

    def build_ui(self):
        self.lbl_footer = tk.Label(
            self.root,
            text="Autor: Tomas Krsko    |    Programmed by: AI",
            font=("Segoe UI", 8),
            fg="#6C7293",
            bg="#12131A",
        )
        self.lbl_footer.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 6))

        self.header_canvas = tk.Canvas(self.root, width=920, height=110, bg="#12131A", highlightthickness=0)
        self.header_canvas.pack(fill=tk.X)
        self.draw_synth_header(self.header_canvas)

        main_container = tk.Frame(self.root, bg="#12131A")
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        res_names = [r[0] for r in RESOLUTIONS]
        self.var_cpu_affinity = tk.BooleanVar(value=bool(self.config.get("cpu_affinity", True)))
        self.var_rebirth_maximized = tk.BooleanVar(value=bool(self.config.get("rebirth_maximized", True)))
        self.var_rebirth_super_rack = tk.BooleanVar(value=bool(self.config.get("rebirth_super_rack", False)))
        self.var_super_rack_scale = tk.StringVar(
            value=super_rack_display_label_for_value(
                self.config.get("rebirth_super_rack_display")
                or self.config.get("rebirth_super_rack_scale", 1.25)
            )
        )
        self._super_rack_bezel = None
        self._super_rack_bezel_root = None
        self._super_rack_canvas = None
        self._super_rack_active = False

        # ==================== TAB 1: Start ====================
        tab_launch = tk.Frame(self.notebook, bg="#1A1C27")
        self.notebook.add(tab_launch, text="Start")

        launch_bar = tk.Frame(tab_launch, bg="#1A1C27", highlightbackground="#282B3C", highlightthickness=1)
        launch_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8))
        self.launch_missing_frame = tk.Frame(launch_bar, bg="#2D1A21", highlightbackground="#FF453A", highlightthickness=1)
        self.lbl_missing_exe = tk.Label(
            self.launch_missing_frame,
            text=(
                "✖ Rebirth.exe not found in the ToolBox folder.\n"
                "Install ReBirth RB-338 using the RB-338 2.0.1 Installer (Step 2 in Get ReBirth), "
                "then deploy/copy Rebirth.exe here. Open the Get ReBirth tab for download and setup."
            ),
            font=("Segoe UI", 9, "bold"),
            fg="#FF9500",
            bg="#2D1A21",
            anchor="w",
            justify=tk.LEFT,
            wraplength=860,
        )
        self.lbl_missing_exe.pack(fill=tk.X, padx=10, pady=10)
        self.btn_launch = tk.Button(
            launch_bar,
            text="🚀 LAUNCH REBIRTH RB-338",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            activebackground="#00C880",
            bd=0,
            cursor="hand2",
            command=self.launch_rebirth,
        )
        self.btn_launch.pack(fill=tk.X, padx=8, pady=8, ipady=10)

        song_card = tk.Frame(tab_launch, bg="#1A1C27")
        song_card.pack(fill=tk.X, padx=12, pady=(6, 4))

        song_h_frame = tk.Frame(song_card, bg="#1A1C27")
        song_h_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(song_h_frame, text="SELECT STARTUP SONG", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.LEFT)
        tk.Button(
            song_h_frame,
            text="Browse for Song...",
            font=("Segoe UI", 8, "bold"),
            fg="#00E5FF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.browse_startup_song,
        ).pack(side=tk.RIGHT, ipadx=8, ipady=2)
        tk.Button(
            song_h_frame,
            text="🎲 Random Song",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#8A2BE2",
            bd=0,
            cursor="hand2",
            command=self.pick_random_startup_song,
        ).pack(side=tk.RIGHT, padx=(0, 6), ipadx=8, ipady=2)

        self.startup_tiles_frame = tk.Frame(song_card, bg="#1A1C27")
        self.startup_tiles_frame.pack(fill=tk.X, pady=(0, 8))

        meta_frame = tk.Frame(song_card, bg="#12131A", highlightbackground="#242736", highlightthickness=1)
        meta_frame.pack(fill=tk.X, pady=(0, 6), ipadx=8, ipady=6)

        m_line1 = tk.Frame(meta_frame, bg="#12131A")
        m_line1.pack(fill=tk.X)
        self.lbl_meta_bpm = tk.Label(m_line1, text="BPM: --", font=("Segoe UI", 9, "bold"), fg="#00FF66", bg="#12131A")
        self.lbl_meta_bpm.pack(side=tk.LEFT, padx=(0, 15))
        self.lbl_meta_mode = tk.Label(m_line1, text="Mode: --", font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#12131A")
        self.lbl_meta_mode.pack(side=tk.LEFT, padx=(0, 15))
        self.lbl_meta_engine = tk.Label(m_line1, text="Engine: ReBirth 2.0 Sound", font=("Segoe UI", 8), fg="#6C7293", bg="#12131A")
        self.lbl_meta_engine.pack(side=tk.LEFT)

        self.lbl_meta_dur = tk.Label(meta_frame, text="Duration: --", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#12131A", anchor="w")
        self.lbl_meta_dur.pack(fill=tk.X, pady=(2, 0))
        self.lbl_meta_mod = tk.Label(meta_frame, text="Mod Name: Standard ReBirth", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A", anchor="w")
        self.lbl_meta_mod.pack(fill=tk.X, pady=(2, 2))
        self.lbl_meta_pats = tk.Label(meta_frame, text="Active Patterns: -- (303 #1: 0 | 303 #2: 0 | 808: 0 | 909: 0)", font=("Segoe UI", 8), fg="#00E5FF", bg="#12131A", anchor="w")
        self.lbl_meta_pats.pack(fill=tk.X, pady=(0, 2))
        self.lbl_meta_title = tk.Label(meta_frame, text="Title: --", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#12131A", anchor="w")
        self.lbl_meta_title.pack(fill=tk.X, pady=(2, 2))
        self.lbl_meta_desc = tk.Label(meta_frame, text="Select a song to parse tempo, active patterns, mod name, and description...", font=("Segoe UI", 8, "italic"), fg="#6C7293", bg="#12131A", anchor="nw", justify=tk.LEFT, wraplength=860, height=3)
        self.lbl_meta_desc.pack(fill=tk.X)

        self.start_info_card = tk.Frame(tab_launch, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        self.start_info_card.pack(fill=tk.X, padx=12, pady=(4, 10), ipadx=10, ipady=8)
        tk.Label(
            self.start_info_card,
            text="LAUNCH READINESS",
            font=("Segoe UI", 8, "bold"),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        self.lbl_start_iso = tk.Label(
            self.start_info_card,
            text="Checking ISO status…",
            font=("Segoe UI", 9, "bold"),
            fg="#00E5FF",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
        )
        self.lbl_start_iso.pack(fill=tk.X)
        self.lbl_start_iso_hint = tk.Label(
            self.start_info_card,
            text="",
            font=("Segoe UI", 8),
            fg="#6C7293",
            bg="#12131A",
            anchor="nw",
            justify=tk.LEFT,
            wraplength=860,
        )
        self.lbl_start_iso_hint.pack(fill=tk.X, pady=(2, 8))
        tk.Label(
            self.start_info_card,
            text="LAUNCH PARAMETERS",
            font=("Segoe UI", 8, "bold"),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        self.lbl_start_params = tk.Label(
            self.start_info_card,
            text="",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="nw",
            justify=tk.LEFT,
            wraplength=860,
        )
        self.lbl_start_params.pack(fill=tk.X)

        # ==================== TAB 2: RBM DB ====================
        tab_mods = tk.Frame(self.notebook, bg="#1A1C27")
        self.notebook.add(tab_mods, text=MOD_TAB_LABEL)

        mod_header = tk.Frame(tab_mods, bg="#1A1C27")
        mod_header.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(mod_header, text="SELECT MOD SKIN", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.LEFT)
        self.lbl_mod_gallery_loading = tk.Label(
            mod_header,
            text="Please wait — loading mod database...",
            font=("Segoe UI", 8, "bold"),
            fg="#FF9500",
            bg="#1A1C27",
        )
        tk.Button(mod_header, text="↻ Refresh", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#242736", bd=0, cursor="hand2", command=self.force_refresh_mod_gallery).pack(side=tk.RIGHT, padx=(0, 6), ipadx=6, ipady=1)
        tk.Label(mod_header, text="Show:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.RIGHT, padx=(0, 4))
        self.combo_mod_filter = ttk.Combobox(
            mod_header,
            values=list(MOD_FILTER_LABELS),
            state="readonly",
            width=14,
            font=("Segoe UI", 8),
            style="Dark.TCombobox",
        )
        self.combo_mod_filter.current(0)
        self.combo_mod_filter.pack(side=tk.RIGHT, padx=(0, 8))
        self.combo_mod_filter.bind("<<ComboboxSelected>>", self.on_mod_filter_changed)
        tk.Button(mod_header, text="📥 Import New Mod...", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#242736", bd=0, cursor="hand2", command=self.import_new_mod).pack(side=tk.RIGHT, ipadx=6, ipady=1)

        tk.Label(
            tab_mods,
            text="Tip: click mod screenshot to select  |  double-click = empty ReBirth project with that mod",
            font=("Segoe UI", 8, "italic"),
            fg="#6C7293",
            bg="#1A1C27",
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8))

        self.mod_tools_row = tk.Frame(tab_mods, bg="#1A1C27")
        self.mod_tools_row.pack(fill=tk.X, padx=12, pady=(0, 4))
        tk.Label(
            self.mod_tools_row,
            text="★ Quick favorites:",
            font=("Segoe UI", 8, "bold"),
            fg="#A0A5C0",
            bg="#1A1C27",
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.mod_fav_quick_frame = tk.Frame(self.mod_tools_row, bg="#1A1C27")
        self.mod_fav_quick_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.mod_tiles_frame = tk.Frame(tab_mods, bg="#1A1C27")
        self.mod_tiles_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        self.mod_loading_overlay = tk.Frame(self.mod_tiles_frame, bg="#1A1C27")
        self.lbl_mod_loading_overlay = tk.Label(
            self.mod_loading_overlay,
            text="Please wait — loading mod database...",
            font=("Segoe UI", 11, "bold"),
            fg="#FF9500",
            bg="#1A1C27",
        )
        self.lbl_mod_loading_overlay.pack(expand=True)

        mod_scroll_wrap = tk.Frame(self.mod_tiles_frame, bg="#1A1C27")
        mod_scroll_wrap.pack(fill=tk.BOTH, expand=True)
        self.mod_scroll_wrap = mod_scroll_wrap
        self.mod_list_canvas = tk.Canvas(mod_scroll_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        self.mod_vscroll = ttk.Scrollbar(mod_scroll_wrap, orient="vertical", command=self._mod_gallery_yview)
        self.mod_list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.mod_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.mod_list_canvas.bind("<Configure>", self._on_mod_list_canvas_configure)
        self.bind_mod_list_scroll()
        self.mod_rows_host = tk.Frame(self.mod_list_canvas, bg="#12131A", width=400, height=400)
        self.mod_rows_host.pack_propagate(False)
        self.mod_rows_host.grid_propagate(False)
        self.mod_rows_host_id = self.mod_list_canvas.create_window(
            0, 0, window=self.mod_rows_host, anchor="nw", width=400, height=400
        )

        # ==================== TAB 3: Inspire Me ====================
        tab_acid = tk.Frame(self.notebook, bg="#1A1C27")
        self.tab_acid = tab_acid
        self.notebook.add(tab_acid, text="✨ Inspire Me")

        acid_bottom_bar = tk.Frame(tab_acid, bg="#1A1C27", highlightbackground="#282B3C", highlightthickness=1)
        acid_bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8))
        mix_btn_row = tk.Frame(acid_bottom_bar, bg="#1A1C27")
        mix_btn_row.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Button(
            mix_btn_row,
            text="▶ Play Mix Once",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            activebackground="#00C880",
            bd=0,
            cursor="hand2",
            command=self.play_acid_full_preview,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 4))
        self.btn_loop_mix = tk.Button(
            mix_btn_row,
            text="🔁 Loop Mix",
            font=("Segoe UI", 9, "bold"),
            fg="#A0A5C0",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=lambda: self.toggle_acid_loop_for_mode("full"),
        )
        self.btn_loop_mix.pack(side=tk.LEFT, ipadx=10, ipady=4, padx=(0, 8))
        mute_row = tk.Frame(acid_bottom_bar, bg="#1A1C27")
        mute_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(mute_row, text="Mix mute:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.LEFT, padx=(0, 6))
        self.var_mute_303_1 = tk.BooleanVar(value=False)
        self.var_mute_303_2 = tk.BooleanVar(value=False)
        self.var_mute_808 = tk.BooleanVar(value=False)
        self.var_mute_909 = tk.BooleanVar(value=False)
        for label, var, color in (
            ("303 #1", self.var_mute_303_1, "#00FF66"),
            ("303 #2", self.var_mute_303_2, "#00E5FF"),
            ("808", self.var_mute_808, "#FF9500"),
            ("909", self.var_mute_909, "#FF9500"),
        ):
            tk.Checkbutton(
                mute_row,
                text=label,
                variable=var,
                font=("Segoe UI", 8),
                fg=color,
                bg="#1A1C27",
                selectcolor="#1F2230",
                command=self.on_acid_mute_changed,
            ).pack(side=tk.LEFT, padx=(0, 8))
        mixer_row = tk.Frame(acid_bottom_bar, bg="#1A1C27")
        mixer_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(mixer_row, text="Mini mixer:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.LEFT, padx=(0, 8))
        mix_levels = self.config.get("acid_mix_levels") or {}
        self.scale_mix_303_1 = tk.Scale(
            mixer_row, from_=0, to=100, orient=tk.HORIZONTAL, length=120,
            label="303 #1", bg="#1A1C27", fg="#00FF66", highlightthickness=0,
            command=self.on_acid_mixer_changed,
        )
        self.scale_mix_303_1.set(int(mix_levels.get("303_1", 85)))
        self.scale_mix_303_1.pack(side=tk.LEFT, padx=(0, 10))
        self.scale_mix_303_2 = tk.Scale(
            mixer_row, from_=0, to=100, orient=tk.HORIZONTAL, length=120,
            label="303 #2", bg="#1A1C27", fg="#00E5FF", highlightthickness=0,
            command=self.on_acid_mixer_changed,
        )
        self.scale_mix_303_2.set(int(mix_levels.get("303_2", 85)))
        self.scale_mix_303_2.pack(side=tk.LEFT, padx=(0, 10))
        self.scale_mix_drums = tk.Scale(
            mixer_row, from_=0, to=100, orient=tk.HORIZONTAL, length=120,
            label="Drums", bg="#1A1C27", fg="#FF9500", highlightthickness=0,
            command=self.on_acid_mixer_changed,
        )
        self.scale_mix_drums.set(int(mix_levels.get("drums", 90)))
        self.scale_mix_drums.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(
            mixer_row,
            text="Reset mix",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.reset_acid_mixer_levels,
        ).pack(side=tk.RIGHT, ipadx=8, ipady=2)
        tk.Label(mute_row, text="Bank:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.RIGHT, padx=(8, 4))
        self.combo_pattern_banks = ttk.Combobox(mute_row, width=24, state="readonly", font=("Segoe UI", 8))
        self.combo_pattern_banks.pack(side=tk.RIGHT, padx=(0, 4))
        self.combo_pattern_banks.bind("<<ComboboxSelected>>", self.on_pattern_bank_selected)
        tk.Button(
            mute_row,
            text="↻",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.refresh_pattern_bank_combo,
        ).pack(side=tk.RIGHT, padx=(0, 4))
        acid_action_row = tk.Frame(acid_bottom_bar, bg="#1A1C27")
        acid_action_row.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Button(acid_action_row, text="📂 Load Song", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#3A3D52", bd=0, cursor="hand2", command=self.load_acid_from_rbs).pack(side=tk.LEFT, ipadx=10, ipady=4)
        tk.Button(acid_action_row, text="💾 Save Song", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#00A86B", bd=0, cursor="hand2", command=self.save_acid_to_rbs).pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        tk.Button(acid_action_row, text="📦 Load Bank", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#3A3D52", bd=0, cursor="hand2", command=self.load_pattern_bank_json).pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        tk.Button(acid_action_row, text="📤 Export Bank", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#242736", bd=0, cursor="hand2", command=self.export_pattern_bank_json).pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        tk.Button(acid_action_row, text="📁 Banks", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#242736", bd=0, cursor="hand2", command=self.open_pattern_banks_folder).pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        self.btn_launch_acid = tk.Button(acid_action_row, text="🚀 Launch in ReBirth", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#8A2BE2", bd=0, cursor="hand2", command=self.launch_generated_acid_in_rebirth)
        self.btn_launch_acid.pack(side=tk.LEFT, padx=8, ipady=4)
        self.lbl_acid_launch_blocked = tk.Label(
            acid_action_row,
            text="✖ Rebirth.exe missing",
            font=("Segoe UI", 8, "bold"),
            fg="#FF9500",
            bg="#1A1C27",
        )
        tk.Button(acid_action_row, text="🎼 Export .MID", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#242736", bd=0, cursor="hand2", command=self.export_generated_to_midi).pack(side=tk.LEFT, ipadx=8, ipady=4)

        acid_main = tk.Frame(tab_acid, bg="#1A1C27")
        acid_main.pack(fill=tk.BOTH, expand=True)

        acid_ctrl = tk.Frame(acid_main, bg="#1A1C27")
        acid_ctrl.pack(fill=tk.X, padx=12, pady=(6, 4))

        tk.Label(acid_ctrl, text="Musical Scale:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.combo_scale = ttk.Combobox(acid_ctrl, values=list(SCALES.keys()), state="readonly", font=("Segoe UI", 9), style="Dark.TCombobox")
        self.combo_scale.current(0)
        self.combo_scale.grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        tk.Label(acid_ctrl, text="Generation Scope:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.combo_gen_scope = ttk.Combobox(acid_ctrl, values=["Single Pattern (Current)", "Full Bank A (A1-A8)", "Full Bank B (B1-B8)", "Full Bank C (C1-C8)", "Full Bank D (D1-D8)", "ALL 32 PATTERNS (A1 to D8)"], state="readonly", font=("Segoe UI", 9), style="Dark.TCombobox")
        self.combo_gen_scope.current(1)
        self.combo_gen_scope.grid(row=0, column=3, sticky="ew", padx=4, pady=4)

        tk.Label(acid_ctrl, text="Note Density (%):", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.scale_density = tk.Scale(acid_ctrl, from_=20, to=100, orient=tk.HORIZONTAL, bg="#1A1C27", fg="#00FF66", highlightthickness=0)
        self.scale_density.set(75)
        self.scale_density.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        tk.Label(acid_ctrl, text="Accent Chance (%):", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.scale_accent = tk.Scale(acid_ctrl, from_=0, to=100, orient=tk.HORIZONTAL, bg="#1A1C27", fg="#FF9500", highlightthickness=0)
        self.scale_accent.set(35)
        self.scale_accent.grid(row=1, column=3, sticky="ew", padx=4, pady=4)

        tk.Label(acid_ctrl, text="Slide Chance (%):", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.scale_slide = tk.Scale(acid_ctrl, from_=0, to=100, orient=tk.HORIZONTAL, bg="#1A1C27", fg="#00E5FF", highlightthickness=0)
        self.scale_slide.set(40)
        self.scale_slide.grid(row=2, column=1, sticky="ew", padx=4, pady=4)

        tk.Label(acid_ctrl, text="Octave Spread:", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.scale_octave = tk.Scale(acid_ctrl, from_=0, to=100, orient=tk.HORIZONTAL, bg="#1A1C27", fg="#FF66CC", highlightthickness=0)
        self.scale_octave.set(60)
        self.scale_octave.grid(row=2, column=3, sticky="ew", padx=4, pady=4)
        acid_ctrl.columnconfigure(1, weight=1)
        acid_ctrl.columnconfigure(3, weight=1)

        gen_btn_frame = tk.Frame(acid_main, bg="#1A1C27")
        gen_btn_frame.pack(fill=tk.X, padx=12, pady=(2, 2))
        tk.Button(gen_btn_frame, text="🎲 Randomize Bank (303 #1 + #2 + TR-808 + TR-909)", font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg="#8A2BE2", activebackground="#9A3EF2", bd=0, cursor="hand2", command=self.generate_acid_pattern).pack(fill=tk.X, ipady=3)

        roll_wrap = tk.Frame(acid_main, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        roll_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))

        self.acid_editor_notebook = ttk.Notebook(roll_wrap)
        self.acid_editor_notebook.pack(fill=tk.X, padx=4, pady=(4, 2))

        tab_303_1 = tk.Frame(self.acid_editor_notebook, bg="#12131A")
        tab_303_2 = tk.Frame(self.acid_editor_notebook, bg="#12131A")
        tab_808 = tk.Frame(self.acid_editor_notebook, bg="#12131A")
        tab_909 = tk.Frame(self.acid_editor_notebook, bg="#12131A")
        self._tab_303_1 = tab_303_1
        self._tab_303_2 = tab_303_2
        self._tab_808 = tab_808
        self._tab_909 = tab_909
        self.acid_editor_notebook.add(tab_303_1, text="TB-303 #1")
        self.acid_editor_notebook.add(tab_303_2, text="TB-303 #2")
        self.acid_editor_notebook.add(tab_808, text="TR-808")
        self.acid_editor_notebook.add(tab_909, text="TR-909")
        self.acid_editor_notebook.bind("<<NotebookTabChanged>>", self.on_acid_editor_tab_changed)

        def _build_303_tab(tab, title, unit_key, loop_attr):
            transport = tk.Frame(tab, bg="#1A1C27")
            transport.pack(fill=tk.X, padx=4, pady=(2, 2))
            tk.Label(transport, text=title, font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#1A1C27").pack(side=tk.LEFT)
            btn_loop = tk.Button(transport, text="🔁 Loop", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#242736", bd=0, cursor="hand2", command=lambda m=unit_key: self.toggle_acid_loop_for_mode(m))
            btn_loop.pack(side=tk.RIGHT, padx=2, ipadx=8, ipady=1)
            setattr(self, loop_attr, btn_loop)
            tk.Button(transport, text="▶ Play Once", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#00A86B", bd=0, cursor="hand2", command=lambda m=unit_key: self.play_acid_303_preview(m)).pack(side=tk.RIGHT, padx=2, ipadx=8, ipady=1)
            tk.Button(transport, text="🎲 Randomize", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#8A2BE2", bd=0, cursor="hand2", command=lambda u=unit_key: self.randomize_303_slot_for_unit(u)).pack(side=tk.RIGHT, padx=2, ipadx=8, ipady=1)
            tk.Button(transport, text="↩ Undo", font=("Segoe UI", 8), fg="#A0A5C0", bg="#242736", bd=0, cursor="hand2", command=self.undo_acid_303_editor).pack(side=tk.RIGHT, padx=2, ipadx=6, ipady=1)

        def _build_drum_tab(tab, title, machine, loop_attr):
            transport = tk.Frame(tab, bg="#1A1C27")
            transport.pack(fill=tk.X, padx=4, pady=(2, 2))
            tk.Label(transport, text=title, font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#1A1C27").pack(side=tk.LEFT)
            btn_loop = tk.Button(transport, text="🔁 Loop", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#242736", bd=0, cursor="hand2", command=lambda m=machine: self.toggle_acid_loop_for_mode(m))
            btn_loop.pack(side=tk.RIGHT, padx=2, ipadx=8, ipady=1)
            setattr(self, loop_attr, btn_loop)
            tk.Button(transport, text="▶ Play Once", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#00A86B", bd=0, cursor="hand2", command=lambda m=machine: self.play_acid_drums_preview(m)).pack(side=tk.RIGHT, padx=2, ipadx=8, ipady=1)
            tk.Button(transport, text="🎲 Randomize", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#8A2BE2", bd=0, cursor="hand2", command=lambda m=machine: self.randomize_drum_slot_for_machine(m)).pack(side=tk.RIGHT, padx=2, ipadx=8, ipady=1)
            tk.Button(transport, text="↩ Undo", font=("Segoe UI", 8), fg="#A0A5C0", bg="#242736", bd=0, cursor="hand2", command=self.undo_acid_drum_editor).pack(side=tk.RIGHT, padx=2, ipadx=6, ipady=1)

        _build_303_tab(tab_303_1, "TB-303 #1 module", "303_1", "btn_loop_303_1")
        _build_303_tab(tab_303_2, "TB-303 #2 module", "303_2", "btn_loop_303_2")
        _build_drum_tab(tab_808, "TR-808 module", "808", "btn_loop_808")
        _build_drum_tab(tab_909, "TR-909 module", "909", "btn_loop_909")

        self.acid_editor_body = tk.Frame(roll_wrap, bg="#12131A")
        self.acid_editor_body.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        tools_bar = tk.Frame(self.acid_editor_body, bg="#12131A")
        tools_bar.pack(fill=tk.X, pady=(0, 4))
        bpm_row = tk.Frame(tools_bar, bg="#12131A")
        bpm_row.pack(fill=tk.X)
        tk.Label(bpm_row, text="Preview BPM", font=("Segoe UI", 7, "bold"), fg="#A0A5C0", bg="#12131A").pack(side=tk.LEFT, padx=(0, 4))
        self.scale_acid_bpm = tk.Scale(bpm_row, from_=80, to=160, orient=tk.HORIZONTAL, length=160, bg="#12131A", fg="#00E5FF", highlightthickness=0, command=self.on_acid_bpm_changed)
        self.scale_acid_bpm.set(128)
        self.scale_acid_bpm.pack(side=tk.LEFT)

        clear_bar = tk.Frame(self.acid_editor_body, bg="#12131A")
        clear_bar.pack(fill=tk.X, pady=(0, 4))
        tk.Label(clear_bar, text="Clear:", font=("Segoe UI", 7, "bold"), fg="#A0A5C0", bg="#12131A").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            clear_bar,
            text="Bank (this instrument)",
            font=("Segoe UI", 7, "bold"),
            fg="#FFFFFF",
            bg="#3A3D52",
            bd=0,
            cursor="hand2",
            command=self.clear_acid_current_bank,
        ).pack(side=tk.LEFT, padx=(0, 4), ipadx=6, ipady=2)
        tk.Button(
            clear_bar,
            text="All patterns (this instrument)",
            font=("Segoe UI", 7, "bold"),
            fg="#FFFFFF",
            bg="#3A3D52",
            bd=0,
            cursor="hand2",
            command=self.clear_acid_all_patterns,
        ).pack(side=tk.LEFT, padx=(0, 4), ipadx=6, ipady=2)
        tk.Button(
            clear_bar,
            text="All banks · all instruments",
            font=("Segoe UI", 7, "bold"),
            fg="#FF9500",
            bg="#2A2030",
            bd=0,
            cursor="hand2",
            command=self.clear_acid_all_instruments,
        ).pack(side=tk.LEFT, ipadx=6, ipady=2)

        editor_row = tk.Frame(self.acid_editor_body, bg="#12131A")
        editor_row.pack(fill=tk.BOTH, expand=True)

        editor_left_panel = tk.Frame(editor_row, bg="#12131A")
        editor_left_panel.pack(side=tk.LEFT, padx=(0, 6))

        editor_center = tk.Frame(editor_row, bg="#12131A")
        editor_center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        editor_right_panel = tk.Frame(editor_row, bg="#12131A")
        editor_right_panel.pack(side=tk.RIGHT, padx=(6, 0))

        self.pattern_selector = ReBirthPatternSelector(editor_left_panel, compact=True, on_change=lambda _s: self.on_pat_slot_changed())
        self.lbl_pattern_selector_ctx = tk.Label(
            editor_left_panel,
            text="Active pattern for TB-303 #1",
            font=("Segoe UI", 7, "bold"),
            fg="#00FF66",
            bg="#12131A",
            wraplength=120,
            justify=tk.CENTER,
        )
        self.lbl_pattern_selector_ctx.pack(anchor="n", pady=(0, 2))
        self.pattern_selector.pack(anchor="n")
        self.pattern_slot_status = tk.Frame(editor_left_panel, bg="#12131A")
        self.pattern_slot_status.pack(anchor="n", pady=(4, 0))
        self._pat_slot_badges = {}
        for key, short, color in (
            ("303_1", "#1", "#00FF66"),
            ("303_2", "#2", "#00E5FF"),
            ("808", "808", "#FF9500"),
            ("909", "909", "#00E5FF"),
        ):
            badge = tk.Label(
                self.pattern_slot_status,
                text=f"{short}:A1",
                font=("Segoe UI", 6, "bold"),
                fg=color,
                bg="#242736",
                padx=3,
                pady=1,
            )
            badge.pack(side=tk.LEFT, padx=1)
            badge.bind("<Button-1>", lambda _e, k=key: self.switch_acid_instrument_tab(k))
            badge.config(cursor="hand2")
            self._pat_slot_badges[key] = badge
        tk.Label(
            editor_left_panel,
            text="click badge → switch module",
            font=("Segoe UI", 6, "italic"),
            fg="#6C7293",
            bg="#12131A",
        ).pack(anchor="n", pady=(2, 0))

        self.var_303_ghost = tk.BooleanVar(value=False)
        tk.Checkbutton(
            editor_left_panel,
            text="Ghost\nother 303",
            variable=self.var_303_ghost,
            font=("Segoe UI", 7, "bold"),
            fg="#FF66CC",
            bg="#12131A",
            selectcolor="#1F2230",
            justify=tk.CENTER,
            command=self.refresh_303_editor_view,
        ).pack(anchor="n", pady=(4, 0))

        tk.Label(editor_right_panel, text="Copy →", font=("Segoe UI", 7, "bold"), fg="#A0A5C0", bg="#12131A").pack(anchor="n")
        self.copy_from_selector = ReBirthPatternSelector(editor_right_panel, compact=True, on_change=None)
        self.copy_from_selector.set_slot("A2")
        self.copy_from_selector.pack(anchor="n", pady=(2, 2))
        self.var_copy_303_1 = tk.BooleanVar(value=True)
        self.var_copy_303_2 = tk.BooleanVar(value=False)
        self.var_copy_drums = tk.BooleanVar(value=True)
        copy_opts = tk.Frame(editor_right_panel, bg="#12131A")
        copy_opts.pack(anchor="n")
        tk.Checkbutton(copy_opts, text="#1", variable=self.var_copy_303_1, font=("Segoe UI", 7), fg="#00FF66", bg="#12131A", selectcolor="#1F2230").pack(side=tk.LEFT)
        tk.Checkbutton(copy_opts, text="#2", variable=self.var_copy_303_2, font=("Segoe UI", 7), fg="#00E5FF", bg="#12131A", selectcolor="#1F2230").pack(side=tk.LEFT)
        tk.Checkbutton(copy_opts, text="Dr", variable=self.var_copy_drums, font=("Segoe UI", 7), fg="#FF9500", bg="#12131A", selectcolor="#1F2230").pack(side=tk.LEFT)
        tk.Button(editor_right_panel, text="Copy", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#242736", bd=0, cursor="hand2", command=self.copy_acid_pattern).pack(fill=tk.X, pady=(4, 0), ipady=1)
        tk.Label(editor_right_panel, text="Ctrl+C/V", font=("Segoe UI", 6, "italic"), fg="#6C7293", bg="#12131A").pack(anchor="n", pady=(4, 0))

        self.acid_piano_roll = Acid303PianoRoll(
            editor_center,
            on_change=self.on_acid_piano_roll_changed,
            on_randomize=self.randomize_current_303_slot,
            on_step_audition=self.audition_303_step,
        )
        self.acid_piano_roll.pack(fill=tk.BOTH, expand=True)
        self.acid_drum_grid = AcidDrumStepGrid(
            editor_center,
            get_is_909=lambda: self.get_acid_editor_context() == "909",
            on_change=self.on_acid_drum_grid_changed,
            on_randomize=self.randomize_current_drum_slot,
            on_hit_audition=self.audition_drum_hit,
        )
        self.acid_drum_grid.pack(fill=tk.BOTH, expand=True)
        self.acid_303_diff = Acid303DiffStrip(editor_center)

        self.bind_acid_shortcuts(tab_acid)
        self.bind_acid_shortcuts(self.acid_piano_roll)
        self.bind_acid_shortcuts(self.acid_drum_grid)
        self.bind_acid_shortcuts(self.acid_piano_roll.canvas)
        self.bind_acid_shortcuts(self.acid_drum_grid.canvas)
        self.on_acid_editor_tab_changed()

        # ==================== TAB 4: Song Library Manager ====================
        tab_library = tk.Frame(self.notebook, bg="#1A1C27")
        self.notebook.add(tab_library, text="📚 Song Library Manager")

        search_bar_frame = tk.Frame(tab_library, bg="#1A1C27")
        search_bar_frame.pack(fill=tk.X, padx=12, pady=(10, 4))

        tk.Label(search_bar_frame, text="🔍 Search:", font=("Segoe UI", 9, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_search = tk.Entry(search_bar_frame, font=("Segoe UI", 9), bg="#12131A", fg="#FFFFFF", insertbackground="#00E5FF", bd=1)
        self.entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry_search.bind("<KeyRelease>", self.filter_library_songs)

        self.btn_fav_filter = tk.Button(search_bar_frame, text="⭐ Favorites Only", font=("Segoe UI", 8, "bold"), fg="#FFD700", bg="#242736", bd=0, cursor="hand2", command=self.toggle_fav_filter)
        self.btn_fav_filter.pack(side=tk.RIGHT)
        self.fav_only_mode = False

        self.status_bar_frame = tk.Frame(tab_library, bg="#1A1C27")
        self.status_bar_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        self.lbl_scan_status = tk.Label(self.status_bar_frame, text="Initializing library scanner...", font=("Segoe UI", 8), fg="#00E5FF", bg="#1A1C27")
        self.lbl_scan_status.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(self.status_bar_frame, style="Horizontal.TProgressbar", mode="indeterminate", length=160)
        self.progress_bar.pack(side=tk.RIGHT)
        self.progress_bar.start(10)

        tree_wrap = tk.Frame(tab_library, bg="#1A1C27")
        tree_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)

        tree_scroll_y = ttk.Scrollbar(tree_wrap, orient="vertical", style="Dark.Vertical.TScrollbar")
        tree_scroll_x = ttk.Scrollbar(tree_wrap, orient="horizontal", style="Dark.Horizontal.TScrollbar")

        self.tree_songs = ttk.Treeview(
            tree_wrap,
            columns=("fav", "title", "bpm", "mode", "dur", "mod_name", "description", "breakdown"),
            show="headings",
            height=18,
            style="Dark.Treeview",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
        )
        tree_scroll_y.config(command=self.tree_songs.yview)
        tree_scroll_x.config(command=self.tree_songs.xview)
        self.tree_songs.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        for col_id, col_width, anchor in [
            ("fav", 35, "center"),
            ("title", 170, "w"),
            ("bpm", 55, "center"),
            ("mode", 90, "center"),
            ("dur", 95, "center"),
            ("mod_name", 130, "w"),
            ("description", 180, "w"),
            ("breakdown", 320, "w"),
        ]:
            stretch_cols = ("title", "mod_name", "description")
            self.tree_songs.column(col_id, width=col_width, anchor=anchor, stretch=(col_id in stretch_cols), minwidth=col_width)
            self.tree_songs.heading(col_id, text=self.library_heading_labels[col_id], command=lambda c=col_id: self.sort_library_by(c))

        self.tree_songs.bind("<Button-3>", self.show_library_context_menu)
        self.tree_songs.bind("<Double-1>", self.on_library_song_double_click)

        lib_btn_bar = tk.Frame(tab_library, bg="#1A1C27")
        lib_btn_bar.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.btn_launch_library = tk.Button(lib_btn_bar, text="🚀 Launch Selected", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#00A86B", bd=0, cursor="hand2", command=self.launch_rebirth_from_library)
        self.btn_launch_library.pack(side=tk.LEFT, ipadx=10, ipady=4)
        self.lbl_library_launch_blocked = tk.Label(
            lib_btn_bar,
            text="✖ Rebirth.exe missing — use Get ReBirth tab to install",
            font=("Segoe UI", 8, "bold"),
            fg="#FF9500",
            bg="#1A1C27",
        )
        self.lbl_library_launch_hint = tk.Label(lib_btn_bar, text="Double-click song = launch", font=("Segoe UI", 8, "italic"), fg="#6C7293", bg="#1A1C27")
        self.lbl_library_launch_hint.pack(side=tk.LEFT, padx=8)
        tk.Button(lib_btn_bar, text="🎲 Random Song", font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#8A2BE2", bd=0, cursor="hand2", command=self.pick_random_library_song).pack(side=tk.LEFT, padx=6, ipadx=10, ipady=4)
        tk.Button(lib_btn_bar, text="⭐ Toggle Favorite", font=("Segoe UI", 8, "bold"), fg="#FFD700", bg="#242736", bd=0, cursor="hand2", command=self.toggle_favorite_selected).pack(side=tk.LEFT, padx=6, ipadx=8, ipady=4)
        tk.Button(lib_btn_bar, text="🎼 Export to .MID", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#242736", bd=0, cursor="hand2", command=self.export_selected_to_midi).pack(side=tk.LEFT, padx=4, ipadx=8, ipady=4)
        tk.Button(lib_btn_bar, text="🖨️ Printable HTML", font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#242736", bd=0, cursor="hand2", command=self.export_selected_to_html).pack(side=tk.LEFT, padx=4, ipadx=8, ipady=4)
        tk.Button(lib_btn_bar, text="🔬 Deconstruct", font=("Segoe UI", 8, "bold"), fg="#00FF66", bg="#242736", bd=0, cursor="hand2", command=self.open_deconstruction_window).pack(side=tk.RIGHT, ipadx=8, ipady=4)

        # ==================== TAB 5: Documents ====================
        tab_documents = tk.Frame(self.notebook, bg="#1A1C27")
        self.tab_documents = tab_documents
        self.notebook.add(tab_documents, text="📄 Documents")

        doc_header = tk.Frame(tab_documents, bg="#1A1C27")
        doc_header.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(doc_header, text="TOOLBOX DOCUMENTS", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27").pack(side=tk.LEFT)
        tk.Button(
            doc_header,
            text="↻ Refresh",
            font=("Segoe UI", 8, "bold"),
            fg="#00E5FF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.refresh_documents_gallery,
        ).pack(side=tk.RIGHT, ipadx=8, ipady=2)

        self.lbl_documents_path = tk.Label(
            tab_documents,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#6C7293",
            bg="#1A1C27",
            anchor="w",
        )
        self.lbl_documents_path.pack(fill=tk.X, padx=12, pady=(0, 4))

        doc_gallery_wrap = tk.Frame(tab_documents, bg="#1A1C27")
        doc_gallery_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
        self.doc_scroll_wrap = doc_gallery_wrap
        self.doc_list_canvas = tk.Canvas(doc_gallery_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        doc_vscroll = ttk.Scrollbar(doc_gallery_wrap, orient="vertical", style="Dark.Vertical.TScrollbar", command=self.doc_list_canvas.yview)
        self.doc_list_canvas.configure(yscrollcommand=doc_vscroll.set)
        self.doc_list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        doc_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.doc_tiles_frame = tk.Frame(self.doc_list_canvas, bg="#12131A")
        self.doc_tiles_window = self.doc_list_canvas.create_window((0, 0), window=self.doc_tiles_frame, anchor="nw")
        self.doc_tiles_frame.bind(
            "<Configure>",
            lambda _e: self.doc_list_canvas.configure(scrollregion=self.doc_list_canvas.bbox("all")),
        )
        self.doc_list_canvas.bind(
            "<Configure>",
            lambda e: self.doc_list_canvas.itemconfig(self.doc_tiles_window, width=e.width),
        )

        def _documents_wheel(event):
            self.doc_list_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.doc_scroll_wrap.bind("<Enter>", lambda _e: self.doc_scroll_wrap.bind_all("<MouseWheel>", _documents_wheel))
        self.doc_scroll_wrap.bind("<Leave>", lambda _e: self.doc_scroll_wrap.unbind_all("<MouseWheel>"))
        self.doc_list_canvas.bind("<Enter>", lambda _e: self.doc_scroll_wrap.bind_all("<MouseWheel>", _documents_wheel))
        self.doc_list_canvas.bind("<Leave>", lambda _e: self.doc_scroll_wrap.unbind_all("<MouseWheel>"))

        self.lbl_documents_detail = tk.Label(
            tab_documents,
            text="Double-click a document to open it with the default Windows app.",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=860,
            highlightbackground="#282B3C",
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        self.lbl_documents_detail.pack(fill=tk.X, padx=12, pady=(0, 10))

        # ==================== TAB: Tips And Tricks ====================
        tab_tutorial = tk.Frame(self.notebook, bg="#1A1C27")
        self.tab_tutorial = tab_tutorial
        self.notebook.add(tab_tutorial, text=TUTORIAL_TAB_LABEL)

        tut_header = tk.Frame(tab_tutorial, bg="#1A1C27")
        tut_header.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(
            tut_header,
            text="TIPS AND TRICKS",
            font=("Segoe UI", 8, "bold"),
            fg="#A0A5C0",
            bg="#1A1C27",
        ).pack(side=tk.LEFT)
        self.lbl_tutorial_progress = tk.Label(
            tut_header,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg="#00E5FF",
            bg="#1A1C27",
        )
        self.lbl_tutorial_progress.pack(side=tk.RIGHT)

        tut_body = tk.Frame(tab_tutorial, bg="#1A1C27")
        tut_body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        tut_body.grid_columnconfigure(1, weight=1)
        tut_body.grid_rowconfigure(0, weight=1)

        tut_list_wrap = tk.Frame(tut_body, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        tut_list_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.tutorial_listbox = tk.Listbox(
            tut_list_wrap,
            bg="#12131A",
            fg="#FFFFFF",
            selectbackground="#242736",
            selectforeground="#00E5FF",
            activestyle="none",
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0,
            exportselection=False,
        )
        tut_list_scroll = ttk.Scrollbar(tut_list_wrap, orient="vertical", command=self.tutorial_listbox.yview)
        self.tutorial_listbox.configure(yscrollcommand=tut_list_scroll.set)
        self.tutorial_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tut_list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tutorial_listbox.bind("<<ListboxSelect>>", self.on_tutorial_step_selected)

        tut_content = tk.Frame(tut_body, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        tut_content.grid(row=0, column=1, sticky="nsew")
        tut_content.grid_rowconfigure(2, weight=1)
        tut_content.grid_columnconfigure(0, weight=1)

        self.lbl_tutorial_title = tk.Label(
            tut_content,
            text="",
            font=("Segoe UI", 12, "bold"),
            fg="#00E5FF",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=620,
        )
        self.lbl_tutorial_title.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))

        self.lbl_tutorial_summary = tk.Label(
            tut_content,
            text="",
            font=("Segoe UI", 9, "italic"),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=620,
        )
        self.lbl_tutorial_summary.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.txt_tutorial_body = tk.Text(
            tut_content,
            bg="#12131A",
            fg="#FFFFFF",
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0,
            padx=12,
            pady=8,
            cursor="arrow",
        )
        self.txt_tutorial_body.grid(row=2, column=0, sticky="nsew")
        self.txt_tutorial_body.configure(state=tk.DISABLED)

        tut_btn_row = tk.Frame(tut_content, bg="#12131A")
        tut_btn_row.grid(row=3, column=0, sticky="ew", padx=12, pady=12)
        self.btn_tutorial_prev = tk.Button(
            tut_btn_row,
            text="◀ Previous",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.tutorial_prev_step,
        )
        self.btn_tutorial_prev.pack(side=tk.LEFT, ipadx=10, ipady=4)
        self.btn_tutorial_done = tk.Button(
            tut_btn_row,
            text="✔ Mark Done",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#3A3D52",
            bd=0,
            cursor="hand2",
            command=self.tutorial_mark_done,
        )
        self.btn_tutorial_done.pack(side=tk.LEFT, padx=(8, 0), ipadx=10, ipady=4)
        self.btn_tutorial_action = tk.Button(
            tut_btn_row,
            text="Try in ToolBox",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=self.tutorial_run_action,
        )
        self.btn_tutorial_action.pack(side=tk.LEFT, padx=(8, 0), ipadx=10, ipady=4)
        self.btn_tutorial_next = tk.Button(
            tut_btn_row,
            text="Next ▶",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=self.tutorial_next_step,
        )
        self.btn_tutorial_next.pack(side=tk.RIGHT, ipadx=10, ipady=4)

        self.tutorial_step_index = 0
        self.populate_tutorial_list()

        # ==================== TAB 6: Settings ====================
        tab_settings = tk.Frame(self.notebook, bg="#1A1C27")
        self.notebook.add(tab_settings, text="Settings")

        self.settings_btn_bar = tk.Frame(tab_settings, bg="#1A1C27", highlightbackground="#282B3C", highlightthickness=1)
        self.settings_btn_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8), ipadx=8, ipady=8)
        settings_btn_row = tk.Frame(self.settings_btn_bar, bg="#1A1C27")
        settings_btn_row.pack(fill=tk.X)
        self.btn_save_settings = tk.Button(
            settings_btn_row,
            text="💾 Save Settings",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=self.save_settings,
        )
        self.btn_save_settings.pack(side=tk.LEFT, ipadx=12, ipady=4)
        self.btn_verify_downloads = tk.Button(
            settings_btn_row,
            text="✔ Verify Downloads",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.verify_download_files,
        )
        self.btn_verify_downloads.pack(side=tk.LEFT, padx=8, ipadx=10, ipady=4)
        tk.Button(
            settings_btn_row,
            text="📦 Backup Collection (7z)...",
            font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.backup_collection_to_7z,
        ).pack(side=tk.LEFT, padx=(0, 8), ipadx=10, ipady=4)
        self.lbl_settings_status = tk.Label(
            self.settings_btn_bar,
            text="",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#1A1C27",
            anchor="w",
            justify=tk.LEFT,
            wraplength=860,
        )
        self.lbl_settings_status.pack(fill=tk.X, pady=(6, 0))

        settings_scroll_outer = tk.Frame(tab_settings, bg="#1A1C27")
        settings_scroll_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=(10, 4))
        self.settings_canvas = tk.Canvas(settings_scroll_outer, bg="#1A1C27", highlightthickness=0)
        settings_vscroll = ttk.Scrollbar(settings_scroll_outer, orient="vertical", style="Dark.Vertical.TScrollbar", command=self.settings_canvas.yview)
        self.settings_canvas.configure(yscrollcommand=settings_vscroll.set)
        settings_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        settings_wrap = tk.Frame(self.settings_canvas, bg="#1A1C27")
        self.settings_canvas_window = self.settings_canvas.create_window((0, 0), window=settings_wrap, anchor="nw")
        settings_wrap.bind("<Configure>", lambda _e: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all")))
        self.settings_canvas.bind(
            "<Configure>",
            lambda e: self.settings_canvas.itemconfig(self.settings_canvas_window, width=e.width),
        )

        def _settings_wheel(event):
            self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.settings_canvas.bind("<Enter>", lambda _e: self.settings_canvas.bind_all("<MouseWheel>", _settings_wheel))
        self.settings_canvas.bind("<Leave>", lambda _e: self.settings_canvas.unbind_all("<MouseWheel>"))

        tk.Label(
            settings_wrap,
            text="ToolBox paths and download sources (stored in ReBirthToolBox.json)",
            font=("Segoe UI", 8, "italic"),
            fg="#6C7293",
            bg="#1A1C27",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))

        launch_card = tk.Frame(settings_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        launch_card.pack(fill=tk.X, pady=(0, 8), ipadx=10, ipady=8)
        tk.Label(launch_card, text="APPEARANCE", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A").pack(anchor="w", padx=10, pady=(4, 6))
        tk.Label(launch_card, text="UI theme (editable in ReBirthToolBox.json → themes)", font=("Segoe UI", 8), fg="#6C7293", bg="#12131A").pack(anchor="w", padx=10)
        self._theme_ids, self._theme_labels = get_theme_choices(self.config)
        self.combo_theme_settings = ttk.Combobox(
            launch_card,
            values=self._theme_labels,
            state="readonly",
            font=("Segoe UI", 9),
            style="Dark.TCombobox",
        )
        try:
            self.combo_theme_settings.current(self._theme_ids.index(self.config.get("theme", "midnight_studio")))
        except ValueError:
            self.combo_theme_settings.current(0)
        self.combo_theme_settings.pack(fill=tk.X, padx=10, pady=(2, 10))
        self.combo_theme_settings.bind("<<ComboboxSelected>>", self.on_theme_selected)
        tk.Label(launch_card, text="LAUNCH OPTIONS", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A").pack(anchor="w", padx=10, pady=(4, 6))
        tk.Label(launch_card, text="Launch screen resolution", font=("Segoe UI", 8), fg="#6C7293", bg="#12131A").pack(anchor="w", padx=10)
        self.combo_res_settings = ttk.Combobox(launch_card, values=res_names, state="readonly", font=("Segoe UI", 9), style="Dark.TCombobox")
        self.combo_res_settings.current(self.selected_res_index)
        self.combo_res_settings.pack(fill=tk.X, padx=10, pady=(2, 8))
        self.combo_res_settings.bind("<<ComboboxSelected>>", self.sync_resolution_from_settings)
        tk.Checkbutton(
            launch_card,
            text="Lock process to single CPU Core (Core 0) [Prevents audio glitches]",
            variable=self.var_cpu_affinity,
            font=("Segoe UI", 8, "bold"),
            fg="#FF9500",
            bg="#12131A",
            selectcolor="#1F2230",
            command=self.refresh_start_launch_info,
        ).pack(anchor="w", padx=10, pady=(0, 4))
        tk.Checkbutton(
            launch_card,
            text="Maximize ReBirth window on launch",
            variable=self.var_rebirth_maximized,
            font=("Segoe UI", 8, "bold"),
            fg="#00E5FF",
            bg="#12131A",
            selectcolor="#1F2230",
            command=self.on_display_mode_toggled,
        ).pack(anchor="w", padx=10, pady=(0, 4))
        tk.Checkbutton(
            launch_card,
            text=f"★ {SUPER_RACK_LABEL} — rack centered, menu kept, side bezel (≤{SUPER_RACK_WIDTH}×{SUPER_RACK_HEIGHT})",
            variable=self.var_rebirth_super_rack,
            font=("Segoe UI", 8, "bold"),
            fg="#FF9500",
            bg="#12131A",
            selectcolor="#1F2230",
            command=self.on_display_mode_toggled,
        ).pack(anchor="w", padx=10, pady=(0, 2))
        scale_row = tk.Frame(launch_card, bg="#12131A")
        scale_row.pack(anchor="w", fill=tk.X, padx=28, pady=(0, 2))
        tk.Label(
            scale_row,
            text="Super Rack screen:",
            font=("Segoe UI", 8, "bold"),
            fg="#A0A5C0",
            bg="#12131A",
        ).pack(side=tk.LEFT)
        self.combo_super_rack_scale = ttk.Combobox(
            scale_row,
            textvariable=self.var_super_rack_scale,
            values=SUPER_RACK_DISPLAY_LABELS,
            state="readonly",
            width=28,
            font=("Segoe UI", 8),
        )
        self.combo_super_rack_scale.pack(side=tk.LEFT, padx=(8, 0))
        self.combo_super_rack_scale.bind("<<ComboboxSelected>>", lambda _e: self.refresh_start_launch_info())
        tk.Label(
            launch_card,
            text=(
                "Minimizes other apps and hides the taskbar first, then launches ReBirth. "
                "“Fit height” switches to a sharp display mode so the rack fills top→bottom "
                "(± a few px) with wallpaper bezels on the left/right — no blurry magnifier. "
                "ToolBox auto-minimizes; taskbar returns when you close ReBirth."
            ),
            font=("Segoe UI", 7, "italic"),
            fg="#6C7293",
            bg="#12131A",
            wraplength=820,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=10, pady=(0, 6))

        iso_card = tk.Frame(settings_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        iso_card.pack(fill=tk.X, pady=(0, 8), ipadx=10, ipady=8)
        tk.Label(iso_card, text="CD-ROM / ISO IMAGE", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A").pack(anchor="w", padx=10, pady=(4, 6))
        iso_bar = tk.Frame(iso_card, bg="#12131A")
        iso_bar.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.lbl_iso_info = tk.Label(iso_bar, text="Searching for ISO file...", font=("Segoe UI", 8), fg="#FFFFFF", bg="#12131A", anchor="w")
        self.lbl_iso_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_zombie = tk.Button(iso_bar, text="⚡ Kill Zombie & Reset ISO", font=("Segoe UI", 8, "bold"), fg="#FF453A", bg="#2D1A21", bd=0, cursor="hand2", command=self.handle_zombie_cleanup)
        self.btn_zombie.pack(side=tk.RIGHT, padx=(4, 0), ipadx=8, ipady=2)
        tk.Button(iso_bar, text="Browse ISO...", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#242736", bd=0, cursor="hand2", command=self.browse_iso_manually).pack(side=tk.RIGHT, ipadx=8, ipady=2)

        dir_card = tk.Frame(settings_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        dir_card.pack(fill=tk.X, pady=(0, 8), ipadx=10, ipady=8)
        tk.Label(
            dir_card,
            text="TOOLBOX FOLDERS (relative paths inside ReBirth ToolBox)",
            font=("Segoe UI", 8, "bold"),
            fg="#A0A5C0",
            bg="#12131A",
        ).pack(anchor="w", padx=10, pady=(4, 2))
        tk.Label(
            dir_card,
            text="These folders are created automatically when possible. Edit the path only if you know what you are doing.",
            font=("Segoe UI", 7, "italic"),
            fg="#6C7293",
            bg="#12131A",
            wraplength=820,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=10, pady=(0, 6))
        self.settings_dir_entries = {}
        self.settings_dir_status = {}
        for dir_key, label_text in (
            ("songs", "Directory for songs"),
            ("documents", "Directory for documents"),
            ("default_songs", "Directory for Default Songs"),
            ("mods", "Directory for Mods"),
            ("downloads", "Downloads folder"),
        ):
            row = tk.Frame(dir_card, bg="#12131A")
            row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=label_text, font=("Segoe UI", 8), fg="#A0A5C0", bg="#12131A", width=24, anchor="w").pack(side=tk.LEFT)
            entry = tk.Entry(row, font=("Segoe UI", 8), bg="#1A1C27", fg="#FFFFFF", insertbackground="#00E5FF", bd=0)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
            entry.bind("<KeyRelease>", lambda _e: self.refresh_settings_directory_status())
            self.settings_dir_entries[dir_key] = entry
            status_lbl = tk.Label(row, text="", font=("Segoe UI", 7), fg="#6C7293", bg="#12131A", anchor="e", width=28)
            status_lbl.pack(side=tk.RIGHT, padx=(8, 0))
            self.settings_dir_status[dir_key] = status_lbl

        self.populate_settings_form()

        # ==================== TAB: Get ReBirth ====================
        tab_downloads = tk.Frame(self.notebook, bg="#1A1C27")
        self.tab_downloads = tab_downloads
        self.notebook.add(tab_downloads, text="Get ReBirth")

        wizard_wrap = tk.Frame(tab_downloads, bg="#1A1C27")
        wizard_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.lbl_wizard_only_notice = tk.Label(
            wizard_wrap,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg="#FF9500",
            bg="#1A1C27",
            anchor="w",
            justify=tk.LEFT,
            wraplength=860,
        )

        url_card = tk.Frame(wizard_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        url_card.pack(fill=tk.X, pady=(0, 10), ipadx=10, ipady=8)
        tk.Label(url_card, text="DOWNLOAD SOURCES (https://)", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A").pack(anchor="w", padx=10, pady=(4, 6))
        tk.Label(
            url_card,
            text="URLs are loaded from ReBirthToolBox.json only — paste your own https links or leave empty and copy files manually into Downloads.",
            font=("Segoe UI", 7, "italic"),
            fg="#6C7293",
            bg="#12131A",
            wraplength=820,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=10, pady=(0, 6))

        def _add_download_url_row(parent, label_text, url_attr, file_attr):
            row = tk.Frame(parent, bg="#12131A")
            row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=label_text, font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#12131A", width=16, anchor="w").pack(side=tk.LEFT)
            entry = tk.Entry(row, font=("Segoe UI", 8), bg="#1A1C27", fg="#FFFFFF", insertbackground="#00E5FF", bd=0)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
            setattr(self, url_attr, entry)
            file_row = tk.Frame(parent, bg="#12131A")
            file_row.pack(fill=tk.X, padx=10, pady=(0, 4))
            tk.Label(file_row, text="Filename", font=("Segoe UI", 7), fg="#6C7293", bg="#12131A", width=16, anchor="w").pack(side=tk.LEFT)
            file_entry = tk.Entry(file_row, font=("Segoe UI", 8), bg="#1A1C27", fg="#FFFFFF", insertbackground="#00E5FF", bd=0)
            file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
            setattr(self, file_attr, file_entry)

        _add_download_url_row(url_card, "ReBirth ISO", "entry_download_iso_url", "entry_download_iso_file")
        _add_download_url_row(url_card, "RB-338 2.0.1 Installer", "entry_download_installer_url", "entry_download_installer_file")
        url_btn_row = tk.Frame(url_card, bg="#12131A")
        url_btn_row.pack(fill=tk.X, padx=10, pady=(4, 2))
        tk.Button(
            url_btn_row,
            text="💾 Save Download Sources",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=self.save_download_sources,
        ).pack(side=tk.LEFT, ipadx=10, ipady=3)
        tk.Button(
            url_btn_row,
            text="🌐 Archive.org search",
            font=("Segoe UI", 8, "bold"),
            fg="#00E5FF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=lambda: webbrowser.open(REBIRTH_DOWNLOAD_PAGE),
        ).pack(side=tk.LEFT, padx=(8, 0), ipadx=8, ipady=3)

        wizard_header = tk.Frame(wizard_wrap, bg="#12131A", highlightbackground="#282B3C", highlightthickness=1)
        wizard_header.pack(fill=tk.X, pady=(0, 10), ipadx=14, ipady=12)
        tk.Label(
            wizard_header,
            text="ReBirth RB-338 Setup Wizard",
            font=("Segoe UI", 12, "bold"),
            fg="#00E5FF",
            bg="#12131A",
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            wizard_header,
            text="Download → install into this ToolBox folder → restart when Rebirth.exe appears.",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=860,
        ).pack(fill=tk.X, pady=(4, 10))

        progress_row = tk.Frame(wizard_header, bg="#12131A")
        progress_row.pack(fill=tk.X)
        self.wizard_step_widgets = []
        self.wizard_step_lines = []
        wizard_steps = [
            ("1", "Download", "#00FF66"),
            ("2", "Extract", "#FF9500"),
            ("3", "Restart", "#00E5FF"),
        ]
        for index, (num, title, accent) in enumerate(wizard_steps):
            step_col = tk.Frame(progress_row, bg="#12131A")
            step_col.pack(side=tk.LEFT, expand=True)
            dot = tk.Label(step_col, text="○", font=("Segoe UI", 18, "bold"), fg="#42475E", bg="#12131A")
            dot.pack()
            lbl = tk.Label(step_col, text=f"{num}. {title}", font=("Segoe UI", 8, "bold"), fg="#6C7293", bg="#12131A")
            lbl.pack(pady=(2, 0))
            self.wizard_step_widgets.append({"dot": dot, "label": lbl, "accent": accent})
            if index < len(wizard_steps) - 1:
                line = tk.Frame(progress_row, bg="#42475E", height=2, width=80)
                line.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=18, padx=8)
                self.wizard_step_lines.append(line)

        folder_row = tk.Frame(wizard_header, bg="#12131A")
        folder_row.pack(fill=tk.X, pady=(12, 0))
        tk.Label(folder_row, text="Install folder:", font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#12131A").pack(side=tk.LEFT)
        self.lbl_wizard_folder = tk.Label(
            folder_row,
            text=BASE_DIR,
            font=("Segoe UI", 8),
            fg="#FFFFFF",
            bg="#12131A",
            anchor="w",
            wraplength=620,
            justify=tk.LEFT,
        )
        self.lbl_wizard_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8))

        self.lbl_wizard_message = tk.Label(
            wizard_wrap,
            text="Ready.",
            font=("Segoe UI", 8),
            fg="#6C7293",
            bg="#1A1C27",
            anchor="w",
            wraplength=860,
            justify=tk.LEFT,
        )
        self.lbl_wizard_message.pack(fill=tk.X, pady=(0, 8))

        steps_grid = tk.Frame(wizard_wrap, bg="#1A1C27")
        steps_grid.pack(fill=tk.BOTH, expand=True)
        self.steps_grid = steps_grid

        self.lbl_rebirth_local_ok = tk.Label(
            wizard_wrap,
            text="",
            font=("Segoe UI", 9),
            fg="#00FF66",
            bg="#1A1C27",
            anchor="w",
            wraplength=860,
            justify=tk.LEFT,
        )

        self.step1_card = tk.Frame(steps_grid, bg="#12131A", highlightbackground="#242736", highlightthickness=1)
        self.step1_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.step2_card = tk.Frame(steps_grid, bg="#12131A", highlightbackground="#242736", highlightthickness=1)
        self.step2_card.grid(row=0, column=1, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.step3_card = tk.Frame(steps_grid, bg="#12131A", highlightbackground="#242736", highlightthickness=1)
        self.step3_card.grid(row=0, column=2, sticky="nsew", pady=(0, 6))
        steps_grid.columnconfigure(0, weight=1, uniform="wizard")
        steps_grid.columnconfigure(1, weight=1, uniform="wizard")
        steps_grid.columnconfigure(2, weight=1, uniform="wizard")
        steps_grid.rowconfigure(0, weight=1)

        tk.Label(self.step1_card, text="STEP 1", font=("Segoe UI", 8, "bold"), fg="#00FF66", bg="#12131A", anchor="w").pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Label(self.step1_card, text="Download files", font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg="#12131A", anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))

        self.lbl_step1_iso = tk.Label(self.step1_card, text="ISO: …", font=("Segoe UI", 8), fg="#A0A5C0", bg="#12131A", anchor="w")
        self.lbl_step1_iso.pack(fill=tk.X, padx=10, pady=1)
        self.lbl_step1_installer = tk.Label(self.step1_card, text="Installer: …", font=("Segoe UI", 8), fg="#A0A5C0", bg="#12131A", anchor="w")
        self.lbl_step1_installer.pack(fill=tk.X, padx=10, pady=(1, 8))

        self.step1_btn_frame = tk.Frame(self.step1_card, bg="#12131A")
        self.step1_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        self.btn_download_iso = tk.Button(
            self.step1_btn_frame,
            text="⬇ ISO",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=lambda: self.start_rebirth_download("iso"),
        )
        self.btn_download_installer = tk.Button(
            self.step1_btn_frame,
            text="⬇ Installer",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#8A2BE2",
            bd=0,
            cursor="hand2",
            command=lambda: self.start_rebirth_download("installer"),
        )
        tk.Button(
            self.step1_btn_frame,
            text="✔ Verify",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#242736",
            bd=0,
            cursor="hand2",
            command=self.verify_download_files,
        ).pack(side=tk.RIGHT, padx=(0, 4), ipadx=6, ipady=4)

        self.lbl_download_status = tk.Label(
            self.step1_card,
            text="Waiting…",
            font=("Segoe UI", 8),
            fg="#6C7293",
            bg="#12131A",
            anchor="w",
            wraplength=240,
            justify=tk.LEFT,
        )
        self.lbl_download_status.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.download_progress = ttk.Progressbar(self.step1_card, style="Horizontal.TProgressbar", mode="determinate")
        self.download_progress.pack(fill=tk.X, padx=10, pady=(0, 6))
        self.download_progress["value"] = 0
        tk.Button(
            self.step1_card,
            text="📂 Open Downloads",
            font=("Segoe UI", 7, "bold"),
            fg="#FF9500",
            bg="#12131A",
            bd=0,
            cursor="hand2",
            command=self.open_downloads_folder,
        ).pack(anchor="w", padx=10, pady=(0, 4))
        tk.Button(
            self.step1_card,
            text="🌐 Archive.org",
            font=("Segoe UI", 7, "bold"),
            fg="#00E5FF",
            bg="#12131A",
            bd=0,
            cursor="hand2",
            command=lambda: webbrowser.open(REBIRTH_DOWNLOAD_PAGE),
        ).pack(anchor="w", padx=10, pady=(0, 10))

        tk.Label(self.step2_card, text="STEP 2", font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#12131A", anchor="w").pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Label(self.step2_card, text="Extract ReBirth here", font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg="#12131A", anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))
        self.lbl_step2_status = tk.Label(
            self.step2_card,
            text=f"Unpacks the installer EXE with 7-Zip into:\n{BASE_DIR}\n(does not run the setup)",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=240,
        )
        self.lbl_step2_status.pack(fill=tk.X, padx=10, pady=(0, 10))

        step2_btn_frame = tk.Frame(self.step2_card, bg="#12131A")
        step2_btn_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.btn_run_installer = tk.Button(
            step2_btn_frame,
            text="📦 Extract ReBirth here",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=self.run_rebirth_installer,
        )
        self.btn_run_installer.pack(fill=tk.X, ipady=6)
        self.btn_extract_rebirth = None

        tk.Label(self.step3_card, text="STEP 3", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#12131A", anchor="w").pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Label(self.step3_card, text="Restart ToolBox", font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg="#12131A", anchor="w").pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(
            self.step3_card,
            text="After Rebirth.exe appears in this folder, restart ToolBox to unlock all tabs.",
            font=("Segoe UI", 8),
            fg="#6C7293",
            bg="#12131A",
            anchor="w",
            wraplength=240,
            justify=tk.LEFT,
        ).pack(fill=tk.X, padx=10, pady=(0, 8))
        self.lbl_step3_status = tk.Label(
            self.step3_card,
            text="Complete Step 2 first.",
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=240,
        )
        self.lbl_step3_status.pack(fill=tk.X, padx=10, pady=(0, 8))

        shortcut_frame = tk.Frame(self.step3_card, bg="#12131A")
        shortcut_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.var_shortcut_desktop = tk.BooleanVar(value=True)
        self.var_shortcut_start = tk.BooleanVar(value=True)
        tk.Checkbutton(
            shortcut_frame,
            text="Desktop shortcut",
            variable=self.var_shortcut_desktop,
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            activebackground="#12131A",
            activeforeground="#00E5FF",
            selectcolor="#242736",
            highlightthickness=0,
            bd=0,
        ).pack(anchor="w")
        tk.Checkbutton(
            shortcut_frame,
            text="Start menu shortcut",
            variable=self.var_shortcut_start,
            font=("Segoe UI", 8),
            fg="#A0A5C0",
            bg="#12131A",
            activebackground="#12131A",
            activeforeground="#00E5FF",
            selectcolor="#242736",
            highlightthickness=0,
            bd=0,
        ).pack(anchor="w", pady=(2, 0))

        self.btn_deploy_launcher = tk.Button(
            self.step3_card,
            text="↻ Restart ToolBox",
            font=("Segoe UI", 8, "bold"),
            fg="#FFFFFF",
            bg="#00A86B",
            bd=0,
            cursor="hand2",
            command=self.restart_application,
        )
        self.btn_deploy_launcher.pack(fill=tk.X, padx=10, ipady=6, pady=(0, 10))

        self.setup_wizard_only = is_setup_wizard_only(self.config)
        self.rebirth_exe_ready = is_rebirth_exe_ready()
        if self.setup_wizard_only:
            self.lbl_wizard_only_notice.config(
                text=(
                    "Setup mode: Rebirth.exe and CD-ROM ISO were not found. "
                    "Complete the steps below — ToolBox will offer a restart when ReBirth is installed."
                ),
            )
            self.lbl_wizard_only_notice.pack(fill=tk.X, pady=(0, 10))
        for tab_id in list(self.notebook.tabs()):
            tab_text = self.notebook.tab(tab_id, "text")
            if self.rebirth_exe_ready and tab_text == "Get ReBirth":
                self.notebook.forget(tab_id)
            elif self.setup_wizard_only and tab_text != "Get ReBirth":
                self.notebook.forget(tab_id)
        if self.setup_wizard_only and hasattr(self, "tab_downloads"):
            try:
                self.notebook.select(self.tab_downloads)
            except Exception:
                pass

        self.populate_download_sources_form()
        self.update_launch_availability()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_notebook_tab_changed)
        if hasattr(self, "tab_downloads") and str(self.tab_downloads) in self.notebook.tabs():
            self.refresh_get_rebirth_ui()

    def build_loading_overlay(self):
        self.loading_overlay = tk.Frame(self.root, bg="#12131A")
        panel = tk.Frame(self.loading_overlay, bg="#1A1C27", highlightbackground="#00E5FF", highlightthickness=2)
        panel.place(relx=0.5, rely=0.45, anchor="center", width=460, height=170)
        self.lbl_loading_title = tk.Label(
            panel,
            text="Please wait...",
            font=("Segoe UI", 14, "bold"),
            fg="#00E5FF",
            bg="#1A1C27",
        )
        self.lbl_loading_title.pack(pady=(18, 6))
        self.lbl_loading_detail = tk.Label(
            panel,
            text="Constructing song & mod database...",
            font=("Segoe UI", 9),
            fg="#A0A5C0",
            bg="#1A1C27",
            wraplength=420,
            justify=tk.CENTER,
        )
        self.lbl_loading_detail.pack(padx=16, pady=(0, 10))
        self.loading_overlay_progress = ttk.Progressbar(panel, style="Horizontal.TProgressbar", mode="indeterminate", length=360)
        self.loading_overlay_progress.pack(pady=(0, 16))
        self.loading_overlay.place_forget()

    def show_loading_overlay(self, title="Please wait...", detail="Constructing song & mod database..."):
        self.lbl_loading_title.config(text=title)
        self.lbl_loading_detail.config(text=detail)
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_overlay.lift()
        self.loading_overlay_progress.start(12)
        self.root.update_idletasks()
        self.root.update()

    def update_loading_overlay(self, detail=None, title=None):
        if title:
            self.lbl_loading_title.config(text=title)
        if detail:
            self.lbl_loading_detail.config(text=detail)
        self.root.update_idletasks()
        self.root.update()

    def hide_loading_overlay(self):
        self.loading_overlay_progress.stop()
        self.loading_overlay.place_forget()

    def show_launch_overlay(self, title="Starting ReBirth...", detail="Please wait..."):
        self.show_loading_overlay(title, detail)
        if hasattr(self, "lbl_scan_status"):
            self.lbl_scan_status.config(text=detail, fg="#FF9500")
        self.root.update_idletasks()

    def update_launch_overlay(self, title=None, detail=None):
        if title:
            self.lbl_loading_title.config(text=title)
        if detail:
            self.lbl_loading_detail.config(text=detail)
            if hasattr(self, "lbl_scan_status"):
                self.lbl_scan_status.config(text=detail, fg="#FF9500")
        self.root.update_idletasks()

    def get_rbs_metadata(self, rbs_path, include_patterns=False):
        if not rbs_path or not os.path.exists(rbs_path):
            return parse_rbs_metadata(rbs_path, include_patterns=include_patterns)
        key = os.path.normcase(os.path.abspath(rbs_path))
        try:
            st = os.stat(rbs_path)
            sig = (st.st_mtime, st.st_size)
        except OSError:
            return parse_rbs_metadata(rbs_path, include_patterns=include_patterns)

        cached = self._metadata_cache.get(key)
        if cached and cached.get("mtime") == sig[0] and cached.get("size") == sig[1]:
            meta = cached.get("meta")
            patterns_included = cached.get("patterns_included", False)
            if meta and (not include_patterns or patterns_included):
                return meta

        meta = parse_rbs_metadata(rbs_path, include_patterns=include_patterns)
        self._metadata_cache[key] = {
            "mtime": sig[0],
            "size": sig[1],
            "meta": meta,
            "patterns_included": include_patterns,
        }
        return meta

    def warm_rbs_metadata_cache(self, songs, include_patterns=False, progress_callback=None):
        total = len(songs)
        for idx, (_filename, path) in enumerate(songs, start=1):
            if not os.path.exists(path):
                continue
            self.get_rbs_metadata(path, include_patterns=include_patterns)
            if progress_callback and total and idx % 25 == 0:
                progress_callback(idx, total)

    def try_load_library_cache(self):
        cache = load_library_cache_from_disk()
        if not cache:
            return False

        songs = []
        for item in cache.get("songs", []):
            path = item.get("path")
            name = item.get("name") or (os.path.basename(path) if path else "")
            if path and os.path.isfile(path):
                songs.append((name, os.path.abspath(path)))

        mods = []
        for entry in cache.get("mods", []):
            if len(entry) >= 4:
                display, path, desc, rebirth_name = entry[0], entry[1], entry[2], entry[3]
            elif len(entry) >= 2:
                display, path = entry[0], entry[1]
                desc, rebirth_name = "", display
            else:
                continue
            if path and os.path.isfile(path):
                mods.append((display, os.path.abspath(path), desc, rebirth_name))

        if not songs and not mods:
            return False

        self._metadata_cache = cache.get("metadata") or {}
        self._mod_info_cache = cache.get("mod_info") or {}
        self.builtin_songs = discover_builtin_default_songs()
        self.rbs_songs = [(name, path) for name, path in songs if not is_under_default_songs(path)]
        self.installed_mods = mods
        self.refresh_startup_song_picker()
        self.populate_library_tree()
        self.mod_songs_index = self.build_mod_songs_index()
        self.mark_mod_gallery_dirty()
        self._library_cache_loaded = True
        return True

    def mark_mod_gallery_dirty(self):
        self._mod_gallery_dirty = True
        self._mod_gallery_built = False
        if getattr(self, "_mod_gallery_building", False):
            self._mod_gallery_reload_pending = True

    def set_mod_gallery_loading(self, active, detail=""):
        label = getattr(self, "lbl_mod_gallery_loading", None)
        overlay = getattr(self, "mod_loading_overlay", None)
        overlay_label = getattr(self, "lbl_mod_loading_overlay", None)
        text = detail or "Please wait — loading mod database..."
        if label and label.winfo_exists():
            label.config(text=text)
            if active:
                if not label.winfo_ismapped():
                    label.pack(side=tk.LEFT, padx=(12, 0))
            elif label.winfo_ismapped():
                label.pack_forget()
        if overlay_label and overlay_label.winfo_exists():
            overlay_label.config(text=text)
        if overlay and overlay.winfo_exists():
            if active:
                overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
                overlay.lift()
            else:
                overlay.place_forget()

    def ensure_mod_gallery(self):
        if getattr(self, "_mod_gallery_building", False):
            self._mod_gallery_reload_pending = True
            return
        catalog = getattr(self, "_mod_gallery_catalog", None) or []
        if self._mod_gallery_built and not self._mod_gallery_dirty:
            if catalog and not getattr(self, "_mod_canvas_rows", {}):
                self.sync_mod_list_canvas_now(reset_scroll=False)
                self._render_mod_gallery_viewport()
            return
        self.set_mod_gallery_loading(True)
        self.refresh_mod_gallery(self.selected_mod_name)

    def force_refresh_mod_gallery(self):
        """Re-scan Mods folder from disk, then rebuild the gallery."""
        self._mod_gallery_dirty = True
        self._mod_gallery_built = False
        self._mod_gallery_reload_pending = False
        try:
            # Drop name cache so renamed/fixed extract_rmb_mod_info results apply
            self._mod_info_cache = {}
            mods = scan_installed_mods(self._mod_info_cache)
            self.installed_mods = mods
            self.mod_songs_index = self.build_mod_songs_index()
            save_library_cache_to_disk(
                self.rbs_songs, self.installed_mods, self._metadata_cache, self._mod_info_cache
            )
        except Exception:
            pass
        self.ensure_mod_gallery()

    def _finish_mod_gallery_build(self, build_id):
        if build_id != getattr(self, "_mod_gallery_build_token", None):
            return
        self._mod_gallery_building = False
        self._mod_gallery_built = True
        self._mod_gallery_dirty = False
        self.set_mod_gallery_loading(False)
        if getattr(self, "_mod_gallery_reload_pending", False):
            self._mod_gallery_reload_pending = False
            self.root.after(50, self._soft_refresh_mod_gallery_catalog)

    def _soft_refresh_mod_gallery_catalog(self):
        if getattr(self, "_mod_gallery_building", False):
            self._mod_gallery_reload_pending = True
            return
        try:
            self._mod_gallery_catalog = self.get_mod_catalog()
        except Exception:
            return
        self._mod_gallery_dirty = False
        self._mod_gallery_built = True
        self.sync_mod_list_canvas_now(reset_scroll=False)
        self._render_mod_gallery_viewport()

    def _deferred_mod_gallery_reload(self):
        self._soft_refresh_mod_gallery_catalog()

    def _mod_gallery_total_height(self):
        catalog = self.get_mod_gallery_display_catalog()
        return len(catalog) * MOD_GALLERY_ROW_HEIGHT

    def _mod_gallery_viewport_height(self):
        canvas = getattr(self, "mod_list_canvas", None)
        if not canvas or not canvas.winfo_exists():
            return 1
        return max(1, canvas.winfo_height())

    def _mod_gallery_max_scroll_y(self):
        return max(0, self._mod_gallery_total_height() - self._mod_gallery_viewport_height())

    def _clamp_mod_gallery_top_y(self):
        max_scroll = self._mod_gallery_max_scroll_y()
        top_y = float(getattr(self, "_mod_gallery_top_y", 0) or 0)
        self._mod_gallery_top_y = max(0.0, min(top_y, float(max_scroll)))

    def _mod_gallery_yview(self, *args):
        if not args:
            return
        max_scroll = self._mod_gallery_max_scroll_y()
        top_y = float(getattr(self, "_mod_gallery_top_y", 0) or 0)
        if args[0] == "moveto":
            fraction = float(args[1])
            top_y = fraction * max_scroll if max_scroll else 0.0
        elif args[0] == "scroll":
            delta = int(args[1])
            unit = args[2] if len(args) > 2 else "units"
            if unit == "units":
                top_y += delta * MOD_GALLERY_ROW_HEIGHT
            elif unit == "pages":
                top_y += delta * self._mod_gallery_viewport_height()
        self._mod_gallery_top_y = max(0.0, min(top_y, float(max_scroll)))
        self._update_mod_gallery_scrollbar()
        self._schedule_mod_viewport_refresh()

    def _update_mod_gallery_scrollbar(self):
        scroll = getattr(self, "mod_vscroll", None)
        if not scroll:
            return
        total = self._mod_gallery_total_height()
        viewport = self._mod_gallery_viewport_height()
        if total <= 0:
            scroll.set(0.0, 1.0)
            return
        top_y = float(getattr(self, "_mod_gallery_top_y", 0) or 0)
        first = top_y / total
        last = min(1.0, (top_y + viewport) / total)
        scroll.set(first, last)

    def _clear_mod_canvas_rows(self):
        pending_build = getattr(self, "_mod_viewport_after_build", None)
        if pending_build:
            try:
                self.root.after_cancel(pending_build)
            except Exception:
                pass
        self._mod_viewport_after_build = None
        self._mod_viewport_build_queue = []
        self._mod_gallery_row_error = None
        host = getattr(self, "mod_rows_host", None)
        if host and host.winfo_exists():
            for child in host.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass
        canvas = getattr(self, "mod_list_canvas", None)
        fallback_id = getattr(self, "_mod_gallery_fallback_win", None)
        self._mod_gallery_fallback_win = None
        if canvas and canvas.winfo_exists():
            if fallback_id:
                try:
                    canvas.delete(fallback_id)
                except Exception:
                    pass
            for item_id in canvas.find_all():
                if item_id == getattr(self, "mod_rows_host_id", None):
                    continue
                try:
                    canvas.delete(item_id)
                except Exception:
                    pass
        self._mod_canvas_rows = {}
        self.mod_tiles.clear()
        self.mod_tile_photos.clear()
        self.mod_row_widgets.clear()

    def _schedule_mod_viewport_refresh(self):
        pending = getattr(self, "_mod_viewport_after", None)
        if pending:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
        self._mod_viewport_after = self.root.after(16, self._render_mod_gallery_viewport)

    def _render_mod_gallery_viewport(self):
        self._mod_viewport_after = None
        catalog = self.get_mod_gallery_display_catalog()
        canvas = getattr(self, "mod_list_canvas", None)
        if not canvas or not canvas.winfo_exists():
            return
        if not catalog:
            canvas.configure(scrollregion=(0, 0, 1, 1))
            filter_mode = getattr(self, "mod_filter_mode", "all")
            if filter_mode != "all":
                self._show_mod_gallery_fallback(
                    canvas,
                    max(canvas.winfo_width(), 320),
                    "No mods in this view. Try another filter or add favorites with ★ on a mod row.",
                )
            return
        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 400)
        viewport_h = max(self._mod_gallery_viewport_height(), 200)
        # Host must be sized explicitly — place() children do not expand the parent,
        # so an unsized host collapses to ~0px and "squashes" every row.
        host = getattr(self, "mod_rows_host", None)
        if host and host.winfo_exists():
            try:
                host.configure(width=width, height=viewport_h)
            except Exception:
                pass
        if hasattr(self, "mod_rows_host_id"):
            try:
                canvas.itemconfig(self.mod_rows_host_id, width=width, height=viewport_h)
                canvas.coords(self.mod_rows_host_id, 0, 0)
            except Exception:
                pass
        canvas.configure(scrollregion=(0, 0, width, viewport_h))
        self._clamp_mod_gallery_top_y()
        top_y = float(getattr(self, "_mod_gallery_top_y", 0) or 0)
        total = len(catalog)
        first_idx = max(0, int(top_y // MOD_GALLERY_ROW_HEIGHT) - MOD_GALLERY_VIEW_BUFFER)
        visible_rows = max(1, viewport_h // MOD_GALLERY_ROW_HEIGHT + 1)
        last_idx = min(total - 1, first_idx + visible_rows + MOD_GALLERY_VIEW_BUFFER * 2)
        keep = set(range(first_idx, last_idx + 1))
        for idx in list(self._mod_canvas_rows.keys()):
            if idx not in keep:
                try:
                    self._mod_canvas_rows[idx]["row"].destroy()
                except Exception:
                    pass
                del self._mod_canvas_rows[idx]
        for idx in sorted(keep):
            canvas_y = int(idx * MOD_GALLERY_ROW_HEIGHT - top_y)
            if idx in self._mod_canvas_rows:
                try:
                    self._mod_canvas_rows[idx]["row"].place(
                        x=0,
                        y=canvas_y,
                        width=width,
                        height=MOD_GALLERY_ROW_HEIGHT,
                    )
                except Exception:
                    pass
                continue
            try:
                row = self._build_mod_gallery_row(catalog[idx])
                if row is None:
                    raise RuntimeError("_build_mod_gallery_row returned None")
                row.place(x=0, y=canvas_y, width=width, height=MOD_GALLERY_ROW_HEIGHT)
                self._mod_canvas_rows[idx] = {
                    "row": row,
                    "name": catalog[idx]["name"],
                }
                if hasattr(self, "_mod_scroll_bind"):
                    self.bind_mod_row_scroll_targets(row)
            except Exception as exc:
                if not getattr(self, "_mod_gallery_row_error", None):
                    self._mod_gallery_row_error = str(exc)
                continue
        self.mod_tiles = {
            entry["name"]: entry["row"] for entry in self._mod_canvas_rows.values()
        }
        self._update_mod_gallery_scrollbar()
        if catalog and not self._mod_canvas_rows:
            detail = getattr(self, "_mod_gallery_row_error", None)
            msg = "Mod list failed to render. Click Refresh above or switch tab and back."
            if detail:
                msg = f"{msg}\n\nDetail: {detail}"
            self._show_mod_gallery_fallback(canvas, width, msg)

    def _show_mod_gallery_fallback(self, canvas, width, message=None):
        hint = getattr(self, "_mod_gallery_fallback_win", None)
        if hint:
            try:
                canvas.delete(hint)
            except Exception:
                pass
        label = tk.Label(
            canvas,
            text=message or "Mod list failed to render. Click Refresh above or switch tab and back.",
            font=("Segoe UI", 10, "italic"),
            fg="#FF9500",
            bg="#12131A",
            wraplength=max(320, width - 40),
            justify=tk.CENTER,
        )
        self._mod_gallery_fallback_win = canvas.create_window(
            max(20, width // 2),
            80,
            window=label,
            anchor="n",
        )

    def _schedule_mod_row_build_batch(self):
        self._render_mod_gallery_viewport()

    def _build_mod_row_batch(self, batch_size=4):
        self._render_mod_gallery_viewport()

    def _on_mod_list_canvas_configure(self, event=None):
        self._clamp_mod_gallery_top_y()
        self._schedule_mod_viewport_refresh()

    def sync_mod_list_canvas_now(self, reset_scroll=False):
        if reset_scroll:
            self._mod_gallery_top_y = 0.0
        self._clamp_mod_gallery_top_y()
        self._update_mod_gallery_scrollbar()
        self._schedule_mod_viewport_refresh()

    def sync_mod_list_canvas(self, _event=None):
        if not hasattr(self, "mod_list_canvas") or not self.mod_list_canvas.winfo_exists():
            return
        pending = getattr(self, "_mod_sync_after_id", None)
        if pending:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
        self._mod_sync_after_id = self.root.after(16, self._sync_mod_list_canvas_impl)

    def _sync_mod_list_canvas_impl(self):
        self._mod_sync_after_id = None
        self.sync_mod_list_canvas_now(reset_scroll=False)

    def bind_mod_list_scroll(self):
        canvas = self.mod_list_canvas
        scroll_wrap = getattr(self, "mod_scroll_wrap", canvas)

        def scroll_units(direction):
            self._mod_gallery_yview("scroll", direction, "units")

        def on_mousewheel(event):
            scroll_units(int(-1 * (event.delta / 120)))
            return "break"

        def on_key(event):
            if event.keysym in ("Up", "KP_Up"):
                scroll_units(-1)
                return "break"
            if event.keysym in ("Down", "KP_Down"):
                scroll_units(1)
                return "break"
            if event.keysym in ("Prior", "KP_Prior"):
                scroll_units(-6)
                return "break"
            if event.keysym in ("Next", "KP_Next"):
                scroll_units(6)
                return "break"
            if event.keysym in ("Home", "KP_Home"):
                self._mod_gallery_yview("moveto", 0.0)
                return "break"
            if event.keysym in ("End", "KP_End"):
                self._mod_gallery_yview("moveto", 1.0)
                return "break"
            return None

        def bind_widget(widget):
            widget.bind("<MouseWheel>", on_mousewheel, add="+")
            widget.bind("<Up>", on_key, add="+")
            widget.bind("<Down>", on_key, add="+")
            widget.bind("<Prior>", on_key, add="+")
            widget.bind("<Next>", on_key, add="+")
            widget.bind("<Home>", on_key, add="+")
            widget.bind("<End>", on_key, add="+")

        bind_widget(canvas)
        scroll_wrap.bind("<Enter>", lambda _e: scroll_wrap.bind_all("<MouseWheel>", on_mousewheel))
        scroll_wrap.bind("<Leave>", lambda _e: scroll_wrap.unbind_all("<MouseWheel>"))
        self._mod_scroll_bind = bind_widget

    def bind_mod_row_scroll_targets(self, widget):
        if hasattr(self, "_mod_scroll_bind"):
            self._mod_scroll_bind(widget)
            for child in widget.winfo_children():
                self.bind_mod_row_scroll_targets(child)

    def bind_instant_combo_nav(self, combo, callback):
        def on_up(event):
            curr = combo.current()
            vals = combo['values']
            if vals and curr > 0:
                combo.current(curr - 1)
                callback()
            return "break"

        def on_down(event):
            curr = combo.current()
            vals = combo['values']
            if vals and curr < len(vals) - 1:
                combo.current(curr + 1)
                callback()
            return "break"

        def on_wheel(event):
            if event.delta < 0:
                on_down(event)
            else:
                on_up(event)
            return "break"

        combo.bind("<Up>", on_up)
        combo.bind("<Down>", on_down)
        combo.bind("<MouseWheel>", on_wheel)

    def get_startup_songs(self):
        songs = list(self.builtin_songs)
        if self.browsed_startup_song:
            songs.append(self.browsed_startup_song)
        return songs

    def browse_startup_song(self):
        path = filedialog.askopenfilename(
            title="Browse for ReBirth Song",
            initialdir=SONGS_DIR if os.path.isdir(SONGS_DIR) else BASE_DIR,
            filetypes=[("ReBirth Song Files", "*.rbs"), ("All Files", "*.*")],
        )
        if not path:
            return
        path = os.path.abspath(path)
        if not is_path_inside_base(path):
            messagebox.showerror("Invalid Song", "Song must stay inside the ReBirth folder.")
            return
        label = f"Custom: {os.path.basename(path)}"
        self.browsed_startup_song = (label, path)
        self.refresh_startup_song_picker(select_path=path)

    def pick_random_startup_song(self):
        candidates = find_all_rbs_songs(max_limit=1000)
        if not candidates:
            messagebox.showinfo("Random Song", "No .RBS songs found in the library folders.")
            return
        _, path = random.choice(candidates)
        known_paths = {song_path for _, song_path in self.get_startup_songs()}
        if path not in known_paths:
            self.browsed_startup_song = (f"Random: {os.path.basename(path)}", path)
            self.refresh_startup_song_picker(select_path=path)
        else:
            self.select_startup_song(path)

    def update_launch_availability(self):
        ready = is_rebirth_exe_ready()
        self.rebirth_exe_ready = ready
        if hasattr(self, "btn_launch"):
            if ready:
                self.launch_missing_frame.pack_forget()
                self.btn_launch.pack(fill=tk.X, padx=8, pady=8, ipady=10)
            else:
                self.btn_launch.pack_forget()
                self.launch_missing_frame.pack(fill=tk.X, padx=8, pady=8)
        if hasattr(self, "btn_launch_library"):
            if ready:
                self.lbl_library_launch_blocked.pack_forget()
                self.btn_launch_library.pack(side=tk.LEFT, ipadx=10, ipady=4)
            else:
                self.btn_launch_library.pack_forget()
                self.lbl_library_launch_blocked.pack(side=tk.LEFT, ipadx=4)
        if hasattr(self, "btn_launch_acid"):
            if ready:
                self.lbl_acid_launch_blocked.pack_forget()
                self.btn_launch_acid.pack(side=tk.LEFT, padx=8, ipady=4)
            else:
                self.btn_launch_acid.pack_forget()
                self.lbl_acid_launch_blocked.pack(side=tk.LEFT, padx=8)
        self.refresh_start_launch_info()

    def populate_download_sources_form(self):
        if not hasattr(self, "entry_download_iso_url"):
            return
        catalog = get_download_catalog(self.config)
        self.entry_download_iso_url.delete(0, tk.END)
        self.entry_download_iso_url.insert(0, catalog["iso"].get("url", ""))
        self.entry_download_iso_file.delete(0, tk.END)
        self.entry_download_iso_file.insert(0, catalog["iso"].get("filename", ""))
        self.entry_download_installer_url.delete(0, tk.END)
        self.entry_download_installer_url.insert(0, catalog["installer"].get("url", ""))
        self.entry_download_installer_file.delete(0, tk.END)
        self.entry_download_installer_file.insert(0, catalog["installer"].get("filename", ""))

    def save_download_sources(self, quiet=False):
        if not hasattr(self, "entry_download_iso_url"):
            return False
        iso_ok, iso_url = validate_https_download_url(self.entry_download_iso_url.get())
        inst_ok, inst_url = validate_https_download_url(self.entry_download_installer_url.get())
        if not iso_ok or not inst_ok:
            messagebox.showerror("Invalid URL", "Download URLs must start with https:// or be left empty.")
            return False
        self.config.setdefault("download_urls", {})
        self.config["download_urls"]["iso"] = {
            "url": iso_url,
            "filename": self.entry_download_iso_file.get().strip() or DEFAULT_DOWNLOAD_CATALOG["iso"]["filename"],
        }
        self.config["download_urls"]["installer"] = {
            "url": inst_url,
            "filename": self.entry_download_installer_file.get().strip() or DEFAULT_DOWNLOAD_CATALOG["installer"]["filename"],
        }
        save_config(self.config)
        if hasattr(self, "refresh_get_rebirth_ui"):
            self.refresh_get_rebirth_ui()
        if not quiet and hasattr(self, "lbl_wizard_message"):
            self.lbl_wizard_message.config(text="Download sources saved.", fg="#00FF66")
        return True

    def save_launch_preferences(self):
        self.save_settings(quiet=True)

    def populate_settings_form(self):
        if not hasattr(self, "settings_dir_entries"):
            return
        dirs = self.config.get("directories") or {}
        for key, entry in self.settings_dir_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, dirs.get(key, DEFAULT_DIRECTORY_PATHS.get(key, "")))
        if hasattr(self, "combo_res_settings"):
            self.combo_res_settings.current(self.selected_res_index)
        self._theme_ids, self._theme_labels = get_theme_choices(self.config)
        if hasattr(self, "combo_theme_settings"):
            self.combo_theme_settings.config(values=self._theme_labels)
            try:
                self.combo_theme_settings.current(self._theme_ids.index(self.config.get("theme", "midnight_studio")))
            except ValueError:
                self.combo_theme_settings.current(0)
        self.var_cpu_affinity.set(bool(self.config.get("cpu_affinity", True)))
        self.var_rebirth_maximized.set(bool(self.config.get("rebirth_maximized", True)))
        if hasattr(self, "var_rebirth_super_rack"):
            self.var_rebirth_super_rack.set(bool(self.config.get("rebirth_super_rack", False)))
        if hasattr(self, "var_super_rack_scale"):
            self.var_super_rack_scale.set(
                super_rack_display_label_for_value(
                    self.config.get("rebirth_super_rack_display")
                    or self.config.get("rebirth_super_rack_scale", 1.25)
                )
            )
        self.refresh_settings_directory_status()

    def on_display_mode_toggled(self):
        # Super Rack and Maximize are mutually preferred — Super wins when both checked.
        if self.var_rebirth_super_rack.get() and self.var_rebirth_maximized.get():
            # Keep both saved independently; launch prefers Super Rack.
            pass
        self.refresh_start_launch_info()

    def start_super_rack_bezel(self):
        self.stop_super_rack_bezel()
        x, y, w, h, sw, sh = compute_super_rack_geometry()
        # Separate Tk root so wallpaper survives ToolBox minimize/iconify.
        bezel_root = tk.Tk()
        bezel_root.withdraw()
        try:
            bezel_root.title("Super Rack Bezel")
        except Exception:
            pass
        bezel = tk.Toplevel(bezel_root)
        bezel.withdraw()
        bezel.overrideredirect(True)
        bezel.configure(bg="#0A0C10")
        try:
            bezel.attributes("-topmost", False)
        except Exception:
            pass
        bezel.geometry(f"{sw}x{sh}+0+0")
        canvas = tk.Canvas(bezel, width=sw, height=sh, highlightthickness=0, bd=0, bg="#0A0C10")
        canvas.pack(fill=tk.BOTH, expand=True)

        # Emulator-style wallpaper: dark felt + subtle diamond tile (MAME bezel vibe).
        canvas.create_rectangle(0, 0, sw, sh, fill="#0A0C10", outline="", tags=("bg",))
        tile = 48
        for gy in range(0, sh + tile, tile):
            for gx in range(0, sw + tile, tile):
                if ((gx // tile) + (gy // tile)) & 1:
                    canvas.create_rectangle(
                        gx, gy, gx + tile, gy + tile,
                        fill="#12151C", outline="", tags=("bg",),
                    )
        step = 64
        for i in range(-sh, sw + sh, step):
            canvas.create_line(i, 0, i + sh, sh, fill="#151922", width=1, tags=("bg",))
        canvas.create_rectangle(0, 0, sw, sh, outline="#06070A", width=40, tags=("bg",))
        canvas.create_rectangle(20, 20, sw - 20, sh - 20, outline="#080A0E", width=20, tags=("bg",))

        pad = 18
        canvas.create_rectangle(
            x - pad - 10, y - pad - 10, x + w + pad + 10, y + h + pad + 10,
            outline="#2A2214", width=8, tags=("frame",),
        )
        canvas.create_rectangle(
            x - pad - 4, y - pad - 4, x + w + pad + 4, y + h + pad + 4,
            outline="#6B5428", width=3, tags=("frame",),
        )
        canvas.create_rectangle(
            x - pad, y - pad, x + w + pad, y + h + pad,
            outline="#C48A2A", width=2, tags=("frame",),
        )
        for cx, cy in (
            (x - pad, y - pad),
            (x + w + pad, y - pad),
            (x - pad, y + h + pad),
            (x + w + pad, y + h + pad),
        ):
            canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#FF9500", outline="#5A4A22", tags=("frame",))

        canvas.create_rectangle(x, y, x + w, y + h, fill="#000000", outline="#1A1C27", width=1, tags=("cutout",))

        canvas.create_text(
            sw // 2,
            max(36, y - pad - 42),
            text="REBIRTH  ·  SUPER RACK",
            fill="#C48A2A",
            font=("Segoe UI", 14, "bold"),
            tags=("label",),
        )
        canvas.create_text(
            sw // 2,
            min(sh - 24, y + h + pad + 32),
            text="Close ReBirth to exit  ·  ToolBox waits minimized",
            fill="#6C7293",
            font=("Segoe UI", 9),
            tags=("label",),
        )

        bezel.deiconify()
        try:
            bezel.update_idletasks()
            bezel_root.update_idletasks()
        except Exception:
            pass
        try:
            bezel.lower()
        except Exception:
            pass
        self._super_rack_bezel_root = bezel_root
        self._super_rack_bezel = bezel
        self._super_rack_canvas = canvas
        self._super_rack_active = True
        self._super_rack_viewport = (x, y, w, h)

    def sync_super_rack_bezel_to_hwnd(self, hwnd=None):
        """Move the bezel cutout to match the live ReBirth window rect."""
        canvas = getattr(self, "_super_rack_canvas", None)
        bezel = getattr(self, "_super_rack_bezel", None)
        if not canvas or not bezel:
            return
        if not hwnd:
            return
        rect = _window_rect(hwnd)
        if not rect:
            return
        x1, y1, x2, y2 = rect
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        pad = 18
        try:
            sw = int(bezel.winfo_screenwidth())
            sh = int(bezel.winfo_screenheight())
            canvas.delete("frame")
            canvas.delete("cutout")
            canvas.delete("label")
            canvas.create_rectangle(
                x1 - pad - 10, y1 - pad - 10, x1 + w + pad + 10, y1 + h + pad + 10,
                outline="#2A2214", width=8, tags=("frame",),
            )
            canvas.create_rectangle(
                x1 - pad - 4, y1 - pad - 4, x1 + w + pad + 4, y1 + h + pad + 4,
                outline="#6B5428", width=3, tags=("frame",),
            )
            canvas.create_rectangle(
                x1 - pad, y1 - pad, x1 + w + pad, y1 + h + pad,
                outline="#C48A2A", width=2, tags=("frame",),
            )
            for cx, cy in (
                (x1 - pad, y1 - pad),
                (x1 + w + pad, y1 - pad),
                (x1 - pad, y1 + h + pad),
                (x1 + w + pad, y1 + h + pad),
            ):
                canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#FF9500", outline="#5A4A22", tags=("frame",))
            canvas.create_rectangle(x1, y1, x1 + w, y1 + h, fill="#000000", outline="#1A1C27", width=1, tags=("cutout",))
            canvas.create_text(
                sw // 2,
                max(36, y1 - pad - 42),
                text="REBIRTH  ·  SUPER RACK",
                fill="#C48A2A",
                font=("Segoe UI", 14, "bold"),
                tags=("label",),
            )
            canvas.create_text(
                sw // 2,
                min(sh - 24, y1 + h + pad + 32),
                text="Close ReBirth to exit  ·  ToolBox waits in the background",
                fill="#6C7293",
                font=("Segoe UI", 9),
                tags=("label",),
            )
            self._super_rack_viewport = (x1, y1, w, h)
            bezel.lower()
        except Exception:
            pass

    def stop_super_rack_bezel(self):
        self._super_rack_active = False
        bezel = getattr(self, "_super_rack_bezel", None)
        bezel_root = getattr(self, "_super_rack_bezel_root", None)
        self._super_rack_bezel = None
        self._super_rack_bezel_root = None
        self._super_rack_canvas = None
        if bezel:
            try:
                bezel.destroy()
            except Exception:
                pass
        if bezel_root:
            try:
                bezel_root.destroy()
            except Exception:
                pass

    def pulse_super_rack_bezel(self, pid=None):
        bezel = getattr(self, "_super_rack_bezel", None)
        bezel_root = getattr(self, "_super_rack_bezel_root", None)
        if not bezel:
            return
        try:
            if bezel.winfo_exists():
                if bezel_root:
                    try:
                        bezel_root.update_idletasks()
                    except Exception:
                        pass
                bezel.update_idletasks()
                if pid:
                    hwnd = find_main_window_for_pid(pid)
                    if hwnd:
                        self.sync_super_rack_bezel_to_hwnd(hwnd)
                bezel.lower()
        except Exception:
            pass

    def refresh_settings_directory_status(self):
        if not hasattr(self, "settings_dir_status"):
            return
        draft_dirs = {}
        for key, entry in self.settings_dir_entries.items():
            draft_dirs[key] = entry.get().strip() or DEFAULT_DIRECTORY_PATHS.get(key, "")
        draft_config = dict(self.config)
        draft_config["directories"] = draft_dirs
        results = ensure_all_config_directories(draft_config)
        for key, lbl in self.settings_dir_status.items():
            info = results.get(key) or {}
            if info.get("ok"):
                lbl.config(text="✔ OK", fg="#00FF66")
            else:
                err = info.get("error") or "Could not create folder"
                lbl.config(text=f"✖ {err}", fg="#FF453A")

    def save_settings(self, quiet=False):
        dirs = {}
        for key, entry in self.settings_dir_entries.items():
            rel = normalize_portable_relative_path(entry.get())
            if not rel:
                messagebox.showerror("Invalid Folder", f"Directory '{key}' must be a relative path inside ReBirth.")
                return
            dirs[key] = rel

        self.config["directories"] = dirs
        self.config["launch_resolution_index"] = self.combo_res_settings.current()
        self.config["rebirth_maximized"] = bool(self.var_rebirth_maximized.get())
        self.config["rebirth_super_rack"] = bool(self.var_rebirth_super_rack.get())
        if hasattr(self, "var_super_rack_scale"):
            mode = resolve_super_rack_display(self.var_super_rack_scale.get())
            self.config["rebirth_super_rack_display"] = mode
            self.config["rebirth_super_rack_scale"] = 1.25 if mode == "fit_height" else 1.0
        self.config["cpu_affinity"] = bool(self.var_cpu_affinity.get())
        if hasattr(self, "combo_theme_settings"):
            theme_idx = self.combo_theme_settings.current()
            if 0 <= theme_idx < len(self._theme_ids):
                self.config["theme"] = self._theme_ids[theme_idx]
        merge_config_themes(self.config)
        self.selected_res_index = self.config["launch_resolution_index"]
        dir_results = apply_config_paths(self.config)
        save_config(self.config)
        self.refresh_settings_directory_status()
        self.iso_path = find_iso_file(self.config)
        self.update_iso_status()
        self.refresh_start_launch_info()
        self.refresh_get_rebirth_ui()
        self.builtin_songs = discover_builtin_default_songs()
        if hasattr(self, "refresh_startup_song_picker"):
            self.refresh_startup_song_picker()
        if hasattr(self, "refresh_documents_gallery"):
            self.refresh_documents_gallery()
        failed_dirs = [key for key, info in dir_results.items() if not info.get("ok")]
        if hasattr(self, "lbl_settings_status"):
            if failed_dirs:
                self.lbl_settings_status.config(
                    text=f"Saved, but folder error(s): {', '.join(failed_dirs)}",
                    fg="#FF9500",
                )
            else:
                self.lbl_settings_status.config(text=f"Saved to {os.path.basename(CONFIG_FILE)}", fg="#00FF66")
        if not quiet:
            if failed_dirs:
                messagebox.showwarning(
                    "Settings Saved",
                    f"Settings saved to:\n{CONFIG_FILE}\n\nCould not prepare folder(s): {', '.join(failed_dirs)}",
                )
            else:
                messagebox.showinfo("Settings Saved", f"Settings saved to:\n{CONFIG_FILE}")

    def backup_collection_to_7z(self):
        if not find_seven_zip_executable():
            messagebox.showerror(
                "7-Zip Required",
                "7-Zip (7z.exe) was not found.\n\n"
                "Install 7-Zip from https://www.7-zip.org/ or copy 7z.exe into the ToolBox folder.",
            )
            return
        stamp = time.strftime("%Y%m%d_%H%M")
        default_name = f"ReBirthToolBox_backup_{stamp}.7z"
        initial_dir = resolve_config_directory(self.config, "downloads", DEFAULT_DIRECTORY_PATHS["downloads"])
        os.makedirs(initial_dir, exist_ok=True)
        output_path = filedialog.asksaveasfilename(
            title="Save ToolBox Backup (7z)",
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".7z",
            filetypes=[("7-Zip archive", "*.7z"), ("All files", "*.*")],
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".7z"):
            output_path += ".7z"
        if hasattr(self, "lbl_settings_status"):
            self.lbl_settings_status.config(text="Creating 7z backup — please wait...", fg="#FF9500")
        self.root.update_idletasks()
        threading.Thread(target=self._backup_collection_worker, args=(output_path,), daemon=True).start()

    def _backup_collection_worker(self, output_path):
        ok, message = create_toolbox_backup_7z(output_path, self.config)
        self.root.after(0, lambda: self._backup_collection_finished(ok, message, output_path))

    def _backup_collection_finished(self, ok, message, output_path):
        if hasattr(self, "lbl_settings_status"):
            self.lbl_settings_status.config(
                text=message if ok else f"Backup failed: {message}",
                fg="#00FF66" if ok else "#FF453A",
            )
        if ok:
            answer = messagebox.askyesno(
                "Backup Complete",
                f"{message}\n\nOpen the folder containing the archive?",
            )
            if answer:
                try:
                    os.startfile(os.path.dirname(os.path.abspath(output_path)))
                except OSError as exc:
                    messagebox.showerror("Open Folder", f"Could not open folder:\n{exc}")
        else:
            messagebox.showerror("Backup Failed", message)

    def verify_download_files(self):
        apply_config_paths(self.config)
        status = scan_rebirth_download_status(self.config)
        catalog = get_download_catalog(self.config)
        lines = [f"Downloads folder: {DOWNLOADS_DIR}", ""]
        checks = (
            ("iso", "ReBirth ISO", status["iso_ready"], catalog["iso"]),
            ("installer", "ReBirth RB-338 2.0.1 Installer", status["installer_ready"], catalog["installer"]),
        )
        missing = []
        for _key, label, ready, info in checks:
            filename = info.get("filename", "?")
            url = (info.get("url") or "").strip()
            if ready:
                lines.append(f"✔ {label}: {filename}")
            else:
                hint = "configure https URL in Settings or copy manually to Downloads"
                if not url:
                    hint = "no URL configured — copy manually to Downloads"
                lines.append(f"✖ {label}: {filename} ({hint})")
                if _key in ("iso", "installer"):
                    missing.append(label)
        text = "\n".join(lines)
        if hasattr(self, "lbl_settings_status"):
            color = "#00FF66" if not missing else "#FF9500"
            self.lbl_settings_status.config(text=text.replace("\n", "   |   "), fg=color)
        if missing:
            messagebox.showwarning("Downloads Check", text)
        else:
            messagebox.showinfo("Downloads Check", text)
        self.refresh_get_rebirth_ui()
        return not missing

    def refresh_startup_song_picker(self, select_path=None):
        for widget in self.startup_tiles_frame.winfo_children():
            widget.destroy()
        self.startup_song_tiles.clear()
        self.startup_tile_photos.clear()

        songs = self.get_startup_songs()
        if not songs:
            tk.Label(
                self.startup_tiles_frame,
                text="Default Songs folder not found.",
                font=("Segoe UI", 9, "italic"),
                fg="#FF9500",
                bg="#1A1C27",
            ).pack(pady=8)
            self.selected_startup_song_path = None
            return

        tile_photo = make_tk_image_from_png(DEFAULT_SCREENSHOT, 360, 150)

        for col, (label, path) in enumerate(songs):
            short = label.split("(")[0].strip()
            if label.startswith("Custom:"):
                short = os.path.splitext(os.path.basename(path))[0]
            filename = os.path.basename(path)
            is_custom = self.browsed_startup_song and path == self.browsed_startup_song[1]
            screenshot = self.get_screenshot_for_song_path(path)
            song_photo = make_tk_image_from_png(screenshot, 360, 150) if screenshot else tile_photo
            tile = tk.Frame(
                self.startup_tiles_frame,
                bg="#12131A",
                highlightbackground="#00E5FF" if is_custom else "#282B3C",
                highlightthickness=2,
                cursor="hand2",
            )
            tile.grid(row=0, column=col, padx=8, pady=2, sticky="nsew")
            self.startup_tiles_frame.grid_columnconfigure(col, weight=1)

            if song_photo:
                img_lbl = tk.Label(tile, image=song_photo, bg="#12131A")
                img_lbl.pack(padx=8, pady=(8, 4))
                img_lbl.bind("<Button-1>", lambda _e, p=path: self.select_startup_song(p))
                self.startup_tile_photos.append(song_photo)
            elif tile_photo:
                img_lbl = tk.Label(tile, image=tile_photo, bg="#12131A")
                img_lbl.pack(padx=8, pady=(8, 4))
                img_lbl.bind("<Button-1>", lambda _e, p=path: self.select_startup_song(p))
            else:
                tk.Label(tile, text="[screenshot missing]", font=("Segoe UI", 8, "italic"), fg="#6C7293", bg="#12131A").pack(pady=(12, 4))

            tk.Label(tile, text=short, font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#12131A", wraplength=220, justify=tk.CENTER).pack(padx=8)
            tk.Label(tile, text=filename, font=("Segoe UI", 7), fg="#6C7293", bg="#12131A", wraplength=220, justify=tk.CENTER).pack(padx=8, pady=(2, 10))
            if is_custom:
                tk.Label(tile, text="BROWSED", font=("Segoe UI", 7, "bold"), fg="#00E5FF", bg="#12131A").pack(pady=(0, 8))

            for widget in tile.winfo_children():
                widget.bind("<Button-1>", lambda _e, p=path: self.select_startup_song(p))
            tile.bind("<Button-1>", lambda _e, p=path: self.select_startup_song(p))
            self.startup_song_tiles[path] = tile

        if tile_photo and not self.startup_tile_photos:
            self.startup_tile_photos.append(tile_photo)

        preferred = select_path or self.selected_startup_song_path
        if preferred and preferred in self.startup_song_tiles:
            self.select_startup_song(preferred)
        else:
            self.select_startup_song(songs[0][1])

    def select_startup_song(self, path):
        self.selected_startup_song_path = path
        for song_path, tile in self.startup_song_tiles.items():
            if song_path == path:
                tile.config(highlightbackground="#00FF66", highlightthickness=3)
            else:
                tile.config(highlightbackground="#282B3C", highlightthickness=2)
        self.on_song_selected()

    def open_documents_folder(self):
        results = ensure_all_config_directories(self.config)
        doc_info = results.get("documents") or {}
        if not doc_info.get("ok"):
            messagebox.showerror("Documents Folder", doc_info.get("error") or "Documents folder is not available.")
            return
        try:
            os.startfile(DOCUMENTS_DIR)
        except Exception as exc:
            messagebox.showerror("Documents Folder", f"Could not open folder:\n{exc}")

    def build_document_preview_photo(self, doc_info):
        path = doc_info["path"]
        ext = doc_info.get("ext") or ""
        max_w, max_h = DOCUMENT_PREVIEW_SIZE
        photo = None
        if ext in DOCUMENT_IMAGE_EXTENSIONS:
            photo = make_document_image_preview(path, max_w, max_h, ext=ext)
        elif ext in DOCUMENT_HTML_EXTENSIONS:
            photo = make_html_preview_photo(path, max_w, max_h, ext=ext)
        elif ext in DOCUMENT_TEXT_EXTENSIONS:
            photo = make_text_preview_photo(path, max_w, max_h, ext=ext)
        if photo:
            return photo
        return make_extension_badge_photo(ext or "file", max_w, max_h)

    def bind_document_tile_events(self, widget, doc_info):
        widget.bind("<Button-1>", lambda _e, d=doc_info: self.select_document(d))
        widget.bind("<Double-Button-1>", lambda _e, d=doc_info: self.open_document_file(d))
        try:
            widget.config(cursor="hand2")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self.bind_document_tile_events(child, doc_info)

    def select_document(self, doc_info):
        modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(doc_info.get("modified", 0)))
        size_text = format_file_size(doc_info.get("size", 0))
        type_text = document_type_label(doc_info.get("ext") or "")
        self.lbl_documents_detail.config(
            text=(
                f"{doc_info.get('rel_path') or doc_info.get('name')}  ·  {type_text}  ·  {size_text}  ·  {modified}\n"
                f"Double-click to open with the default Windows app."
            ),
            fg="#A0A5C0",
        )
        for path_key, tile in self.document_tiles.items():
            if path_key == doc_info["path"]:
                tile.config(highlightbackground="#00FF66", highlightthickness=2)
            else:
                tile.config(highlightbackground="#282B3C", highlightthickness=1)

    def open_document_file(self, doc_info):
        path = doc_info.get("path")
        if not path or not os.path.exists(path):
            messagebox.showerror("Open Document", "File no longer exists.")
            self.refresh_documents_gallery()
            return
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror("Open Document", f"Could not open file:\n{exc}")

    def refresh_documents_gallery(self):
        if not hasattr(self, "doc_tiles_frame"):
            return

        for widget in self.doc_tiles_frame.winfo_children():
            widget.destroy()
        self.document_tiles.clear()
        self.document_tile_photos.clear()

        results = ensure_all_config_directories(self.config)
        doc_info = results.get("documents") or {}
        rel = (self.config.get("directories") or {}).get("documents", DEFAULT_DIRECTORY_PATHS["documents"])
        if not doc_info.get("ok"):
            err = doc_info.get("error") or "Documents folder is not available"
            self.lbl_documents_path.config(text=f"✖ ./{rel} — {err}", fg="#FF453A")
            self.lbl_documents_detail.config(
                text="Fix the documents folder path in Settings → TOOLBOX FOLDERS.",
                fg="#FF9500",
            )
            tk.Label(
                self.doc_tiles_frame,
                text="Documents folder could not be created.",
                font=("Segoe UI", 10, "italic"),
                fg="#FF453A",
                bg="#12131A",
            ).grid(row=0, column=0, padx=12, pady=20, sticky="w")
            return

        self.lbl_documents_path.config(text=f"Folder: ./{rel}   ({DOCUMENTS_DIR})", fg="#6C7293")
        self.document_files = scan_documents_folder(DOCUMENTS_DIR)
        if not self.document_files:
            self.lbl_documents_detail.config(
                text="No documents yet. Copy manuals, notes, screenshots, or other files into the Documents folder shown above.",
                fg="#6C7293",
            )
            tk.Label(
                self.doc_tiles_frame,
                text="No documents found in the configured Documents folder.",
                font=("Segoe UI", 10, "italic"),
                fg="#6C7293",
                bg="#12131A",
                justify=tk.LEFT,
            ).pack(padx=12, pady=20, anchor="w")
            return

        preview_w, preview_h = DOCUMENT_PREVIEW_SIZE
        for doc in self.document_files:
            row = tk.Frame(
                self.doc_tiles_frame,
                bg="#1A1C27",
                highlightbackground="#282B3C",
                highlightthickness=1,
            )
            row.pack(fill=tk.X, padx=8, pady=4)

            preview_frame = tk.Frame(row, bg="#242736", width=preview_w, height=preview_h)
            preview_frame.pack(side=tk.LEFT, padx=(8, 10), pady=8)
            preview_frame.pack_propagate(False)
            preview = tk.Label(preview_frame, bg="#242736", bd=0)
            preview.pack(expand=True)
            photo = self.build_document_preview_photo(doc)
            if photo:
                preview.config(image=photo)
                self.document_tile_photos.append(photo)
            else:
                preview.config(
                    text=document_type_label(doc.get("ext") or ""),
                    fg="#00E5FF",
                    font=("Segoe UI", 9, "bold"),
                )

            info = tk.Frame(row, bg="#1A1C27")
            info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=8)
            display_name = doc.get("rel_path") or doc.get("name")
            tk.Label(
                info,
                text=display_name,
                font=("Segoe UI", 9, "bold"),
                fg="#FFFFFF",
                bg="#1A1C27",
                anchor="w",
                justify=tk.LEFT,
                wraplength=620,
            ).pack(fill=tk.X)
            type_label = document_type_label(doc.get("ext") or "")
            tk.Label(
                info,
                text=f"{type_label}  ·  {format_file_size(doc.get('size', 0))}  ·  {time.strftime('%Y-%m-%d', time.localtime(doc.get('modified', 0)))}",
                font=("Segoe UI", 8),
                fg="#6C7293",
                bg="#1A1C27",
                anchor="w",
            ).pack(fill=tk.X, pady=(4, 0))

            self.bind_document_tile_events(row, doc)
            self.document_tiles[doc["path"]] = row

        if self.document_files:
            self.select_document(self.document_files[0])
        self.doc_tiles_frame.update_idletasks()
        self.doc_list_canvas.configure(scrollregion=self.doc_list_canvas.bbox("all"))

    def scan_files_async(self):
        show_overlay = not self._library_cache_loaded
        if show_overlay:
            self.show_loading_overlay("Please wait...", "Scanning song library and mod skins...")

        def worker():
            def on_progress(count):
                if show_overlay:
                    self.root.after(0, lambda c=count: self.update_loading_overlay(f"Scanning songs... found {c} .rbs files"))
                self.root.after(0, lambda c=count: self.lbl_scan_status.config(text=f"Scanning library... Found {c} .rbs songs"))

            songs = find_all_rbs_songs(progress_callback=on_progress)
            if show_overlay:
                self.root.after(0, lambda: self.update_loading_overlay("Scanning installed mod skins..."))
            mods = scan_installed_mods(self._mod_info_cache)
            library_songs = [(name, path) for name, path in songs if not is_under_default_songs(path)]

            def on_meta_progress(done, total):
                if show_overlay:
                    self.root.after(0, lambda d=done, t=total: self.update_loading_overlay(f"Reading song metadata... {d}/{t}"))

            self.warm_rbs_metadata_cache(library_songs, include_patterns=False, progress_callback=on_meta_progress)
            self.root.after(0, lambda: self.update_file_lists(songs, mods, show_overlay=show_overlay))

        threading.Thread(target=worker, daemon=True).start()

    def update_file_lists(self, songs, mods, show_overlay=True):
        current_path = self.get_selected_song_path()
        self.builtin_songs = discover_builtin_default_songs()
        self.rbs_songs = [(name, path) for name, path in songs if not is_under_default_songs(path)]
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        lib_count = len(self.rbs_songs)
        default_count = len(self.builtin_songs)
        self.lbl_scan_status.config(
            text=f"✔ Library Scan Complete: {default_count} default + {lib_count} library songs.",
            fg="#00FF66"
        )

        self.refresh_startup_song_picker(current_path)
        self.populate_library_tree()

        self.installed_mods = mods
        self.mod_songs_index = self.build_mod_songs_index()
        self.mark_mod_gallery_dirty()
        try:
            tab_text = self.notebook.tab(self.notebook.select(), "text")
            if tab_text == MOD_TAB_LABEL:
                self.ensure_mod_gallery()
        except Exception:
            pass
        save_library_cache_to_disk(self.rbs_songs, self.installed_mods, self._metadata_cache, self._mod_info_cache)
        self._library_cache_loaded = True
        if show_overlay:
            self.hide_loading_overlay()

    def build_mod_songs_index(self):
        index = {}
        mod_entries = []
        for entry in self.installed_mods:
            if len(entry) >= 4:
                display, path, _desc, rebirth_name = entry[0], entry[1], entry[2], entry[3]
            else:
                display, path = entry[0], entry[1]
                rebirth_name = resolve_mod_rebirth_name(path, display)
            mod_entries.append((display, path, rebirth_name))

        for filename, path in self.rbs_songs:
            meta = self.get_rbs_metadata(path, include_patterns=False)
            song_mod = (meta.get("mod_name") or "Standard ReBirth").strip()
            if not song_mod or song_mod == "Standard ReBirth" or "standard" in song_mod.lower():
                index.setdefault("standard rebirth", []).append((filename, path))
                continue

            matched_display = None
            for display, _mod_path, rebirth_name in mod_entries:
                if mod_names_match(song_mod, rebirth_name) or mod_names_match(song_mod, display):
                    matched_display = display
                    break

            if matched_display:
                key = matched_display.strip().lower()
            else:
                key = song_mod.lower()
            index.setdefault(key, []).append((filename, path))

        for key in index:
            index[key].sort(key=lambda item: item[0].lower())
        return index

    def update_library_headings(self):
        for col_id, label in self.library_heading_labels.items():
            heading = label
            if col_id == self.library_sort_column:
                heading += " ▼" if self.library_sort_reverse else " ▲"
            self.tree_songs.heading(col_id, text=heading)

    def sort_library_by(self, column_id):
        if self.library_sort_column == column_id:
            self.library_sort_reverse = not self.library_sort_reverse
        else:
            self.library_sort_column = column_id
            self.library_sort_reverse = False
        self.populate_library_tree()

    def populate_library_tree(self):
        for item in self.tree_songs.get_children():
            self.tree_songs.delete(item)

        search_q = self.entry_search.get().lower()
        rows = []

        for filename, path in self.rbs_songs:
            if not os.path.exists(path):
                continue
            is_fav = "⭐" if path in self.config.get("favorites", []) else ""
            if self.fav_only_mode and not is_fav:
                continue

            meta = self.get_rbs_metadata(path, include_patterns=False)
            parsed_title = meta["title"] if meta["title"] else filename
            mode_str = format_display_mode(meta["mode"])
            if meta.get("format") == "legacy_midi":
                mode_str = f"{mode_str} (v{meta.get('format_version') or '3.x'})"
            mod_name = meta.get("mod_name") or "Standard ReBirth"
            description = (meta.get("comments") or "").replace("\n", " ").strip()
            if description == "No description available.":
                description = ""

            if search_q and not any(
                search_q in field.lower()
                for field in (parsed_title, filename, mod_name, description)
            ):
                continue

            rows.append({
                "path": path,
                "fav": is_fav,
                "filename": filename,
                "bpm": str(meta["bpm"]) if meta["bpm"] else "--",
                "bpm_num": meta["bpm"] or 0,
                "mode": mode_str,
                "dur": meta["duration_str"],
                "mod_name": mod_name,
                "description": description[:120],
                "breakdown": meta["pattern_breakdown"],
            })

        sort_keys = {
            "fav": lambda r: r["fav"],
            "title": lambda r: r["filename"].lower(),
            "bpm": lambda r: r["bpm_num"],
            "mode": lambda r: r["mode"].lower(),
            "dur": lambda r: r["dur"].lower(),
            "mod_name": lambda r: r["mod_name"].lower(),
            "description": lambda r: r["description"].lower(),
            "breakdown": lambda r: r["breakdown"].lower(),
        }
        rows.sort(key=sort_keys.get(self.library_sort_column, sort_keys["title"]), reverse=self.library_sort_reverse)

        for row in rows:
            self.tree_songs.insert(
                "",
                tk.END,
                values=(
                    row["fav"], row["filename"], row["bpm"], row["mode"], row["dur"],
                    row["mod_name"], row["description"], row["breakdown"],
                ),
                tags=(row["path"],),
            )

        self.update_library_headings()

    def filter_library_songs(self, event=None):
        self.populate_library_tree()

    def toggle_fav_filter(self):
        self.fav_only_mode = not self.fav_only_mode
        self.btn_fav_filter.config(bg="#FFD700" if self.fav_only_mode else "#242736", fg="#12131A" if self.fav_only_mode else "#FFD700")
        self.populate_library_tree()

    def toggle_favorite_selected(self):
        sel = self.tree_songs.selection()
        if not sel: return
        item_tags = self.tree_songs.item(sel[0], "tags")
        if not item_tags: return
        path = item_tags[0]

        favs = self.config.get("favorites", [])
        if path in favs:
            favs.remove(path)
        else:
            favs.append(path)
        self.config["favorites"] = favs
        save_config(self.config)
        self.populate_library_tree()

    def get_selected_song_path(self):
        return self.selected_startup_song_path or find_template_rbs()

    def get_selected_library_path(self):
        sel = self.tree_songs.selection()
        if not sel:
            return None
        item_tags = self.tree_songs.item(sel[0], "tags")
        return item_tags[0] if item_tags else None

    def on_song_selected(self, event=None):
        path = self.get_selected_song_path()
        if path:
            meta = self.get_rbs_metadata(path, include_patterns=True)
            self.lbl_meta_bpm.config(text=f"BPM: {meta['bpm'] or 'Unknown'}")
            self.lbl_meta_mode.config(text=f"Mode: {format_display_mode(meta['mode'])}")
            self.lbl_meta_dur.config(text=f"Duration: {meta['duration_str']}")
            self.lbl_meta_engine.config(text=f"Engine: {meta['sound_engine']}")
            self.lbl_meta_mod.config(text=f"Mod Name: {meta['mod_name']}")
            self.lbl_meta_pats.config(text=f"Active Patterns: {meta['active_patterns']} total ({meta['pattern_breakdown']})")
            self.lbl_meta_title.config(text=f"Title: {meta['title']}")
            self.lbl_meta_desc.config(text=meta['comments'][:120])
        self.refresh_start_launch_info()

    def export_selected_to_midi(self):
        path = self.get_selected_library_path()
        if not path:
            return
        default_fn = os.path.splitext(os.path.basename(path))[0] + ".mid"
        out_p = filedialog.asksaveasfilename(title="Export Song to MIDI", defaultextension=".mid", initialfile=default_fn, filetypes=[("MIDI Files", "*.mid")])
        if out_p:
            meta = self.get_rbs_metadata(path, include_patterns=False)
            bpm = meta.get("bpm") or 120.0
            try:
                with open(path, "rb") as f:
                    is_legacy_midi = f.read(4) == b"MThd"
            except Exception:
                is_legacy_midi = False
            if is_legacy_midi:
                shutil.copy2(path, out_p)
                messagebox.showinfo(
                    "MIDI Export",
                    f"Legacy ReBirth song copied to:\n{out_p}\n\nTempo: {bpm:g} BPM (already embedded in file)",
                )
            elif export_rbs_to_midi(path, out_p, bpm=bpm):
                messagebox.showinfo("MIDI Export", f"Successfully exported to:\n{out_p}\n\nTempo: {bpm:g} BPM")

    def show_library_context_menu(self, event):
        row_id = self.tree_songs.identify_row(event.y)
        if row_id:
            self.tree_songs.selection_set(row_id)
            self.tree_songs.focus(row_id)
            self.tree_songs.see(row_id)

        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#242736",
            fg="#E8EAF6",
            activebackground="#00A86B",
            activeforeground="#FFFFFF",
            bd=0,
        )
        menu.add_command(label="Launch Selected", command=self.launch_rebirth_from_library)
        menu.add_command(label="Random Song", command=self.pick_random_library_song)
        menu.add_separator()
        menu.add_command(label="Toggle Favorite", command=self.toggle_favorite_selected)
        menu.add_command(label="Export to .MID", command=self.export_selected_to_midi)
        menu.add_command(label="Export Pattern Bank", command=self.export_selected_to_pattern_bank)
        menu.add_command(label="Export All Pattern Banks...", command=self.export_all_songs_to_pattern_banks)
        menu.add_command(label="Printable HTML", command=self.export_selected_to_html)
        menu.add_command(label="Deconstruct", command=self.open_deconstruction_window)
        menu.add_command(label="Open in Inspire Me", command=self.open_selected_in_inspire_me)
        menu.add_separator()
        menu.add_command(label="Delete Song", command=self.delete_selected_library_song)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def delete_selected_library_song(self):
        path = self.get_selected_library_path()
        if not path:
            messagebox.showinfo("Select Song", "Please select a song in the library first.")
            return
        if is_under_default_songs(path):
            messagebox.showwarning("Protected Song", "Default Songs cannot be deleted from here.")
            return
        filename = os.path.basename(path)
        if not messagebox.askyesno("Delete Song", f"Permanently delete this song?\n\n{filename}"):
            return
        try:
            os.remove(path)
            norm_deleted = os.path.normcase(os.path.abspath(path))
            favs = self.config.get("favorites", [])
            self.config["favorites"] = [f for f in favs if os.path.normcase(os.path.abspath(f)) != norm_deleted]
            save_config(self.config)
            self.rbs_songs = [
                (name, p)
                for name, p in self.rbs_songs
                if os.path.normcase(os.path.abspath(p)) != norm_deleted and os.path.exists(p)
            ]
            self.mod_songs_index = self.build_mod_songs_index()
            self.populate_library_tree()
            messagebox.showinfo("Deleted", f"Removed:\n{filename}")
        except Exception as exc:
            messagebox.showerror("Delete Failed", f"Could not delete song:\n{exc}")

    def export_selected_to_html(self):
        path = self.get_selected_library_path()
        if not path:
            return
        default_fn = os.path.splitext(os.path.basename(path))[0] + "_cheatsheet.html"
        out_p = filedialog.asksaveasfilename(title="Export Printable HTML Cheat Sheet", defaultextension=".html", initialfile=default_fn, filetypes=[("HTML Files", "*.html")])
        if out_p:
            if export_html_cheatsheet(path, out_p):
                webbrowser.open(out_p)

    def export_selected_to_pattern_bank(self):
        path = self.get_selected_library_path()
        if not path:
            messagebox.showinfo("Select Song", "Please select a song in the library first.")
            return
        ensure_pattern_banks_dir()
        default_name = os.path.splitext(os.path.basename(path))[0] + "_bank.json"
        out_p = filedialog.asksaveasfilename(
            title="Export Song to Pattern Bank",
            defaultextension=".json",
            initialdir=PATTERN_BANKS_DIR,
            initialfile=default_name,
            filetypes=[("Pattern Bank JSON", "*.json"), ("All Files", "*.*")],
        )
        if not out_p:
            return
        try:
            export_song_to_pattern_bank_json(
                path,
                out_p,
                description=f"Extracted from {os.path.basename(path)}",
                author="ReBirth ToolBox",
                tags=["song-export"],
            )
            messagebox.showinfo("Export Pattern Bank", f"Pattern bank saved to:\n{out_p}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not export pattern bank:\n{exc}")

    def export_all_songs_to_pattern_banks(self):
        ensure_pattern_banks_dir()
        out_dir = filedialog.askdirectory(
            title="Export All Songs as Pattern Banks",
            initialdir=PATTERN_BANKS_DIR,
        )
        if not out_dir:
            return
        songs = []
        seen = set()
        for name, path in list(getattr(self, "rbs_songs", [])) + list(getattr(self, "builtin_songs", [])):
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen or not os.path.exists(path):
                continue
            seen.add(norm)
            songs.append((name, path))
        if not songs:
            messagebox.showinfo("Export Pattern Banks", "No songs available to export.")
            return
        if not messagebox.askyesno(
            "Export All Pattern Banks",
            f"Export {len(songs)} song(s) into:\n{out_dir}\n\nContinue?",
        ):
            return
        exported = 0
        skipped = 0
        for name, path in songs:
            try:
                patterns_1, patterns_2, drums_808, drums_909 = import_patterns_from_rbs(path)
                if not any((patterns_1, patterns_2, drums_808, drums_909)):
                    skipped += 1
                    continue
                safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in os.path.splitext(name)[0]).strip() or "Song"
                out_p = os.path.join(out_dir, f"{safe}_bank.json")
                export_song_to_pattern_bank_json(
                    path,
                    out_p,
                    description=f"Bulk export from {name}",
                    author="ReBirth ToolBox",
                    tags=["bulk-export"],
                )
                exported += 1
            except Exception:
                skipped += 1
        self.refresh_pattern_bank_combo()
        messagebox.showinfo(
            "Export All Pattern Banks",
            f"Finished bulk export.\n\nExported: {exported}\nSkipped: {skipped}\nFolder:\n{out_dir}",
        )

    def get_acid_drum_machine(self):
        ctx = self.get_acid_editor_context()
        if ctx == "808":
            return "808"
        if ctx == "909":
            return "909"
        return self.generated_drum_machine or "909"

    def get_acid_editor_context(self):
        if not hasattr(self, "acid_editor_notebook"):
            return "303_1"
        try:
            idx = self.acid_editor_notebook.index(self.acid_editor_notebook.select())
        except Exception:
            return "303_1"
        return ("303_1", "303_2", "808", "909")[min(idx, 3)]

    def get_active_303_patterns(self):
        if self.get_acid_editor_context() == "303_2":
            return self.generated_patterns_303_2
        return self.generated_patterns

    def get_drum_patterns_store(self, machine=None):
        machine = machine or self.get_acid_drum_machine()
        if machine == "808":
            return self.generated_drum_patterns_808
        return self.generated_drum_patterns_909

    def get_acid_generation_params(self):
        return {
            "scale_intervals": SCALES.get(self.combo_scale.get(), SCALES["Pentatonic Minor"]),
            "density": self.scale_density.get() / 100.0,
            "accent_p": self.scale_accent.get() / 100.0,
            "slide_p": self.scale_slide.get() / 100.0,
            "octave_spread": self.scale_octave.get() / 100.0,
            "is_909": self.get_acid_drum_machine() != "808",
        }

    def has_any_acid_patterns(self):
        return bool(
            self.generated_patterns
            or self.generated_patterns_303_2
            or self.generated_drum_patterns_808
            or self.generated_drum_patterns_909
        )

    def get_pat_slot_code(self, ctx=None):
        ctx = ctx or self.get_acid_editor_context()
        slots = getattr(self, "acid_active_slots", None) or {}
        if ctx in slots:
            return slots[ctx]
        if hasattr(self, "pattern_selector"):
            return self.pattern_selector.get_slot()
        return "A1"

    def switch_acid_instrument_tab(self, ctx):
        tab_index = {"303_1": 0, "303_2": 1, "808": 2, "909": 3}.get(ctx)
        if tab_index is None or not hasattr(self, "acid_editor_notebook"):
            return
        try:
            self.acid_editor_notebook.select(tab_index)
        except Exception:
            pass

    def _update_pattern_slot_ui(self):
        ctx = self.get_acid_editor_context()
        titles = {
            "303_1": ("TB-303 #1", "#00FF66"),
            "303_2": ("TB-303 #2", "#00E5FF"),
            "808": ("TR-808", "#FF9500"),
            "909": ("TR-909", "#00E5FF"),
        }
        title, color = titles.get(ctx, ("Pattern", "#A0A5C0"))
        if hasattr(self, "lbl_pattern_selector_ctx"):
            self.lbl_pattern_selector_ctx.config(
                text=f"Active pattern for {title}",
                fg=color,
            )
        if hasattr(self, "pattern_selector"):
            self.pattern_selector.config(highlightbackground=color)
            self.pattern_selector.set_slot(self.get_pat_slot_code(ctx))
        badge_labels = {"303_1": "#1", "303_2": "#2", "808": "808", "909": "909"}
        badge_colors = {"303_1": "#00FF66", "303_2": "#00E5FF", "808": "#FF9500", "909": "#00E5FF"}
        for key, badge in getattr(self, "_pat_slot_badges", {}).items():
            slot = self.acid_active_slots.get(key, "A1")
            short = badge_labels.get(key, key)
            is_active = key == ctx
            badge.config(
                text=f"{short}:{slot}",
                bg="#FF3366" if is_active else "#242736",
                fg="#FFFFFF" if is_active else badge_colors.get(key, "#A0A5C0"),
            )

    def get_acid_preview_bpm(self):
        if hasattr(self, "scale_acid_bpm"):
            try:
                return int(float(self.scale_acid_bpm.get()))
            except (TypeError, ValueError):
                pass
        return getattr(self, "acid_preview_bpm", 128)

    def get_acid_mute_flags(self, for_full=False):
        if not for_full:
            return {"mute_303_1": False, "mute_303_2": False, "mute_drums": False}
        machine = self.get_active_launch_drum_machine()
        mute_drums = self.var_mute_808.get() if machine == "808" else self.var_mute_909.get()
        return {
            "mute_303_1": self.var_mute_303_1.get(),
            "mute_303_2": self.var_mute_303_2.get(),
            "mute_drums": mute_drums,
        }

    def get_acid_mix_gains(self):
        if hasattr(self, "scale_mix_303_1"):
            return {
                "gain_303_1": max(0.0, min(1.0, self.scale_mix_303_1.get() / 100.0)),
                "gain_303_2": max(0.0, min(1.0, self.scale_mix_303_2.get() / 100.0)),
                "gain_drums": max(0.0, min(1.0, self.scale_mix_drums.get() / 100.0)),
            }
        levels = self.config.get("acid_mix_levels") or {}
        return {
            "gain_303_1": max(0.0, min(1.0, float(levels.get("303_1", 85)) / 100.0)),
            "gain_303_2": max(0.0, min(1.0, float(levels.get("303_2", 85)) / 100.0)),
            "gain_drums": max(0.0, min(1.0, float(levels.get("drums", 90)) / 100.0)),
        }

    def save_acid_mixer_levels(self):
        if not hasattr(self, "scale_mix_303_1"):
            return
        self.config["acid_mix_levels"] = {
            "303_1": int(self.scale_mix_303_1.get()),
            "303_2": int(self.scale_mix_303_2.get()),
            "drums": int(self.scale_mix_drums.get()),
        }
        save_config(self.config)

    def on_acid_mixer_changed(self, _val=None):
        self.save_acid_mixer_levels()
        if self.acid_loop_enabled:
            self._acid_preview_mode = "full"
            self.update_acid_loop_buttons()
            self.schedule_acid_loop_restart()

    def reset_acid_mixer_levels(self):
        if not hasattr(self, "scale_mix_303_1"):
            return
        self.scale_mix_303_1.set(85)
        self.scale_mix_303_2.set(85)
        self.scale_mix_drums.set(90)
        self.on_acid_mixer_changed()

    def on_acid_bpm_changed(self, _val=None):
        self.acid_preview_bpm = self.get_acid_preview_bpm()
        if self.acid_loop_enabled and self._acid_preview_mode == "full":
            self.schedule_acid_loop_restart()

    def on_acid_mute_changed(self):
        if self.acid_loop_enabled:
            self._acid_preview_mode = "full"
            self.update_acid_loop_buttons()
            self.schedule_acid_loop_restart()

    def _get_acid_step_duration(self):
        return 15.0 / max(80, self.get_acid_preview_bpm())

    def _get_acid_pattern_duration(self):
        return 16 * self._get_acid_step_duration()

    def _reset_playhead_clock(self):
        self._playhead_start = time.perf_counter()
        self._last_playhead_step = -1

    def start_playhead_animation(self, pattern_count=1):
        self.stop_playhead_animation()
        self._playhead_running = True
        self._playhead_pattern_count = max(1, pattern_count)
        self._reset_playhead_clock()
        self._tick_playhead()

    def _tick_playhead(self):
        if not self._playhead_running:
            return
        elapsed = time.perf_counter() - self._playhead_start
        step_idx = int(elapsed / self._get_acid_step_duration()) % 16
        if step_idx != getattr(self, "_last_playhead_step", -1):
            self._last_playhead_step = step_idx
            if hasattr(self, "acid_piano_roll"):
                self.acid_piano_roll.set_playhead(step_idx)
            if hasattr(self, "acid_drum_grid"):
                self.acid_drum_grid.set_playhead(step_idx)
        self._playhead_timer_id = self.root.after(16, self._tick_playhead)

    def stop_playhead_animation(self):
        self._playhead_running = False
        self._last_playhead_step = -1
        if self._playhead_timer_id:
            try:
                self.root.after_cancel(self._playhead_timer_id)
            except Exception:
                pass
            self._playhead_timer_id = None
        if hasattr(self, "acid_piano_roll"):
            self.acid_piano_roll.set_playhead(None)
        if hasattr(self, "acid_drum_grid"):
            self.acid_drum_grid.set_playhead(None)

    def _schedule_playhead_stop(self, duration_seconds=None):
        duration_seconds = duration_seconds or self._get_acid_pattern_duration()
        ms = max(100, int(duration_seconds * 1000))
        self.root.after(ms, self.stop_playhead_animation)

    def apply_loaded_pattern_stores(self, patterns_1, patterns_2, drums_808, drums_909):
        self.stop_all_acid_preview()
        self.generated_patterns = dict(patterns_1 or {})
        self.generated_patterns_303_2 = dict(patterns_2 or {})
        self.generated_drum_patterns_808 = dict(drums_808 or {})
        self.generated_drum_patterns_909 = dict(drums_909 or {})
        self.generated_drum_machine = self.get_active_launch_drum_machine()
        self.acid_active_slots = {"303_1": "A1", "303_2": "A1", "808": "A1", "909": "A1"}
        if hasattr(self, "pattern_selector"):
            self.pattern_selector.set_slot("A1")
        self._update_pattern_slot_ui()
        self.on_pat_slot_changed()
        self.refresh_pattern_selector_fill_state()

    def load_pattern_bank_json(self):
        ensure_pattern_banks_dir()
        path = filedialog.askopenfilename(
            title="Load Pattern Bank (.json)",
            initialdir=PATTERN_BANKS_DIR,
            filetypes=[("Pattern Bank JSON", "*.json"), ("All Files", "*.*")],
        )
        if not path:
            return
        if self.has_any_acid_patterns() and not messagebox.askyesno(
            "Load Pattern Bank",
            "Load will replace ALL current editor patterns with this bank.\n\nContinue?",
        ):
            return
        try:
            patterns_1, patterns_2, drums_808, drums_909, meta = import_patterns_from_bank_json(path)
        except Exception as exc:
            messagebox.showerror("Load Failed", f"Could not read pattern bank:\n{path}\n\n{exc}")
            return
        if not any((patterns_1, patterns_2, drums_808, drums_909)):
            messagebox.showinfo("Load Pattern Bank", "No patterns were found in this bank file.")
            return
        self.apply_loaded_pattern_stores(patterns_1, patterns_2, drums_808, drums_909)
        bank_name = meta.get("name") or os.path.basename(path)
        messagebox.showinfo(
            "Load Pattern Bank",
            f"Loaded bank:\n{bank_name}\n\n"
            f"303 #1: {len(patterns_1)} slots\n"
            f"303 #2: {len(patterns_2)} slots\n"
            f"TR-808: {len(drums_808)} slots\n"
            f"TR-909: {len(drums_909)} slots",
        )

    def export_pattern_bank_json(self):
        if not self.has_any_acid_patterns():
            messagebox.showinfo("Generate First", "Please generate or load patterns first!")
            return
        ensure_pattern_banks_dir()
        default_name = "My_Pattern_Bank.json"
        out_p = filedialog.asksaveasfilename(
            title="Export Pattern Bank (.json)",
            defaultextension=".json",
            initialdir=PATTERN_BANKS_DIR,
            initialfile=default_name,
            filetypes=[("Pattern Bank JSON", "*.json"), ("All Files", "*.*")],
        )
        if not out_p:
            return
        bank_name = os.path.splitext(os.path.basename(out_p))[0]
        try:
            export_patterns_to_bank_json(
                out_p,
                self.generated_patterns,
                self.generated_patterns_303_2,
                self.generated_drum_patterns_808,
                self.generated_drum_patterns_909,
                name=bank_name,
                description="Exported from ReBirth ToolBox Inspire Me editor.",
                author="ReBirth ToolBox",
                tags=["custom"],
            )
            messagebox.showinfo("Export Pattern Bank", f"Pattern bank saved to:\n{out_p}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not write pattern bank:\n{exc}")

    def open_pattern_banks_folder(self):
        ensure_pattern_banks_dir()
        try:
            os.startfile(PATTERN_BANKS_DIR)
        except Exception as exc:
            messagebox.showerror("Pattern Banks Folder", f"Could not open folder:\n{exc}")

    def load_acid_from_rbs_path(self, path, *, confirm=True, switch_tab=True, show_success=True):
        if not path or not os.path.exists(path):
            messagebox.showwarning("Load Song", "Song file not found.")
            return False
        if confirm and self.has_any_acid_patterns() and not messagebox.askyesno(
            "Load Song",
            "Load will replace ALL current editor patterns with this song.\n\nContinue?",
        ):
            return False
        try:
            patterns_1, patterns_2, drums_808, drums_909 = import_patterns_from_rbs(path)
        except Exception as exc:
            messagebox.showerror("Load Failed", f"Could not read song:\n{path}\n\n{exc}")
            return False
        if not any((patterns_1, patterns_2, drums_808, drums_909)):
            messagebox.showinfo("Load Song", "No editable patterns were found in this song.")
            return False
        meta = self.get_rbs_metadata(path, include_patterns=False)
        legacy_note = ""
        if meta.get("format") == "legacy_midi":
            legacy_note = "\nLegacy v3.x song — TR-909 patterns are not stored in this format."
        self.apply_loaded_pattern_stores(patterns_1, patterns_2, drums_808, drums_909)
        if switch_tab and hasattr(self, "tab_acid"):
            self.notebook.select(self.tab_acid)
        if show_success:
            messagebox.showinfo(
                "Load Song",
                f"Loaded:\n{os.path.basename(path)}\n\n"
                f"303 #1: {len(patterns_1)} slots\n"
                f"303 #2: {len(patterns_2)} slots\n"
                f"TR-808: {len(drums_808)} slots\n"
                f"TR-909: {len(drums_909)} slots"
                f"{legacy_note}",
            )
        return True

    def load_acid_from_rbs(self):
        path = filedialog.askopenfilename(
            title="Load complete song (.RBS)",
            filetypes=[("ReBirth Song Files", "*.rbs"), ("All Files", "*.*")],
        )
        if not path:
            return
        self.load_acid_from_rbs_path(path, confirm=True, switch_tab=True, show_success=True)

    def open_selected_in_inspire_me(self):
        path = self.get_selected_library_path()
        if not path:
            messagebox.showinfo("Select Song", "Please select a song in the library first.")
            return
        self.load_acid_from_rbs_path(path, confirm=True, switch_tab=True, show_success=True)

    def import_acid_from_rbs(self):
        self.load_acid_from_rbs()

    def get_active_launch_drum_machine(self):
        ctx = self.get_acid_editor_context()
        if ctx in ("808", "909"):
            return ctx
        slot_code = self.get_pat_slot_code()
        if self.generated_drum_patterns_909.get(slot_code):
            return "909"
        if self.generated_drum_patterns_808.get(slot_code):
            return "808"
        return self.generated_drum_machine or "909"

    def get_mix_drum_matrix(self, slot_code=None):
        slot_code = slot_code or self.get_pat_slot_code()
        ctx = self.get_acid_editor_context()
        if ctx == "808":
            return self.generated_drum_patterns_808.get(slot_code)
        if ctx == "909":
            return self.generated_drum_patterns_909.get(slot_code)
        return self.generated_drum_patterns_909.get(slot_code) or self.generated_drum_patterns_808.get(slot_code)

    def build_acid_steps_for_slot(self, slot_code, params=None, variation_seed=0, unit_index=0):
        params = params or self.get_acid_generation_params()
        return generate_melodic_acid_steps(
            slot_code,
            params["scale_intervals"],
            params["density"],
            params["accent_p"],
            params["slide_p"],
            octave_spread=params["octave_spread"],
            variation_seed=variation_seed,
            unit_index=unit_index,
        )

    def get_active_303_patterns(self):
        if self.get_acid_editor_context() == "303_2":
            return self.generated_patterns_303_2
        return self.generated_patterns

    def populate_acid_slots(self, target_slots, replace_all=False, replace_bank_only=False, variation_seed=None, randomize_303=True, randomize_drums=True):
        params = self.get_acid_generation_params()
        if variation_seed is None:
            variation_seed = random.randint(0, 2_000_000_000)

        if replace_all:
            if randomize_303:
                self.generated_patterns = {}
                self.generated_patterns_303_2 = {}
            if randomize_drums:
                self.generated_drum_patterns_909 = {}
                self.generated_drum_patterns_808 = {}
        elif replace_bank_only and target_slots:
            bank = target_slots[0][0]
            for slot in list(self.generated_patterns.keys()):
                if slot[0] == bank:
                    if randomize_303:
                        self.generated_patterns.pop(slot, None)
                        self.generated_patterns_303_2.pop(slot, None)
                    if randomize_drums:
                        self.generated_drum_patterns_909.pop(slot, None)
                        self.generated_drum_patterns_808.pop(slot, None)

        for slot_code in target_slots:
            slot_idx = pattern_slot_to_index(slot_code) or 0
            slot_seed = variation_seed + slot_idx * 131
            if randomize_303:
                self.generated_patterns[slot_code] = self.build_acid_steps_for_slot(
                    slot_code, params, variation_seed=slot_seed, unit_index=0
                )
                self.generated_patterns_303_2[slot_code] = self.build_acid_steps_for_slot(
                    slot_code,
                    params,
                    variation_seed=slot_seed + random.randint(200_000, 900_000),
                    unit_index=1,
                )
            if randomize_drums:
                self.generated_drum_patterns_909[slot_code] = generate_acid_drum_matrix(
                    slot_code, is_909=True, variation_seed=slot_seed + 900_007
                )
                self.generated_drum_patterns_808[slot_code] = generate_acid_drum_matrix(
                    slot_code, is_909=False, variation_seed=slot_seed + 900_017
                )
        self.generated_drum_machine = self.get_active_launch_drum_machine()
        self.refresh_pattern_selector_fill_state()

    def write_acid_launch_file(self, active_slot_code=None):
        active_slot_code = active_slot_code or self.get_pat_slot_code()
        if not self.has_any_acid_patterns():
            return False, None
        launch_path = get_acid_launch_path()
        source_rbs = find_template_rbs()
        if not source_rbs:
            return False, launch_path
        drum_machine = self.get_active_launch_drum_machine()
        ok = write_acid_patterns_to_rbs(
            launch_path,
            self.generated_patterns,
            source_rbs,
            song_title="Acid Gen Launch",
            drum_machine=drum_machine,
            active_slot_code=active_slot_code,
            clear_unwritten_slots=True,
            generated_patterns_303_2=self.generated_patterns_303_2,
            generated_drum_patterns_808=self.generated_drum_patterns_808,
            generated_drum_patterns_909=self.generated_drum_patterns_909,
        )
        return ok, launch_path

    def _acid_instrument_label(self, ctx=None):
        ctx = ctx or self.get_acid_editor_context()
        return {
            "303_1": "TB-303 #1",
            "303_2": "TB-303 #2",
            "808": "TR-808",
            "909": "TR-909",
        }.get(ctx, ctx)

    def _get_acid_store_for_context(self, ctx=None):
        ctx = ctx or self.get_acid_editor_context()
        if ctx == "303_2":
            return self.generated_patterns_303_2
        if ctx == "808":
            return self.generated_drum_patterns_808
        if ctx == "909":
            return self.generated_drum_patterns_909
        return self.generated_patterns

    def _clear_acid_slots_in_store(self, store, slot_codes):
        for slot_code in slot_codes:
            store.pop(slot_code, None)
        self.on_pat_slot_changed()
        self.refresh_pattern_selector_fill_state()
        if self.acid_loop_enabled:
            self.schedule_acid_loop_restart()

    def clear_acid_current_bank(self):
        ctx = self.get_acid_editor_context()
        store = self._get_acid_store_for_context(ctx)
        label = self._acid_instrument_label(ctx)
        bank = "A"
        if hasattr(self, "pattern_selector"):
            bank = self.pattern_selector.get_slot()[0].upper()
        slot_codes = [f"{bank}{num}" for num in range(1, 9)]
        if not messagebox.askyesno(
            "Clear Bank",
            f"Clear bank {bank} ({bank}1–{bank}8) for {label} only?\n\nOther instruments are left unchanged.",
        ):
            return
        self._clear_acid_slots_in_store(store, slot_codes)

    def clear_acid_all_patterns(self):
        ctx = self.get_acid_editor_context()
        store = self._get_acid_store_for_context(ctx)
        label = self._acid_instrument_label(ctx)
        if not store:
            messagebox.showinfo("Nothing to Clear", f"{label} has no patterns yet.")
            return
        if not messagebox.askyesno(
            "Clear All Patterns",
            f"Clear ALL 32 pattern slots (A1–D8) for {label} only?\n\nOther instruments are left unchanged.",
        ):
            return
        slot_codes = [f"{bank}{num}" for bank in "ABCD" for num in range(1, 9)]
        self._clear_acid_slots_in_store(store, slot_codes)

    def clear_acid_all_instruments(self):
        if not self.has_any_acid_patterns():
            messagebox.showinfo("Nothing to Clear", "There are no patterns in the editor yet.")
            return
        if not messagebox.askyesno(
            "Clear All Banks from All Instruments",
            "Clear EVERY pattern slot (A1–D8) for TB-303 #1, TB-303 #2, TR-808, and TR-909?",
        ):
            return
        self.generated_patterns = {}
        self.generated_patterns_303_2 = {}
        self.generated_drum_patterns_808 = {}
        self.generated_drum_patterns_909 = {}
        self.on_pat_slot_changed()
        self.refresh_pattern_selector_fill_state()
        if self.acid_loop_enabled:
            self.schedule_acid_loop_restart()

    def generate_acid_pattern(self):
        scope_idx = self.combo_gen_scope.current()
        populate_kwargs = {"randomize_303": True, "randomize_drums": True}

        if scope_idx == 0:
            target_slots = [self.get_pat_slot_code()]
            self.populate_acid_slots(target_slots, **populate_kwargs)
        elif scope_idx == 1:
            target_slots = [f"A{i}" for i in range(1, 9)]
            self.populate_acid_slots(target_slots, replace_bank_only=True, **populate_kwargs)
        elif scope_idx == 2:
            target_slots = [f"B{i}" for i in range(1, 9)]
            self.populate_acid_slots(target_slots, replace_bank_only=True, **populate_kwargs)
        elif scope_idx == 3:
            target_slots = [f"C{i}" for i in range(1, 9)]
            self.populate_acid_slots(target_slots, replace_bank_only=True, **populate_kwargs)
        elif scope_idx == 4:
            target_slots = [f"D{i}" for i in range(1, 9)]
            self.populate_acid_slots(target_slots, replace_bank_only=True, **populate_kwargs)
        else:
            target_slots = [f"{b}{n}" for b in ["A", "B", "C", "D"] for n in range(1, 9)]
            self.populate_acid_slots(target_slots, replace_all=True, **populate_kwargs)

        self.on_pat_slot_changed()
        if self.acid_loop_enabled:
            self.schedule_acid_loop_restart()

    def randomize_303_slot_for_unit(self, unit="303_1"):
        slot_code = self.get_pat_slot_code()
        params = self.get_acid_generation_params()
        unit_index = 0 if unit == "303_1" else 1
        store = self.generated_patterns if unit_index == 0 else self.generated_patterns_303_2
        seed = random.randint(0, 2_000_000_000)
        store[slot_code] = self.build_acid_steps_for_slot(slot_code, params, variation_seed=seed, unit_index=unit_index)
        self.refresh_303_editor_view(slot_code)
        self.schedule_acid_loop_restart()

    def randomize_current_303_slot(self):
        unit = "303_2" if self.get_acid_editor_context() == "303_2" else "303_1"
        self.randomize_303_slot_for_unit(unit)

    def randomize_drum_slot_for_machine(self, machine="909"):
        slot_code = self.get_pat_slot_code()
        is_909 = machine != "808"
        matrix = generate_acid_drum_matrix(
            slot_code,
            is_909=is_909,
            variation_seed=random.randint(0, 2_000_000_000),
        )
        self.get_drum_patterns_store(machine)[slot_code] = matrix
        if self.get_acid_editor_context() == machine and hasattr(self, "acid_drum_grid"):
            self.acid_drum_grid.load_matrix(matrix)
        self.schedule_acid_loop_restart()

    def randomize_current_drum_slot(self):
        ctx = self.get_acid_editor_context()
        machine = ctx if ctx in ("808", "909") else self.get_active_launch_drum_machine()
        self.randomize_drum_slot_for_machine(machine)

    def copy_acid_pattern(self):
        from_slot = self.copy_from_selector.get_slot()
        to_slot = self.get_pat_slot_code()
        if not from_slot or not to_slot:
            return
        if from_slot == to_slot:
            messagebox.showinfo("Copy Pattern", "Choose different source and destination slots.")
            return
        copied = []
        if self.var_copy_303_1.get() and from_slot in self.generated_patterns:
            self.generated_patterns[to_slot] = clone_303_steps(self.generated_patterns[from_slot])
            copied.append("303 #1")
        if self.var_copy_303_2.get() and from_slot in self.generated_patterns_303_2:
            self.generated_patterns_303_2[to_slot] = clone_303_steps(self.generated_patterns_303_2[from_slot])
            copied.append("303 #2")
        if self.var_copy_drums.get():
            copied_drums = []
            src909 = self.generated_drum_patterns_909.get(from_slot)
            src808 = self.generated_drum_patterns_808.get(from_slot)
            if src909:
                self.generated_drum_patterns_909[to_slot] = clone_drum_matrix(src909, is_909=True)
                copied_drums.append("TR-909")
            if src808:
                self.generated_drum_patterns_808[to_slot] = clone_drum_matrix(src808, is_909=False)
                copied_drums.append("TR-808")
            if copied_drums:
                copied.extend(copied_drums)
        if not copied:
            messagebox.showinfo("Copy Pattern", f"No data to copy from slot {from_slot}.")
            return
        if self.get_pat_slot_code() == to_slot:
            self.on_pat_slot_changed()
        messagebox.showinfo("Copy Pattern", f"Copied {', '.join(copied)} from {from_slot} → {to_slot}.")

    def refresh_303_editor_view(self, slot_code=None):
        slot_code = slot_code or self.get_pat_slot_code()
        steps_1 = self.generated_patterns.get(slot_code, [])
        steps_2 = self.generated_patterns_303_2.get(slot_code, [])
        ctx = self.get_acid_editor_context()
        if ctx == "303_2":
            active, other = steps_2, steps_1
        else:
            active, other = steps_1, steps_2
        ghost = other if getattr(self, "var_303_ghost", None) and self.var_303_ghost.get() else None
        if hasattr(self, "acid_piano_roll"):
            self.acid_piano_roll.load_steps(active, ghost_steps=ghost)
        if hasattr(self, "acid_303_diff"):
            self.acid_303_diff.pack_forget()

    def on_acid_piano_roll_changed(self, steps):
        slot_code = self.get_pat_slot_code()
        self.get_active_303_patterns()[slot_code] = normalize_303_steps(steps)
        steps_1 = self.generated_patterns.get(slot_code, [])
        steps_2 = self.generated_patterns_303_2.get(slot_code, [])
        if hasattr(self, "acid_piano_roll") and getattr(self, "var_303_ghost", None) and self.var_303_ghost.get():
            ctx = self.get_acid_editor_context()
            other = steps_2 if ctx == "303_1" else steps_1
            self.acid_piano_roll.ghost_steps = normalize_303_steps(other)
            self.acid_piano_roll.redraw()
        self.refresh_pattern_selector_fill_state()
        self.schedule_acid_loop_restart()

    def on_acid_drum_grid_changed(self, matrix):
        slot_code = self.get_pat_slot_code()
        self.get_drum_patterns_store()[slot_code] = matrix
        self.refresh_pattern_selector_fill_state()
        self.schedule_acid_loop_restart()

    def on_pat_slot_changed(self, event=None):
        ctx = self.get_acid_editor_context()
        if hasattr(self, "pattern_selector"):
            self.acid_active_slots[ctx] = self.pattern_selector.get_slot()
        slot_code = self.get_pat_slot_code(ctx)
        if ctx in ("303_1", "303_2"):
            self.refresh_303_editor_view(slot_code)
        elif ctx in ("808", "909") and hasattr(self, "acid_drum_grid"):
            drum_matrix = self.get_drum_patterns_store(ctx).get(slot_code)
            self.acid_drum_grid.load_matrix(drum_matrix)
        else:
            self.refresh_303_editor_view(slot_code)
        self._update_pattern_slot_ui()
        self.refresh_pattern_selector_fill_state()
        if self.acid_loop_enabled:
            self.schedule_acid_loop_restart()

    def refresh_pattern_selector_fill_state(self):
        ctx = self.get_acid_editor_context()
        if ctx == "303_2":
            store = self.generated_patterns_303_2
            kind = "303"
        elif ctx == "808":
            store = self.generated_drum_patterns_808
            kind = "drums"
        elif ctx == "909":
            store = self.generated_drum_patterns_909
            kind = "drums"
        else:
            store = self.generated_patterns
            kind = "303"
        filled = collect_filled_pattern_slots_for_store(store, kind)
        if hasattr(self, "pattern_selector"):
            self.pattern_selector.set_filled_state(filled)

    def refresh_pattern_bank_combo(self):
        if not hasattr(self, "combo_pattern_banks"):
            return
        ensure_pattern_banks_dir()
        labels = []
        self._pattern_bank_paths = {}
        for path in list_pattern_bank_files():
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                name = payload.get("name") or os.path.splitext(os.path.basename(path))[0]
            except Exception:
                name = os.path.splitext(os.path.basename(path))[0]
            label = f"{name}  ({os.path.relpath(path, PATTERN_BANKS_DIR)})"
            labels.append(label)
            self._pattern_bank_paths[label] = path
        self.combo_pattern_banks["values"] = labels
        if labels:
            self.combo_pattern_banks.current(0)
        else:
            self.combo_pattern_banks.set("")

    def on_pattern_bank_selected(self, _event=None):
        if not hasattr(self, "combo_pattern_banks"):
            return
        label = self.combo_pattern_banks.get()
        path = (getattr(self, "_pattern_bank_paths", {}) or {}).get(label)
        if not path:
            return
        if self.has_any_acid_patterns() and not messagebox.askyesno(
            "Load Pattern Bank",
            f"Load bank:\n{label}\n\nThis replaces ALL current editor patterns.\n\nContinue?",
        ):
            return
        try:
            patterns_1, patterns_2, drums_808, drums_909, meta = import_patterns_from_bank_json(path)
        except Exception as exc:
            messagebox.showerror("Load Failed", f"Could not read pattern bank:\n{path}\n\n{exc}")
            return
        if not any((patterns_1, patterns_2, drums_808, drums_909)):
            messagebox.showinfo("Load Pattern Bank", "No patterns were found in this bank file.")
            return
        self.apply_loaded_pattern_stores(patterns_1, patterns_2, drums_808, drums_909)
        bank_name = meta.get("name") or os.path.basename(path)
        messagebox.showinfo(
            "Load Pattern Bank",
            f"Loaded bank:\n{bank_name}",
        )

    def on_acid_editor_tab_changed(self, _event=None):
        ctx = self.get_acid_editor_context()
        if ctx in ("303_1", "303_2"):
            self.acid_drum_grid.pack_forget()
            self.acid_piano_roll.pack(fill=tk.BOTH, expand=True)
        elif ctx in ("808", "909"):
            self.acid_piano_roll.pack_forget()
            self.acid_303_diff.pack_forget()
            self.acid_drum_grid.pack(fill=tk.BOTH, expand=True)
        self.on_pat_slot_changed()
        if self.acid_loop_enabled:
            self._acid_preview_mode = self.get_acid_preview_mode_from_editor()
            self.schedule_acid_loop_restart()
        self.update_acid_loop_buttons()

    def get_acid_preview_mode_from_editor(self):
        ctx = self.get_acid_editor_context()
        if ctx in ("303_1", "303_2", "808", "909"):
            return ctx
        return "full"

    def get_acid_preview_wav(self, mode="full"):
        slot_code = self.get_pat_slot_code()
        steps_1 = self.generated_patterns.get(slot_code, [])
        steps_2 = self.generated_patterns_303_2.get(slot_code, [])
        silent = [{"active": False}] * 16
        bpm = self.get_acid_preview_bpm()
        if mode == "303_1":
            return synthesize_303_pattern_audio(steps_1 or silent, bpm=bpm)
        if mode == "303_2":
            return synthesize_303_pattern_audio(steps_2 or silent, bpm=bpm)
        if mode == "808":
            drum_matrix = self.generated_drum_patterns_808.get(slot_code)
            if not drum_matrix:
                return None
            return synthesize_acid_preview_audio(silent, drum_matrix=drum_matrix, bpm=bpm)
        if mode == "909":
            drum_matrix = self.generated_drum_patterns_909.get(slot_code)
            if not drum_matrix:
                return None
            return synthesize_acid_preview_audio(silent, drum_matrix=drum_matrix, bpm=bpm)
        drum_matrix = self.get_mix_drum_matrix(slot_code)
        mute = self.get_acid_mute_flags(for_full=True)
        gains = self.get_acid_mix_gains()
        return synthesize_acid_mix_preview(
            steps_1,
            steps_2,
            drum_matrix=drum_matrix,
            bpm=bpm,
            mute_303_1=mute["mute_303_1"],
            mute_303_2=mute["mute_303_2"],
            mute_drums=mute["mute_drums"],
            gain_303_1=gains["gain_303_1"],
            gain_303_2=gains["gain_303_2"],
            gain_drums=gains["gain_drums"],
        )

    def _wav_duration_seconds(self, wav_path):
        try:
            with wave.open(wav_path, "rb") as wf:
                rate = wf.getframerate() or 44100
                return max(0.1, wf.getnframes() / float(rate))
        except Exception:
            return 2.0

    def stop_all_acid_preview(self):
        self.acid_loop_enabled = False
        self.stop_playhead_animation()
        if self._acid_preview_restart_id:
            try:
                self.root.after_cancel(self._acid_preview_restart_id)
            except Exception:
                pass
            self._acid_preview_restart_id = None
        self._acid_preview_stop.set()
        stop_wav_playback()
        self.update_acid_loop_buttons()

    def stop_acid_preview(self):
        self._acid_preview_stop.set()
        stop_wav_playback()
        if not self.acid_loop_enabled:
            self.stop_playhead_animation()

    def start_acid_loop_preview(self):
        self.stop_acid_preview()
        if not self.acid_loop_enabled:
            return
        wav_path = self.get_acid_preview_wav(self._acid_preview_mode)
        if not wav_path:
            return

        self._acid_preview_stop = threading.Event()
        stop_event = self._acid_preview_stop
        self.start_playhead_animation()

        def worker():
            try:
                if HAS_WINSOUND:
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                    while not stop_event.is_set() and self.acid_loop_enabled:
                        time.sleep(0.05)
                else:
                    while not stop_event.is_set() and self.acid_loop_enabled:
                        play_wav_sync(wav_path)
            finally:
                stop_wav_playback()

        self._acid_preview_thread = threading.Thread(target=worker, daemon=True)
        self._acid_preview_thread.start()

    def play_acid_303_preview(self, unit="303_1"):
        self.stop_acid_preview()
        slot_code = self.get_pat_slot_code()
        store = self.generated_patterns if unit == "303_1" else self.generated_patterns_303_2
        steps = store.get(slot_code, [])
        if not steps:
            messagebox.showinfo("Generate First", "Please generate or edit 303 steps first!")
            return
        bpm = self.get_acid_preview_bpm()
        wav_path = synthesize_303_pattern_audio(steps, bpm=bpm)
        if not wav_path or not play_audio_file(wav_path):
            messagebox.showerror("Playback Error", "Could not play 303 preview.")
            return
        self.start_playhead_animation()
        self._schedule_playhead_stop(self._get_acid_pattern_duration())

    def play_acid_drums_preview(self, machine=None):
        self.stop_acid_preview()
        machine = machine or self.get_acid_drum_machine()
        slot_code = self.get_pat_slot_code()
        drum_matrix = self.get_drum_patterns_store(machine).get(slot_code)
        if not drum_matrix:
            messagebox.showinfo("Generate First", "Please generate or edit drum steps first!")
            return
        bpm = self.get_acid_preview_bpm()
        wav_path = synthesize_acid_preview_audio([{"active": False}] * 16, drum_matrix=drum_matrix, bpm=bpm)
        if not wav_path or not play_audio_file(wav_path):
            messagebox.showerror("Playback Error", "Could not play drum preview.")
            return
        self.start_playhead_animation()
        self._schedule_playhead_stop(self._get_acid_pattern_duration())

    def play_acid_full_preview(self):
        self.stop_acid_preview()
        slot_code = self.get_pat_slot_code()
        steps_1 = self.generated_patterns.get(slot_code, [])
        steps_2 = self.generated_patterns_303_2.get(slot_code, [])
        drum_matrix = self.get_mix_drum_matrix(slot_code)
        if not steps_1 and not steps_2 and not drum_matrix:
            messagebox.showinfo("Generate First", "Please generate Acid patterns first!")
            return
        bpm = self.get_acid_preview_bpm()
        mute = self.get_acid_mute_flags(for_full=True)
        gains = self.get_acid_mix_gains()
        wav_path = synthesize_acid_mix_preview(
            steps_1,
            steps_2,
            drum_matrix=drum_matrix,
            bpm=bpm,
            mute_303_1=mute["mute_303_1"],
            mute_303_2=mute["mute_303_2"],
            mute_drums=mute["mute_drums"],
            gain_303_1=gains["gain_303_1"],
            gain_303_2=gains["gain_303_2"],
            gain_drums=gains["gain_drums"],
        )
        if not wav_path:
            messagebox.showerror("Playback Error", "Could not synthesize preview audio.")
            return
        if not play_audio_file(wav_path):
            messagebox.showerror("Playback Error", f"Could not play preview:\n{wav_path}")
            return
        self.start_playhead_animation()
        self._schedule_playhead_stop(self._get_acid_pattern_duration())

    def play_acid_synth_audition(self):
        self.stop_acid_preview()
        slot_code = self.get_pat_slot_code()
        steps = self.get_active_303_patterns().get(slot_code, [])
        if not steps:
            messagebox.showinfo("Generate First", "Please generate Acid patterns first!")
            return

        bpm = self.get_acid_preview_bpm()
        wav_path = synthesize_303_pattern_audio(steps, bpm=bpm)
        if not wav_path:
            messagebox.showerror("Playback Error", "Could not synthesize preview audio.")
            return
        if not play_audio_file(wav_path):
            messagebox.showerror("Playback Error", f"Could not play preview:\n{wav_path}")
            return
        self.start_playhead_animation()
        self._schedule_playhead_stop(self._get_acid_pattern_duration())

    def audition_303_step(self, step):
        if not step or not step.get("active"):
            return
        if self.acid_loop_enabled:
            return
        bpm = self.get_acid_preview_bpm()
        wav_path = synthesize_303_step_audition_wav(step, bpm=bpm)
        if wav_path:
            play_audition_wav(wav_path)

    def audition_drum_hit(self, inst_label, accent=False):
        if self.acid_loop_enabled:
            return
        bpm = self.get_acid_preview_bpm()
        is_909 = self.get_acid_editor_context() == "909"
        wav_path = synthesize_drum_hit_audition_wav(inst_label, accent=accent, is_909=is_909, bpm=bpm)
        if wav_path:
            play_audition_wav(wav_path)

    def schedule_acid_loop_restart(self):
        if not self.acid_loop_enabled:
            return
        if self._acid_preview_restart_id:
            self.root.after_cancel(self._acid_preview_restart_id)
        self._acid_preview_restart_id = self.root.after(180, self._restart_acid_loop_preview)

    def _restart_acid_loop_preview(self):
        self._acid_preview_restart_id = None
        if not self.acid_loop_enabled:
            return
        self.start_acid_loop_preview()

    def update_acid_loop_buttons(self):
        active = "#00A86B"
        idle = "#242736"
        fg_active = "#FFFFFF"
        fg_idle = "#A0A5C0"
        mode = self._acid_preview_mode if self.acid_loop_enabled else None
        loop_buttons = (
            ("btn_loop_303_1", "303_1"),
            ("btn_loop_303_2", "303_2"),
            ("btn_loop_808", "808"),
            ("btn_loop_909", "909"),
            ("btn_loop_mix", "full"),
        )
        for attr, loop_mode in loop_buttons:
            if hasattr(self, attr):
                btn = getattr(self, attr)
                on = mode == loop_mode
                btn.config(bg=active if on else idle, fg=fg_active if on else fg_idle)

    def toggle_acid_loop_for_mode(self, mode):
        if self.acid_loop_enabled and self._acid_preview_mode == mode:
            self.acid_loop_enabled = False
            self.stop_acid_preview()
            self.stop_playhead_animation()
        else:
            self.acid_loop_enabled = True
            self._acid_preview_mode = mode
            self.start_acid_loop_preview()
        self.update_acid_loop_buttons()

    def bind_acid_shortcuts(self, widget):
        widget.bind("<Control-z>", self.acid_shortcut_undo)
        widget.bind("<Control-r>", self.acid_shortcut_randomize)
        widget.bind("<space>", self.acid_shortcut_space)

    def acid_shortcut_undo(self, event=None):
        if self._acid_editor_is_drums():
            self.undo_acid_drum_editor()
        else:
            self.undo_acid_303_editor()
        return "break"

    def acid_shortcut_randomize(self, event=None):
        if self._acid_editor_is_drums():
            self.randomize_current_drum_slot()
        else:
            self.randomize_current_303_slot()
        return "break"

    def acid_shortcut_space(self, event=None):
        self.toggle_acid_loop_for_mode(self.get_acid_preview_mode_from_editor())
        return "break"

    def _acid_editor_is_drums(self):
        return self.get_acid_editor_context() in ("808", "909")

    def undo_acid_303_editor(self):
        if hasattr(self, "acid_piano_roll"):
            self.acid_piano_roll.undo()

    def undo_acid_drum_editor(self):
        if hasattr(self, "acid_drum_grid"):
            self.acid_drum_grid.undo()

    def save_acid_to_rbs(self):
        if not self.has_any_acid_patterns():
            messagebox.showinfo("Generate First", "Please generate Acid patterns first!")
            return
        out_p = filedialog.asksaveasfilename(title="Save Song (.rbs)", defaultextension=".rbs", initialfile="Acid_Bank_Generated.rbs", filetypes=[("ReBirth Song Files", "*.rbs")])
        if out_p:
            source_rbs = self.get_selected_song_path() or find_template_rbs()
            if not source_rbs:
                messagebox.showerror("No Template", "Default Songs folder is missing.\n\nExpected:\n  Default Songs\\Silent Default Song.rbs\n  Default Songs\\ReBirth 1.0 Default Song.rbs")
                return
            song_title = os.path.splitext(os.path.basename(out_p))[0]
            drum_machine = self.get_active_launch_drum_machine()
            if write_acid_patterns_to_rbs(
                out_p,
                self.generated_patterns,
                source_rbs,
                song_title=song_title,
                drum_machine=drum_machine,
                active_slot_code=self.get_pat_slot_code(),
                generated_patterns_303_2=self.generated_patterns_303_2,
                generated_drum_patterns_808=self.generated_drum_patterns_808,
                generated_drum_patterns_909=self.generated_drum_patterns_909,
            ):
                messagebox.showinfo(
                    "Saved",
                    f"Pattern bank saved to new song:\n{out_p}\n\n"
                    f"({len(self.generated_patterns)} TB-303 #1 slots, "
                    f"{len(self.generated_patterns_303_2)} TB-303 #2 slots, "
                    f"{len(self.generated_drum_patterns_808)} TR-808 + "
                    f"{len(self.generated_drum_patterns_909)} TR-909 drum slots)",
                )
                self.scan_files_async()
            else:
                messagebox.showerror("Save Failed", "Could not write patterns into the .rbs file. Check that the template song is a valid ReBirth 2.0 song.")

    def export_generated_to_midi(self):
        if not self.has_any_acid_patterns():
            messagebox.showinfo("Generate First", "Please generate Acid patterns first!")
            return
        out_p = filedialog.asksaveasfilename(title="Export Pattern Bank to .MID", defaultextension=".mid", initialfile="Acid_Bank.mid", filetypes=[("MIDI Files", "*.mid")])
        if out_p:
            slot_code = self.get_pat_slot_code()
            drum_machine = self.get_active_launch_drum_machine()
            drum_store = self.get_drum_patterns_store(drum_machine)
            deconstructed = generated_patterns_to_deconstructed(
                self.generated_patterns,
                generated_drum_patterns=drum_store,
                drum_machine=drum_machine,
                slot_code=slot_code,
            )
            deconstructed["303_2"] = [
                {"name": slot, "steps": steps}
                for slot, steps in sorted(
                    (self.generated_patterns_303_2 or {}).items(),
                    key=lambda item: pattern_slot_sort_key(item[0]),
                )
                if not slot_code or slot == slot_code
            ]
            if export_rbs_to_midi(None, out_p, deconstructed=deconstructed, bpm=125.0):
                messagebox.showinfo("Exported", f"Pattern bank exported to MIDI:\n{out_p}")
            else:
                messagebox.showerror("Export Failed", "Could not export generated patterns to MIDI.")

    def launch_generated_acid_in_rebirth(self):
        if not is_rebirth_exe_ready():
            messagebox.showwarning(
                "Rebirth.exe Missing",
                "Install ReBirth first using the Get ReBirth tab (RB-338 2.0.1 Installer).",
            )
            return
        if not self.has_any_acid_patterns():
            messagebox.showinfo("Generate First", "Please generate Acid patterns first!")
            return

        os.makedirs(DEFAULT_SONGS_DIR, exist_ok=True)
        slot_code = self.get_pat_slot_code()
        ok, launch_path = self.write_acid_launch_file(active_slot_code=slot_code)
        if not ok:
            messagebox.showerror("Launch Failed", "Could not build launch song from generated patterns.")
            return

        self.launch_rebirth(selected_song_path=launch_path)

    def find_installed_mod_path(self, mod_name):
        key = (mod_name or "Standard ReBirth").strip().lower()
        if "standard" in key:
            return None
        for entry in self.installed_mods:
            display = entry[0]
            path = entry[1]
            rebirth_name = entry[3] if len(entry) >= 4 else resolve_mod_rebirth_name(path, display)
            if display.strip().lower() == key:
                return path
            if rebirth_name and rebirth_name.strip().lower() == key:
                return path
            if mod_names_match(mod_name, rebirth_name) or mod_names_match(mod_name, display):
                return path
        return None

    def get_selected_mod_info(self):
        selected = self.selected_mod_name or "Standard ReBirth"
        for entry in self.installed_mods:
            if entry[0] == selected:
                display, path = entry[0], entry[1]
                desc = entry[2] if len(entry) >= 3 else ""
                rebirth_name = entry[3] if len(entry) >= 4 else resolve_mod_rebirth_name(path, display)
                return {
                    "name": display,
                    "path": path,
                    "desc": desc,
                    "rebirth_name": rebirth_name,
                }
        return {"name": selected, "path": None, "desc": "", "rebirth_name": selected}

    def get_screenshot_for_song_path(self, song_path):
        meta = self.get_rbs_metadata(song_path, include_patterns=False)
        mod_name = meta.get("mod_name") or "Standard ReBirth"
        mod_path = self.find_installed_mod_path(mod_name)
        return find_mod_screenshot_path(mod_path, mod_name)

    def get_mod_songs(self, mod_name):
        key = (mod_name or "Standard ReBirth").strip().lower()
        matches = list(self.mod_songs_index.get(key, []))
        if not matches:
            for idx_key, songs in self.mod_songs_index.items():
                if key in idx_key or idx_key in key:
                    matches.extend(songs)
            seen = set()
            unique_matches = []
            for filename, path in matches:
                if path.lower() in seen:
                    continue
                seen.add(path.lower())
                unique_matches.append((filename, path))
            matches = sorted(unique_matches, key=lambda item: item[0].lower())
        return matches

    def get_mod_favorites(self):
        favs = self.config.get("mod_favorites") or []
        if not isinstance(favs, list):
            favs = []
        return [str(name) for name in favs if str(name).strip()]

    def get_mod_recent(self):
        recent = self.config.get("mod_recent") or []
        if not isinstance(recent, list):
            recent = []
        return [str(name) for name in recent if str(name).strip()][:MOD_RECENT_MAX]

    def is_mod_favorite(self, mod_name):
        key = normalize_mod_name_key(mod_name)
        return key in {normalize_mod_name_key(name) for name in self.get_mod_favorites()}

    def touch_mod_recent(self, mod_name):
        name = (mod_name or "Standard ReBirth").strip() or "Standard ReBirth"
        recent = [n for n in self.get_mod_recent() if normalize_mod_name_key(n) != normalize_mod_name_key(name)]
        recent.insert(0, name)
        self.config["mod_recent"] = recent[:MOD_RECENT_MAX]
        save_config(self.config)

    def toggle_mod_favorite(self, mod_info):
        name = (mod_info.get("name") or "Standard ReBirth").strip() or "Standard ReBirth"
        favs = self.get_mod_favorites()
        key = normalize_mod_name_key(name)
        if any(normalize_mod_name_key(item) == key for item in favs):
            favs = [item for item in favs if normalize_mod_name_key(item) != key]
        else:
            favs.append(name)
        self.config["mod_favorites"] = favs
        save_config(self.config)
        self.refresh_mod_fav_quick_bar()
        self._mod_gallery_top_y = 0.0
        self._clear_mod_canvas_rows()
        self.sync_mod_list_canvas_now(reset_scroll=True)
        self._render_mod_gallery_viewport()

    def refresh_mod_fav_quick_bar(self):
        frame = getattr(self, "mod_fav_quick_frame", None)
        if not frame or not frame.winfo_exists():
            return
        for child in frame.winfo_children():
            child.destroy()
        favs = self.get_mod_favorites()[:10]
        if not favs:
            tk.Label(
                frame,
                text="(click ☆ on a mod to pin it here)",
                font=("Segoe UI", 8, "italic"),
                fg="#6C7293",
                bg="#1A1C27",
            ).pack(side=tk.LEFT)
            return
        catalog = getattr(self, "_mod_gallery_catalog", None) or []
        by_name = {normalize_mod_name_key(item["name"]): item for item in catalog}
        for fav_name in favs:
            mod_info = by_name.get(normalize_mod_name_key(fav_name))
            if not mod_info:
                mod_info = {"name": fav_name, "path": self.find_installed_mod_path(fav_name)}
            short = fav_name if len(fav_name) <= 18 else fav_name[:16] + "…"
            tk.Button(
                frame,
                text=f"★ {short}",
                font=("Segoe UI", 8, "bold"),
                fg="#00FF66",
                bg="#242736",
                bd=0,
                cursor="hand2",
                command=lambda m=mod_info: self.select_mod_from_quick_bar(m),
            ).pack(side=tk.LEFT, padx=(0, 4), ipady=1)

    def select_mod_from_quick_bar(self, mod_info):
        self.mod_filter_mode = "all"
        if hasattr(self, "combo_mod_filter"):
            self.combo_mod_filter.current(0)
        self.select_mod(mod_info)
        self._mod_gallery_top_y = 0.0
        self._clear_mod_canvas_rows()
        self.sync_mod_list_canvas_now(reset_scroll=True)
        self._render_mod_gallery_viewport()

    def on_mod_filter_changed(self, _event=None):
        idx = self.combo_mod_filter.current() if hasattr(self, "combo_mod_filter") else 0
        modes = ("all", "favorites", "recent")
        self.mod_filter_mode = modes[idx] if 0 <= idx < len(modes) else "all"
        self._mod_gallery_top_y = 0.0
        self._clear_mod_canvas_rows()
        self.sync_mod_list_canvas_now(reset_scroll=True)
        self._render_mod_gallery_viewport()

    def get_mod_gallery_display_catalog(self):
        catalog = getattr(self, "_mod_gallery_catalog", None) or []
        if not catalog:
            return []
        filter_mode = getattr(self, "mod_filter_mode", "all")
        if filter_mode == "favorites":
            fav_keys = {normalize_mod_name_key(name) for name in self.get_mod_favorites()}
            return [item for item in catalog if normalize_mod_name_key(item["name"]) in fav_keys]
        if filter_mode == "recent":
            by_name = {normalize_mod_name_key(item["name"]): item for item in catalog}
            recent = []
            for name in self.get_mod_recent():
                item = by_name.get(normalize_mod_name_key(name))
                if item and item not in recent:
                    recent.append(item)
            return recent
        fav_keys = [normalize_mod_name_key(name) for name in self.get_mod_favorites()]
        recent_keys = [normalize_mod_name_key(name) for name in self.get_mod_recent()]
        pinned = []
        seen = set()
        for key in fav_keys + recent_keys:
            if key in seen:
                continue
            item = next((entry for entry in catalog if normalize_mod_name_key(entry["name"]) == key), None)
            if item:
                pinned.append(item)
                seen.add(key)
        rest = sorted(
            [entry for entry in catalog if normalize_mod_name_key(entry["name"]) not in seen],
            key=lambda entry: entry["name"].lower(),
        )
        return pinned + rest

    def get_mod_catalog(self):
        screenshot_index = get_cached_mod_screenshot_index()
        standard_shot = find_mod_screenshot_path_fast(mod_name="Standard ReBirth", screenshot_index=screenshot_index)
        catalog = [{
            "name": "Standard ReBirth",
            "path": None,
            "filename": "",
            "desc": "Standard ReBirth dual-303, 808, and 909 original synthesizer rack.",
            "screenshot": standard_shot,
            "preview_source": "default",
        }]
        for entry in self.installed_mods:
            if len(entry) >= 4:
                mod_name, mod_path, mod_desc, rebirth_name = entry[0], entry[1], entry[2], entry[3]
            else:
                mod_name, mod_path, mod_desc = entry[0], entry[1], entry[2] if len(entry) >= 3 else ""
                rebirth_name = entry[3] if len(entry) >= 4 else mod_name
            screenshot = find_mod_screenshot_path_fast(mod_path, mod_name, screenshot_index)
            preview_source = "screenshot"
            if screenshot and mod_path and "\\.previews\\" in screenshot.replace("/", "\\").lower():
                preview_source = "embedded"
            desc = mod_desc or f"Custom mod skin: {mod_name}"
            if rebirth_name and rebirth_name.strip().lower() != mod_name.strip().lower():
                desc = f"{desc}\nReBirth mod name: {rebirth_name}"
            catalog.append({
                "name": mod_name,
                "path": mod_path,
                "filename": os.path.basename(mod_path) if mod_path else "",
                "desc": desc,
                "rebirth_name": rebirth_name,
                "screenshot": screenshot,
                "preview_source": preview_source,
            })
        return catalog

    def refresh_mod_gallery(self, select_name=None):
        build_id = getattr(self, "_mod_gallery_build_token", 0) + 1
        self._mod_gallery_build_token = build_id
        self._mod_gallery_building = True
        self._mod_gallery_reload_pending = False
        self.set_mod_gallery_loading(True, "Please wait — loading mod database...")
        self._clear_mod_canvas_rows()
        self._mod_gallery_top_y = 0.0
        self._mod_gallery_select_name = select_name
        self.root.after(0, lambda bid=build_id: self._prepare_mod_gallery_catalog(bid))

    def _prepare_mod_gallery_catalog(self, build_id):
        if build_id != getattr(self, "_mod_gallery_build_token", None):
            return
        try:
            catalog = self.get_mod_catalog()
            self._mod_gallery_catalog = catalog
        except Exception:
            catalog = []
            self._mod_gallery_catalog = []
        if not catalog:
            canvas = self.mod_list_canvas
            empty = tk.Label(
                canvas,
                text="No mods found. Import a .rmb / .rbm file into the Mods folder.",
                font=("Segoe UI", 9, "italic"),
                fg="#FF9500",
                bg="#12131A",
            )
            win_id = canvas.create_window(12, 20, window=empty, anchor="nw")
            self._mod_canvas_rows[0] = {"win_id": win_id, "row": empty, "name": ""}
            canvas.configure(scrollregion=(0, 0, 400, 80))
            self._finish_mod_gallery_build(build_id)
            return
        total = len(catalog)
        self.set_mod_gallery_loading(True, f"Please wait — loading {total} mod(s)...")
        self.root.after(0, lambda bid=build_id: self._complete_mod_gallery_virtual(bid))

    def _complete_mod_gallery_virtual(self, build_id):
        if build_id != getattr(self, "_mod_gallery_build_token", None):
            return
        self.set_mod_gallery_loading(False)
        try:
            self.sync_mod_list_canvas_now(reset_scroll=True)
            self._mod_gallery_row_error = None
            self._render_mod_gallery_viewport()
        except Exception as exc:
            canvas = getattr(self, "mod_list_canvas", None)
            if canvas and canvas.winfo_exists():
                self._show_mod_gallery_fallback(
                    canvas,
                    max(canvas.winfo_width(), 400),
                    f"Mod gallery render error:\n{exc}",
                )
        try:
            catalog = getattr(self, "_mod_gallery_catalog", []) or []
            preferred = self._mod_gallery_select_name or self.selected_mod_name
            selected = next((m for m in catalog if m["name"] == preferred), catalog[0] if catalog else None)
            if selected:
                self.select_mod(selected)
        except Exception:
            pass
        try:
            self.refresh_mod_fav_quick_bar()
        except Exception:
            pass
        if build_id == getattr(self, "_mod_gallery_build_token", None):
            self._finish_mod_gallery_build(build_id)

    def _build_mod_gallery_row(self, mod, parent=None):
        host = parent or getattr(self, "mod_rows_host", None) or self.mod_list_canvas
        row = tk.Frame(
            host,
            bg="#12131A",
            height=MOD_GALLERY_ROW_HEIGHT,
            highlightbackground="#282B3C",
            highlightthickness=2,
        )
        row.grid_propagate(False)
        row.pack_propagate(False)
        row.grid_columnconfigure(0, minsize=MOD_GALLERY_LEFT_WIDTH + 16)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, minsize=210)

        left = tk.Frame(row, bg="#12131A")
        left.grid(row=0, column=0, sticky="nw", padx=(8, 10), pady=8)

        fav_row = tk.Frame(left, bg="#12131A")
        fav_row.pack(anchor="ne", fill=tk.X)
        is_fav = self.is_mod_favorite(mod.get("name"))
        fav_btn = tk.Button(
            fav_row,
            text="★" if is_fav else "☆",
            font=("Segoe UI", 10, "bold"),
            fg="#FF9500" if is_fav else "#6C7293",
            bg="#12131A",
            activebackground="#12131A",
            bd=0,
            cursor="hand2",
            command=lambda m=mod: self.toggle_mod_favorite(m),
        )
        fav_btn.pack(side=tk.RIGHT)

        thumb_box = tk.Frame(
            left,
            bg="#12131A",
            width=MOD_GALLERY_IMG_WIDTH,
            height=MOD_GALLERY_IMG_HEIGHT,
            highlightbackground="#282B3C",
            highlightthickness=1,
        )
        thumb_box.pack(anchor="n")
        thumb_box.pack_propagate(False)

        screenshot = mod.get("screenshot")
        if not screenshot:
            screenshot = resolve_mod_preview_path(mod.get("path"), mod.get("name"))
            if screenshot:
                mod["screenshot"] = screenshot
        tile_photo = (
            make_tk_image_from_png(screenshot, MOD_GALLERY_IMG_WIDTH, MOD_GALLERY_IMG_HEIGHT)
            if screenshot
            else None
        )
        if tile_photo:
            img_lbl = tk.Label(thumb_box, image=tile_photo, bg="#12131A", cursor="hand2")
            img_lbl.place(relx=0.5, rely=0.5, anchor="center")
            self.mod_tile_photos.append(tile_photo)
            img_lbl.bind("<Button-1>", lambda _e, m=mod: self.select_mod(m))
            img_lbl.bind("<Double-Button-1>", lambda _e, m=mod: self.launch_mod_empty_project(m))
            thumb_box.bind("<Button-1>", lambda _e, m=mod: self.select_mod(m))
            thumb_box.bind("<Double-Button-1>", lambda _e, m=mod: self.launch_mod_empty_project(m))
            thumb_box.config(cursor="hand2")
        else:
            ph = tk.Label(
                thumb_box,
                text="No screenshot",
                font=("Segoe UI", 8, "italic"),
                fg="#6C7293",
                bg="#12131A",
                cursor="hand2",
            )
            ph.place(relx=0.5, rely=0.5, anchor="center")
            ph.bind("<Button-1>", lambda _e, m=mod: self.select_mod(m))
            ph.bind("<Double-Button-1>", lambda _e, m=mod: self.launch_mod_empty_project(m))

        mid = tk.Frame(row, bg="#12131A")
        mid.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=8)
        display_name = sanitize_tk_text(mod.get("name") or "Unknown mod", 140)
        filename = (mod.get("filename") or "").strip()
        if not filename and mod.get("path"):
            filename = os.path.basename(mod["path"])
        name_lbl = tk.Label(
            mid,
            text=display_name,
            font=("Segoe UI", 12, "bold"),
            fg="#FFFFFF",
            bg="#12131A",
            anchor="w",
            justify=tk.LEFT,
            wraplength=420,
            cursor="hand2",
        )
        name_lbl.pack(fill=tk.X)
        name_lbl.bind("<Button-1>", lambda _e, m=mod: self.select_mod(m))
        name_lbl.bind("<Double-Button-1>", lambda _e, m=mod: self.launch_mod_empty_project(m))
        if filename:
            file_lbl = tk.Label(
                mid,
                text=sanitize_tk_text(filename, 160),
                font=("Consolas", 9),
                fg="#00E5FF",
                bg="#12131A",
                anchor="w",
                justify=tk.LEFT,
                wraplength=420,
                cursor="hand2",
            )
            file_lbl.pack(fill=tk.X, pady=(2, 0))
            file_lbl.bind("<Button-1>", lambda _e, m=mod: self.select_mod(m))
            file_lbl.bind("<Double-Button-1>", lambda _e, m=mod: self.launch_mod_empty_project(m))
        rebirth_id = (mod.get("rebirth_name") or "").strip()
        if rebirth_id and rebirth_id.lower() != display_name.lower() and rebirth_id.lower() != (filename or "").lower():
            tk.Label(
                mid,
                text=f"ReBirth id: {sanitize_tk_text(rebirth_id, 120)}",
                font=("Segoe UI", 8),
                fg="#6C7293",
                bg="#12131A",
                anchor="w",
            ).pack(fill=tk.X, pady=(2, 0))
        tk.Label(mid, text="DESCRIPTION", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A", anchor="w").pack(fill=tk.X, pady=(10, 0))
        tk.Label(
            mid,
            text=sanitize_tk_text(mod.get("desc") or mod.get("name") or ""),
            font=("Segoe UI", 8, "italic"),
            fg="#A0A5C0",
            bg="#12131A",
            anchor="nw",
            justify=tk.LEFT,
            wraplength=420,
        ).pack(fill=tk.X, pady=(4, 0))

        right = tk.Frame(row, bg="#12131A", width=210)
        right.grid(row=0, column=2, sticky="ne", padx=(0, 8), pady=8)
        tk.Label(right, text="SONGS USING THIS MOD", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A", anchor="w").pack(fill=tk.X)
        matches = self.get_mod_songs(mod["name"])
        if not matches:
            song_text = "(No songs in library use this mod)"
        else:
            preview = ", ".join(filename for filename, _path in matches[:3])
            if len(matches) > 3:
                preview += f"  (+{len(matches) - 3} more)"
            song_text = f"{len(matches)} song(s): {sanitize_tk_text(preview, 180)}"
        tk.Label(
            right,
            text=song_text,
            font=("Segoe UI", 8),
            fg="#00E5FF",
            bg="#12131A",
            anchor="nw",
            justify=tk.LEFT,
            wraplength=200,
        ).pack(fill=tk.X, pady=(4, 0))

        row.bind("<Button-1>", lambda _e, m=mod: self.select_mod(m))
        self.mod_tiles[mod["name"]] = row
        self.mod_row_widgets[mod["name"]] = {"row": row, "song_paths": [path for _fn, path in matches]}
        if hasattr(self, "_mod_scroll_bind"):
            self.bind_mod_row_scroll_targets(row)
        return row

    def select_mod(self, mod_info):
        self.selected_mod_name = mod_info["name"]
        self.selected_mod_path = mod_info.get("path")
        self.touch_mod_recent(mod_info["name"])
        for name, row in self.mod_tiles.items():
            if name == mod_info["name"]:
                row.config(highlightbackground="#00FF66", highlightthickness=3)
            else:
                row.config(highlightbackground="#282B3C", highlightthickness=2)
        self.refresh_start_launch_info()

    def launch_mod_empty_project(self, mod_info):
        self.select_mod(mod_info)
        self.launch_blank_project_with_mod()

    def launch_mod_song_from_list(self, listbox, song_paths, mod_info):
        if not song_paths:
            return
        sel = listbox.curselection()
        if not sel or sel[0] >= len(song_paths):
            return
        self.select_mod(mod_info)
        song_path = song_paths[sel[0]]
        mod_path = mod_info.get("path")
        if mod_path:
            mod_path = ensure_mod_in_rebirth_mods_folder(mod_path)
            song_path = prepare_rebirth_launch_song(song_path, mod_path)
        self.launch_rebirth(selected_song_path=song_path)

    def open_downloads_folder(self):
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        os.startfile(DOWNLOADS_DIR)

    def get_tutorial_completed_steps(self):
        completed = self.config.get("tutorial_completed_steps") or []
        if not isinstance(completed, list):
            completed = []
        return [str(item) for item in completed]

    def save_tutorial_progress(self, step_id=None):
        if step_id:
            self.config["tutorial_last_step_id"] = step_id
        save_config(self.config)

    def populate_tutorial_list(self):
        if not hasattr(self, "tutorial_listbox"):
            return
        self.tutorial_listbox.delete(0, tk.END)
        completed = set(self.get_tutorial_completed_steps())
        for step in REBIRTH_TUTORIAL_STEPS:
            mark = "✔ " if step["id"] in completed else "○ "
            self.tutorial_listbox.insert(tk.END, mark + step["title"])
        if not hasattr(self, "tutorial_step_index"):
            last_id = self.config.get("tutorial_last_step_id") or "welcome"
            self.tutorial_step_index = next(
                (i for i, s in enumerate(REBIRTH_TUTORIAL_STEPS) if s["id"] == last_id),
                0,
            )
        self.refresh_tutorial_step()

    def refresh_tutorial_step(self):
        if not hasattr(self, "lbl_tutorial_title"):
            return
        idx = min(max(0, getattr(self, "tutorial_step_index", 0)), len(REBIRTH_TUTORIAL_STEPS) - 1)
        self.tutorial_step_index = idx
        step = REBIRTH_TUTORIAL_STEPS[idx]
        completed = set(self.get_tutorial_completed_steps())
        done_count = sum(1 for s in REBIRTH_TUTORIAL_STEPS if s["id"] in completed)
        self.lbl_tutorial_progress.config(
            text=f"Progress: {done_count}/{len(REBIRTH_TUTORIAL_STEPS)} completed"
        )
        self.lbl_tutorial_title.config(text=step["title"])
        self.lbl_tutorial_summary.config(text=step.get("summary") or "")
        self.txt_tutorial_body.configure(state=tk.NORMAL)
        self.txt_tutorial_body.delete("1.0", tk.END)
        self.txt_tutorial_body.insert(tk.END, step.get("body") or "")
        self.txt_tutorial_body.configure(state=tk.DISABLED)
        action_label = step.get("action_label") or "Try in ToolBox"
        self.btn_tutorial_action.config(text=action_label)
        self.btn_tutorial_prev.config(state=tk.NORMAL if idx > 0 else tk.DISABLED)
        self.btn_tutorial_next.config(state=tk.NORMAL if idx < len(REBIRTH_TUTORIAL_STEPS) - 1 else tk.DISABLED)
        if step["id"] in completed:
            self.btn_tutorial_done.config(text="✔ Completed", fg="#00FF66")
        else:
            self.btn_tutorial_done.config(text="✔ Mark Done", fg="#FFFFFF")
        if hasattr(self, "tutorial_listbox"):
            self.tutorial_listbox.selection_clear(0, tk.END)
            self.tutorial_listbox.selection_set(idx)
            self.tutorial_listbox.see(idx)
        self.save_tutorial_progress(step["id"])

    def on_tutorial_step_selected(self, _event=None):
        sel = self.tutorial_listbox.curselection()
        if not sel:
            return
        self.tutorial_step_index = sel[0]
        self.refresh_tutorial_step()

    def tutorial_prev_step(self):
        if self.tutorial_step_index > 0:
            self.tutorial_step_index -= 1
            self.refresh_tutorial_step()

    def tutorial_next_step(self):
        if self.tutorial_step_index < len(REBIRTH_TUTORIAL_STEPS) - 1:
            self.tutorial_step_index += 1
            self.refresh_tutorial_step()

    def tutorial_mark_done(self):
        step = REBIRTH_TUTORIAL_STEPS[self.tutorial_step_index]
        completed = self.get_tutorial_completed_steps()
        if step["id"] not in completed:
            completed.append(step["id"])
        self.config["tutorial_completed_steps"] = completed
        if self.tutorial_step_index < len(REBIRTH_TUTORIAL_STEPS) - 1:
            self.tutorial_step_index += 1
            self.config["tutorial_last_step_id"] = REBIRTH_TUTORIAL_STEPS[self.tutorial_step_index]["id"]
        save_config(self.config)
        self.populate_tutorial_list()

    def tutorial_run_action(self):
        step = REBIRTH_TUTORIAL_STEPS[self.tutorial_step_index]
        action = step.get("action") or "launch"
        tab_map = {
            "launch": "Start",
            "inspire": "✨ Inspire Me",
            "library": "📚 Song Library Manager",
            "documents": "📄 Documents",
            "mods": MOD_TAB_LABEL,
            "downloads": "Get ReBirth",
        }
        target = tab_map.get(action, "Start")
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == target:
                self.notebook.select(tab_id)
                break
        if action == "downloads":
            self.refresh_get_rebirth_ui()

    def on_notebook_tab_changed(self, _event=None):
        try:
            tab_text = self.notebook.tab(self.notebook.select(), "text")
        except Exception:
            return
        if tab_text == "Get ReBirth":
            self.refresh_get_rebirth_ui()
            self.schedule_rebirth_status_poll()
        elif tab_text == "✨ Inspire Me":
            self.refresh_pattern_bank_combo()
            self.refresh_pattern_selector_fill_state()
        elif tab_text == "📄 Documents":
            if not self._documents_gallery_loaded:
                self.refresh_documents_gallery()
                self._documents_gallery_loaded = True
        elif tab_text == MOD_TAB_LABEL:
            self.ensure_mod_gallery()
            self.sync_mod_list_canvas()
            self.root.after(50, self._render_mod_gallery_viewport)
        elif tab_text == TUTORIAL_TAB_LABEL:
            self.refresh_tutorial_step()
        else:
            self.cancel_rebirth_status_poll()

    def schedule_rebirth_status_poll(self):
        self.cancel_rebirth_status_poll()

        def tick():
            try:
                tab_text = self.notebook.tab(self.notebook.select(), "text")
            except Exception:
                return
            if tab_text != "Get ReBirth":
                return

            _install_root, rebirth_exe = resolve_rebirth_install_root(self.config)
            if rebirth_exe or is_rebirth_exe_ready():
                self.refresh_get_rebirth_ui()
                if self.setup_wizard_only and not getattr(self, "_install_restart_prompted", False):
                    self._install_restart_prompted = True
                    self.root.after(400, self.prompt_restart_after_install)
                return

            self._rebirth_poll_id = self.root.after(3000, tick)

        self._rebirth_poll_id = self.root.after(3000, tick)

    def cancel_rebirth_status_poll(self):
        poll_id = getattr(self, "_rebirth_poll_id", None)
        if poll_id:
            try:
                self.root.after_cancel(poll_id)
            except Exception:
                pass
        self._rebirth_poll_id = None

    def set_wizard_message(self, text, color="#A0A5C0"):
        if hasattr(self, "lbl_wizard_message"):
            self.lbl_wizard_message.config(text=text, fg=color)

    def update_wizard_step_indicators(self, completed_steps):
        if not hasattr(self, "wizard_step_widgets"):
            return
        for index, widget in enumerate(self.wizard_step_widgets):
            if index < completed_steps:
                widget["dot"].config(text="✔", fg="#00FF66")
                widget["label"].config(fg="#00FF66")
            elif index == completed_steps:
                widget["dot"].config(text="●", fg=widget["accent"])
                widget["label"].config(fg=widget["accent"])
            else:
                widget["dot"].config(text="○", fg="#42475E")
                widget["label"].config(fg="#6C7293")
        for index, line in enumerate(getattr(self, "wizard_step_lines", [])):
            line.config(bg="#00FF66" if index < completed_steps else "#42475E")

    def refresh_get_rebirth_ui(self):
        if not hasattr(self, "lbl_step1_iso"):
            return

        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        status = scan_rebirth_download_status(self.config)
        iso_info = get_download_file_info(self.config, "iso")
        inst_info = get_download_file_info(self.config, "installer")

        if status["iso_ready"]:
            self.lbl_step1_iso.config(text=f"✔ ISO ready ({iso_info.get('filename', '')})", fg="#00FF66")
        else:
            self.lbl_step1_iso.config(text=f"✖ ISO missing ({iso_info.get('filename', '')})", fg="#FF9500")

        if status["installer_ready"]:
            self.lbl_step1_installer.config(text=f"✔ Installer ready ({inst_info.get('filename', '')})", fg="#00FF66")
        else:
            self.lbl_step1_installer.config(text=f"✖ Installer missing ({inst_info.get('filename', '')})", fg="#FF9500")

        protected_buttons = (
            self.btn_download_iso,
            self.btn_download_installer,
        )
        for widget in self.step1_btn_frame.winfo_children():
            if widget in protected_buttons:
                widget.pack_forget()

        if not status["iso_ready"] and (iso_info.get("url") or "").strip():
            self.btn_download_iso.pack(side=tk.LEFT, ipadx=10, ipady=4)
        if not status["installer_ready"] and (inst_info.get("url") or "").strip():
            self.btn_download_installer.pack(side=tk.LEFT, padx=(0, 6), ipadx=10, ipady=4)

        step1_done = status["iso_ready"] and status["installer_ready"]
        if step1_done:
            self.lbl_download_status.config(text="Step 1 complete", fg="#00FF66")
        elif status["iso_ready"] or status["installer_ready"]:
            self.lbl_download_status.config(text="Download remaining file(s) or use Verify", fg="#FF9500")
        else:
            rel_downloads = (self.config.get("directories") or {}).get("downloads", "Downloads")
            self.lbl_download_status.config(text=f"Save files to ./{rel_downloads} or configure URLs in Settings", fg="#6C7293")

        install_dir = get_configured_install_dir(self.config)
        install_root, rebirth_exe = resolve_rebirth_install_root(self.config)
        self.lbl_wizard_folder.config(text=install_dir, fg="#FFFFFF")

        if status["installer_ready"]:
            self.btn_run_installer.config(state=tk.NORMAL)
        else:
            self.btn_run_installer.config(state=tk.DISABLED)

        if status["iso_ready"] and (not self.iso_path or not os.path.exists(self.iso_path)):
            self.iso_path = status["iso_path"]
            self.update_iso_status()

        step2_done = bool(rebirth_exe) or is_rebirth_exe_ready()
        if step2_done:
            rebirth_label = rebirth_exe or EXE_PATH
            self.lbl_step2_status.config(
                text=f"✔ Step 2 complete\n{os.path.basename(rebirth_label)} found",
                fg="#00FF66",
            )
        else:
            self.lbl_step2_status.config(
                text=f"Unpacks installer EXE with 7-Zip into:\n{install_dir}\n(does not run setup)",
                fg="#A0A5C0",
            )

        step3_done = step2_done and not self.setup_wizard_only
        if step2_done:
            self.lbl_step3_status.config(text="Ready — restart ToolBox to unlock all tabs.", fg="#00E5FF")
            self.btn_deploy_launcher.config(state=tk.NORMAL, text="↻ Restart ToolBox")
        else:
            self.lbl_step3_status.config(text="Complete Step 2 first.", fg="#6C7293")
            self.btn_deploy_launcher.config(state=tk.DISABLED, text="↻ Restart ToolBox")

        completed_steps = int(step1_done) + int(step2_done) + int(step2_done)
        self.update_wizard_step_indicators(completed_steps)

        if step2_done and self.setup_wizard_only:
            self.set_wizard_message("ReBirth unpacked — restart ToolBox to unlock all tabs.", "#00FF66")
        elif step2_done:
            self.set_wizard_message("Setup complete — ReBirth is ready in this folder.", "#00FF66")
        elif step1_done:
            self.set_wizard_message("Step 1 complete — click Extract ReBirth here in Step 2.", "#00E5FF")
        else:
            self.set_wizard_message("Download the ISO and installer, then extract ReBirth here.", "#A0A5C0")

    def get_launch_resolution_index(self):
        return min(max(0, self.selected_res_index), len(RESOLUTIONS) - 1)

    def set_launch_resolution_index(self, idx, source="sync"):
        if getattr(self, "_resolution_sync_source", None):
            return
        idx = min(max(0, idx), len(RESOLUTIONS) - 1)
        self._resolution_sync_source = source
        self.selected_res_index = idx
        combo = getattr(self, "combo_res_settings", None)
        if combo is not None:
            combo.current(idx)
        self.config["launch_resolution_index"] = idx
        save_config(self.config)
        self._resolution_sync_source = None
        self.refresh_start_launch_info()

    def sync_resolution_from_settings(self, _event=None):
        self.set_launch_resolution_index(self.combo_res_settings.current(), "settings")

    def pick_rebirth_install_folder(self):
        initial = get_configured_install_dir(self.config) or REBIRTH_EXTRACT_DIR
        if not os.path.isdir(initial):
            initial = BASE_DIR
        path = filedialog.askdirectory(title="Select ReBirth Install Folder", initialdir=initial)
        if not path:
            return None
        path = os.path.abspath(path)
        self.config["rebirth_install_dir"] = path
        save_config(self.config)
        self.set_wizard_message(f"Install folder set: {path}", "#00E5FF")
        self.refresh_get_rebirth_ui()
        return path

    def ensure_rebirth_install_folder(self):
        install_dir = get_configured_install_dir(self.config)
        if install_dir:
            return install_dir
        return self.pick_rebirth_install_folder()

    def require_download_files_for_install(self):
        status = scan_rebirth_download_status(self.config)
        missing = []
        if not status["iso_ready"]:
            missing.append("ReBirth ISO")
        if not status["installer_ready"]:
            missing.append("ReBirth RB-338 2.0.1 Installer")
        if missing:
            self.verify_download_files()
            messagebox.showwarning(
                "Missing Download Files",
                "Required files are not in the Downloads folder yet:\n\n- "
                + "\n- ".join(missing)
                + "\n\nConfigure https URLs in Settings, download manually, or use Verify.",
            )
            return False
        return True

    def run_rebirth_installer(self):
        """Step 2: unpack installer EXE with 7-Zip into the ToolBox folder (never launch setup)."""
        self.extract_rebirth_portable()

    def prompt_restart_after_install(self):
        if not is_rebirth_exe_ready():
            return
        self.config["rebirth_install_dir"] = BASE_DIR
        save_config(self.config)
        self.refresh_get_rebirth_ui()
        if messagebox.askyesno(
            "ReBirth Installed",
            "Rebirth.exe was detected in the ToolBox folder.\n\nRestart ToolBox now to unlock all tabs?",
        ):
            self.restart_application()

    def restart_application(self):
        launcher_path = os.path.join(BASE_DIR, LAUNCHER_MAIN_FILE)
        try:
            if getattr(self, "var_shortcut_desktop", None) and getattr(self, "var_shortcut_start", None):
                if self.var_shortcut_desktop.get() or self.var_shortcut_start.get():
                    create_launcher_shortcuts(
                        launcher_path,
                        desktop=self.var_shortcut_desktop.get(),
                        start_menu=self.var_shortcut_start.get(),
                    )
        except Exception:
            pass
        target_path, arguments = get_launcher_shortcut_target(launcher_path)
        try:
            if arguments:
                subprocess.Popen(f'"{target_path}" {arguments}', cwd=BASE_DIR, shell=True)
            else:
                subprocess.Popen([target_path], cwd=BASE_DIR)
        except Exception as exc:
            messagebox.showerror("Restart Failed", f"Could not restart ToolBox:\n{exc}")
            return
        self.root.after(120, self.root.destroy)

    def extract_rebirth_portable(self):
        if not self.require_download_files_for_install():
            return
        status = scan_rebirth_download_status(self.config)
        if not status["installer_ready"]:
            self.set_wizard_message("Download the installer in Step 1 first.", "#FF9500")
            return

        if not find_seven_zip_executable():
            messagebox.showerror(
                "7-Zip Required",
                "Step 2 only unpacks the installer EXE — it never runs setup.\n\n"
                "Install 7-Zip (https://www.7-zip.org/) or copy 7z.exe into the ToolBox folder.",
            )
            self.set_wizard_message("7-Zip required to unpack the installer EXE.", "#FF9500")
            return

        # Always unpack into the ToolBox folder we are running from.
        install_dir = os.path.abspath(BASE_DIR)
        self.config["rebirth_install_dir"] = install_dir
        save_config(self.config)

        self.show_loading_overlay("Extracting ReBirth…", f"Unpacking installer into:\n{install_dir}")
        self.set_wizard_message(f"Unpacking installer into:\n{install_dir}", "#00E5FF")
        self.lbl_step2_status.config(
            text=f"Extracting into:\n{install_dir}\n\nPlease wait…",
            fg="#00E5FF",
        )
        installer_path = status["installer_path"]

        def worker():
            try:
                ok, rebirth_exe, mode = extract_rebirth_installer(installer_path, install_dir)
                if not ok:
                    self.root.after(0, lambda msg=mode: messagebox.showerror("Extract Failed", msg))
                    self.root.after(0, self.hide_loading_overlay)
                    self.root.after(0, self.refresh_get_rebirth_ui)
                    return

                def done():
                    self.hide_loading_overlay()
                    self.set_wizard_message(
                        f"Step 2 complete — ReBirth unpacked into:\n{install_dir}",
                        "#00FF66",
                    )
                    self.refresh_get_rebirth_ui()
                    if is_rebirth_exe_ready():
                        self.prompt_restart_after_install()

                self.root.after(0, done)
            except Exception as exc:
                error_text = str(exc)
                self.root.after(0, lambda msg=error_text: messagebox.showerror("Extract Failed", msg))
                self.root.after(0, self.hide_loading_overlay)
                self.root.after(0, self.refresh_get_rebirth_ui)

        threading.Thread(target=worker, daemon=True).start()

    def deploy_launcher_to_rebirth_folder(self):
        install_root, rebirth_exe = resolve_rebirth_install_root(self.config)
        if not rebirth_exe or not install_root:
            self.set_wizard_message("Step 2 required — Rebirth.exe not found in install folder.", "#FF9500")
            return

        try:
            deployed = deploy_launcher_to_directory(BASE_DIR, install_root)
            launcher_path = os.path.join(install_root, LAUNCHER_MAIN_FILE)
            desktop = self.var_shortcut_desktop.get()
            start_menu = self.var_shortcut_start.get()
            shortcut_note = ""
            if desktop or start_menu:
                created = create_launcher_shortcuts(launcher_path, desktop=desktop, start_menu=start_menu)
                if created:
                    shortcut_note = f" Shortcuts: {len(created)} created."
                else:
                    shortcut_note = " Shortcuts could not be created."

            items = ", ".join(deployed) if deployed else "nothing"
            self.set_wizard_message(
                f"Step 3 complete — copied {items}.{shortcut_note}",
                "#00FF66",
            )
            self.refresh_get_rebirth_ui()
        except Exception as exc:
            messagebox.showerror("Deploy Failed", str(exc))

    def start_rebirth_download(self, file_key):
        if self.download_in_progress:
            self.set_wizard_message("Please wait for the current download to finish.", "#FF9500")
            return
        info = get_download_file_info(self.config, file_key)
        if not info:
            return
        url = (info.get("url") or "").strip()
        if not url:
            rel_downloads = (self.config.get("directories") or {}).get("downloads", "Downloads")
            messagebox.showinfo(
                "Manual Download Required",
                f"No https URL configured for:\n{info.get('title', file_key)}\n\n"
                f"Place this file manually in:\n./{rel_downloads}/\n{info.get('filename', '')}",
            )
            self.set_wizard_message(f"Manual download required: {info.get('filename', file_key)}", "#FF9500")
            return

        dest_path = get_rebirth_download_path(file_key, self.config)
        if not dest_path:
            return
        if os.path.exists(dest_path):
            if not messagebox.askyesno("File Exists", f"{info['filename']} already exists.\n\nDownload again and overwrite?"):
                return

        self.download_in_progress = True
        self.download_progress["value"] = 0
        self.lbl_download_status.config(text=f"Starting: {info['filename']}", fg="#00E5FF")
        self.set_wizard_message(f"Downloading {info['filename']}…", "#00E5FF")

        def worker():
            def on_progress(done, total):
                def ui():
                    if total > 0:
                        pct = min(100, int(done * 100 / total))
                        self.download_progress["value"] = pct
                        self.lbl_download_status.config(
                            text=f"Downloading {info['filename']}... {pct}% ({format_bytes(done)} / {format_bytes(total)})",
                            fg="#00E5FF",
                        )
                    else:
                        self.lbl_download_status.config(
                            text=f"Downloading {info['filename']}... {format_bytes(done)}",
                            fg="#00E5FF",
                        )
                self.root.after(0, ui)

            try:
                download_timeout = 7200 if file_key == "iso" else 900
                download_file_with_progress(url, dest_path, on_progress, timeout=download_timeout)

                def done():
                    self.download_in_progress = False
                    self.download_progress["value"] = 100
                    self.lbl_download_status.config(text="Download complete", fg="#00FF66")
                    if file_key == "iso":
                        self.iso_path = dest_path
                        self.update_iso_status()
                    self.set_wizard_message(f"Saved: {info['filename']}", "#00FF66")
                    self.refresh_get_rebirth_ui()

                self.root.after(0, done)
            except Exception as exc:
                error_text = str(exc)

                def fail(message=error_text):
                    self.download_in_progress = False
                    self.download_progress["value"] = 0
                    self.lbl_download_status.config(text="Download failed", fg="#FF453A")
                    self.set_wizard_message(f"Download failed: {message}", "#FF453A")
                    messagebox.showerror("Download Failed", message)

                self.root.after(0, fail)

        threading.Thread(target=worker, daemon=True).start()

    def import_mod_screenshot_pack(self):
        archive_path = filedialog.askopenfilename(
            title="Import Mod Screenshot Pack (.zip)",
            filetypes=[("Zip Archives", "*.zip"), ("All Files", "*.*")],
        )
        if not archive_path:
            return
        screenshots_dir = os.path.join(MODS_DIR, "Screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        imported = 0
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                for member in archive.namelist():
                    if member.endswith("/"):
                        continue
                    ext = os.path.splitext(member)[1].lower()
                    if ext not in (".png", ".jpg", ".jpeg", ".bmp"):
                        continue
                    dest_name = os.path.basename(member)
                    if not dest_name:
                        continue
                    with archive.open(member) as src, open(os.path.join(screenshots_dir, dest_name), "wb") as dst:
                        dst.write(src.read())
                    imported += 1
        except Exception as exc:
            messagebox.showerror("Import Failed", f"Could not import screenshot pack:\n{exc}")
            return
        messagebox.showinfo(
            "Screenshot Pack Imported",
            f"Imported {imported} screenshot file(s) into:\n{screenshots_dir}",
        )
        invalidate_mod_screenshot_index_cache()
        self.mark_mod_gallery_dirty()
        try:
            if self.notebook.tab(self.notebook.select(), "text") == MOD_TAB_LABEL:
                self.ensure_mod_gallery()
        except Exception:
            pass

    def import_new_mod(self):
        file_p = filedialog.askopenfilename(title="Select ReBirth Mod File (.rmb / .rbm)", filetypes=[("ReBirth Mod Files", "*.rmb;*.rbm")])
        if not file_p:
            return
        os.makedirs(MODS_DIR, exist_ok=True)
        dest_p = os.path.join(MODS_DIR, os.path.basename(file_p))
        try:
            if os.path.normcase(os.path.abspath(file_p)) != os.path.normcase(os.path.abspath(dest_p)):
                shutil.copy2(file_p, dest_p)
            # Drop stale cache for this path so naming/launch identity is recomputed
            cache_key = os.path.normcase(os.path.abspath(dest_p))
            if hasattr(self, "_mod_info_cache"):
                self._mod_info_cache.pop(cache_key, None)
            mod_info = extract_rmb_mod_info(dest_p)
            imported_name = mod_info["name"] or preferred_mod_file_stem(dest_p)
            rebirth_name = mod_info.get("rebirth_name") or preferred_mod_file_stem(dest_p)
            messagebox.showinfo(
                "Mod Imported",
                f"Mod copied into the ToolBox Mods folder:\n{dest_p}\n\n"
                f"Display name: {imported_name}\n"
                f"ReBirth identity: {rebirth_name}",
            )
            self.selected_mod_name = imported_name
            self.selected_mod_path = dest_p
            self.mark_mod_gallery_dirty()
            # Immediate rescan so the new file appears without waiting for a full library pass
            try:
                mods = scan_installed_mods(self._mod_info_cache)
                self.installed_mods = mods
                self.mod_songs_index = self.build_mod_songs_index()
            except Exception:
                pass
            self.scan_files_async()
            try:
                if self.notebook.tab(self.notebook.select(), "text") == MOD_TAB_LABEL:
                    self.force_refresh_mod_gallery()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import mod: {e}")

    def open_deconstruction_window(self):
        path = self.get_selected_library_path()
        if not path:
            messagebox.showinfo("Select Song", "Please select a song in the library first.")
            return
        meta = self.get_rbs_metadata(path, include_patterns=True)
        title = meta.get("title") or os.path.splitext(os.path.basename(path))[0]
        SongDeconstructionWindow(self.root, path, title, meta=meta)

    def update_iso_status(self):
        if self.iso_path and os.path.exists(self.iso_path):
            self.lbl_iso_info.config(text=f"✔ ISO Ready: {os.path.basename(self.iso_path)}", fg="#00E5FF")
        else:
            self.lbl_iso_info.config(text="✖ No .iso file found!", fg="#FF453A")
        self.refresh_start_launch_info()

    def check_zombie_status(self):
        if is_process_running(EXE_NAME):
            self.btn_zombie.config(bg="#FF453A", fg="#FFFFFF", text="⚠ Zombie ReBirth Running! Click to Kill")
        else:
            self.btn_zombie.config(bg="#2D1A21", fg="#FF453A", text="⚡ Kill Zombie & Reset ISO")

    def handle_zombie_cleanup(self):
        kill_zombie_process()
        if self.iso_path:
            dismount_iso(self.iso_path)
        messagebox.showinfo("Zombie Cleanup", "Successfully reset ReBirth environment!")
        self.check_zombie_status()

    def browse_iso_manually(self):
        file_p = filedialog.askopenfilename(title="Select ReBirth ISO File", filetypes=[("ISO Images", "*.iso")])
        if file_p:
            self.iso_path = file_p
            self.update_iso_status()
            self.refresh_start_launch_info()

    def launch_blank_project_with_mod(self):
        mod_info = self.get_selected_mod_info()
        mod_path = mod_info.get("path")
        if mod_path:
            mod_path = ensure_mod_in_rebirth_mods_folder(mod_path)
        rebirth_name = resolve_mod_rebirth_name(mod_path, mod_info.get("name") or "Standard ReBirth")

        source_rbs = find_template_rbs(prefer_silent=True)
        if not source_rbs:
            messagebox.showerror("No Template", "Silent Default Song.rbs was not found in Default Songs.")
            return

        os.makedirs(DEFAULT_SONGS_DIR, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in rebirth_name).strip() or "Mod"
        template_path = os.path.join(DEFAULT_SONGS_DIR, f"_EmptyMod_{safe_name}.rbs")

        if generate_mod_rbs(rebirth_name, template_path, source_rbs):
            self.launch_rebirth(selected_song_path=template_path)
        else:
            messagebox.showerror("Launch Failed", "Could not prepare empty mod project.")

    def launch_rebirth_from_library(self):
        if not is_rebirth_exe_ready():
            messagebox.showwarning(
                "Rebirth.exe Missing",
                "Install ReBirth first using the Get ReBirth tab (RB-338 2.0.1 Installer).",
            )
            return
        sel = self.tree_songs.selection()
        if sel:
            item_tags = self.tree_songs.item(sel[0], "tags")
            if item_tags:
                self.launch_rebirth(selected_song_path=item_tags[0])
                return
        self.launch_rebirth()

    def on_library_song_double_click(self, event):
        if self.tree_songs.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.tree_songs.identify_row(event.y)
        if not row_id:
            return
        self.tree_songs.selection_set(row_id)
        self.tree_songs.focus(row_id)
        self.launch_rebirth_from_library()

    def pick_random_library_song(self):
        items = self.tree_songs.get_children()
        if not items:
            messagebox.showinfo("Random Song", "No songs match the current library view.")
            return
        choice = random.choice(items)
        self.tree_songs.selection_set(choice)
        self.tree_songs.focus(choice)
        self.tree_songs.see(choice)
        values = self.tree_songs.item(choice, "values")
        song_name = values[1] if len(values) > 1 else "song"
        self.lbl_scan_status.config(text=f"🎲 Random pick: {song_name}", fg="#FF9500")

    def launch_rebirth(self, selected_song_path=None):
        self.stop_all_acid_preview()

        if not is_admin():
            messagebox.showerror(
                "Admin Required",
                "Administrator rights are required to mount the ISO image.\n\n"
                "Please restart the ToolBox and approve the UAC prompt at startup."
            )
            return

        if not is_rebirth_exe_ready():
            messagebox.showwarning(
                "Rebirth.exe Missing",
                f"{EXE_NAME} was not found in the ToolBox folder.\n\n"
                "Open the Get ReBirth tab, download the RB-338 2.0.1 Installer, run Step 2 install, "
                "then deploy Rebirth.exe into this folder.",
            )
            return

        if not self.iso_path or not os.path.exists(self.iso_path):
            messagebox.showwarning("ISO Not Found", "Please provide a valid ISO image file.")
            return

        idx = self.get_launch_resolution_index()
        _, width, height = RESOLUTIONS[idx]
        if not selected_song_path:
            selected_song_path = self.get_selected_song_path()

        self.show_launch_overlay("Starting ReBirth...", "Preparing launch...")

        if selected_song_path and os.path.exists(selected_song_path):
            self.update_launch_overlay(detail="Checking song and mod requirements...")
            meta = self.get_rbs_metadata(selected_song_path, include_patterns=False)
            required_mod = (meta.get("mod_name") or "Standard ReBirth").strip()
            if required_mod and required_mod != "Standard ReBirth" and "standard" not in required_mod.lower():
                mod_path = self.find_installed_mod_path(required_mod)
                if not mod_path:
                    mod_path = self.find_installed_mod_path(self.selected_mod_name)
                if mod_path:
                    self.update_launch_overlay(detail=f"Preparing mod: {required_mod}")
                    mod_path = ensure_mod_in_rebirth_mods_folder(mod_path)
                    selected_song_path = prepare_rebirth_launch_song(selected_song_path, mod_path)

        self.update_launch_overlay(title="Starting ReBirth...", detail="Mounting ReBirth CD image...")
        drive_letter = mount_iso(self.iso_path)
        if not drive_letter:
            self.hide_loading_overlay()
            messagebox.showerror("ISO Error", "Failed to mount ISO disk!")
            return

        self.update_launch_overlay(detail="Configuring ReBirth environment...")
        stabilize_rebirth_environment(BASE_DIR, drive_letter, selected_song_path)
        force_retro_compatibility()
        dismiss_mounted_cd_windows(drive_letter)

        screen_changed = False
        use_super_rack = bool(self.config.get("rebirth_super_rack", False)) or bool(self.var_rebirth_super_rack.get())
        super_display = "fit_height"
        fill_height = False
        if use_super_rack:
            if hasattr(self, "var_super_rack_scale"):
                super_display = resolve_super_rack_display(self.var_super_rack_scale.get(), self.config)
            else:
                super_display = resolve_super_rack_display(config=self.config)
            fill_height = super_display == "fit_height"

        if use_super_rack:
            # 1) Clear the desk — minimize every other app before ReBirth starts.
            self.update_launch_overlay(
                title=f"{SUPER_RACK_LABEL}",
                detail="Minimizing other windows...",
            )
            try:
                exclude = []
                try:
                    exclude.append(int(self.root.winfo_id()))
                except Exception:
                    pass
                minimize_other_windows(exclude_hwnds=exclude)
            except Exception:
                pass
            try:
                self.update_launch_overlay(detail="Hiding taskbar...")
                hide_taskbar_for_super_rack()
            except Exception:
                pass
            time.sleep(0.25)

            if fill_height:
                self.update_launch_overlay(
                    detail="Fitting sharp display mode (top→bottom, side bezel)...",
                )
                ok, rw, rh = apply_super_rack_fit_resolution()
                screen_changed = bool(ok)
                self.update_launch_overlay(
                    detail=f"{SUPER_RACK_LABEL}: {rw}×{rh} (fit height, side bezel)",
                )
            else:
                self.update_launch_overlay(
                    detail=f"{SUPER_RACK_LABEL}: keeping desktop resolution...",
                )
        elif width and height:
            self.update_launch_overlay(detail=f"Setting screen resolution to {width}×{height}...")
            screen_changed = change_resolution(width, height)

        process_name = os.path.basename(EXE_PATH)
        try:
            self.update_launch_overlay(title="Launching ReBirth...", detail="Starting Rebirth.exe...")
            short_song_path = get_short_path_name(selected_song_path) if selected_song_path else None
            cmd = [EXE_PATH, short_song_path] if short_song_path else [EXE_PATH]
            proc = subprocess.Popen(cmd, cwd=BASE_DIR)
            if self.var_cpu_affinity.get():
                set_cpu_affinity_core_0(proc.pid)

            if use_super_rack:
                self.update_launch_overlay(
                    title=f"{SUPER_RACK_LABEL}",
                    detail="Centering rack + wallpaper — ToolBox will minimize...",
                )
                try:
                    self.start_super_rack_bezel()
                except Exception:
                    pass

                def super_worker():
                    dismiss_mounted_cd_windows(drive_letter)
                    super_rack_window_for_pid(
                        proc.pid,
                        timeout=45.0,
                        hold_seconds=14.0,
                        tick_callback=lambda: self.root.after(0, lambda: self.pulse_super_rack_bezel(proc.pid)),
                        fill_height=fill_height,
                    )

                threading.Thread(target=super_worker, daemon=True).start()
            elif self.config.get("rebirth_maximized", True):
                def maximize_worker():
                    dismiss_mounted_cd_windows(drive_letter)
                    maximize_window_for_pid(proc.pid, timeout=40.0)

                threading.Thread(target=maximize_worker, daemon=True).start()

            time.sleep(2)
            if use_super_rack:
                try:
                    self.hide_loading_overlay()
                except Exception:
                    pass
                try:
                    self.root.iconify()
                except Exception:
                    pass
                try:
                    self.root.update_idletasks()
                except Exception:
                    pass
            else:
                self.update_launch_overlay(
                    title="ReBirth is running",
                    detail="Close ReBirth when you are done — ToolBox stays open in the background.",
                )
            while is_process_running(process_name):
                if use_super_rack:
                    try:
                        apply_super_rack_for_pid(proc.pid, fill_height=fill_height)
                        self.pulse_super_rack_bezel(proc.pid)
                        try:
                            if self.root.state() != "iconic":
                                self.root.iconify()
                        except Exception:
                            pass
                        try:
                            br = getattr(self, "_super_rack_bezel_root", None)
                            if br:
                                br.update()
                        except Exception:
                            pass
                        self.root.update()
                    except Exception:
                        pass
                    time.sleep(0.6)
                else:
                    time.sleep(1)
        except Exception as e:
            self.hide_loading_overlay()
            messagebox.showerror("Launch Error", f"Error: {e}")
        finally:
            try:
                cleanup_super_rack_session(getattr(proc, "pid", None) if "proc" in locals() else None)
            except Exception:
                pass
            self.stop_super_rack_bezel()
            if screen_changed:
                restore_resolution()
            dismount_iso(self.iso_path)
            self.hide_loading_overlay()
            if hasattr(self, "lbl_scan_status"):
                self.lbl_scan_status.config(text="ReBirth closed — ToolBox ready.", fg="#00A86B")
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass

if __name__ == "__main__":
    ensure_admin_elevation()
    hide_console_window()
    root = tk.Tk()
    root.title("ReBirth ToolBox")
    root.geometry("920x900")
    root.minsize(920, 780)
    root.configure(bg="#12131A")
    set_window_icon(root)
    early_splash = tk.Frame(root, bg="#12131A")
    early_splash.place(relx=0, rely=0, relwidth=1, relheight=1)
    tk.Label(
        early_splash,
        text="Please wait...",
        font=("Segoe UI", 14, "bold"),
        fg="#00E5FF",
        bg="#12131A",
    ).pack(pady=(260, 8))
    tk.Label(
        early_splash,
        text="Starting ReBirth ToolBox...",
        font=("Segoe UI", 9),
        fg="#A0A5C0",
        bg="#12131A",
    ).pack()
    root.update()
    app = ModernRebirthStudioToolBox(root)
    try:
        early_splash.destroy()
    except Exception:
        pass
    root.mainloop()