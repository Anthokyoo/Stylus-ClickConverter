# Stylus ClickConverter (Raw Input Unity Fix)

A low-level Windows utility designed to convert physical stylus screen taps into native left mouse clicks, featuring full continuous drag-and-drop support. This tool was developed to bypass input handling in game engines such as Unity (e.g., Dofus 3 Unity), which typically isolate digitizer events from standard mouse events and prevent stylus interaction within the game environment.

## Technical Overview

Standard workarounds for stylus input conversion on modern Windows 11 devices often fail for the following reasons:
1. High-level hooks (`pynput`) and registry modifications are ignored by Unity's raw input polling.
2. Kernel-level interception is frequently blocked by Windows 11 Core Isolation (HVCI) or anti-cheat software.
3. Modern I2C touchscreens route stylus data through alternative pathways, bypassing standard mouse APIs.

To resolve this, the script utilizes the Windows Raw Input API (`WM_INPUT`, UsagePage `0x0D`, Usage `0x02`) to intercept hardware packets directly from the digitizer before OS-level translation occurs. 

Analysis of the raw hexadecimal data stream reveals that the 10th byte (index 9) dictates the physical state of the pen tip. The application parses the Tip Switch bit (`current_byte & 0x01`) to determine pressure state transitions:
* Bit = 1: Pen tip is physically pressed against the surface.
* Bit = 0: Pen tip is hovering or lifted.

### Anti-Bounce Engine & Unity Optimization
Instead of injecting an instantaneous combined click, the application separates the `LEFTDOWN` and `LEFTUP` Win32 `mouse_event` calls to support drag-and-drop. 
To handle hardware imperfections, it implements a thread-safe queue system with a 40ms hardware debounce timer. This filter absorbs microscopic physical bounces ("pen bounce") that occur when the hard plastic nib strikes the screen, preventing unintended double-clicks or drag interruptions. Additionally, a 15ms micro-delay is applied prior to the `LEFTDOWN` event to account for cursor teleportation rendering delays within the Unity engine.

## Known Hardware Behaviors

* **Fast Swipes / Dropped Drags:** Executing a very rapid drag motion across the digitizer may cause a dragged item to drop prematurely. This is a physical hardware limitation, not a software defect. During fast and wide swipes, the stylus nib naturally loses physical contact with the surface due to reduced friction and hand elevation. If this lift-off exceeds the 40ms debounce threshold, the application accurately interprets it as a deliberate release and triggers a `LEFTUP` event. Increasing the timeout further would introduce noticeable input lag when intentionally dropping items.

## Hardware Compatibility

This utility was developed and verified on the following hardware configuration:
* OS: Windows 11 Pro
* Device: Lenovo Yoga 7i 2-in-1 Gen 10 (Intel Core Ultra 7)
* Stylus: Lenovo Linear Pen

As the Raw Input packet structure is highly standardized, this solution is expected to function with most Wacom AES and modern Windows Ink digitizers without requiring deep OS settings modifications or registry edits.

## Installation and Usage

1. Navigate to the Releases section of this repository.
2. Download the compiled executable (`ClickConverter.exe`).
3. Run the application. A compact, semi-transparent overlay interface will appear in the top-left corner of the screen displaying the current operational state.
4. The stylus can now be used to register standard mouse clicks and drag events within the target application.

**Interface Controls:**
* **`STATUS: ON / OFF` Button** : Tap directly with the stylus to toggle the conversion state dynamically (useful when standard text input is required in-game).
* **`QUIT` Button** : Terminate the application process safely.

## Source Code

Developers can clone this repository to review or compile the Python source code.
* **Dependencies:** Core functionalities rely exclusively on native Windows libraries (`ctypes`), thread queues (`queue`, `threading`), and the standard graphical interface library (`tkinter`).
* **Compilation:** When compiling via PyInstaller, do not use the `--noconsole` or `-w` flags, as strict 64-bit memory addressing requires the console allocation. The script is programmed to automatically hide the console window at runtime (`SW_HIDE`).
