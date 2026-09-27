# Stylus ClickConverter (Raw Input Unity Fix)

A low-level Windows utility designed to convert physical stylus screen taps into native left mouse clicks. This tool was developed to bypass input handling in game engines such as Unity (e.g., Dofus 3 Unity), which typically isolate digitizer events from standard mouse events and prevent stylus interaction within the game environment.

## Technical Overview

Standard workarounds for stylus input conversion on modern Windows 11 2-in-1 devices often fail for the following reasons:
1. High-level hooks (`pynput`) and registry modifications are ignored by Unity's raw input polling.
2. Kernel-level interception is frequently blocked by Windows 11 Core Isolation (HVCI) or anti-cheat software.
3. Modern I2C touchscreens route stylus data through alternative pathways, bypassing standard mouse APIs.

To resolve this, the script utilizes the Windows Raw Input API (`WM_INPUT`, UsagePage `0x0D`, Usage `0x02`) to intercept hardware packets directly from the digitizer before OS-level translation occurs.

Analysis of the raw hexadecimal data stream reveals that the 10th byte (index 9) dictates the physical state of the pen tip:
* `0x20` (32) = Pen is hovering over the screen.
* `0x21` (33) = Pen tip is physically pressed against the surface.

The application monitors the data stream exclusively for this state transition. Upon detecting `0x21`, it injects a pure Win32 `mouse_event` (Left Down followed by Left Up) at the current cursor coordinates.

## Hardware Compatibility

This utility was developed and verified on the following hardware configuration:
* OS: Windows 11 Pro
* Device: Lenovo Yoga 7i 2-in-1 Gen 10 (Intel Core Ultra 7)
* Stylus: Lenovo Linear Pen

As the Raw Input packet structure is highly standardized, this solution is expected to function with most Wacom AES and modern Windows Ink digitizers without requiring OS settings modifications or registry edits.

## Installation and Usage

1. Navigate to the Releases section of this repository.
2. Download the compiled executable (`ClickConverter.exe`).
3. Run the application. A transparent overlay will appear in the top-left corner of the screen displaying the current status (ON).
4. The stylus can now be used to register standard mouse clicks within the target application.

**Keyboard Shortcuts:**
* `T + Y` : Toggle the converter ON or OFF.
* `U + I` : Terminate the application process.

## Source Code

Developers can clone this repository to review or compile the Python source code.
* Dependencies: `pynput` is required for keyboard shortcut listening. `ctypes` and `tkinter` are utilized from the standard library.
* Configuration: If a specific stylus brand utilizes a different byte index for pressure state, the target byte can be adjusted by modifying `raw_data[9]` in the source code after conducting raw packet analysis.
