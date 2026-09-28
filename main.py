import tkinter as tk
import ctypes
from ctypes import wintypes
import os
import sys
import time
import threading
import queue
from pynput import keyboard

# --- MASQUAGE IMMÉDIAT DE LA CONSOLE ---
# C'est la méthode la plus stable : on lance l'application normalement,
# mais on ordonne à Windows de rendre la console invisible à la milliseconde 1.
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32
hwnd_console = kernel32.GetConsoleWindow()
if hwnd_console != 0:
    user32.ShowWindow(hwnd_console, 0) # 0 = SW_HIDE

# --- VARIABLES GLOBALES ---
is_active = True
toggle_lock = False
pressed_keys = set()
was_pressed = False
input_queue = queue.Queue()

# --- CONSTANTES WIN32 ---
WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x0100

LRESULT = ctypes.c_ssize_t

# --- TYPAGE STRICT 64 BITS (C'est ce qui corrige l'OverflowError) ---
user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = ctypes.c_void_p

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.DWORD, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
]
user32.CreateWindowExW.restype = ctypes.c_void_p

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", ctypes.c_void_p)
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", ctypes.c_void_p),
        ("wParam", wintypes.WPARAM)
    ]

# --- GESTION DES RACCOURCIS CLAVIER ---
def on_press(key):
    global is_active, toggle_lock
    try:
        if hasattr(key, 'char') and key.char:
            char = key.char.lower()
            pressed_keys.add(char)
            
            if 't' in pressed_keys and 'y' in pressed_keys:
                if not toggle_lock:
                    is_active = not is_active
                    toggle_lock = True
            
            if 'u' in pressed_keys and 'i' in pressed_keys:
                os._exit(0)
    except AttributeError: pass

def on_release(key):
    global toggle_lock
    try:
        if hasattr(key, 'char') and key.char:
            char = key.char.lower()
            pressed_keys.discard(char)
            if 't' not in pressed_keys or 'y' not in pressed_keys:
                toggle_lock = False
    except AttributeError: pass

# --- WORKER ANTI-REBOND ---
def mouse_worker_thread():
    is_physically_down = False
    is_logically_down = False

    while True:
        try:
            event = input_queue.get(timeout=0.04)
            if event == True:
                is_physically_down = True
                if not is_logically_down and is_active:
                    time.sleep(0.015)
                    user32.mouse_event(0x0002, 0, 0, 0, 0) # LEFTDOWN
                    is_logically_down = True
            else:
                is_physically_down = False
        except queue.Empty:
            if not is_physically_down and is_logically_down:
                if is_active:
                    user32.mouse_event(0x0004, 0, 0, 0, 0) # LEFTUP
                is_logically_down = False

# --- ÉCOUTE MATÉRIELLE DU STYLET ---
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
user32.GetRawInputData.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.c_uint]
user32.GetRawInputData.restype = ctypes.c_uint

def wnd_proc(hwnd, msg, wparam, lparam):
    global was_pressed
    if msg == WM_INPUT:
        size = ctypes.c_uint(0)
        hRawInput = ctypes.c_void_p(lparam)
        
        user32.GetRawInputData(hRawInput, RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
        
        if size.value > 0:
            buffer = ctypes.create_string_buffer(size.value)
            if user32.GetRawInputData(hRawInput, RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)) == size.value:
                raw_data = buffer.raw[ctypes.sizeof(RAWINPUTHEADER):]
                
                if len(raw_data) > 9:
                    current_byte = raw_data[9]
                    is_pressed = (current_byte & 0x01) == 1
                    
                    if is_pressed and not was_pressed:
                        input_queue.put(True)
                    elif not is_pressed and was_pressed:
                        input_queue.put(False)
                        
                    was_pressed = is_pressed
                    
    elif msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

def pen_listener_thread():
    wnd_proc_cb = WNDPROC(wnd_proc)
    
    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", ctypes.c_uint),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", ctypes.c_void_p),
            ("hIcon", ctypes.c_void_p),
            ("hCursor", ctypes.c_void_p),
            ("hbrBackground", ctypes.c_void_p),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR)
        ]

    wndclass = WNDCLASS()
    wndclass.lpfnWndProc = wnd_proc_cb
    wndclass.hInstance = kernel32.GetModuleHandleW(None)
    wndclass.lpszClassName = "DofusPenClass"

    user32.RegisterClassW(ctypes.byref(wndclass))
    
    hwnd = user32.CreateWindowExW(
        0, "DofusPenClass", "Pen Listener", 0, 
        0, 0, 0, 0, 
        None, None, wndclass.hInstance, None
    )

    devices = (RAWINPUTDEVICE * 1)()
    devices[0].usUsagePage = 0x0D
    devices[0].usUsage = 0x02
    devices[0].dwFlags = RIDEV_INPUTSINK
    devices[0].hwndTarget = hwnd
    user32.RegisterRawInputDevices(devices, 1, ctypes.sizeof(RAWINPUTDEVICE))

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

# --- INTERFACE GRAPHIQUE (UI) ---
class StylusConverterApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.8)
        self.root.geometry("140x45+10+10")
        self.root.configure(bg="#222222")
        
        frame = tk.Frame(self.root, bg="#222222")
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        self.btn_status = tk.Button(
            frame, text="STATUS: ON", command=self.toggle_active_from_ui,
            bg="#2ecc71", fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT, cursor="hand2"
        )
        self.btn_status.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        
        self.btn_quit = tk.Button(
            frame, text="QUIT", command=self.quit_app,
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT, cursor="hand2"
        )
        self.btn_quit.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(2, 0))
        
        self.update_ui_loop()

    def toggle_active_from_ui(self):
        global is_active
        is_active = not is_active

    def quit_app(self):
        os._exit(0)

    def update_ui_loop(self):
        if is_active:
            self.btn_status.config(text="STATUS: ON", bg="#2ecc71")
        else:
            self.btn_status.config(text="STATUS: OFF", bg="#e74c3c")
        self.root.after(100, self.update_ui_loop)

# --- LANCEMENT GLOBAL ---
if __name__ == "__main__":
    threading.Thread(target=mouse_worker_thread, daemon=True).start()
    
    kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    kb_listener.start()
    threading.Thread(target=pen_listener_thread, daemon=True).start()
    
    app = StylusConverterApp()
    app.root.mainloop()