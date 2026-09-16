import os
import sys
import glob
import time
import winreg
import ctypes
import math
import struct
import random
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- CONFIGURATION & CONSTANTS ---
EXE_NAME = "Rebirth.exe"
EXE_PATH = os.path.abspath(EXE_NAME)
DEFAULT_TARGET_SONG = "Silent Default Song.rbs"

# Base64 encoded 32x32 studio synth icon (zero-dependency)
APP_ICON_BASE64 = (
    "R0lGODlhIAAgAPMAAMwAAAD/AP///0BAQIyMAMzMM8zM/93d3b29vdzc3LW1tbW1/8z//2Zm"
    "ZgAAAAAAAAAAACH5BAEAAAEALAAAAAAgACAAAASOMMiJqp134807/2AohkRZmlzpnmu6vnAs"
    "z3Rt33qu73zv/8CgcEgsGo/IpHLJbDqf0Kh0Sq1ar9is9osNj8lkbrmMXq/YrHaLXWq/4LB4"
    "SCyaz+ijup0+u+PxeUp7e3+AfYGGh26Ki4yNj4+RkJKSkpOWl5iZmpucnZ6foKGio6Slpqeo"
    "qaqrrK2ur7CxgREAOw=="
)

def set_window_icon(window):
    """ Sets application icon from embedded base64 data """
    try:
        icon_img = tk.PhotoImage(data=APP_ICON_BASE64)
        window.iconphoto(True, icon_img)
        window._app_icon_ref = icon_img
    except Exception:
        pass

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

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_wchar * 32),
        ("dwSupport", ctypes.c_ulong)
    ]

RESOLUTIONS = [
    ("Current Resolution (Desktop / No Change)", None, None),
    ("640 x 480 (4:3 Retro VGA)", 640, 480),
    ("800 x 600 (4:3 Retro SVGA)", 800, 600),
    ("1024 x 768 (4:3 XGA)", 1024, 768),
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

def change_resolution(width, height):
    """ Temporarily changes screen resolution via Windows User32 API """
    user32 = ctypes.windll.user32
    devmode = DEVMODE()
    devmode.dmSize = ctypes.sizeof(DEVMODE)
    devmode.dmFields = 0x00080000 | 0x00100000
    devmode.dmPelsWidth = width
    devmode.dmPelsHeight = height
    return user32.ChangeDisplaySettingsA(ctypes.byref(devmode), 4) == 0

def restore_resolution():
    """ Restores original system display resolution """
    ctypes.windll.user32.ChangeDisplaySettingsA(None, 0)

def is_admin():
    """ Checks for Administrator privileges under Windows """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def get_base_dir():
    """ Returns absolute path to launcher root directory """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_short_path_name(long_name):
    """ Converts long Windows path to 8.3 short path format for retro 32-bit app compatibility """
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

def parse_rbs_metadata(rbs_path):
    """ Parses IFF format .rbs files (Propellerhead RBS v4.2 spec) to extract song metadata """
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
        "duration_str": "N/A"
    }
    if not rbs_path or not os.path.exists(rbs_path):
        return info

    try:
        with open(rbs_path, "rb") as f:
            content = f.read()

        # 1. Parse "GLOB" Chunk
        glob_idx = content.find(b"GLOB")
        if glob_idx != -1 and len(content) >= glob_idx + 8 + 512:
            glob_data = content[glob_idx + 8 : glob_idx + 8 + 512]
            mode_byte = glob_data[0]
            info["mode"] = "Song Mode" if mode_byte == 1 else "Pattern Mode"

            tempo_raw = struct.unpack(">I", glob_data[2:6])[0]
            if tempo_raw > 0:
                info["bpm"] = round(tempo_raw / 1000.0, 1)

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

        # 2. Parse "USRI" Chunk
        usri_idx = content.find(b"USRI")
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

            web_raw = usri_data[242:343].split(b"\x00")[0]
            info["web"] = web_raw.decode("latin-1", errors="ignore").strip()

        # 3. Synchronized Pattern Deconstruction Count
        deconstructed = deconstruct_rbs_song(rbs_path)
        c_303_1 = len(deconstructed.get("303_1", []))
        c_303_2 = len(deconstructed.get("303_2", []))
        c_808 = len(deconstructed.get("808", []))
        c_909 = len(deconstructed.get("909", []))

        total_active = c_303_1 + c_303_2 + c_808 + c_909
        info["active_patterns"] = total_active
        info["pattern_breakdown"] = f"303 #1: {c_303_1} | 303 #2: {c_303_2} | 808: {c_808} | 909: {c_909}"

        # 4. Parse TRAK Chunks
        max_trak_ticks = 0
        trak_pos = 0
        while True:
            t_idx = content.find(b"TRAK", trak_pos)
            if t_idx == -1:
                break
            trak_pos = t_idx + 4
            if len(content) >= t_idx + 12:
                try:
                    num_events = struct.unpack(">I", content[t_idx+4:t_idx+8])[0]
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

        trak_bars = math.ceil(max_trak_ticks / 96) if max_trak_ticks > 0 else 0
        total_bars = max(info["loop_end"], trak_bars)
        info["total_bars"] = total_bars

        # 5. Calculate Duration
        if info["bpm"] and info["bpm"] > 0 and total_bars > 0:
            total_sec = total_bars * (240.0 / info["bpm"])
            mins = int(total_sec // 60)
            secs = int(total_sec % 60)
            info["duration_str"] = f"~{mins:02d}:{secs:02d} ({total_bars} Bars)"
        elif info["mode"] == "Pattern Mode":
            info["duration_str"] = "Looping Pattern"
        else:
            info["duration_str"] = "N/A"

    except Exception:
        pass

    return info

def deconstruct_rbs_song(rbs_path):
    """ Deconstructs 303 notes and 808/909 drum matrices from RBS v1/v2 files """
    notes_map = ["C ", "C#", "D ", "D#", "E ", "F ", "F#", "G ", "G#", "A ", "A#", "B ", "C5"]
    result = {
        "303_1": [],
        "303_2": [],
        "808": [],
        "909": []
    }
    if not rbs_path or not os.path.exists(rbs_path):
        return result

    try:
        with open(rbs_path, "rb") as f:
            content = f.read()

        # Parse 303 Synthesizers
        tb303_indices = []
        pos = 0
        while True:
            idx = content.find(b"303 ", pos)
            if idx == -1:
                break
            tb303_indices.append(idx)
            pos = idx + 4

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
                        active = bool(flags & 0x10)
                        
                        if active:
                            has_notes = True
                            step_data = {
                                "note": note_str.strip(),
                                "up": up,
                                "accent": accent,
                                "slide": slide,
                                "active": True
                            }
                        else:
                            step_data = {
                                "note": "--",
                                "up": "-",
                                "accent": "-",
                                "slide": "-",
                                "active": False
                            }
                        steps_data.append(step_data)

                    if has_notes:
                        result[key].append({"name": pat_name, "steps": steps_data})

        # Parse TR-808 Drum Machine
        idx_808 = content.find(b"808 ")
        if idx_808 != -1 and len(content) >= idx_808 + 8 + 6238:
            chunk_data = content[idx_808 + 8 : idx_808 + 8 + 6238]
            inst_labels = ["AC", "BD", "SD", "LT", "MT", "HT", "RS", "CP", "CB", "CY", "OH", "CH"]
            for p in range(32):
                bank_char = chr(65 + (p // 8))
                pat_num = (p % 8) + 1
                pat_name = f"{bank_char}{pat_num}"
                pat_bytes = chunk_data[30 + p*194 : 30 + (p+1)*194]
                
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

        # Parse TR-909 Drum Machine
        idx_909 = content.find(b"909 ")
        if idx_909 != -1 and len(content) >= idx_909 + 8 + 6239:
            chunk_data = content[idx_909 + 8 : idx_909 + 8 + 6239]
            inst_labels_909 = ["AC", "BD", "SD", "LT", "MT", "HT", "RS", "CP", "CH", "OH", "CC", "RC"]
            for p in range(32):
                bank_char = chr(65 + (p // 8))
                pat_num = (p % 8) + 1
                pat_name = f"{bank_char}{pat_num}"
                pat_bytes = chunk_data[30 + p*194 : 30 + (p+1)*194]
                
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

class SongDeconstructionWindow(tk.Toplevel):
    def __init__(self, parent, song_path, song_title):
        super().__init__(parent)
        self.title(f"Song Deconstruction Inspector - {song_title}")
        self.geometry("880x620")
        self.configure(bg="#12131A")
        self.transient(parent)
        self.grab_set()

        set_window_icon(self)

        self.song_path = song_path
        self.deconstructed_data = deconstruct_rbs_song(song_path)

        lbl_header = tk.Label(self, text=f"🔬 PATTERN DECONSTRUCTION MATRIX: {song_title}", font=("Segoe UI", 11, "bold"), fg="#00E5FF", bg="#12131A")
        lbl_header.pack(anchor="w", padx=15, pady=(12, 6))

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        # Add tabs for devices
        self.create_303_tab(notebook, "TB-303 #1", self.deconstructed_data["303_1"])
        self.create_303_tab(notebook, "TB-303 #2", self.deconstructed_data["303_2"])
        self.create_drum_tab(notebook, "TR-808 Drums", self.deconstructed_data["808"])
        self.create_drum_tab(notebook, "TR-909 Drums", self.deconstructed_data["909"])

        btn_bar = tk.Frame(self, bg="#12131A")
        btn_bar.pack(fill=tk.X, padx=15, pady=(0, 12))

        btn_copy = tk.Button(btn_bar, text="📋 Copy to Clipboard", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#242736", activebackground="#2E3347", bd=0, cursor="hand2", command=self.copy_to_clipboard)
        btn_copy.pack(side=tk.LEFT, ipadx=10, ipady=4)

        btn_save = tk.Button(btn_bar, text="💾 Save Full Report to .TXT", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#00A86B", activebackground="#00C880", bd=0, cursor="hand2", command=self.save_to_txt)
        btn_save.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=4)

        btn_close = tk.Button(btn_bar, text="Close Window", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#3A3D52", activebackground="#505570", bd=0, cursor="hand2", command=self.destroy)
        btn_close.pack(side=tk.RIGHT, ipadx=15, ipady=4)

    def create_303_tab(self, notebook, title, patterns):
        frame = tk.Frame(notebook, bg="#1A1C27")
        notebook.add(frame, text=title)

        txt = tk.Text(frame, bg="#12131A", fg="#00FF66", font=("Consolas", 9), bd=0, highlightthickness=0, wrap=tk.NONE)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        if not patterns:
            txt.insert(tk.END, "No active patterns found for this unit.\n")
        else:
            txt.insert(tk.END, f"=== {title} ACTIVE PATTERNS ({len(patterns)} total) ===\n")
            txt.insert(tk.END, "Legend: Step (01-16) | Note Pitch | Attr (^/v Octave, A Accent, S Slide)\n\n")
            for p in patterns:
                txt.insert(tk.END, f"Pattern {p['name']}:\n")
                steps_h = " ".join([f"{i+1:02d}".center(5) for i in range(16)])
                notes_h = " ".join([s['note'].center(5) for s in p['steps']])
                attrs_h = " ".join([f"{s['up']}{s['accent']}{s['slide']}".center(5) for s in p['steps']])
                txt.insert(tk.END, f" Step: {steps_h}\n")
                txt.insert(tk.END, f" Note: {notes_h}\n")
                txt.insert(tk.END, f" Attr: {attrs_h}\n")
                txt.insert(tk.END, "-" * 95 + "\n")

        txt.config(state=tk.DISABLED)

    def create_drum_tab(self, notebook, title, patterns):
        frame = tk.Frame(notebook, bg="#1A1C27")
        notebook.add(frame, text=title)

        txt = tk.Text(frame, bg="#12131A", fg="#FF9500", font=("Consolas", 9), bd=0, highlightthickness=0, wrap=tk.NONE)
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        if not patterns:
            txt.insert(tk.END, "No active drum patterns found for this unit.\n")
        else:
            txt.insert(tk.END, f"=== {title} ACTIVE PATTERNS ({len(patterns)} total) ===\n")
            txt.insert(tk.END, "Legend: x=Hit, A=Accent, F=Flam, .=Rest\n\n")
            for p in patterns:
                txt.insert(tk.END, f"Pattern {p['name']}:\n")
                steps_line = " ".join([f"{i+1:02d}" for i in range(16)])
                txt.insert(tk.END, f"     Step: {steps_line}\n")
                for inst_lbl, hits in p['matrix'].items():
                    hits_str = "  ".join(hits)
                    txt.insert(tk.END, f"     {inst_lbl:4s}: {hits_str}\n")
                txt.insert(tk.END, "-" * 70 + "\n")

        txt.config(state=tk.DISABLED)

    def generate_full_report_text(self):
        meta = parse_rbs_metadata(self.song_path)

        full_text = f"REBIRTH RB-338 DECONSTRUCTED PATTERNS REPORT\n"
        full_text += f"Song Path: {self.song_path}\n"
        full_text += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        full_text += "=" * 75 + "\n\n"

        # Song Summary & Metadata Section
        full_text += "=== SONG METADATA & SUMMARY ===\n\n"
        full_text += f"  Title            : {meta['title']}\n"
        full_text += f"  Tempo (BPM)      : {meta['bpm'] if meta['bpm'] else 'Unknown'}\n"
        full_text += f"  Playback Mode    : {meta['mode']}\n"
        full_text += f"  Duration & Bars  : {meta['duration_str']}\n"
        if meta['loop_end'] > 0:
            full_text += f"  Loop Bounds      : Bar {meta['loop_start']} to Bar {meta['loop_end']}\n"
        full_text += f"  Mod Name         : {meta['mod_name']}\n"
        full_text += f"  Sound Engine     : {meta['sound_engine']}\n"
        full_text += f"  Active Patterns  : {meta['active_patterns']} total ({meta['pattern_breakdown']})\n"
        if meta.get('comments'):
            formatted_comm = meta['comments'].replace("\n", "\n                     ")
            full_text += f"  Song Description : {formatted_comm}\n"
        full_text += "\n" + "=" * 75 + "\n\n"

        # Legend & Abbreviations Section
        full_text += "=== LEGEND & SYMBOL EXPLANATIONS ===\n\n"
        full_text += "TB-303 Synthesizers:\n"
        full_text += "  Step : Pattern step index (01 to 16)\n"
        full_text += "  Note : Pitch name (C, C#, D, D#, E, F, F#, G, G#, A, A#, B, C5) or '--' for rest/pause\n"
        full_text += "  Attr : Attributes trio formatted as [Octave][Accent][Slide]:\n"
        full_text += "         - Octave: '^' = Transpose Up (+1 Oct), 'v' = Transpose Down (-1 Oct), '-' = Normal\n"
        full_text += "         - Accent: 'A' = Accent Enabled, '-' = Normal\n"
        full_text += "         - Slide : 'S' = Slide / Portamento Enabled, '-' = Normal\n\n"
        full_text += "TR-808 / TR-909 Drum Machines:\n"
        full_text += "  Triggers : 'x' = Normal Hit | 'A' = Accented Hit | 'F' = Flam (TR-909 only) | '.' = Rest / Silence\n"
        full_text += "  Instrument Labels:\n"
        full_text += "    AC = Accent Track        BD = Bass Drum (Kick)     SD = Snare Drum\n"
        full_text += "    LT = Low Tom             MT = Mid Tom              HT = Hi Tom\n"
        full_text += "    RS = Rim Shot            CP = Hand Clap            CB = Cowbell (808)\n"
        full_text += "    CY = Cymbal (808)        OH = Open Hi-Hat          CH = Closed Hi-Hat\n"
        full_text += "    CC = Crash Cymbal (909)  RC = Ride Cymbal (909)\n"
        full_text += "=" * 75 + "\n\n"

        for dev_key, dev_title in [("303_1", "TB-303 #1"), ("303_2", "TB-303 #2")]:
            full_text += f"=== {dev_title} ACTIVE PATTERNS ({len(self.deconstructed_data[dev_key])} total) ===\n"
            if not self.deconstructed_data[dev_key]:
                full_text += "No active patterns.\n\n"
            for p in self.deconstructed_data[dev_key]:
                full_text += f"Pattern {p['name']}:\n"
                steps_h = " ".join([f"{i+1:02d}".center(5) for i in range(16)])
                notes_h = " ".join([s['note'].center(5) for s in p['steps']])
                attrs_h = " ".join([f"{s['up']}{s['accent']}{s['slide']}".center(5) for s in p['steps']])
                full_text += f" Step: {steps_h}\n"
                full_text += f" Note: {notes_h}\n"
                full_text += f" Attr: {attrs_h}\n\n"

        for dev_key, dev_title in [("808", "TR-808 Drums"), ("909", "TR-909 Drums")]:
            full_text += f"=== {dev_title} ACTIVE PATTERNS ({len(self.deconstructed_data[dev_key])} total) ===\n"
            if not self.deconstructed_data[dev_key]:
                full_text += "No active drum patterns.\n\n"
            for p in self.deconstructed_data[dev_key]:
                full_text += f"Pattern {p['name']}:\n"
                steps_line = " ".join([f"{i+1:02d}" for i in range(16)])
                full_text += f"     Step: {steps_line}\n"
                for inst_lbl, hits in p['matrix'].items():
                    hits_str = "  ".join(hits)
                    full_text += f"     {inst_lbl:4s}: {hits_str}\n"
                full_text += "\n"

        full_text += "=" * 75 + "\n"
        full_text += "Report generated automatically by ReBirthLauncher\n"
        full_text += "=" * 75 + "\n"

        return full_text

    def copy_to_clipboard(self):
        full_text = self.generate_full_report_text()
        self.clipboard_clear()
        self.clipboard_append(full_text)
        messagebox.showinfo("Clipboard", "Deconstructed pattern report copied to clipboard!")

    def save_to_txt(self):
        song_name = os.path.basename(self.song_path)
        default_filename = os.path.splitext(song_name)[0] + "_deconstructed.txt"
        file_path = filedialog.asksaveasfilename(
            title="Save Deconstruction Report as Text File",
            defaultextension=".txt",
            initialfile=default_filename,
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                report_content = self.generate_full_report_text()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                messagebox.showinfo("Saved", f"Deconstruction report saved successfully to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")

def find_iso_file():
    """ Automatically locates any .iso file in the launcher root folder """
    folder = get_base_dir()
    iso_files = glob.glob(os.path.join(folder, "*.iso"))
    if iso_files:
        return os.path.abspath(iso_files[0])
    return None

def mount_iso(iso_path):
    """ Mounts ISO via PowerShell, suppresses automatic Explorer pop-up window, and returns drive letter """
    ps_command = (
        f"$vol = (Mount-DiskImage -ImagePath '{iso_path}' -PassThru | Get-Volume).DriveLetter; "
        f"Start-Sleep -Milliseconds 400; "
        f"(New-Object -ComObject Shell.Application).Windows() | Where-Object {{ $_.LocationURL -like \"*$vol*\" }} | ForEach-Object {{ $_.Quit() }}; "
        f"Write-Output $vol"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True)
    return result.stdout.strip()

def dismount_iso(iso_path):
    """ Unmounts virtual CD disk """
    ps_command = f"Dismount-DiskImage -ImagePath '{iso_path}'"
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True)

def detect_midi_devices():
    """ Returns list of connected MIDI input device names using winmm.dll """
    devices = []
    try:
        winmm = ctypes.windll.winmm
        num_devs = winmm.midiInGetNumDevs()
        caps = MIDIINCAPSW()
        for i in range(num_devs):
            if winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                devices.append(caps.szPname)
    except Exception:
        pass
    return devices

def set_cpu_affinity_core_0(pid):
    """ Locks specified process ID to single CPU core (Core 0) to avoid multi-core audio glitches """
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x0200, False, pid)
        if handle:
            ctypes.windll.kernel32.SetProcessAffinityMask(handle, 1)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass

def find_all_rbs_songs(max_limit=1000):
    """ Fast scanner for .rbs song files across directory tree """
    songs = []
    found_count = 0
    base_folder = get_base_dir()
    for root, _, files in os.walk(base_folder):
        for file in files:
            if file.lower().endswith(".rbs"):
                full_path = os.path.abspath(os.path.join(root, file))
                songs.append((file, full_path))
                found_count += 1
                if found_count >= max_limit:
                    break
        if found_count >= max_limit:
            break
    songs.sort(key=lambda x: x[0].lower())
    return songs

def force_retro_compatibility():
    """ Applies compatibility flags to fix font alignment in Preferences window """
    reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppNameCompatFlags\Layers"
    compat_flags = "~ RUNASADMIN GDIDPISCALE DPIUNAWARE"
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, EXE_PATH, 0, winreg.REG_SZ, compat_flags)
        winreg.CloseKey(key)
    except Exception:
        pass

def stabilize_rebirth_environment(game_folder, drive_letter, song_path=None):
    """ Writes drive paths and song selection into 32-bit and 64-bit Windows registry """
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

def is_process_running(process_name):
    """ Checks if ReBirth process is running """
    cmd = f'tasklist /FI "IMAGENAME eq {process_name}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return process_name.lower() in result.stdout.lower()

def kill_zombie_process():
    """ Terminates stuck ReBirth process forcefully """
    cmd = f'taskkill /F /IM "{EXE_NAME}"'
    subprocess.run(cmd, shell=True, capture_output=True)

class ModernRebirthLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("ReBirthLauncher")
        self.root.geometry("620x760")
        self.root.resizable(False, False)
        self.root.configure(bg="#12131A")

        set_window_icon(self.root)

        self.iso_path = find_iso_file()
        self.selected_res_index = 5
        self.rbs_songs = []

        self.setup_styles()
        self.build_ui()
        self.update_iso_status()
        self.check_zombie_status()
        self.scan_files_async()
        self.refresh_midi_status()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.style.configure("TCombobox", 
                             fieldbackground="#1A1C27", 
                             background="#282B3C", 
                             foreground="#E0E0E0", 
                             darkcolor="#12131A", 
                             lightcolor="#282B3C",
                             arrowcolor="#00E5FF",
                             padding=5)
        self.style.map("TCombobox", 
                       fieldbackground=[("readonly", "#1A1C27")],
                       foreground=[("readonly", "#FFFFFF")])

    def draw_synth_header(self, canvas):
        """ Draws synthesizer rack header banner with TB-303 oscilloscope and knobs """
        canvas.create_rectangle(0, 0, 620, 110, fill="#191B24", outline="#2A2D3E", width=2)
        
        screws = [(15, 15), (605, 15), (15, 95), (605, 95)]
        for sx, sy in screws:
            canvas.create_oval(sx-5, sy-5, sx+5, sy+5, fill="#3A3D52", outline="#505570", width=1)
            canvas.create_line(sx-3, sy-3, sx+3, sy+3, fill="#12131A", width=1.5)

        # Oscilloscope Screen
        canvas.create_rectangle(35, 20, 185, 90, fill="#08140B", outline="#1A3B20", width=2)
        for x in range(45, 185, 15):
            canvas.create_line(x, 20, x, 90, fill="#0F2815", width=1)
        for y in range(30, 90, 15):
            canvas.create_line(35, y, 185, y, fill="#0F2815", width=1)
            
        wave_pts = [
            (35, 55), (50, 35), (50, 75), (65, 35), (65, 75), 
            (80, 55), (95, 30), (110, 80), (125, 40), (140, 70), (155, 55), (185, 55)
        ]
        for i in range(len(wave_pts)-1):
            canvas.create_line(wave_pts[i][0], wave_pts[i][1], wave_pts[i+1][0], wave_pts[i+1][1], fill="#00FF66", width=2)

        # Header text
        canvas.create_text(320, 38, text="REBIRTHLAUNCHER", font=("Segoe UI", 18, "bold"), fill="#00E5FF")
        canvas.create_text(320, 62, text="DUAL 303 + 808 + 909 NATIVE RACK", font=("Segoe UI", 8, "bold"), fill="#FF9500")
        canvas.create_text(320, 80, text="PRO STUDIO ENGINE", font=("Segoe UI", 7, "bold"), fill="#6C7293")

        # Knobs
        knob_centers = [(465, 55), (515, 55), (565, 55)]
        knob_labels = ["CUTOFF", "RESO", "ACCENT"]
        
        for idx, (kx, ky) in enumerate(knob_centers):
            canvas.create_oval(kx-18, ky-18, kx+18, ky+18, fill="#282B3C", outline="#414660", width=2)
            canvas.create_oval(kx-13, ky-13, kx+13, ky+13, fill="#1A1C27", outline="#282B3C", width=1)
            angle = math.radians(220 - (idx * 50))
            rx = kx + 12 * math.cos(angle)
            ry = ky - 12 * math.sin(angle)
            canvas.create_line(kx, ky, rx, ry, fill="#FF9500", width=2.5)
            canvas.create_text(kx, ky+27, text=knob_labels[idx], font=("Segoe UI", 6, "bold"), fill="#8E95B3")

    def build_ui(self):
        canvas_header = tk.Canvas(self.root, width=620, height=110, bg="#12131A", highlightthickness=0)
        canvas_header.pack(fill=tk.X, pady=0)
        self.draw_synth_header(canvas_header)

        main_container = tk.Frame(self.root, bg="#12131A")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 1. Virtual Disk & System Status Card
        sys_card = tk.Frame(main_container, bg="#1A1C27", highlightbackground="#282B3C", highlightthickness=1)
        sys_card.pack(fill=tk.X, pady=(0, 10), ipady=6, ipadx=10)

        lbl_sys_title = tk.Label(sys_card, text="SYSTEM & VIRTUAL DRIVE STATUS", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27")
        lbl_sys_title.pack(anchor="w", padx=12, pady=(4, 2))

        iso_btn_frame = tk.Frame(sys_card, bg="#1A1C27")
        iso_btn_frame.pack(fill=tk.X, padx=12, pady=(0, 4))

        self.lbl_iso_info = tk.Label(iso_btn_frame, text="Searching for ISO file...", font=("Segoe UI", 8), fg="#FFFFFF", bg="#1A1C27", anchor="w")
        self.lbl_iso_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_zombie = tk.Button(iso_btn_frame, text="⚡ Kill Zombie & Reset ISO", font=("Segoe UI", 8, "bold"), fg="#FF453A", bg="#2D1A21", activebackground="#3D202A", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.handle_zombie_cleanup)
        self.btn_zombie.pack(side=tk.RIGHT, padx=(5, 0), ipadx=8, ipady=2)

        btn_browse_iso = tk.Button(iso_btn_frame, text="Browse ISO...", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#242736", activebackground="#2E3347", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.browse_iso_manually)
        btn_browse_iso.pack(side=tk.RIGHT, padx=5, ipadx=8, ipady=2)

        midi_bar = tk.Frame(sys_card, bg="#1A1C27")
        midi_bar.pack(fill=tk.X, padx=12, pady=(2, 2))

        self.lbl_midi = tk.Label(midi_bar, text="Detecting MIDI Devices...", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#1A1C27", anchor="w")
        self.lbl_midi.pack(side=tk.LEFT)

        btn_refresh_midi = tk.Button(midi_bar, text="↻ Refresh MIDI", font=("Segoe UI", 7, "bold"), fg="#8E95B3", bg="#242736", activebackground="#2E3347", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.refresh_midi_status)
        btn_refresh_midi.pack(side=tk.RIGHT, ipadx=6, ipady=1)

        # 2. Song Selector & Song Inspector Card (.rbs)
        song_card = tk.Frame(main_container, bg="#1A1C27", highlightbackground="#282B3C", highlightthickness=1)
        song_card.pack(fill=tk.X, pady=(0, 10), ipady=6, ipadx=10)

        song_header_frame = tk.Frame(song_card, bg="#1A1C27")
        song_header_frame.pack(fill=tk.X, padx=12, pady=(4, 4))

        lbl_song_heading = tk.Label(song_header_frame, text="STARTUP SONG & SONG INSPECTOR (.RBS)", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27")
        lbl_song_heading.pack(side=tk.LEFT)

        btn_browse_song = tk.Button(song_header_frame, text="Browse...", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#242736", activebackground="#2E3347", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.browse_song_manually)
        btn_browse_song.pack(side=tk.RIGHT, ipadx=6, ipady=1)

        btn_deconstruct = tk.Button(song_header_frame, text="🔬 Deconstruct", font=("Segoe UI", 8, "bold"), fg="#00FF66", bg="#242736", activebackground="#2E3347", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.open_deconstruction_window)
        btn_deconstruct.pack(side=tk.RIGHT, padx=4, ipadx=6, ipady=1)

        btn_random_song = tk.Button(song_header_frame, text="🎲 Random", font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#242736", activebackground="#2E3347", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.pick_random_song)
        btn_random_song.pack(side=tk.RIGHT, padx=(0, 4), ipadx=6, ipady=1)

        self.combo_songs = ttk.Combobox(song_card, values=["[Default / Last Opened Song]"], state="readonly", font=("Segoe UI", 9))
        self.combo_songs.current(0)
        self.combo_songs.pack(fill=tk.X, padx=12, pady=(0, 8))
        self.combo_songs.bind("<<ComboboxSelected>>", self.on_song_selected)

        # Dynamic Metadata Display Panel (Clean non-overlapping grid layout)
        meta_frame = tk.Frame(song_card, bg="#12131A", highlightbackground="#242736", highlightthickness=1)
        meta_frame.pack(fill=tk.X, padx=12, pady=(0, 4), ipadx=8, ipady=6)

        m_line1 = tk.Frame(meta_frame, bg="#12131A")
        m_line1.pack(fill=tk.X)

        self.lbl_meta_bpm = tk.Label(m_line1, text="BPM: --", font=("Segoe UI", 9, "bold"), fg="#00FF66", bg="#12131A")
        self.lbl_meta_bpm.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_meta_mode = tk.Label(m_line1, text="Mode: --", font=("Segoe UI", 8, "bold"), fg="#FF9500", bg="#12131A")
        self.lbl_meta_mode.pack(side=tk.LEFT, padx=(0, 15))

        self.lbl_meta_engine = tk.Label(m_line1, text="Engine: ReBirth 2.0 Sound", font=("Segoe UI", 8), fg="#6C7293", bg="#12131A")
        self.lbl_meta_engine.pack(side=tk.LEFT)

        m_line2 = tk.Frame(meta_frame, bg="#12131A")
        m_line2.pack(fill=tk.X, pady=(2, 0))

        self.lbl_meta_dur = tk.Label(m_line2, text="Duration: --", font=("Segoe UI", 8, "bold"), fg="#00E5FF", bg="#12131A", anchor="w")
        self.lbl_meta_dur.pack(side=tk.LEFT)

        self.lbl_meta_mod = tk.Label(meta_frame, text="Mod Name: Standard ReBirth", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#12131A", anchor="w")
        self.lbl_meta_mod.pack(fill=tk.X, pady=(2, 2))

        self.lbl_meta_pats = tk.Label(meta_frame, text="Active Patterns: -- (303 #1: 0 | 303 #2: 0 | 808: 0 | 909: 0)", font=("Segoe UI", 8), fg="#00E5FF", bg="#12131A", anchor="w")
        self.lbl_meta_pats.pack(fill=tk.X, pady=(0, 2))

        self.lbl_meta_title = tk.Label(meta_frame, text="Title: [Default / Last Opened]", font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#12131A", anchor="w")
        self.lbl_meta_title.pack(fill=tk.X, pady=(2, 2))

        self.lbl_meta_desc = tk.Label(meta_frame, text="Select a song to parse tempo, active patterns, mod name, and description...", font=("Segoe UI", 8, "italic"), fg="#6C7293", bg="#12131A", anchor="w", justify=tk.LEFT)
        self.lbl_meta_desc.pack(fill=tk.X)

        # 3. Resolution & Hardware Settings Card
        setting_card = tk.Frame(main_container, bg="#1A1C27", highlightbackground="#282B3C", highlightthickness=1)
        setting_card.pack(fill=tk.X, pady=(0, 10), ipady=6, ipadx=10)

        lbl_res = tk.Label(setting_card, text="LAUNCH SCREEN RESOLUTION", font=("Segoe UI", 8, "bold"), fg="#A0A5C0", bg="#1A1C27")
        lbl_res.pack(anchor="w", padx=12, pady=(4, 4))

        res_names = [r[0] for r in RESOLUTIONS]
        self.combo_res = ttk.Combobox(setting_card, values=res_names, state="readonly", font=("Segoe UI", 9))
        self.combo_res.current(self.selected_res_index)
        self.combo_res.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.var_cpu_affinity = tk.BooleanVar(value=True)
        chk_affinity = tk.Checkbutton(
            setting_card, 
            text="Lock process to single CPU Core (Core 0) [Prevents multi-core audio glitches]", 
            variable=self.var_cpu_affinity, 
            font=("Segoe UI", 8, "bold"), 
            fg="#FF9500", 
            bg="#1A1C27", 
            activebackground="#1A1C27", 
            activeforeground="#FF9500", 
            selectcolor="#1F2230"
        )
        chk_affinity.pack(anchor="w", padx=12, pady=(0, 4))

        # 4. Big Launch Button
        self.btn_launch = tk.Button(main_container, text="LAUNCH REBIRTH RB-338 STUDIO", font=("Segoe UI", 11, "bold"), fg="#FFFFFF", bg="#00A86B", activebackground="#00C880", activeforeground="#FFFFFF", bd=0, cursor="hand2", command=self.launch_rebirth)
        self.btn_launch.pack(fill=tk.X, ipady=11, pady=(4, 0))

        lbl_footer = tk.Label(self.root, text="Author: TomasKrs  (c)2026    Programmed by AI", font=("Segoe UI", 8), fg="#42475E", bg="#12131A")
        lbl_footer.pack(side=tk.BOTTOM, pady=6)

    def open_deconstruction_window(self):
        """ Opens modal window to inspect 303/808/909 step patterns """
        song_idx = self.combo_songs.current()
        if song_idx > 0 and len(self.rbs_songs) >= song_idx:
            song_path = self.rbs_songs[song_idx - 1][1]
            song_title = os.path.basename(song_path)
            SongDeconstructionWindow(self.root, song_path, song_title)
        else:
            messagebox.showinfo("Select Song", "Please select a specific .rbs song file first to deconstruct its patterns.")

    def on_song_selected(self, event=None):
        """ Triggers when user selects a song from the dropdown """
        song_idx = self.combo_songs.current()
        if song_idx > 0 and len(self.rbs_songs) >= song_idx:
            song_path = self.rbs_songs[song_idx - 1][1]
            meta = parse_rbs_metadata(song_path)
            
            bpm_str = f"BPM: {meta['bpm']}" if meta['bpm'] else "BPM: Unknown"
            self.lbl_meta_bpm.config(text=bpm_str)
            self.lbl_meta_mode.config(text=f"Mode: {meta['mode']}")

            dur_str = f"Duration: {meta['duration_str']}"
            if meta['loop_end'] > 0:
                dur_str += f" [Loop: Bar {meta['loop_start']}-{meta['loop_end']}]"
            self.lbl_meta_dur.config(text=dur_str)

            self.lbl_meta_engine.config(text=f"Engine: {meta['sound_engine']}")
            self.lbl_meta_mod.config(text=f"Mod Name: {meta['mod_name']}")
            self.lbl_meta_pats.config(text=f"Active Patterns: {meta['active_patterns']} total ({meta['pattern_breakdown']})")
            
            title_str = meta['title'] if meta['title'] else os.path.basename(song_path)
            self.lbl_meta_title.config(text=f"Title: {title_str}")
            
            desc_str = meta['comments'][:120] + ("..." if len(meta['comments']) > 120 else "")
            self.lbl_meta_desc.config(text=desc_str if desc_str else "No additional song description.")
        else:
            self.lbl_meta_bpm.config(text="BPM: --")
            self.lbl_meta_mode.config(text="Mode: --")
            self.lbl_meta_dur.config(text="Duration: --")
            self.lbl_meta_engine.config(text="Engine: ReBirth 2.0 Sound")
            self.lbl_meta_mod.config(text="Mod Name: Standard ReBirth")
            self.lbl_meta_pats.config(text="Active Patterns: -- (303 #1: 0 | 303 #2: 0 | 808: 0 | 909: 0)")
            self.lbl_meta_title.config(text="Title: [Default / Last Opened]")
            self.lbl_meta_desc.config(text="Select a song to parse tempo, active patterns, mod name, and description...")

    def pick_random_song(self):
        """ Picks a random song from the loaded list """
        if self.rbs_songs:
            random_idx = random.randint(0, len(self.rbs_songs) - 1)
            self.combo_songs.current(random_idx + 1)
            self.on_song_selected()

    def browse_song_manually(self):
        """ Opens file dialog to select any custom .rbs song file from disk """
        file_selected = filedialog.askopenfilename(
            title="Select ReBirth Song (.rbs)",
            filetypes=[("ReBirth Song Files", "*.rbs"), ("All Files", "*.*")]
        )
        if file_selected:
            song_name = os.path.basename(file_selected)
            existing_paths = [s[1].lower() for s in self.rbs_songs]
            if file_selected.lower() not in existing_paths:
                self.rbs_songs.insert(0, (song_name, file_selected))
                song_display = ["[Default / Last Opened Song]"] + [s[0] for s in self.rbs_songs]
                self.combo_songs['values'] = song_display
                self.combo_songs.current(1)
            else:
                idx = existing_paths.index(file_selected.lower())
                self.combo_songs.current(idx + 1)
            self.on_song_selected()

    def scan_files_async(self):
        """ Scans songs in background thread """
        def worker():
            songs = find_all_rbs_songs()
            self.root.after(0, lambda: self.update_file_lists(songs))

        threading.Thread(target=worker, daemon=True).start()

    def update_file_lists(self, songs):
        self.rbs_songs = songs
        song_display = ["[Default / Last Opened Song]"] + [s[0] for s in songs]
        self.combo_songs['values'] = song_display
        
        for idx, (name, path) in enumerate(songs):
            if DEFAULT_TARGET_SONG.lower() in name.lower():
                self.combo_songs.current(idx + 1)
                self.on_song_selected()
                break

    def refresh_midi_status(self):
        """ Scans system for active MIDI controllers """
        devices = detect_midi_devices()
        if devices:
            dev_str = ", ".join(devices)
            self.lbl_midi.config(text=f"✔ MIDI Active: {dev_str}", fg="#00FF66")
        else:
            self.lbl_midi.config(text="✖ No MIDI input device detected (Connect controller before launch)", fg="#FF9500")

    def update_iso_status(self):
        """ Updates ISO status text in GUI """
        if self.iso_path and os.path.exists(self.iso_path):
            name = os.path.basename(self.iso_path)
            self.lbl_iso_info.config(text=f"✔ ISO Ready: {name}", fg="#00E5FF")
        else:
            self.lbl_iso_info.config(text="✖ No .iso file found in game directory!", fg="#FF453A")

    def check_zombie_status(self):
        """ Highlights zombie process button if ReBirth is running """
        if is_process_running(EXE_NAME):
            self.btn_zombie.config(bg="#FF453A", fg="#FFFFFF", text="⚠ Zombie ReBirth Running! Click to Kill")
        else:
            self.btn_zombie.config(bg="#2D1A21", fg="#FF453A", text="⚡ Kill Zombie & Reset ISO")

    def handle_zombie_cleanup(self):
        """ Force terminates stuck ReBirth process and unmounts ISO """
        kill_zombie_process()
        if self.iso_path:
            dismount_iso(self.iso_path)
        messagebox.showinfo("Zombie Cleanup", "Successfully terminated stuck ReBirth process and reset ISO drive!")
        self.check_zombie_status()

    def browse_iso_manually(self):
        """ Opens file dialog to select ISO image manually """
        file_selected = filedialog.askopenfilename(title="Select ReBirth ISO Image", filetypes=[("ISO Images", "*.iso"), ("All Files", "*.*")])
        if file_selected:
            self.iso_path = file_selected
            self.update_iso_status()

    def launch_rebirth(self):
        """ Mounts ISO, sets affinity, updates registry, changes resolution, and launches game """
        if not is_admin():
            messagebox.showerror("Administrator Rights", "Please run this launcher as Administrator!")
            return

        if not os.path.exists(EXE_PATH):
            messagebox.showerror("Error", f"File {EXE_NAME} was not found in the launcher directory!")
            return

        if not self.iso_path or not os.path.exists(self.iso_path):
            messagebox.showwarning("ISO Not Found", "Please copy an .iso file into the game directory or select it manually using the button!")
            return

        idx = self.combo_res.current()
        _, width, height = RESOLUTIONS[idx]

        song_idx = self.combo_songs.current()
        selected_song_path = self.rbs_songs[song_idx - 1][1] if song_idx > 0 else None

        self.root.withdraw()

        # 1. Mount ISO file silently
        drive_letter = mount_iso(self.iso_path)
        if not drive_letter:
            messagebox.showerror("ISO Error", "Failed to mount virtual ISO disk!")
            self.root.deiconify()
            return

        folder = get_base_dir()

        # 2. Registry stabilization and DPI compatibility fix
        stabilize_rebirth_environment(folder, drive_letter, selected_song_path)
        force_retro_compatibility()

        # 3. Change screen resolution if selected
        screen_changed = False
        if width and height:
            screen_changed = change_resolution(width, height)

        process_name = os.path.basename(EXE_PATH)

        try:
            # 4. Launch process
            short_song_path = get_short_path_name(selected_song_path) if selected_song_path else None
            cmd = [EXE_PATH, short_song_path] if short_song_path else [EXE_PATH]

            proc = subprocess.Popen(cmd, cwd=folder)

            if self.var_cpu_affinity.get():
                set_cpu_affinity_core_0(proc.pid)

            time.sleep(2)
            while is_process_running(process_name):
                time.sleep(1)
        except Exception as e:
            messagebox.showerror("Launch Error", f"An error occurred while starting the application: {e}")
        finally:
            if screen_changed:
                restore_resolution()
            dismount_iso(self.iso_path)
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernRebirthLauncher(root)
    root.mainloop()