import tkinter as tk
import ctypes
from ctypes import wintypes
import os
import time
import threading
from pynput import keyboard
import sys

# --- MASQUAGE PROPRE DE LA CONSOLE AU LANCEMENT ---
# Cela permet de garder le comportement technique de la console tout en la rendant invisible
if sys.executable.endswith("pythonw.exe") or True: # Force le masquage si exécuté en .exe
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    hwnd = kernel32.GetConsoleWindow()
    if hwnd != 0:
        user32.ShowWindow(hwnd, 0) # 0 = SW_HIDE (Cache la fenêtre instantanément)

# --- VARIABLES GLOBALES ---
is_active = True
toggle_lock = False
pressed_keys = set()

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
                    #print(f"[*] Mode : {'ON' if is_active else 'OFF'}")
            
            # ARRÊT TOTAL (U + I)
            if 'u' in pressed_keys and 'i' in pressed_keys:
                #print("\n[!] U + I détecté. Arrêt complet du programme...")
                os._exit(0)
    except AttributeError: pass

def on_release(key):
    global toggle_lock
    try:
        if hasattr(key, 'char') and key.char:
            char = key.char.lower()
            pressed_keys.discard(char)
            
            # On déverrouille la bascule si on relâche T ou Y
            if 't' not in pressed_keys or 'y' not in pressed_keys:
                toggle_lock = False
    except AttributeError: pass

# --- INJECTION DU CLIC (DOFUS) ---
def trigger_left_click():
    # On exécute le clic UNIQUEMENT si le programme est sur ON
    if is_active:
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.03)
        user32.mouse_event(0x0004, 0, 0, 0, 0)

# --- ANALYSEUR MATÉRIEL (TOURNE EN TÂCHE DE FOND) ---
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
user32.GetRawInputData.argtypes = [wintypes.HANDLE, ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.c_uint]
user32.GetRawInputData.restype = ctypes.c_uint

was_pressed = False

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
                
                # Suivi de l'octet magique (index 9)
                if len(raw_data) > 9:
                    current_byte = raw_data[9]
                    is_pressed = (current_byte & 0x01) == 1
                    
                    if is_pressed and not was_pressed:
                        threading.Thread(target=trigger_left_click).start()
                        
                    was_pressed = is_pressed
                    
    if msg == WM_DESTROY:
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
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HANDLE),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HANDLE),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR)
        ]

    wndclass = WNDCLASS()
    wndclass.lpfnWndProc = wnd_proc_cb
    wndclass.hInstance = kernel32.GetModuleHandleW(None)
    wndclass.lpszClassName = "DofusPenClass"

    user32.RegisterClassW(ctypes.byref(wndclass))
    hwnd = user32.CreateWindowExW(0, "DofusPenClass", "Pen Listener", 0, 0, 0, 0, 0, None, None, wndclass.hInstance, None)

    # Configuration de l'écoute du stylet
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

# --- INTERFACE GRAPHIQUE (UI) TRANSPARENTE ---
def run_ui():
    root = tk.Tk()
    
    # Paramètres de la fenêtre
    root.overrideredirect(True) # Enlève la barre de titre et les bordures
    root.attributes("-topmost", True) # Force la fenêtre au premier plan
    root.attributes("-transparentcolor", "black") # Rend le fond noir totalement invisible
    
    # Position en haut à gauche (+marge de 20 pixels)
    root.geometry("+20+20")
    root.config(bg="black")
    
    # Création du texte
    label = tk.Label(root, text="ClickConverter : ON", font=("Segoe UI", 16, "bold"), bg="black")
    label.pack()

    # Boucle de mise à jour de l'affichage
    def update_ui():
        if is_active:
            label.config(text="ClickConverter : ON", fg="#00FF00") # Vert
        else:
            label.config(text="ClickConverter : OFF", fg="#FF0000") # Rouge
            
        root.after(100, update_ui) # Relance la vérification toutes les 100ms

    update_ui()
    root.mainloop()

# --- LANCEMENT GLOBAL ---
if __name__ == "__main__":
    #print("=== DOFUS 3 CLICK CONVERTER (AVEC UI) ===")
    #print("-> Interface lancée en haut à gauche de l'écran.")
    #print("-> T + Y : Activer / Désactiver (ON/OFF)")
    #print("-> U + I : Fermer complètement le programme\n")

    # 1. Lancement de l'écouteur clavier
    kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    kb_listener.start()

    # 2. Lancement du traqueur de stylet dans un Thread séparé
    threading.Thread(target=pen_listener_thread, daemon=True).start()

    # 3. Lancement de l'interface graphique (bloquant, doit rester sur le processus principal)
    run_ui()
