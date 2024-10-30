import ctypes
import cv2
import json
import math
import mss
import numpy as np
import os
import sys
import time
import torch
import win32api
from pynput import keyboard
from termcolor import colored
import multiprocessing
from PyQt5 import QtWidgets, QtGui, QtCore

class Overlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool |
            QtCore.Qt.WindowTransparentForInput
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.showFullScreen()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        screen = QtWidgets.QApplication.primaryScreen()
        rect = screen.geometry()
        center_x = rect.width() / 2
        center_y = rect.height() / 2

        radius = 100 
        sides = 80

        points = []
        for i in range(sides + 1):
            angle = (i / sides) * 2 * math.pi
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            points.append(QtCore.QPointF(x, y))

        pen = QtGui.QPen(QtGui.QColor(255, 255, 255))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawPolyline(QtGui.QPolygonF(points))

def run_overlay():
    app = QtWidgets.QApplication(sys.argv)
    overlay = Overlay()
    sys.exit(app.exec_())

prev_frame_time = 0
new_frame_time = 0
PUL = ctypes.POINTER(ctypes.c_ulong)

class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class Minecraft:
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    screen = mss.mss()
    pixel_increment = 1
    Minecraft_status = colored("DESACTIVADO", 'red')

    def __init__(self, box_constant=250, collect_data=False, mouse_delay=0.0001, debug=False):
        self.box_constant = box_constant
        self.collect_data = collect_data
        self.mouse_delay = mouse_delay
        self.debug = debug
        with open("config/config.json") as f:
            Minecraft.sens_config = json.load(f)
        print("[INFO] Cargando el modelo de red")
        self.model = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt', force_reload=False)
        if torch.cuda.is_available():
            print(colored("CUDA ACTIVADO", "green"))
        else:
            print(colored("CUDA DESACTIVADO", "red"))
        self.model.conf = 0.75
        self.model.iou = 0.75
        print("\n[INFO] Presiona 'F1' PARA ACTIVAR/DESACTIVAR el sistema\n[INFO] Presiona 'F2' para salir\n[INFO] Presiona 'F3' para activar/desactivar el overlay")

    @staticmethod
    def update_status_Minecraft():
        if Minecraft.Minecraft_status == colored("ACTIVADO", 'green'):
            Minecraft.Minecraft_status = colored("DESACTIVADO", 'red')
        else:
            Minecraft.Minecraft_status = colored("ACTIVADO", 'green')
        print(f"[!] [{Minecraft.Minecraft_status}]")

    @staticmethod
    def left_click():
        ctypes.windll.user32.mouse_event(0x0002)
        Minecraft.sleep(0.0001)
        ctypes.windll.user32.mouse_event(0x0004)

    @staticmethod
    def sleep(duration, get_now=time.perf_counter):
        if duration == 0: return
        now = get_now()
        end = now + duration
        while now < end:
            now = get_now()

    @staticmethod
    def is_Minecraft_enabled():
        return True if Minecraft.Minecraft_status == colored("ACTIVADO", 'green') else False

    @staticmethod
    def is_targeted():
        return True if win32api.GetKeyState(0x02) in (-127, -128) else False

    @staticmethod
    def is_target_locked(x, y):
        threshold = 5
        return True if 960 - threshold <= x <= 960 + threshold and 540 - threshold <= y <= 540 + threshold else False

    def move_crosshair(self, x, y):
        if Minecraft.is_targeted():
            scale = Minecraft.sens_config["targeting_scale"]
        else:
            return
        if self.debug: start_time = time.perf_counter()
        for rel_x, rel_y in Minecraft.interpolate_coordinates_from_center((x, y), scale):
            Minecraft.ii_.mi = MouseInput(rel_x, rel_y, 0, 0x0001, 0, ctypes.pointer(Minecraft.extra))
            input_obj = Input(ctypes.c_ulong(0), Minecraft.ii_)
            ctypes.windll.user32.SendInput(1, ctypes.byref(input_obj), ctypes.sizeof(input_obj))
            if not self.debug: Minecraft.sleep(self.mouse_delay)
        if self.debug:
            print(f"TIME: {time.perf_counter() - start_time}")
            print("DEBUG: SLEEPING FOR 1 SECOND")
            time.sleep(1)

    @staticmethod
    def interpolate_coordinates_from_center(absolute_coordinates, scale):
        diff_x = (absolute_coordinates[0] - 960) * scale / Minecraft.pixel_increment
        diff_y = (absolute_coordinates[1] - 540) * scale / Minecraft.pixel_increment
        length = int(math.dist((0, 0), (diff_x, diff_y)))
        if length == 0: return
        unit_x = (diff_x / length) * Minecraft.pixel_increment
        unit_y = (diff_y / length) * Minecraft.pixel_increment
        x = y = sum_x = sum_y = 0
        for k in range(0, length):
            sum_x += x
            sum_y += y
            x, y = round(unit_x * k - sum_x), round(unit_y * k - sum_y)
            yield x, y

    def start(self):
        print("[INFO] Captura de pantalla inicial")
        half_screen_width = ctypes.windll.user32.GetSystemMetrics(0) / 2
        half_screen_height = ctypes.windll.user32.GetSystemMetrics(1) / 2
        detection_box = {
            'left': int(half_screen_width - self.box_constant // 2),
            'top': int(half_screen_height - self.box_constant // 2),
            'width': int(self.box_constant),
            'height': int(self.box_constant)
        }       
        prev_frame_time = time.time()
        while True:
            new_frame_time = time.time() 
            if not Minecraft.is_Minecraft_enabled():
                time.sleep(0.1)
                continue
            frame = np.array(Minecraft.screen.grab(detection_box))
            with torch.no_grad():
                results = self.model(frame)
            if len(results.xyxy[0]) != 0:
                for *box, conf, cls in results.xyxy[0]:
                    x1y1 = [int(x.item()) for x in box[:2]]
                    x2y2 = [int(x.item()) for x in box[2:]]
                    relative_head_X, relative_head_Y = int((x1y1[0] + x2y2[0]) / 2), int((x1y1[1] + x2y2[1]) / 2 - (x2y2[1] - x1y1[1]) / 2.7)
                    absolute_head_X = relative_head_X + detection_box['left']
                    absolute_head_Y = relative_head_Y + detection_box['top']
                    confidence_percentage = conf.item() * 100
                    if Minecraft.is_target_locked(absolute_head_X, absolute_head_Y):
                        cv2.putText(frame, f"Lockeado ({confidence_percentage:.2f}%)", (x1y1[0] + 40, x1y1[1]), cv2.FONT_HERSHEY_DUPLEX, 0.5, (115, 244, 113), 2)
                    else:
                        cv2.putText(frame, f"Objetivo ({confidence_percentage:.2f}%)", (x1y1[0] + 40, x1y1[1]), cv2.FONT_HERSHEY_DUPLEX, 0.5, (115, 113, 244), 2)

                    if Minecraft.is_Minecraft_enabled():
                        self.move_crosshair(absolute_head_X, absolute_head_Y)
            fps = 1 / (new_frame_time - prev_frame_time) if (new_frame_time - prev_frame_time) > 0 else 0
            prev_frame_time = new_frame_time

            cv2.imshow("Kayy IA", frame)
            if cv2.waitKey(1) & 0xFF == ord('0'):
                break

    @staticmethod
    def clean_up():
        print("\n[INFO] Cerrando el sistema...")
        Minecraft.screen.close()
        os._exit(0)
        
def setup():
    path = "config"
    if not os.path.exists(path):
        os.makedirs(path)
    print("[Kayy IA] Configure la sensibilidad de los ejes X e Y")
    xy_sens = float(input("Sensibilidad del eje X e Y (Fortnite): "))
    targeting_sens = float(input("Sensibilidad de puntería (Fortnite): "))

    sensitivity_settings = {
        "xy_sens": xy_sens,
        "targeting_sens": targeting_sens,
        "xy_scale": 10 / xy_sens,
        "targeting_scale": 1000 / (targeting_sens * xy_sens)
    }
    with open('config/config.json', 'w') as outfile:
        json.dump(sensitivity_settings, outfile)
    print("[INFO] Configuración de sensibilidad completa")

# Variables globales para gestionar el overlay
overlay_process = None
overlay_active = False

def toggle_overlay():
    global overlay_process
    global overlay_active
    if overlay_active:
        if overlay_process is not None and overlay_process.is_alive():
            overlay_process.terminate()
            overlay_process.join()
            print("[INFO] Overlay desactivado.")
        overlay_active = False
    else:
        overlay_process = multiprocessing.Process(target=run_overlay, daemon=True)
        overlay_process.start()
        print("[INFO] Overlay activado.")
        overlay_active = True

def on_release(key):
    if key == keyboard.Key.f1:
        Minecraft.update_status_Minecraft()
    elif key == keyboard.Key.f2:
        Minecraft.clean_up()
    elif key == keyboard.Key.f3:
        toggle_overlay()

if __name__ == "__main__":

    os.system('cls' if os.name == 'nt' else 'clear')
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    if not os.path.exists("config/config.json"):
        print("[!] La configuración de sensibilidad no está establecida")
        setup()
    listener = keyboard.Listener(on_release=on_release)
    listener.start()
    lunar = Minecraft(collect_data="collect_data" in sys.argv)
    try:
        lunar.start()
    except KeyboardInterrupt:
        Minecraft.clean_up()
    finally:
        if overlay_process is not None:
            overlay_process.terminate()
        listener.stop()
