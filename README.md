# ReBirthLauncher

Modern Companion, Native Compatibility Wrapper & RBS Pattern Inspector for Propellerhead ReBirth RB-338

Seamlessly run the legendary 90s dual-303 / 808 / 909 synth rack on modern 64-bit Windows 10 & 11.




<img width="618" height="680" alt="obrázok" src="https://github.com/user-attachments/assets/7fcf2ab4-782a-41a4-a294-f9e32add22b8" />



# Overview

ReBirth RB-338 (created by Propellerhead Software in 1997) is one of the most iconic software synthesizers in electronic music history. However, running this legacy 32-bit application on modern Windows systems presents severe compatibility issues:

CD Protection Checks: Requires a physical/virtual CD image mounted on every startup.

High-DPI & Scaling Glitches: Text overflow and broken layout alignments in the Preferences and dialog windows.

Multi-Core Audio Dropouts: Audio crackling, dropouts, or crashes on CPUs with high core counts.

Dynamic Drive Letter & Registry Desynchronization: Changing virtual drive letters leads to "Insert CD" error dialogs.

Fixed Low Resolution: The interface is tiny on high-density (1080p, 1440p, 4K) displays.

Win32Help: You don't need to install this. Launcher will bypass the screen with Help. This was the main problem around Win10/11.

ReBirthLauncher is a GUI tool built to solve every single legacy issue automatically, while introducing powerful modern tools like RBS Binary Song Parsing and 303/808/909 Step Pattern Deconstruction.

# ✨ Key Features

## 💿 Silent Virtual CD Automation

Automatically scans the launcher root directory for any .iso disc image.

Mounts the virtual disk silently via native PowerShell commands (Mount-DiskImage).

Anti-AutoPlay Suppression: Automatically suppresses and silently closes the Windows Explorer drive pop-up window upon mounting.

Dismounts the virtual drive automatically when exiting the application.

## ⚙️ Windows Registry & Environment Stabilization

Dynamically writes current virtual CD drive letters (CDPath), installation root (SourcePath, InstallationPath), and selected startup songs (LastSong, DefaultSong).

Writes across both 32-bit (SOFTWARE\Propellerhead Software\ReBirth) and 64-bit (Wow6432Node) registry keys as well as VirtualStore.

Converts long file paths into 8.3 Short Path Names (GetShortPathNameW) for 100% legacy 32-bit file parsing compatibility.

## 🔍 High-DPI & Font Alignment Fix

Writes compatibility flags (~ RUNASADMIN GDIDPISCALE DPIUNAWARE) to AppNameCompatFlags\Layers to fix garbled text and overflowing fonts in the Preferences menu.

## 🖥️ Display Resolution Switcher

Offers temporary system resolution switching via Windows User32.dll API (ChangeDisplaySettingsA).

Supports 17 preset profiles ranging from retro 640x480 (VGA), 800x600 (SVGA), 1280x960 (4:3 Retro Optimal) up to 4K Ultra HD (3840x2160) and UltraWide (21:9).

Guaranteed Restoration: Uses a strict try...finally block to restore your original desktop resolution even if the application crashes.

## ⚡ Single-Core CPU Affinity Locking

Lock ReBirth to CPU Core 0 using Windows Kernel API (SetProcessAffinityMask).

Eliminates multi-core audio buffer synchronization dropouts, clicks, and glitches.

## 🔬 RBS File Binary Inspector (IFF Parser)

Native binary parser for Propellerhead RBS v1.0 & v2.0/v4.2 file formats (GLOB, USRI, TRAK chunks).

Metadata Extraction: Displays Tempo (BPM), Mode (Song vs. Pattern), Sound Engine (ReBirth 2.0 vs. Vintage 1.5 Sound), Custom Mod Pack Name, Loop Bounds, Song Duration (~MM:SS), Total Bars, and User Comments.

Active Pattern Counter: Scans active (non-empty) patterns for TB-303 #1, TB-303 #2, TR-808, and TR-909.

## 🎶 Song Pattern Deconstruction Engine

Deep binary inspection of 303 note sequences and drum step matrices.

TB-303 Synthesizers: Decodes pitch (C1–C4), transpose up/down (^/v), accent (A), and slide (S) flags into structured 16-step grids.

TR-808 & TR-909 Drum Machines: Decodes step trigger matrices including normal hits (x), accents (A), and flams (F).

Exporting Options: Copy complete pattern reports to the clipboard or export full text reports (.txt) complete with legends and song statistics.

## 🎹 MIDI Device Auto-Detection

Uses native winmm.dll C-types calls (midiInGetNumDevs / midiInGetDevCapsW) to detect connected USB/MIDI controllers in real-time.

## 🛠️ Zombie Process & Emergency Cleanup

One-click ⚡ Kill Zombie & Reset ISO tool detects stuck background instances of Rebirth.exe and force-terminates them while unmounting stalled ISO images.

## 🎨 User Interface Design

DAW Dark Studio Aesthetic: Dark theme styled with cyan (#00E5FF), neon green (#00FF66), and amber (#FF9500) LED indicators.

Vector Canvas Rack Banner: Features a custom-rendered synthesizer rack header with an active TB-303 oscilloscope wave display, mounting screws, and analog control knobs (Cutoff, Reso, Accent).

Zero External GUI Dependencies: Built natively with Python's included tkinter and ttk packages. Includes an embedded Base64 studio icon.

# 🚀 Getting Started

Prerequisites

Operating System: Windows 10 or Windows 11 (64-bit recommended).

Privileges: Administrator Rights (required for virtual drive mounting and registry operations).

ReBirth Installation: Rebirth.exe and any valid .iso disc image placed in the same folder as the launcher {you can also have a mini rebirth cd with only 2 files).


Ideas: TomasKrs
Programmed by: AI
