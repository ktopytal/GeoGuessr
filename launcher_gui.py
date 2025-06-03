import tkinter as tk
from tkinter import ttk, messagebox, Menu
import subprocess
import threading
import time
import sys
import os
import datetime
from queue import Queue
import socket 
import requests
import json
import shutil # Do kopiowania plików (dla aktualizacji)

# --- Wersja Aplikacji ---
# WAŻNE: Zmieniaj tę wartość, gdy wydajesz "nową" wersję launchera
APP_VERSION = "1.1.0" 

# --- Konfiguracja Ścieżek ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
BACKEND_DIR = os.path.join(BASE_DIR, 'geoguessr_backend')
FRONTEND_SCRIPT_NAME = 'geoguessr_game.py'
BACKEND_SCRIPT_NAME = 'app.py'
FRONTEND_CONFIG_PATH = os.path.join(BASE_DIR, 'config.py') 
LAUNCHER_SCRIPT_PATH = os.path.join(BASE_DIR, os.path.basename(__file__))

# --- Konfiguracja Aktualizatora ---
# Zmień na prawdziwy URL, gdzie będziesz hostować plik z wersją i pliki aktualizacji
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/ktopytal/GeoGuessr/main/latest_launcher_version.txt" # Przykład
UPDATE_DOWNLOAD_URL = "https://raw.githubusercontent.com/ktopytal/GeoGuessr/main/launcher_gui.py" # Przykład: nowy plik launchera

# --- Konfiguracja uruchamiania ---
PYTHON_EXECUTABLE = 'python3' 
BACKEND_PORT = 5000 
BACKEND_STARTUP_DELAY = 7 
CONNECTION_CHECK_INTERVAL = 1000 # Interwał odświeżania statusu backendu (ms)

class AppLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"GeoGuessr Launcher v{APP_VERSION}")
        self.geometry("800x750") # Większe okno dla lepszego UI
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing) 
        self.configure(bg="#ECEFF1") 

        # Procesy
        self.backend_process = None
        self.frontend_process = None
        self.log_queue = Queue() 

        # Style dla ttk
        self.setup_styles()

        self.frontend_config = self._load_frontend_config() 
        global BACKEND_PORT 
        BACKEND_PORT = self.frontend_config.get("BACKEND_PORT", 5000) 

        self.create_widgets()
        self.create_menu()
        
        self.process_logs_thread = threading.Thread(target=self.process_logs, daemon=True)
        self.process_logs_thread.start()

        self.check_backend_status_periodically()
        self.check_for_updates() # Sprawdź aktualizacje przy starcie

    def setup_styles(self):
        """Konfiguruje nowoczesne style dla widżetów Tkinter."""
        self.style = ttk.Style(self)
        self.style.theme_use("clam") 
        
        # General Button Style
        self.style.configure("TButton", font=("Inter", 10, "bold"), padding=10, relief="flat", background="#3F51B5", foreground="white", borderwidth=0) # Głęboki błękit
        self.style.map("TButton", 
                       background=[('active', '#5C6BC0'), ('disabled', '#B0BEC5')],
                       foreground=[('disabled', '#F5F5F5')])
        
        # Accent Button (for Start/Save)
        self.style.configure("Accent.TButton", background="#4CAF50") # Zieleń
        self.style.map("Accent.TButton", 
                       background=[('active', '#66BB6A'), ('disabled', '#B0BEC5')])

        # Danger Button (for Stop/Exit)
        self.style.configure("Danger.TButton", background="#F44336") # Czerwień
        self.style.map("Danger.TButton", 
                       background=[('active', '#E57373'), ('disabled', '#B0BEC5')])
        
        self.style.configure("TLabel", font=("Roboto", 10), background="#ECEFF1", foreground="#263238")
        self.style.configure("TLabelFrame", font=("Roboto", 11, "bold"), background="#ECEFF1", foreground="#263238", relief="flat", padding=[10, 5, 10, 10])
        self.style.configure("TLabelframe.Label", font=("Roboto", 11, "bold"), background="#ECEFF1", foreground="#263238") # Tytuł ramki
        
        self.style.configure("TEntry", fieldbackground="#FFFFFF", foreground="#263238", borderwidth=1, relief="solid", padding=5)

        # Status Labels
        self.style.configure("Green.TLabel", background="#E8F5E9", foreground="#2E7D32", font=("Roboto", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Red.TLabel", background="#FFEBEE", foreground="#C62828", font=("Roboto", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Yellow.TLabel", background="#FFFDE7", foreground="#FF8F00", font=("Roboto", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Blue.TLabel", background="#E3F2FD", foreground="#1565C0", font=("Roboto", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Gray.TLabel", background="#CFD8DC", foreground="#37474F", font=("Roboto", 10, "bold"), padding=5, relief="flat") 
        
        # Progressbar
        self.style.configure("TProgressbar", thickness=15)
        self.style.configure("green.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#66BB6A")
        self.style.configure("blue.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#42A5F5")
        self.style.configure("red.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#EF5350")


    def _load_frontend_config(self):
        """Wczytuje konfigurację frontendu z pliku JSON."""
        print(f"[{datetime.datetime.now()}] [LAUNCHER] Próbuję wczytać konfigurację frontendu z: {FRONTEND_CONFIG_PATH}")
        if not os.path.exists(FRONTEND_CONFIG_PATH):
            messagebox.showerror("Błąd Konfiguracji", f"Brak pliku konfiguracyjnego frontendu: {FRONTEND_CONFIG_PATH}\n"
                                                      "Upewnij się, że plik config.py istnieje i jest w formacie JSON.")
            print(f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Brak pliku konfiguracyjnego frontendu.")
            sys.exit(1)
        try:
            with open(FRONTEND_CONFIG_PATH, 'r') as f:
                config_data = json.load(f)
            print(f"[{datetime.datetime.now()}] [LAUNCHER_SUCCESS] Konfiguracja frontendu wczytana pomyślnie.")
            return config_data
        except json.JSONDecodeError as e:
            messagebox.showerror("Błąd Konfiguracji", f"Błąd w pliku konfiguracyjnym frontendu (JSON Syntax Error):\n{e}\n"
                                                      "Sprawdź format JSON w config.py.")
            print(f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Błąd parsowania JSON w config.py: {e}")
            sys.exit(1)
        except Exception as e:
            messagebox.showerror("Błąd Konfiguracji", f"Nie udało się wczytać pliku konfiguracyjnego frontendu:\n{e}")
            print(f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Nie udało się wczytać config.py: {e}")
            sys.exit(1)

    def _save_frontend_config(self):
        """Zapisuje bieżącą konfigurację frontendu do pliku JSON."""
        print(f"[{datetime.datetime.now()}] [LAUNCHER] Próbuję zapisać konfigurację frontendu do: {FRONTEND_CONFIG_PATH}")
        try:
            with open(FRONTEND_CONFIG_PATH, 'w') as f:
                json.dump(self.frontend_config, f, indent=4) 
            print(f"[{datetime.datetime.now()}] [LAUNCHER_SUCCESS] Konfiguracja frontendu zapisana pomyślnie.")
            return True
        except Exception as e:
            messagebox.showerror("Błąd Zapisu", f"Nie udało się zapisać pliku konfiguracyjnego frontendu:\n{e}")
            print(f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Nie udało się zapisać config.py: {e}")
            return False

    def create_menu(self):
        """Tworzy pasek menu."""
        menubar = Menu(self)
        self.config(menu=menubar)

        settings_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ustawienia", menu=settings_menu)
        settings_menu.add_command(label="Port Backendu", command=self.show_port_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="Sprawdź aktualizacje", command=self.check_for_updates_manual)
        settings_menu.add_separator()
        settings_menu.add_command(label="O programie", command=self.show_about_dialog)

    def show_port_settings(self):
        """Wyświetla okno dialogowe do zmiany portu backendu."""
        settings_window = Toplevel(self)
        settings_window.title("Ustawienia Portu Backendu")
        settings_window.geometry("350x180") # Większe okno ustawień
        settings_window.transient(self)
        settings_window.grab_set()
        settings_window.configure(bg="#ECEFF1")

        ttk.Label(settings_window, text="Port Backendu:", font=("Roboto", 11, "bold")).pack(pady=10)
        self.port_entry = ttk.Entry(settings_window, width=20, font=("Roboto", 10))
        self.port_entry.insert(0, str(BACKEND_PORT)) 
        self.port_entry.pack(pady=5)

        ttk.Label(settings_window, text="Wymaga restartu launchera i backendu", font=("Roboto", 9), foreground="#757575").pack(pady=5)

        def save_port():
            global BACKEND_PORT
            try:
                new_port = int(self.port_entry.get())
                if not (1024 <= new_port <= 65535):
                    messagebox.showerror("Błąd", "Port musi być liczbą całkowitą z zakresu 1024-65535.")
                    return
                
                if new_port != BACKEND_PORT:
                    BACKEND_PORT = new_port
                    self.frontend_config["BACKEND_PORT"] = new_port
                    if self._save_frontend_config():
                        messagebox.showinfo("Zapisano", f"Port backendu zmieniono na {new_port}.\n"
                                                        "Zmiany zostaną zastosowane po ponownym uruchomieniu launchera.")
                        self.port_status_label.config(text=f"Port: {BACKEND_PORT}", style="Blue.TLabel")
                    else:
                        BACKEND_PORT = self.frontend_config.get("BACKEND_PORT", 5000) 
                settings_window.destroy()
            except ValueError:
                messagebox.showerror("Błąd", "Port musi być poprawną liczbą.")

        ttk.Button(settings_window, text="Zapisz", command=save_port, style="Accent.TButton").pack(pady=10)

    def show_about_dialog(self):
        """Wyświetla okno 'O programie'."""
        messagebox.showinfo("O programie", f"GeoGuessr Launcher v{APP_VERSION}\n\n"
                                           "Autor: deloskiyt\n\n"
                                           "Projekt edukacyjny, uruchamiający grę GeoGuessr "
                                           "z własnym backendem i lokalnymi obrazami.\n"
                                           "Zbudowany z miłości do kodowania i geografii w 2025 roku.")

    def create_widgets(self):
        # Nagłówek
        header_frame = ttk.Frame(self, padding=15, style="TFrame")
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="GeoGuessr Launcher", font=("Arial", 22, "bold"), foreground="#263238").pack(pady=5)

        # Sekcja Statusu Serwera
        status_frame = ttk.LabelFrame(self, text="Status Serwera Backend", padding=15)
        status_frame.pack(padx=20, pady=10, fill=tk.X)
        
        status_info_frame = ttk.Frame(status_frame)
        status_info_frame.pack(fill=tk.X)
        self.backend_status_label = ttk.Label(status_info_frame, text="Backend: Nie uruchomiony", style="Yellow.TLabel")
        self.backend_status_label.pack(side=tk.LEFT, padx=5, pady=2)
        self.port_status_label = ttk.Label(status_info_frame, text=f"Port: {BACKEND_PORT}", style="Yellow.TLabel")
        self.port_status_label.pack(side=tk.LEFT, padx=15, pady=2)
        
        self.check_port_button = ttk.Button(status_info_frame, text="Sprawdź Port", command=self.check_port_availability)
        self.check_port_button.pack(side=tk.RIGHT)

        # Sekcja Licencji
        license_frame = ttk.LabelFrame(self, text="Zarządzanie Licencją", padding=15)
        license_frame.pack(padx=20, pady=10, fill=tk.X)

        ttk.Label(license_frame, text="Klucz Licencyjny:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.license_entry = ttk.Entry(license_frame, width=50)
        self.license_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        current_license_key = self.frontend_config.get("LICENSE_KEY_FOR_SERVER_CHECK", "")
        self.license_entry.insert(0, current_license_key)

        self.save_license_button = ttk.Button(license_frame, text="Zapisz Klucz", command=self.save_license_key, style="Accent.TButton")
        self.save_license_button.grid(row=0, column=2, padx=5, pady=5)
        license_frame.columnconfigure(1, weight=1) 

        # Sekcja Postępu Uruchamiania
        progress_frame = ttk.LabelFrame(self, text="Status Uruchamiania", padding=15)
        progress_frame.pack(padx=20, pady=10, fill=tk.X)
        self.startup_progress_label = ttk.Label(progress_frame, text="Gotowy do uruchomienia", style="Blue.TLabel")
        self.startup_progress_label.pack(pady=5)
        self.startup_progressbar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate", style="blue.Horizontal.TProgressbar")
        self.startup_progressbar.pack(pady=10)


        # Przyciski kontrolne
        button_frame = ttk.Frame(self, padding=15)
        button_frame.pack(pady=10)

        self.start_button = ttk.Button(button_frame, text="Uruchom GeoGuessr", command=self.start_app_thread, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.stop_button = ttk.Button(button_frame, text="Zatrzymaj wszystko", command=self.stop_app_thread, state=tk.DISABLED, style="Danger.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=10)

        # Ramka na logi
        log_frame = ttk.LabelFrame(self, text="Logi Aplikacji", padding=15)
        log_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, state="disabled", wrap="word", bg="black", fg="white", font=("Courier New", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Tagowanie logów (poprawione tagi dla spójności z logerem Pythona)
        self.log_text.tag_config("INFO", foreground="#ADD8E6") 
        self.log_text.tag_config("DEBUG", foreground="#A9A9A9")
        self.log_text.tag_config("SUCCESS", foreground="#90EE90")
        self.log_text.tag_config("WARNING", foreground="#FFD700")
        self.log_text.tag_config("ERROR", foreground="#FF6347")
        self.log_text.tag_config("CRITICAL", foreground="#FF4500")
        self.log_text.tag_config("LAUNCHER", foreground="#00CED1")
        self.log_text.tag_config("BACKEND", foreground="#FFB6C1")
        self.log_text.tag_config("FRONTEND", foreground="#FAFAD2")
        self.log_text.tag_config("LICENCJA", foreground="#DA70D6")


    def append_log(self, message, tag=None):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END) 
        self.log_text.config(state="disabled")

    def process_logs(self):
        """Pobiera logi z kolejki i wyświetla je w polu tekstowym."""
        while True:
            try:
                message, tag = self.log_queue.get(timeout=0.1)
                self.append_log(message, tag)
            except Exception:
                pass 
            time.sleep(0.01)

    def _get_log_tag(self, line):
        """Pomocnicza funkcja do określania tagu na podstawie zawartości linii logu."""
        if "[FRONTEND_INFO]" in line: return "FRONTEND"
        elif "[FRONTEND_BŁĄD]" in line: return "ERROR"
        elif "[FRONTEND_SUKCES]" in line: return "SUCCESS"
        elif "[FRONTEND_LICENCJA]" in line: return "LICENCJA"
        elif "[FRONTEND_KRYTYCZNY]" in line: return "CRITICAL"
        
        elif "[BACKEND_INFO]" in line: return "BACKEND"
        elif "[BACKEND_DEBUG]" in line: return "DEBUG"
        elif "[BACKEND_SUKCES]" in line: return "SUCCESS"
        elif "[BACKEND_BŁĄD]" in line: return "ERROR"
        elif "[BACKEND_LICENCJA]" in line: return "LICENCJA"
        elif "[BACKEND_KRYTYCZNY]" in line: return "CRITICAL"

        elif "[LAUNCHER]" in line: return "LAUNCHER"
        elif "[LAUNCHER_ERROR]" in line: return "ERROR"
        elif "[LAUNCHER_WARNING]" in line: return "WARNING"
        
        elif "[INFO]" in line: return "INFO" 
        elif "[WARNING]" in line: return "WARNING"
        elif "[ERROR]" in line: return "ERROR"
        elif "[CRITICAL]" in line: return "CRITICAL"
        
        return None 

    def start_app_thread(self):
        """Uruchamia procesy w osobnym wątku."""
        self.start_button.config(state=tk.DISABLED, style="TButton") # Zwykły styl
        self.stop_button.config(state=tk.DISABLED, style="TButton") # Zwykły styl
        self.startup_progress_label.config(text="Rozpoczynam uruchamianie...", style="Blue.TLabel")
        self.startup_progressbar.config(mode="indeterminate", style="blue.Horizontal.TProgressbar")
        self.startup_progressbar.start() # Rozpocznij animację paska postępu
        threading.Thread(target=self._start_app_logic, daemon=True).start()

    def _start_app_logic(self):
        """Logika uruchamiania backendu i frontendu."""
        self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Startowanie aplikacji GeoGuessr...", "LAUNCHER"))
        
        self.startup_progress_label.config(text=f"Sprawdzam dostępność portu {BACKEND_PORT}...", style="Blue.TLabel")
        if not self.is_port_available(BACKEND_PORT):
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Port {BACKEND_PORT} jest już używany. Nie mogę uruchomić backendu.", "ERROR"))
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Proszę zamknąć inną aplikację używającą tego portu lub zmienić port w config.py backendu.", "ERROR"))
            self.start_button.config(state=tk.NORMAL, style="Accent.TButton") # Przywróć styl
            self.stop_button.config(state=tk.DISABLED, style="Danger.TButton") # Przywróć styl
            self.backend_status_label.config(text="BŁĄD PORTU", style="Red.TLabel")
            self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Zajęty)", style="Red.TLabel")
            self.startup_progress_label.config(text="Błąd: Port zajęty", style="Red.TLabel")
            self.startup_progressbar.stop() # Zatrzymaj animację
            self.startup_progressbar.config(mode="determinate", value=0, style="red.Horizontal.TProgressbar") # Pokaż błąd
            return

        self.startup_progress_label.config(text="Uruchamiam backend...", style="Blue.TLabel")
        self.backend_process = self._launch_process(
            "backend Flask", 
            os.path.join(BACKEND_DIR, BACKEND_SCRIPT_NAME), 
            cwd=BACKEND_DIR
        )
        if not self.backend_process: 
            self.startup_progress_label.config(text="Błąd: Backend nie uruchomił się", style="Red.TLabel")
            self.startup_progressbar.stop()
            self.startup_progressbar.config(mode="determinate", value=0, style="red.Horizontal.TProgressbar")
            return

        self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Czekam {BACKEND_STARTUP_DELAY} sekund na uruchomienie backendu...", "LAUNCHER"))
        self.startup_progress_label.config(text=f"Czekam {BACKEND_STARTUP_DELAY}s na backend...", style="Blue.TLabel")
        # Symulacja paska postępu deterministycznego
        for i in range(BACKEND_STARTUP_DELAY * 10): # Co 0.1s
            self.startup_progressbar.config(mode="determinate", value=(i+1) * (100 / (BACKEND_STARTUP_DELAY * 10)))
            time.sleep(0.1)
        
        self.startup_progress_label.config(text="Sprawdzam, czy backend nasłuchuje...", style="Blue.TLabel")
        if not self.is_backend_listening():
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Backend nie nasłuchuje na porcie {BACKEND_PORT} po uruchomieniu.", "ERROR"))
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Sprawdź logi backendu pod kątem błędów uruchamiania.", "ERROR"))
            self.stop_app_thread() 
            self.start_button.config(state=tk.NORMAL, style="Accent.TButton")
            self.stop_button.config(state=tk.DISABLED, style="Danger.TButton")
            self.backend_status_label.config(text="BŁĄD STARTU", style="Red.TLabel")
            self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Problem)", style="Red.TLabel")
            self.startup_progress_label.config(text="Błąd: Backend nie nasłuchuje", style="Red.TLabel")
            self.startup_progressbar.stop()
            self.startup_progressbar.config(mode="determinate", value=0, style="red.Horizontal.TProgressbar")
            return

        self.startup_progress_label.config(text="Uruchamiam frontend...", style="Blue.TLabel")
        self.frontend_process = self._launch_process(
            "frontend Tkinter", 
            os.path.join(BASE_DIR, FRONTEND_SCRIPT_NAME), 
            cwd=BASE_DIR 
        )
        if not self.frontend_process:
            self.stop_app_thread() 
            self.startup_progress_label.config(text="Błąd: Frontend nie uruchomił się", style="Red.TLabel")
            self.startup_progressbar.stop()
            self.startup_progressbar.config(mode="determinate", value=0, style="red.Horizontal.TProgressbar")
            return

        self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Frontend jest uruchomiony. Zamknij okno gry, aby zakończyć działanie backendu.", "LAUNCHER"))
        self.stop_button.config(state=tk.NORMAL, style="Danger.TButton") 
        self.start_button.config(state=tk.DISABLED, style="TButton")
        self.startup_progress_label.config(text="GeoGuessr uruchomiony!", style="Green.TLabel")
        self.startup_progressbar.stop()
        self.startup_progressbar.config(mode="determinate", value=100, style="green.Horizontal.TProgressbar")


        self.frontend_process.wait() 
        self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Frontend został zamknięty.", "LAUNCHER"))
        self.stop_app_thread() 

    def _launch_process(self, name, script_path, cwd=None):
        """Pomocnicza funkcja do uruchamiania pojedynczego procesu."""
        try:
            process = subprocess.Popen(
                [PYTHON_EXECUTABLE, script_path], 
                cwd=cwd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True, 
                bufsize=1
            )
            threading.Thread(target=self._read_process_output, args=(process, name), daemon=True).start()
            return process
        except FileNotFoundError:
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Interpreter '{PYTHON_EXECUTABLE}' nie znaleziony dla {name}.", "ERROR"))
            messagebox.showerror("Błąd Uruchamiania", f"Interpreter '{PYTHON_EXECUTABLE}' nie znaleziony dla {name}.")
            return None
        except Exception as e:
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Nie udało się uruchomić {name}: {e}", "ERROR"))
            messagebox.showerror("Błąd Uruchamiania", f"Nie udało się uruchomić {name}: {e}")
            return None

    def _read_process_output(self, process, name):
        """Czyta wyjście procesu i umieszcza je w kolejce logów."""
        for line in process.stdout:
            tag = self._get_log_tag(line) 
            self.log_queue.put((line.strip(), tag))

    def stop_app_thread(self):
        """Zatrzymuje procesy w osobnym wątku."""
        self.start_button.config(state=tk.DISABLED, style="TButton")
        self.stop_button.config(state=tk.DISABLED, style="TButton")
        self.startup_progress_label.config(text="Zatrzymuję procesy...", style="Yellow.TLabel")
        self.startup_progressbar.config(mode="indeterminate", style="yellow.Horizontal.TProgressbar")
        self.startup_progressbar.start()
        self.backend_status_label.config(text="Zatrzymuję...", style="Yellow.TLabel")
        self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Zatrzymuję...)", style="Yellow.TLabel")
        threading.Thread(target=self._stop_app_logic, daemon=True).start()

    def _stop_app_logic(self):
        """Logika zamykania backendu i frontendu."""
        self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Zamykanie procesów...", "LAUNCHER"))
        
        self.terminate_process(self.frontend_process, "frontend")
        self.terminate_process(self.backend_process, "backend")
        
        self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Wszystkie procesy zostały zamknięte.", "LAUNCHER"))
        self.backend_process = None
        self.frontend_process = None
        self.start_button.config(state=tk.NORMAL, style="Accent.TButton")
        self.stop_button.config(state=tk.DISABLED, style="Danger.TButton")
        self.backend_status_label.config(text="Nie uruchomiony", style="Yellow.TLabel")
        self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Wolny)", style="Green.TLabel")
        self.startup_progress_label.config(text="Gotowy do uruchomienia", style="Blue.TLabel")
        self.startup_progressbar.stop()
        self.startup_progressbar.config(mode="determinate", value=0, style="blue.Horizontal.TProgressbar")


    def terminate_process(self, process, name):
        """Pomocnicza funkcja do zamykania pojedynczego procesu."""
        if process and process.poll() is None:
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Próba zakończenia procesu {name} (PID: {process.pid})...", "LAUNCHER"))
            try:
                process.terminate()
                process.wait(timeout=5)
                if process.poll() is None:
                    self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_WARNING] Proces {name} nie zamknął się czysto, zabijam go (PID: {process.pid}).", "WARNING"))
                    process.kill()
            except Exception as e:
                self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Błąd podczas zamykania {name}: {e}", "ERROR"))

    def on_closing(self):
        """Obsługa zamykania okna launchera."""
        if messagebox.askokcancel("Zamknij Launcher", "Czy na pewno chcesz zamknąć GeoGuessr Launcher i wszystkie uruchomione procesy?"):
            self.stop_app_thread() 
            self.after(2000, self.destroy) 

    def is_port_available(self, port):
        """Sprawdza, czy dany port jest wolny."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except socket.error: 
                return False

    def is_backend_listening(self):
        """Sprawdza, czy backend nasłuchuje na swoim porcie poprzez zapytanie HTTP."""
        try:
            response = requests.get(f"http://127.0.0.1:{BACKEND_PORT}/", timeout=1) 
            return response.status_code == 200
        except requests.exceptions.RequestException: 
            return False

    def check_backend_status_periodically(self):
        """Sprawdza status backendu i aktualizuje etykietę co 2 sekundy."""
        if self.backend_process and self.backend_process.poll() is None: 
            if self.is_backend_listening():
                self.backend_status_label.config(text="Backend: Aktywny ✅", style="Green.TLabel") # Dodano ikonę
                self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Nasłuchuje)", style="Green.TLabel")
            else:
                self.backend_status_label.config(text="Backend: Uruchomiony, ale nie nasłuchuje ⚠️", style="Yellow.TLabel") # Dodano ikonę
                self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Problem)", style="Red.TLabel")
        else: # Proces nie uruchomiony lub zakończył się
            self.backend_status_label.config(text="Backend: Nie uruchomiony ❌", style="Yellow.TLabel") # Dodano ikonę
            if self.is_port_available(BACKEND_PORT):
                self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Wolny)", style="Green.TLabel") 
            else:
                self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Zajęty)", style="Red.TLabel")
                
        self.after(CONNECTION_CHECK_INTERVAL, self.check_backend_status_periodically) 
        
    def check_port_availability(self):
        """Funkcja wywoływana przyciskiem 'Sprawdź Port'."""
        if self.is_port_available(BACKEND_PORT):
            messagebox.showinfo("Status Portu", f"Port {BACKEND_PORT} jest wolny.")
            self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Wolny)", style="Green.TLabel")
        else:
            messagebox.showerror("Status Portu", f"Port {BACKEND_PORT} jest już używany przez inną aplikację.")
            self.port_status_label.config(text=f"Port: {BACKEND_PORT} (Zajęty)", style="Red.TLabel")

    def save_license_key(self):
        """Zapisuje nowy klucz licencyjny do pliku config.py frontendu."""
        new_key = self.license_entry.get().strip()
        if not new_key:
            messagebox.showwarning("Błąd Licencji", "Klucz licencyjny nie może być pusty.")
            return

        self.frontend_config["LICENSE_KEY_FOR_SERVER_CHECK"] = new_key
        if self._save_frontend_config():
            messagebox.showinfo("Zapisano", "Klucz licencyjny został zapisany.\n"
                                          "Uruchom ponownie grę, aby zastosować zmiany.")
            self.append_log(f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Nowy klucz licencyjny zapisany.", "LAUNCHER")
        else:
            messagebox.showerror("Błąd", "Nie udało się zapisać klucza licencyjnego.")
            self.append_log(f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Nie udało się zapisać klucza licencyjnego.", "ERROR")

    def save_port_settings(self, new_port):
        """Zapisuje zmieniony port backendu do config.py frontendu."""
        global BACKEND_PORT
        try:
            new_port_int = int(new_port)
            if not (1024 <= new_port_int <= 65535):
                messagebox.showerror("Błąd", "Port musi być liczbą całkowitą z zakresu 1024-65535.")
                return False
            
            if new_port_int != BACKEND_PORT:
                BACKEND_PORT = new_port_int
                self.frontend_config["BACKEND_PORT"] = new_port_int
                if self._save_frontend_config():
                    messagebox.showinfo("Zapisano", f"Port backendu zmieniono na {new_port_int}.\n"
                                                    "Zmiany zostaną zastosowane po ponownym uruchomieniu launchera.")
                    self.port_status_label.config(text=f"Port: {BACKEND_PORT}", style="Blue.TLabel")
                    self.append_log(f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Port backendu zmieniono na {new_port_int}.", "LAUNCHER")
                    return True
                else:
                    self.append_log(f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] Nie udało się zapisać nowego portu.", "ERROR")
                    return False
            return True 
        except ValueError:
            messagebox.showerror("Błąd", "Port musi być poprawną liczbą.")
            return False

    def check_for_updates_manual(self):
        """Funkcja wywoływana ręcznie z menu: Sprawdź aktualizacje."""
        self.append_log(f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Ręczne sprawdzanie aktualizacji...", "LAUNCHER")
        threading.Thread(target=self._perform_update_check, args=(True,), daemon=True).start()

    def check_for_updates(self):
        """Automatyczne sprawdzanie aktualizacji przy starcie launchera."""
        self.append_log(f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Automatyczne sprawdzanie aktualizacji (bieżąca wersja: {APP_VERSION})...", "LAUNCHER")
        threading.Thread(target=self._perform_update_check, args=(False,), daemon=True).start()

    def _perform_update_check(self, manual_check=False):
        """Logika sprawdzania aktualizacji."""
        try:
            response = requests.get(UPDATE_CHECK_URL, timeout=5)
            response.raise_for_status()
            latest_version = response.text.strip()
            
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Znaleziono najnowszą wersję online: {latest_version}", "LAUNCHER"))

            if self._compare_versions(APP_VERSION, latest_version):
                if messagebox.askyesno("Dostępna Aktualizacja", 
                                       f"Dostępna jest nowsza wersja launchera: {latest_version}.\n"
                                       f"Twoja wersja: {APP_VERSION}.\n\n"
                                       "Czy chcesz pobrać i zainstalować aktualizację teraz?\n"
                                       "(Wymagany restart launchera)"):
                    self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Rozpoczynam pobieranie aktualizacji...", "LAUNCHER"))
                    self._download_and_install_update(latest_version)
                else:
                    self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Aktualizacja odrzucona przez użytkownika.", "LAUNCHER"))
            else:
                if manual_check:
                    messagebox.showinfo("Aktualizacja", f"Używasz najnowszej wersji ({APP_VERSION}).")
                self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_INFO] Używasz już najnowszej wersji: {APP_VERSION}", "LAUNCHER"))

        except requests.exceptions.RequestException as e:
            error_msg = f"Błąd połączenia podczas sprawdzania aktualizacji: {e}"
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] {error_msg}", "ERROR"))
            if manual_check:
                messagebox.showerror("Błąd Aktualizacji", error_msg + "\nSprawdź połączenie z internetem.")
        except Exception as e:
            error_msg = f"Nieoczekiwany błąd podczas sprawdzania aktualizacji: {e}"
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] {error_msg}", "ERROR"))
            if manual_check:
                messagebox.showerror("Błąd Aktualizacji", error_msg)

    def _compare_versions(self, current_v, latest_v):
        """Porównuje numery wersji (np. '1.0.0' vs '1.1.0')."""
        current_parts = list(map(int, current_v.split('.')))
        latest_parts = list(map(int, latest_v.split('.')))
        
        # Upewnij się, że obie listy mają tę samą długość (uzupełnij zerami)
        max_len = max(len(current_parts), len(latest_parts))
        current_parts += [0] * (max_len - len(current_parts))
        latest_parts += [0] * (max_len - len(latest_parts))

        return latest_parts > current_parts # Zwraca True, jeśli latest_v jest nowsza

    def _download_and_install_update(self, latest_version):
        """Pobiera i instaluje nową wersję launchera."""
        try:
            # Pobierz nową wersję launchera
            response = requests.get(UPDATE_DOWNLOAD_URL, timeout=10)
            response.raise_for_status()
            new_launcher_code = response.text

            # Zapisz tymczasowo nową wersję
            temp_launcher_path = LAUNCHER_SCRIPT_PATH + ".new"
            with open(temp_launcher_path, 'w') as f:
                f.write(new_launcher_code)
            
            # Stwórz backup obecnej wersji
            backup_launcher_path = LAUNCHER_SCRIPT_PATH + ".bak"
            shutil.copy2(LAUNCHER_SCRIPT_PATH, backup_launcher_path)

            # Zastąp stary plik nowym
            os.replace(temp_launcher_path, LAUNCHER_SCRIPT_PATH)
            
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_SUCCESS] Launcher zaktualizowany do wersji {latest_version}!", "SUCCESS"))
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER] Proszę ZAMKNĄĆ i PONOWNIE URUCHOMIĆ ten launcher, aby zastosować aktualizację.", "LAUNCHER"))
            messagebox.showinfo("Aktualizacja", f"Launcher został pomyślnie zaktualizowany do wersji {latest_version}!\n"
                                              "Proszę ZAMKNĄĆ i PONOWNIE URUCHOMIĆ ten program, aby zastosować zmiany.")
            
            self.start_button.config(state=tk.DISABLED) # Zablokuj przyciski po aktualizacji
            self.stop_button.config(state=tk.DISABLED)

        except requests.exceptions.RequestException as e:
            error_msg = f"Błąd pobierania aktualizacji: {e}"
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] {error_msg}", "ERROR"))
            messagebox.showerror("Błąd Aktualizacji", error_msg + "\nSprawdź połączenie z internetem.")
        except Exception as e:
            error_msg = f"Błąd instalacji aktualizacji: {e}"
            self.log_queue.put((f"[{datetime.datetime.now()}] [LAUNCHER_ERROR] {error_msg}", "ERROR"))
            messagebox.showerror("Błąd Aktualizacji", error_msg + "\nSpróbuj ponownie lub przywróć plik .bak.")


if __name__ == "__main__":
    app = AppLauncher()
    app.mainloop()
