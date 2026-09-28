import tkinter as tk
import ctypes
from ctypes import wintypes
import os
import sys
import time
import threading
from pynput import keyboard

# --- VARIABLES GLOBALES ---
is_active = True
toggle_lock = False
pressed_keys = set()
was_pressed = False

# --- CONSTANTES WIN32 ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x0100

LRESULT = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND)
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM)
    ]

# --- GESTION DES RACCOURCIS CLAVIER ---
def on_press(key):
    global is_active, toggle_lock
    try:
        if hasattr(key, 'char') and key.char:
            char = key.char.lower()
            pressed_keys.add(char)
            
            # BASCULE ON/OFF (T + Y)
            if 't' in pressed_keys and 'y' in pressed_keys:
                if not toggle_lock:
                    is_active = not is_active
                    toggle_lock = True
                    print(f"[!] ClickConverter : {'ON' if is_active else 'OFF'}", flush=True)
            
            # ARRÊT TOTAL (U + I)
            if 'u' in pressed_keys and 'i' in pressed_keys:
                print("\n[!] U + I détecté. Arrêt complet du programme...", flush=True)
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

# --- INJECTION DU CLIC ---
def trigger_left_click():
    if is_active:
        print("[DEBUG] 🖱️ Clic gauche envoyé à Windows !", flush=True)
        user32.mouse_event(0x0002, 0, 0, 0, 0) # LEFTDOWN
        time.sleep(0.04)
        user32.mouse_event(0x0004, 0, 0, 0, 0) # LEFTUP

# --- ÉCOUTE MATÉRIELLE DU STYLET ---
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
user32.GetRawInputData.argtypes = [wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.c_uint]
user32.GetRawInputData.restype = ctypes.c_uint

def wnd_proc(hwnd, msg, wparam, lparam):
    global was_pressed
    if msg == WM_INPUT:
        size = ctypes.c_uint(0)
        hRawInput = ctypes.cast(lparam, wintypes.HANDLE)
        
        user32.GetRawInputData(hRawInput, RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
        
        if size.value > 0:
            buffer = ctypes.create_string_buffer(size.value)
            if user32.GetRawInputData(hRawInput, RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)) == size.value:
                raw_data = buffer.raw[ctypes.sizeof(RAWINPUTHEADER):]
                
                # Suivi du Tip Switch
                if len(raw_data) > 9:
                    current_byte = raw_data[9]
                    is_pressed = (current_byte & 0x01) == 1
                    
                    if is_pressed and not was_pressed:
                        threading.Thread(target=trigger_left_click).start()
                        
                    was_pressed = is_pressed
                    
    elif msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

def pen_listener_thread():
    wnd_proc_cb = WNDPROC(wnd_proc)
    
    class WNDCLASS(ctypes.Structure):
        _fields_ = [
            ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
            ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
            ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)
        ]

    wndclass = WNDCLASS()
    wndclass.lpfnWndProc = wnd_proc_cb
    wndclass.hInstance = kernel32.GetModuleHandleW(None)
    wndclass.lpszClassName = "DofusPenClass"

    user32.RegisterClassW(ctypes.byref(wndclass))
    hwnd = user32.CreateWindowExW(0, "DofusPenClass", "Pen Listener", 0, 0, 0, 0, 0, None, None, wndclass.hInstance, None)

    devices = (RAWINPUTDEVICE * 1)()
    devices[0].usUsagePage = 0x0D # Stylet
    devices[0].usUsage = 0x02
    devices[0].dwFlags = RIDEV_INPUTSINK
    devices[0].hwndTarget = hwnd
    user32.RegisterRawInputDevices(devices, 1, ctypes.sizeof(RAWINPUTDEVICE))

    print("[DEBUG] Moteur d'écoute matériel lancé et prêt.", flush=True)
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
        
        # Bouton d'état (ON / OFF)
        self.btn_status = tk.Button(
            frame, 
            text="STATUS: ON", 
            command=self.toggle_active_from_ui,
            bg="#2ecc71", 
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.btn_status.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        
        # Bouton Quitter
        self.btn_quit = tk.Button(
            frame, 
            text="QUIT", 
            command=self.quit_app,
            bg="#e74c3c", 
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.btn_quit.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(2, 0))
        
        # Lancement de la boucle de rafraîchissement
        self.update_ui_loop()

    def toggle_active_from_ui(self):
        global is_active
        is_active = not is_active
        print(f"[!] ClickConverter : {'ON' if is_active else 'OFF'}", flush=True)

    def quit_app(self):
        print("\n[!] Fermeture via le bouton QUIT...", flush=True)
        os._exit(0) # os._exit() permet de forcer la fermeture propre de tous les threads

    def update_ui_loop(self):
        # Synchronise l'apparence du bouton avec la variable globale 'is_active'
        # (pratique si tu utilises T+Y pour changer l'état au lieu du bouton)
        if is_active:
            self.btn_status.config(text="STATUS: ON", bg="#2ecc71")
        else:
            self.btn_status.config(text="STATUS: OFF", bg="#e74c3c")
            
        self.root.after(100, self.update_ui_loop) # Vérifie l'état toutes les 100ms

# --- LANCEMENT GLOBAL ---
if __name__ == "__main__":
    print("=== DOFUS CLICK CONVERTER DÉMARRÉ ===", flush=True)
    
    # 1. Écouteur clavier (raccourcis T+Y et U+I)
    kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    kb_listener.start()
    
    # 2. Écouteur matériel du stylet
    threading.Thread(target=pen_listener_thread, daemon=True).start()
    
    # 3. Interface Graphique Interactive
    app = StylusConverterApp()
    app.root.mainloop()