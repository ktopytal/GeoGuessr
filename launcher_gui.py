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
import shutil 
import tkinter as tk 
from tkinter import messagebox, Menu, ttk 

# --- Konfiguracja Wersji Aplikacji ---
APP_VERSION = "1.2.0" 

# --- Konfiguracja Ścieżek ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
BACKEND_DIR = os.path.join(BASE_DIR, 'geoguessr_backend')
# WWW_DIR jest teraz nieużywane, ponieważ panel admina został usunięty
FRONTEND_SCRIPT_NAME = 'geoguessr_game.py'
BACKEND_APP_SCRIPT_NAME = 'app.py' 
FRONTEND_CONFIG_PATH = os.path.join(BASE_DIR, 'config.py') 
LAUNCHER_SCRIPT_PATH = os.path.join(BASE_DIR, os.path.basename(__file__))

# --- Konfiguracja Aktualizatora ---
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/ktopytal/GeoGuessr/main/latest_launcher_version.txt" 
UPDATE_DOWNLOAD_URL = "https://raw.githubusercontent.com/ktopytal/GeoGuessr/main/start_launcher.py" 

# --- Konfiguracja Uruchamiania ---
PYTHON_EXECUTABLE = 'python3' 
BACKEND_PORT = 5000 
BACKEND_STARTUP_DELAY = 7 # Czas oczekiwania na uruchomienie backendu gry (sekundy)
CONNECTION_CHECK_INTERVAL = 1000 # Interwał odświeżania statusu procesów (ms)

class AppStyles:
    """Klasa do konfiguracji stylów ttk."""
    def __init__(self, root):
        self.style = ttk.Style(root)
        self.style.theme_use("clam") 
        
        self.style.configure("TButton", font=("Arial", 10, "bold"), padding=8, relief="flat", background="#607D8B", foreground="white", borderwidth=0) 
        self.style.map("TButton", 
                       background=[('active', '#78909C'), ('disabled', '#B0BEC5')]) 
        
        self.style.configure("Accent.TButton", background="#4CAF50") 
        self.style.map("Accent.TButton", 
                       background=[('active', '#66BB6A'), ('disabled', '#B0BEC5')])

        self.style.configure("Danger.TButton", background="#F44336") 
        self.style.map("Danger.TButton", 
                       background=[('active', '#E57373'), ('disabled', '#B0BEC5')])

        self.style.configure("TLabel", font=("Arial", 10), background="#ECEFF1", foreground="#263238")
        
        self.style.configure("TLabelframe", font=("Arial", 11, "bold"), background="#ECEFF1", foreground="#263238", relief="flat", padding=[10, 5, 10, 10])
        self.style.configure("TLabelframe.Label", font=("Arial", 11, "bold"), background="#ECEFF1", foreground="#263238") 

        self.style.configure("TEntry", fieldbackground="#FFFFFF", foreground="#263238", borderwidth=1, relief="solid", padding=5)

        self.style.configure("Green.TLabel", background="#E8F5E9", foreground="#2E7D32", font=("Arial", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Red.TLabel", background="#FFEBEE", foreground="#C62828", font=("Arial", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Yellow.TLabel", background="#FFFDE7", foreground="#FF8F00", font=("Arial", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Blue.TLabel", background="#E3F2FD", foreground="#1565C0", font=("Arial", 10, "bold"), padding=5, relief="flat") 
        self.style.configure("Gray.TLabel", background="#CFD8DC", foreground="#37474F", font=("Arial", 10, "bold"), padding=5, relief="flat") 
        
        self.style.configure("TProgressbar", thickness=15)
        self.style.configure("blue.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#42A5F5")
        self.style.configure("green.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#66BB6A")
        self.style.configure("red.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#EF5350")
        self.style.configure("yellow.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#FFCA28") 

class AppLauncher(tk.Tk): 
    def __init__(self):
        super().__init__()
        self.log_message("Inicjalizacja launchera...", level="INFO", component="LAUNCHER_INIT")
        self.title(f"GeoGuessr Launcher v{APP_VERSION}")
        self.geometry("700x550") 
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing) 
        self.config(bg="#ECEFF1") 

        # Inicjalizacja stylów
        self.styles = AppStyles(self)

        # Procesy
        self.backend_game_process = None
        self.frontend_game_process = None
        self.log_queue = Queue() 

        # Wczytaj konfigurację frontendu
        self.frontend_config = self._load_frontend_config() 
        
        # Ustaw globalny port backendu gry
        global BACKEND_PORT 
        BACKEND_PORT = self.frontend_config.get("BACKEND_PORT", 5000) 

        self.create_widgets()
        self.create_menu()
        
        # Uruchom wątek do przetwarzania logów
        self.process_logs_thread = threading.Thread(target=self.process_logs, daemon=True)
        self.process_logs_thread.start()

        # Rozpocznij cykliczne sprawdzanie statusu backendu
        self.check_backend_status_periodically()
        # Sprawdź aktualizacje przy starcie launchera
        self.check_for_updates()
        self.log_message("Launcher zainicjowany pomyślnie.", level="INFO", component="LAUNCHER_INIT")

    # --- Metody obsługujące zdarzenia i logikę ---

    def _load_frontend_config(self):
        """Wczytuje konfigurację frontendu z pliku JSON."""
        self.log_message(f"Próbuję wczytać konfigurację frontendu z: {FRONTEND_CONFIG_PATH}", level="INFO", component="KONFIGURACJA")
        if not os.path.exists(FRONTEND_CONFIG_PATH):
            self.log_message(f"BŁĄD KRYTYCZNY: Brak pliku konfiguracyjnego frontendu: {FRONTEND_CONFIG_PATH}. Aplikacja zostanie zamknięta.", level="CRITICAL", component="KONFIGURACJA")
            messagebox.showerror("Błąd Konfiguracji", f"Brak pliku konfiguracyjnego frontendu: {FRONTEND_CONFIG_PATH}\n"
                                                      "Upewnij się, że plik config.py istnieje i jest w formacie JSON.")
            sys.exit(1)
        try:
            with open(FRONTEND_CONFIG_PATH, 'r') as f:
                config_data = json.load(f)
            self.log_message("Konfiguracja frontendu wczytana pomyślnie.", level="SUCCESS", component="KONFIGURACJA")
            return config_data
        except json.JSONDecodeError as e:
            self.log_message(f"BŁĄD KRYTYCZNY: Błąd parsowania JSON w config.py: {e}. Aplikacja zostanie zamknięta.", level="CRITICAL", component="KONFIGURACJA")
            messagebox.showerror("Błąd Konfiguracji", f"Błąd w pliku konfiguracyjnym frontendu (Błąd składni JSON):\n{e}\n"
                                                      "Sprawdź format JSON w config.py.")
            sys.exit(1)
        except Exception as e:
            self.log_message(f"BŁĄD KRYTYCZNY: Nie udało się wczytać config.py: {e}. Aplikacja zostanie zamknięta.", level="CRITICAL", component="KONFIGURACJA")
            messagebox.showerror("Błąd Konfiguracji", f"Nie udało się wczytać pliku konfiguracyjnego frontendu:\n{e}")
            sys.exit(1)

    def _save_frontend_config(self):
        """Zapisuje bieżącą konfigurację frontendu do pliku JSON."""
        self.log_message(f"Próbuję zapisać konfigurację frontendu do: {FRONTEND_CONFIG_PATH}", level="INFO", component="KONFIGURACJA")
        try:
            with open(FRONTEND_CONFIG_PATH, 'w') as f:
                json.dump(self.frontend_config, f, indent=4) 
            self.log_message("Konfiguracja frontendu zapisana pomyślnie.", level="SUCCESS", component="KONFIGURACJA")
            return True
        except Exception as e:
            messagebox.showerror("Błąd Zapisu", f"Nie udało się zapisać pliku konfiguracyjnego frontendu:\n{e}")
            self.log_message(f"BŁĄD: Nie udało się zapisać config.py: {e}", level="ERROR", component="KONFIGURACJA")
            return False

    def create_menu(self):
        """Tworzy pasek menu aplikacji."""
        self.log_message("Tworzenie menu aplikacji.", level="INFO", component="GUI_INIT")
        menubar = Menu(self)
        self.config(menu=menubar)

        settings_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ustawienia", menu=settings_menu)
        settings_menu.add_command(label="Sprawdź aktualizacje", command=self.check_for_updates_manual)
        settings_menu.add_separator()
        settings_menu.add_command(label="O programie", command=self.show_about_dialog)
        self.log_message("Menu aplikacji utworzone.", level="INFO", component="GUI_INIT")

    def show_about_dialog(self):
        """Wyświetla okno 'O programie'."""
        self.log_message("Wyświetlanie okna 'O programie'.", level="INFO", component="GUI_EVENT")
        messagebox.showinfo("O programie GeoGuessr Launcher", f"GeoGuessr Launcher v{APP_VERSION}\n\n"
                                           "Autor: deloskiyt\n\n"
                                           "Projekt edukacyjny, uruchamiający grę GeoGuessr "
                                           "z własnym backendem i lokalnymi obrazami.\n"
                                           "Zbudowany z miłości do kodowania i geografii w 2025 roku.")

    def create_widgets(self):
        """Tworzy wszystkie widżety GUI."""
        self.log_message("Tworzenie widżetów GUI...", level="INFO", component="GUI_INIT")

        # Nagłówek
        header_frame = ttk.Frame(self, padding=15) 
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="GeoGuessr Launcher", font=("Arial", 18, "bold"), foreground="#263238").pack(pady=5)

        # Sekcja Statusu Serwera (tylko gry)
        status_frame = ttk.LabelFrame(self, text="Status Serwera Gry", padding=15) 
        status_frame.pack(padx=20, pady=10, fill=tk.X)
        
        status_info_frame = ttk.Frame(status_frame) 
        status_info_frame.pack(fill="x", padx=10, pady=5)
        
        # Status Backendu Gry
        ttk.Label(status_info_frame, text="Gry:", font=("Arial", 11, "bold")).pack(side="left", padx=(0,5))
        self.backend_game_status_label = ttk.Label(status_info_frame, text="Nie uruchomiony", style="Yellow.TLabel") 
        self.backend_game_status_label.pack(side="left", padx=(0,10))
        self.game_port_status_label = ttk.Label(status_info_frame, text=f"Port: {BACKEND_PORT}", style="Yellow.TLabel")
        self.game_port_status_label.pack(side="left", padx=(0,10))

        # Sekcja Postępu Uruchamiania
        progress_frame = ttk.LabelFrame(self, text="Status Uruchamiania", padding=15)
        progress_frame.pack(padx=20, pady=10, fill=tk.X)
        
        self.startup_progress_label = ttk.Label(progress_frame, text="Gotowy do uruchomienia", style="Blue.TLabel") 
        self.startup_progress_label.pack(pady=5)
        self.startup_progressbar = ttk.Progressbar(progress_frame, orient="horizontal", length=400, mode="determinate", style="blue.Horizontal.TProgressbar") 
        self.startup_progressbar.pack(pady=10)

        # Przyciski kontrolne
        control_panel_frame = ttk.Frame(self, padding=15) 
        control_panel_frame.pack(pady=10)

        self.start_button = ttk.Button(control_panel_frame, text="Uruchom GeoGuessr", command=self.start_app_thread, style="Accent.TButton")
        self.start_button.pack(side="left", padx=10)

        self.stop_button = ttk.Button(control_panel_frame, text="Zatrzymaj wszystko", command=self.stop_app_thread, state="disabled", style="Danger.TButton")
        self.stop_button.pack(side="left", padx=10)
        
        # Ramka na logi
        log_frame = ttk.LabelFrame(self, text="Logi Aplikacji", padding=15) 
        log_frame.pack(padx=20, pady=10, fill="both", expand=True)
        ttk.Label(log_frame, text="Logi Aplikacji", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=5)

        self.log_text = tk.Text(log_frame, state="disabled", wrap="word", bg="black", fg="white", font=("Courier New", 9)) 
        self.log_text.pack(fill="both", expand=True)

        # Tagowanie logów
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
        self.log_message("Widżety GUI utworzone.", level="INFO", component="GUI_INIT")


    def append_log(self, message, tag=None):
        """Dodaje wiadomość do pola logów GUI i automatycznie przewija."""
        self.log_text.config(state="normal") 
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END) 
        self.log_text.config(state="disabled")

    def log_message(self, message, level="INFO", component="LAUNCHER"):
        """Ujednolicona funkcja do logowania wiadomości z poziomu launchera."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # ms
        full_message = f"[{timestamp}] [{level}] [{component}] {message}"
        self.log_queue.put((full_message, level)) # Dodaj do kolejki logów


    def process_logs(self):
        """Pobiera logi z kolejki i wyświetla je w polu tekstowym."""
        self.log_message("Wątek przetwarzania logów uruchomiony.", level="DEBUG", component="LAUNCHER_THREAD")
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
        elif "[FRONTEND_BŁĄD]" in line or "[FRONTEND_ERROR]" in line: return "ERROR"
        elif "[FRONTEND_SUKCES]" in line or "[FRONTEND_SUCCESS]" in line: return "SUCCESS"
        elif "[FRONTEND_LICENCJA]" in line: return "LICENCJA"
        elif "[FRONTEND_KRYTYCZNY]" in line or "[FRONTEND_CRITICAL]" in line: return "CRITICAL"
        
        elif "[BACKEND_INFO]" in line: return "BACKEND"
        elif "[BACKEND_DEBUG]" in line: return "DEBUG"
        elif "[BACKEND_SUKCES]" in line or "[BACKEND_SUCCESS]" in line: return "SUCCESS"
        elif "[BACKEND_BŁĄD]" in line or "[BACKEND_ERROR]" in line: return "ERROR"
        elif "[BACKEND_LICENCJA]" in line: return "LICENCJA"
        elif "[BACKEND_KRYTYCZNY]" in line or "[BACKEND_CRITICAL]" in line: return "CRITICAL"
        
        elif "[PANEL_ADMINA_FLASK_OUTPUT]" in line: return "BACKEND" # Nadal używamy tego taga dla logów z admina
        elif "[BACKEND_GRY_OUTPUT]" in line: return "BACKEND" 

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
        self.log_message("Próba uruchomienia aplikacji.", level="INFO", component="URUCHAMIANIE")
        self.start_button.config(state=tk.DISABLED, style="TButton") 
        self.stop_button.config(state=tk.DISABLED, style="TButton") 
        # Przycisk admina nie istnieje, więc go nie konfigurujemy

        self.startup_progress_label.config(text="Rozpoczynam uruchamianie...", foreground="blue")
        self.startup_progressbar.config(mode="indeterminate", style="blue.Horizontal.TProgressbar") 
        self.startup_progressbar.start() 
        self.backend_game_status_label.config(text="Uruchamiam...", foreground="orange")
        self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Uruchamiam...)", foreground="orange")
        
        threading.Thread(target=self._start_app_logic, daemon=True).start()
        self.log_message("Wątek uruchamiania aplikacji rozpoczęty.", level="DEBUG", component="URUCHAMIANIE")

    def _start_app_logic(self):
        """Logika uruchamiania backendu i frontendu."""
        self.log_message("Rozpoczynam logikę uruchamiania...", level="DEBUG", component="URUCHAMIANIE")
        
        # --- Sprawdzenie portu gry ---
        self.startup_progress_label.config(text=f"Sprawdzam dostępność portu gry ({BACKEND_PORT})...", foreground="blue")
        if not self.is_port_available(BACKEND_PORT):
            self.show_startup_error(f"Port {BACKEND_PORT} jest już używany. Zmień port w config.py i uruchom ponownie.")
            self.log_message(f"Błąd: Port {BACKEND_PORT} zajęty.", level="ERROR", component="URUCHAMIANIE")
            return
        self.log_message(f"Port {BACKEND_PORT} dostępny.", level="DEBUG", component="URUCHAMIANIE")

        # --- Usunięto sprawdzanie portu admina ---
        # self.startup_progress_label.config(text=f"Sprawdzam dostępność portu admina ({ADMIN_PANEL_PORT})...", foreground="blue")
        # if not self.is_port_available(ADMIN_PANEL_PORT):
        #    self.show_startup_error(f"Port {ADMIN_PANEL_PORT} jest już używany. Zmień port w config.py i uruchom ponownie.")
        #    return
        # self.log_message(f"Port {ADMIN_PANEL_PORT} dostępny.", level="DEBUG", component="URUCHAMIANIE")
        
        # --- Uruchomienie Backendu Gry ---
        self.startup_progress_label.config(text="Uruchamiam backend gry...", foreground="blue")
        self.backend_game_process = self._launch_process(
            "backend gry", 
            os.path.join(BACKEND_DIR, BACKEND_APP_SCRIPT_NAME), 
            cwd=BACKEND_DIR,
            env={"FLASK_APP": BACKEND_APP_SCRIPT_NAME, "FLASK_RUN_PORT": str(BACKEND_PORT)} 
        )
        if self.backend_game_process is None: # Sprawdzenie, czy proces w ogóle wystartował
            self.show_startup_error("Backend gry nie uruchomił się, proces zwrócił None.")
            return

        self.log_message(f"Czekam {BACKEND_STARTUP_DELAY} sekund na uruchomienie backendu gry...", level="INFO", component="URUCHAMIANIE")
        self.startup_progress_label.config(text=f"Czekam {BACKEND_STARTUP_DELAY}s na backend gry...", foreground="blue")
        self.startup_progressbar.config(mode="determinate", style="blue.Horizontal.TProgressbar") 
        for i in range(BACKEND_STARTUP_DELAY * 10): 
            self.startup_progressbar.step(100 / (BACKEND_STARTUP_DELAY * 10)) 
            time.sleep(0.1)
        
        self.startup_progress_label.config(text="Sprawdzam, czy backend gry nasłuchuje...", foreground="blue")
        if not self.is_backend_listening(BACKEND_PORT):
            self.show_startup_error(f"Backend gry nie nasłuchuje na porcie {BACKEND_PORT}. Sprawdź jego logi.")
            return
        self.log_message(f"Backend gry uruchomiony i nasłuchuje na porcie {BACKEND_PORT}.", level="SUCCESS", component="URUCHAMIANIE")


        # --- Usunięto uruchamianie Panelu Admina ---
        # self.admin_panel_process = self._launch_process(...)
        # self.log_message("Panel admina uruchomiony...", ...)

        # --- Uruchomienie Frontendu Gry ---
        self.startup_progress_label.config(text="Uruchamiam frontend gry...", foreground="blue")
        self.frontend_game_process = self._launch_process(
            "frontend gry", 
            os.path.join(BASE_DIR, FRONTEND_SCRIPT_NAME), 
            cwd=BASE_DIR 
        )
        if self.frontend_game_process is None: # Sprawdzenie, czy proces w ogóle wystartował
            self.show_startup_error("Frontend gry nie uruchomił się, proces zwrócił None.")
            return
        self.log_message("Frontend gry uruchomiony. Zamknij okno gry, aby zakończyć działanie backendów.", level="INFO", component="URUCHAMIANIE")

        self.stop_button.config(state=tk.NORMAL, style="Danger.TButton") 
        self.start_button.config(state=tk.DISABLED, style="TButton") 
        # Przycisk admina nie istnieje
        # self.admin_panel_button.config(state=tk.NORMAL, style="Purple.TButton") 
        self.startup_progress_label.config(text="GeoGuessr uruchomiony! ✅", foreground="green")
        self.startup_progressbar.stop()
        self.startup_progressbar.config(value=100, style="green.Horizontal.TProgressbar") 

        # Czekaj na zamknięcie frontendu i następnie zatrzymaj wszystko
        self.log_message("Oczekiwanie na zamknięcie okna gry...", level="DEBUG", component="URUCHAMIANIE")
        self.frontend_game_process.wait() 
        self.log_message("Frontend został zamknięty.", level="INFO", component="URUCHAMIANIE")
        self.stop_app_thread() 

    def show_startup_error(self, message):
        """Wyświetla błąd uruchamiania i resetuje UI."""
        self.log_message(f"Błąd uruchamiania: {message}", level="ERROR", component="URUCHAMIANIE")
        messagebox.showerror("Błąd Uruchamiania", message + "\nSprawdź logi aplikacji.")
        
        # Natychmiast zatrzymaj wszystko po błędzie, aby nie pozostawić procesów
        self.stop_app_thread() 
        
        # Resetuj UI po błędzie
        self.start_button.config(state=tk.NORMAL, style="Accent.TButton")
        self.stop_button.config(state=tk.DISABLED, style="Danger.TButton")
        # Przycisk admina nie istnieje
        # self.admin_panel_button.config(state=tk.DISABLED, style="Purple.TButton") 
        self.startup_progress_label.config(text="Błąd uruchamiania ❌", foreground="red")
        self.startup_progressbar.stop()
        self.startup_progressbar.config(value=0, style="red.Horizontal.TProgressbar") 


    def _launch_process(self, name, script_path, cwd=None, env=None):
        """Pomocnicza funkcja do uruchamiania pojedynczego procesu."""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            process = subprocess.Popen(
                [PYTHON_EXECUTABLE, script_path], 
                cwd=cwd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True, 
                bufsize=1,
                env=full_env 
            )
            self.log_message(f"Pomyślnie uruchomiono proces {name} (PID: {process.pid}).", level="INFO", component="PROCESY")
            threading.Thread(target=self._read_process_output, args=(process, name), daemon=True).start()
            return process
        except FileNotFoundError:
            self.log_message(f"Błąd: Interpreter '{PYTHON_EXECUTABLE}' nie znaleziony dla {name}. Aplikacja zostanie zamknięta.", level="CRITICAL", component="PROCESY")
            messagebox.showerror("Błąd Uruchamiania", f"Interpreter '{PYTHON_EXECUTABLE}' nie znaleziony dla {name}.")
            sys.exit(1) # Zakończ aplikację, jeśli nie ma interpretera
            return None # Na wszelki wypadek
        except Exception as e:
            self.log_message(f"Błąd: Nie udało się uruchomić {name}: {e}", level="CRITICAL", component="PROCESY")
            messagebox.showerror("Błąd Uruchamiania", f"Nie udało się uruchomić {name}: {e}")
            return None

    def _read_process_output(self, process, name):
        """Czyta wyjście procesu i umieszcza je w kolejce logów."""
        for line in process.stdout:
            tag = self._get_log_tag(line) 
            self.log_queue.put((f"[{name.upper().replace(' ', '_')}_OUTPUT] {line.strip()}", tag)) 

    def stop_app_thread(self):
        """Zatrzymuje procesy w osobnym wątku."""
        self.log_message("Rozpoczynam zamykanie aplikacji.", level="INFO", component="ZAMYKANIE")
        self.start_button.config(state=tk.DISABLED, style="TButton")
        self.stop_button.config(state=tk.DISABLED, style="TButton")
        # Przycisk admina nie istnieje, więc go nie konfigurujemy
        
        self.startup_progress_label.config(text="Zatrzymuję procesy...", foreground="orange")
        self.startup_progressbar.config(mode="indeterminate", style="Yellow.Horizontal.TProgressbar")
        self.startup_progressbar.start()
        self.backend_game_status_label.config(text="Zatrzymuję...", foreground="orange")
        self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Zatrzymuję...)", foreground="orange")

        threading.Thread(target=self._stop_app_logic, daemon=True).start()
        self.log_message("Wątek zamykania aplikacji rozpoczęty.", level="DEBUG", component="ZAMYKANIE")

    def _stop_app_logic(self):
        """Logika zamykania backendu i frontendu."""
        self.log_message("Rozpoczynam logikę zamykania...", level="DEBUG", component="ZAMYKANIE")
        
        self.terminate_process(self.frontend_game_process, "frontend gry")
        # Usunięto zamykanie panelu admina
        self.terminate_process(self.backend_game_process, "backend gry") 
        
        self.log_message("Wszystkie procesy zostały zamknięte.", level="INFO", component="ZAMYKANIE")
        self.backend_game_process = None
        self.frontend_game_process = None

        # Resetuj UI po zamknięciu
        self.start_button.config(state=tk.NORMAL, style="Accent.TButton")
        self.stop_button.config(state=tk.DISABLED, style="Danger.TButton")
        # Przycisk admina nie istnieje
        # self.admin_panel_button.config(state=tk.DISABLED, style="Purple.TButton") 
        self.backend_game_status_label.config(text="Nie uruchomiony ❌", foreground="orange")
        self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Wolny)", foreground="green")
        self.startup_progress_label.config(text="Gotowy do uruchomienia", foreground="blue")
        self.startup_progressbar.stop()
        self.startup_progressbar.config(value=0, style="blue.Horizontal.TProgressbar")
        self.log_message("UI zresetowane po zamknięciu procesów.", level="DEBUG", component="ZAMYKANIE")


    def terminate_process(self, process, name):
        """Pomocnicza funkcja do eleganckiego zamykania procesu potomnego."""
        if process and process.poll() is None: 
            self.log_message(f"Próba zakończenia procesu {name} (PID: {process.pid})...", level="INFO", component="ZAMYKANIE")
            try:
                process.terminate() 
                process.wait(timeout=5) 
                if process.poll() is None: 
                    self.log_message(f"Proces {name} nie zamknął się czysto, zabijam go (PID: {process.pid}).", level="WARNING", component="ZAMYKANIE")
                    process.kill() 
            except Exception as e:
                self.log_message(f"Błąd podczas zamykania {name}: {e}", level="ERROR", component="ZAMYKANIE")

    def on_closing(self):
        """Obsługuje zdarzenie zamknięcia okna launchera."""
        self.log_message("Użytkownik próbuje zamknąć launcher.", level="INFO", component="GUI_EVENT")
        if messagebox.askokcancel("Zamknij Launcher", "Czy na pewno chcesz zamknąć GeoGuessr Launcher i wszystkie uruchomione procesy?"):
            self.log_message("Zamykanie launchera potwierdzone przez użytkownika.", level="INFO", component="GUI_EVENT")
            self.stop_app_thread() 
            # Daj czas na zakończenie wątku stop_app_thread, zanim zniszczymy okno
            self.after(2000, self.destroy) # destroy musi być w głównym wątku Tkinter

    def is_port_available(self, port):
        """Sprawdza, czy dany port jest wolny."""
        self.log_message(f"Sprawdzam dostępność portu: {port}", level="DEBUG", component="SIEĆ")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                self.log_message(f"Port {port} jest wolny.", level="DEBUG", component="SIEĆ")
                return True
            except socket.error as e: 
                self.log_message(f"Port {port} jest zajęty: {e}", level="WARNING", component="SIEĆ")
                return False

    def is_backend_listening(self, port):
        """Sprawdza, czy serwer nasłuchuje na swoim porcie poprzez zapytanie HTTP."""
        try:
            response = requests.get(f"http://127.0.0.1:{port}/", timeout=1) 
            if response.status_code == 200:
                self.log_message(f"Serwer nasłuchuje na porcie {port} (status 200).", level="DEBUG", component="SIEĆ")
                return True
            else:
                self.log_message(f"Serwer nasłuchuje na porcie {port}, ale zwrócił status {response.status_code}.", level="WARNING", component="SIEĆ")
                return False
        except requests.exceptions.RequestException as e: 
            self.log_message(f"Błąd połączenia z serwerem na porcie {port}: {e}", level="WARNING", component="SIEĆ")
            return False

    def check_backend_status_periodically(self):
        """Sprawdza status backendu gry i aktualizuje etykiety co 1 sekundę."""
        self.log_message("Cykliczne sprawdzanie statusu backendu gry.", level="DEBUG", component="MONITORING")
        # Sprawdź status backendu gry
        if self.backend_game_process and self.backend_game_process.poll() is None: 
            if self.is_backend_listening(BACKEND_PORT):
                self.backend_game_status_label.config(text="Aktywny ✅", foreground="green") 
                self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Nasłuchuje)", foreground="green")
            else:
                self.backend_game_status_label.config(text="Uruchomiony, ale nie nasłuchuje ⚠️", foreground="orange") 
                self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Problem)", foreground="red")
        else: # Proces nie uruchomiony lub zakończył się
            self.backend_game_status_label.config(text="Nie uruchomiony ❌", foreground="orange") 
            if self.is_port_available(BACKEND_PORT): 
                self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Wolny)", foreground="green") 
            else:
                self.game_port_status_label.config(text=f"Port: {BACKEND_PORT} (Zajęty)", foreground="red")
        
        # Brak panelu admina, więc usunięto jego sprawdzanie
        
        self.after(CONNECTION_CHECK_INTERVAL, self.check_backend_status_periodically) 
        
    def open_admin_panel(self): # Funkcja nadal istnieje, ale przycisk jest usunięty z GUI
        """Otwiera panel admina w domyślnej przeglądarce."""
        self.log_message("Użytkownik próbował otworzyć panel admina, ale funkcja jest niedostępna.", level="WARNING", component="GUI_EVENT")
        messagebox.showinfo("Panel Admina", "Panel administratora nie jest dostępny w tej wersji launchera.")
        

    def check_for_updates_manual(self):
        """Funkcja wywoływana ręcznie z menu: Sprawdź aktualizacje."""
        self.log_message("Ręczne sprawdzanie aktualizacji...", level="INFO", component="AKTUALIZACJE")
        threading.Thread(target=self._perform_update_check, args=(True,), daemon=True).start()

    def check_for_updates(self):
        """Automatyczne sprawdzanie aktualizacji przy starcie launchera."""
        self.log_message(f"Automatyczne sprawdzanie aktualizacji (bieżąca wersja: {APP_VERSION})...", level="INFO", component="AKTUALIZACJE")
        threading.Thread(target=self._perform_update_check, args=(False,), daemon=True).start()

    def _perform_update_check(self, manual_check=False):
        """Logika sprawdzania aktualizacji."""
        self.log_message("Rozpoczynam logikę sprawdzania aktualizacji.", level="DEBUG", component="AKTUALIZACJE")
        try:
            response = requests.get(UPDATE_CHECK_URL, timeout=5)
            response.raise_for_status()
            latest_version = response.text.strip()
            
            self.log_message(f"Znaleziono najnowszą wersję online: {latest_version}", level="INFO", component="AKTUALIZACJE")

            if self._compare_versions(APP_VERSION, latest_version):
                self.log_message(f"Nowsza wersja ({latest_version}) dostępna. Bieżąca: {APP_VERSION}.", level="INFO", component="AKTUALIZACJE")
                if messagebox.askyesno("Dostępna Aktualizacja", 
                                       f"Dostępna jest nowsza wersja launchera: {latest_version}.\n"
                                       f"Twoja wersja: {APP_VERSION}.\n\n"
                                       "Czy chcesz pobrać i zainstalować aktualizację teraz?\n"
                                       "(Wymagany restart launchera)"):
                    self.log_message("Użytkownik zaakceptował aktualizację.", level="INFO", component="AKTUALIZACJE")
                    self._download_and_install_update(latest_version)
                else:
                    self.log_message("Aktualizacja odrzucona przez użytkownika.", level="INFO", component="AKTUALIZACJE")
            else:
                self.log_message(f"Używasz już najnowszej wersji: {APP_VERSION}", level="INFO", component="AKTUALIZACJE")
                if manual_check:
                    messagebox.showinfo("Aktualizacja", f"Używasz najnowszej wersji ({APP_VERSION}).")

        except requests.exceptions.RequestException as e:
            error_msg = f"Błąd połączenia podczas sprawdzania aktualizacji: {e}"
            self.log_message(error_msg, level="ERROR", component="AKTUALIZACJE")
            if manual_check:
                messagebox.showerror("Błąd Aktualizacji", error_msg + "\nSprawdź połączenie z internetem.")
        except Exception as e:
            error_msg = f"Nieoczekiwany błąd podczas sprawdzania aktualizacji: {e}"
            self.log_message(error_msg, level="CRITICAL", component="AKTUALIZACJE")
            if manual_check:
                messagebox.showerror("Błąd Aktualizacji", error_msg)

    def _compare_versions(self, current_v, latest_v):
        """Porównuje numery wersji (np. '1.0.0' vs '1.1.0')."""
        current_parts = list(map(int, current_v.split('.')))
        latest_parts = list(map(int, latest_v.split('.')))
        
        max_len = max(len(current_parts), len(latest_parts))
        current_parts += [0] * (max_len - len(current_parts))
        latest_parts += [0] * (max_len - len(latest_parts))
        self.log_message(f"Porównywanie wersji: bieżąca {current_v} vs najnowsza {latest_v}", level="DEBUG", component="AKTUALIZACJE")
        return latest_parts > current_parts 

    def _download_and_install_update(self, latest_version):
        """Pobiera i instaluje nową wersję launchera."""
        self.log_message("Rozpoczynam pobieranie i instalację aktualizacji.", level="INFO", component="AKTUALIZACJE")
        try:
            response = requests.get(UPDATE_DOWNLOAD_URL, timeout=10)
            response.raise_for_status()
            new_launcher_code = response.text

            temp_launcher_path = LAUNCHER_SCRIPT_PATH + ".new"
            with open(temp_launcher_path, 'w') as f:
                f.write(new_launcher_code)
            self.log_message(f"Nowy launcher zapisany tymczasowo: {temp_launcher_path}", level="DEBUG", component="AKTUALIZACJE")
            
            backup_launcher_path = LAUNCHER_SCRIPT_PATH + ".bak"
            shutil.copy2(LAUNCHER_SCRIPT_PATH, backup_launcher_path)
            self.log_message(f"Utworzono kopię zapasową launchera: {backup_launcher_path}", level="DEBUG", component="AKTUALIZACJE")

            os.replace(temp_launcher_path, LAUNCHER_SCRIPT_PATH)
            self.log_message(f"Zastąpiono stary launcher nowym: {LAUNCHER_SCRIPT_PATH}", level="DEBUG", component="AKTUALIZACJE")
            
            self.log_message(f"Launcher zaktualizowany do wersji {latest_version}!", level="SUCCESS", component="AKTUALIZACJE")
            self.log_message("Proszę ZAMKNĄĆ i PONOWNIE URUCHOMIĆ ten launcher, aby zastosować aktualizację.", level="INFO", component="AKTUALIZACJE")
            messagebox.showinfo("Aktualizacja", f"Launcher został pomyślnie zaktualizowany do wersji {latest_version}!\n"
                                              "Proszę ZAMKNĄĆ i PONOWNIE URUCHOMIĆ ten program, aby zastosować zmiany.")
            
            self.start_button.config(state=tk.DISABLED, style="TButton") 
            self.stop_button.config(state=tk.DISABLED, style="TButton")
            # Przycisk admina nie istnieje
            # self.admin_panel_button.config(state=tk.DISABLED, style="TButton") 

        except requests.exceptions.RequestException as e:
            error_msg = f"Błąd pobierania aktualizacji: {e}"
            self.log_message(error_msg, level="ERROR", component="AKTUALIZACJE")
            messagebox.showerror("Błąd Aktualizacji", error_msg + "\nSprawdź połączenie z internetem.")
        except Exception as e:
            error_msg = f"Błąd instalacji aktualizacji: {e}"
            self.log_message(error_msg, level="CRITICAL", component="AKTUALIZACJE")
            messagebox.showerror("Błąd Aktualizacji", error_msg + "\nSpróbuj ponownie lub przywróć plik .bak.")


if __name__ == "__main__":
    app = AppLauncher()
    app.mainloop()
