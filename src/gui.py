# gui.py - Modern version with Blitz/Rapid options

import os
import multiprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from overlay import run
from stockfish_bot import StockfishBot
from selenium.common import WebDriverException
import keyboard


class ModernGUI:
    def __init__(self, master):
        self.master = master
        
        # Color scheme
        self.bg_primary = "#1e1e2e"
        self.bg_secondary = "#2a2a3e"
        self.bg_tertiary = "#363654"
        self.accent_color = "#7aa2f7"
        self.accent_hover = "#89b4fa"
        self.text_primary = "#c0caf5"
        self.text_secondary = "#9aa5ce"
        self.success_color = "#9ece6a"
        self.error_color = "#f7768e"
        self.warning_color = "#e0af68"

        # Used for closing the threads
        self.exit = False

        # The Selenium Chrome driver
        self.chrome = None
        self.chrome_url = None
        self.chrome_session_id = None

        # Used for the communication between the GUI and the Stockfish Bot process
        self.stockfish_bot_pipe = None
        self.overlay_screen_pipe = None

        # The Stockfish Bot process
        self.stockfish_bot_process = None
        self.overlay_screen_process = None
        self.restart_after_stopping = False

        # Used for storing the match moves
        self.match_moves = []

        # Set the window properties
        master.title("Chess Bot Pro")
        master.geometry("1000x700")
        master.configure(bg=self.bg_primary)
        master.resizable(False, False)
        master.attributes("-topmost", True)
        master.protocol("WM_DELETE_WINDOW", self.on_close_listener)

        # Create main container
        main_container = tk.Frame(master, bg=self.bg_primary)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel with scrollbar
        left_canvas = tk.Canvas(main_container, bg=self.bg_secondary, highlightthickness=0, width=380)
        left_scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=left_canvas.yview)
        
        left_panel = tk.Frame(left_canvas, bg=self.bg_secondary)
        left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
        
        def on_frame_configure(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        
        left_panel.bind("<Configure>", on_frame_configure)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        left_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 0))
        left_scrollbar.grid(row=0, column=1, sticky="ns")

        # Status section
        self.create_status_section(left_panel)
        
        # Time Control section
        self.create_time_control_section(left_panel)

        # Website section
        self.create_website_section(left_panel)

        # Browser section
        self.create_browser_section(left_panel)

        # Control buttons
        self.create_control_section(left_panel)

        # Options section
        self.create_options_section(left_panel)

        # Stockfish parameters
        self.create_stockfish_section(left_panel)

        # Misc section
        self.create_misc_section(left_panel)

        # Right panel - Moves display
        right_panel = tk.Frame(main_container, bg=self.bg_secondary)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        self.create_moves_section(right_panel)

        # Configure grid weights
        main_container.grid_columnconfigure(0, weight=0)
        main_container.grid_columnconfigure(1, weight=0)
        main_container.grid_columnconfigure(2, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        # Start threads
        self.start_background_threads()

    def create_section_header(self, parent, text):
        """Create a styled section header"""
        frame = tk.Frame(parent, bg=self.bg_secondary)
        frame.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        label = tk.Label(
            frame,
            text=text,
            font=("Segoe UI", 11, "bold"),
            bg=self.bg_secondary,
            fg=self.accent_color
        )
        label.pack(anchor=tk.W)
        
        separator = tk.Frame(frame, height=2, bg=self.accent_color)
        separator.pack(fill=tk.X, pady=(3, 0))
        
        return frame

    def create_status_section(self, parent):
        """Create status display section"""
        self.create_section_header(parent, "STATUS")
        
        status_frame = tk.Frame(parent, bg=self.bg_tertiary)
        status_frame.pack(fill=tk.X, padx=15, pady=5)
        
        # Status indicator
        status_container = tk.Frame(status_frame, bg=self.bg_tertiary)
        status_container.pack(pady=10)
        
        tk.Label(
            status_container,
            text="●",
            font=("Segoe UI", 20),
            bg=self.bg_tertiary,
            fg=self.error_color
        ).pack(side=tk.LEFT)
        
        self.status_text = tk.Label(
            status_container,
            text="INACTIVE",
            font=("Segoe UI", 12, "bold"),
            bg=self.bg_tertiary,
            fg=self.text_primary
        )
        self.status_text.pack(side=tk.LEFT, padx=10)
        
        # Evaluation info frame
        self.eval_info_frame = tk.Frame(status_frame, bg=self.bg_tertiary)
        self.eval_info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Evaluation metrics
        eval_metrics = [
            ("Evaluation:", "eval_text"),
            ("Win/Draw/Loss:", "wdl_text"),
            ("Material:", "material_text"),
            ("Bot Accuracy:", "bot_acc_text"),
            ("Opponent Accuracy:", "opp_acc_text")
        ]
        
        for label_text, attr_name in eval_metrics:
            row = tk.Frame(self.eval_info_frame, bg=self.bg_tertiary)
            row.pack(fill=tk.X, pady=2)
            
            tk.Label(
                row,
                text=label_text,
                font=("Segoe UI", 9),
                bg=self.bg_tertiary,
                fg=self.text_secondary,
                width=18,
                anchor=tk.W
            ).pack(side=tk.LEFT)
            
            value_label = tk.Label(
                row,
                text="-",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_tertiary,
                fg=self.text_primary
            )
            value_label.pack(side=tk.LEFT)
            setattr(self, attr_name, value_label)

    def create_time_control_section(self, parent):
        """Create time control selection section"""
        self.create_section_header(parent, "TIME CONTROL")
        
        time_frame = tk.Frame(parent, bg=self.bg_secondary)
        time_frame.pack(fill=tk.X, padx=15, pady=5)
        
        self.time_control = tk.StringVar(value="custom")
        
        time_options = [
            ("Custom", "custom"),
            ("Blitz (1-5s)", "blitz"),
            ("Rapid (5-10s)", "rapid")
        ]
        
        for text, value in time_options:
            rb = tk.Radiobutton(
                time_frame,
                text=text,
                variable=self.time_control,
                value=value,
                font=("Segoe UI", 9),
                bg=self.bg_secondary,
                fg=self.text_primary,
                selectcolor=self.bg_tertiary,
                activebackground=self.bg_secondary,
                activeforeground=self.accent_color,
                command=self.on_time_control_change
            )
            rb.pack(anchor=tk.W, pady=2)
        
        # Custom delay range settings
        self.custom_delay_frame = tk.Frame(time_frame, bg=self.bg_secondary)
        self.custom_delay_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            self.custom_delay_frame,
            text="Custom Delay Range (seconds)",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(anchor=tk.W)
        
        delay_inputs = tk.Frame(self.custom_delay_frame, bg=self.bg_secondary)
        delay_inputs.pack(fill=tk.X, pady=2)
        
        tk.Label(
            delay_inputs,
            text="Min:",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(side=tk.LEFT)
        
        self.custom_delay_min = tk.DoubleVar(value=1.0)
        min_entry = tk.Entry(
            delay_inputs,
            textvariable=self.custom_delay_min,
            font=("Segoe UI", 9),
            bg=self.bg_tertiary,
            fg=self.text_primary,
            width=6,
            relief=tk.FLAT,
            insertbackground=self.text_primary
        )
        min_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        tk.Label(
            delay_inputs,
            text="Max:",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(side=tk.LEFT)
        
        self.custom_delay_max = tk.DoubleVar(value=20.0)
        max_entry = tk.Entry(
            delay_inputs,
            textvariable=self.custom_delay_max,
            font=("Segoe UI", 9),
            bg=self.bg_tertiary,
            fg=self.text_primary,
            width=6,
            relief=tk.FLAT,
            insertbackground=self.text_primary
        )
        max_entry.pack(side=tk.LEFT, padx=5)

    def create_website_section(self, parent):
        """Create website selection section"""
        self.create_section_header(parent, "PLATFORM")
        
        website_frame = tk.Frame(parent, bg=self.bg_secondary)
        website_frame.pack(fill=tk.X, padx=15, pady=5)
        
        self.website = tk.StringVar(value="chesscom")
        
        websites = [("Chess.com", "chesscom"), ("Lichess.org", "lichess")]
        
        for text, value in websites:
            rb = tk.Radiobutton(
                website_frame,
                text=text,
                variable=self.website,
                value=value,
                font=("Segoe UI", 9),
                bg=self.bg_secondary,
                fg=self.text_primary,
                selectcolor=self.bg_tertiary,
                activebackground=self.bg_secondary,
                activeforeground=self.accent_color
            )
            rb.pack(anchor=tk.W, pady=2)

    def create_browser_section(self, parent):
        """Create browser control section"""
        browser_frame = tk.Frame(parent, bg=self.bg_secondary)
        browser_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.opening_browser = False
        self.opened_browser = False
        
        self.open_browser_button = tk.Button(
            browser_frame,
            text="OPEN BROWSER",
            command=self.on_open_browser_button_listener,
            font=("Segoe UI", 10, "bold"),
            bg=self.accent_color,
            fg="#1e1e2e",
            activebackground=self.accent_hover,
            relief=tk.FLAT,
            cursor="hand2",
            pady=8
        )
        self.open_browser_button.pack(fill=tk.X)

    def create_control_section(self, parent):
        """Create start/stop control section"""
        control_frame = tk.Frame(parent, bg=self.bg_secondary)
        control_frame.pack(fill=tk.X, padx=15, pady=5)
        
        self.running = False
        
        self.start_button = tk.Button(
            control_frame,
            text="START BOT",
            command=self.on_start_button_listener,
            font=("Segoe UI", 11, "bold"),
            bg=self.success_color,
            fg="#1e1e2e",
            activebackground="#b9f27c",
            relief=tk.FLAT,
            cursor="hand2",
            state="disabled",
            pady=10
        )
        self.start_button.pack(fill=tk.X)

    def create_options_section(self, parent):
        """Create options checkboxes section"""
        self.create_section_header(parent, "OPTIONS")
        
        options_frame = tk.Frame(parent, bg=self.bg_secondary)
        options_frame.pack(fill=tk.X, padx=15, pady=5)
        
        # Manual mode
        self.enable_manual_mode = tk.BooleanVar(value=False)
        manual_cb = tk.Checkbutton(
            options_frame,
            text="Manual Mode (Press 3 to move)",
            variable=self.enable_manual_mode,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary,
            activeforeground=self.accent_color
        )
        manual_cb.pack(anchor=tk.W, pady=2)
        
        # Mouseless mode
        self.enable_mouseless_mode = tk.BooleanVar(value=False)
        mouseless_cb = tk.Checkbutton(
            options_frame,
            text="Mouseless Mode",
            variable=self.enable_mouseless_mode,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary
        )
        mouseless_cb.pack(anchor=tk.W, pady=2)
        
        # Non-stop puzzles
        self.enable_non_stop_puzzles = tk.IntVar(value=0)
        puzzles_cb = tk.Checkbutton(
            options_frame,
            text="Non-stop Puzzles",
            variable=self.enable_non_stop_puzzles,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary
        )
        puzzles_cb.pack(anchor=tk.W, pady=2)
        
        # Non-stop matches
        self.enable_non_stop_matches = tk.IntVar(value=0)
        matches_cb = tk.Checkbutton(
            options_frame,
            text="Non-stop Online Matches",
            variable=self.enable_non_stop_matches,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary
        )
        matches_cb.pack(anchor=tk.W, pady=2)
        
        # Bongcloud
        self.enable_bongcloud = tk.IntVar(value=0)
        bongcloud_cb = tk.Checkbutton(
            options_frame,
            text="Bongcloud Opening",
            variable=self.enable_bongcloud,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary
        )
        bongcloud_cb.pack(anchor=tk.W, pady=2)
        
        # Random delay
        self.enable_random_delay = tk.BooleanVar(value=False)
        delay_cb = tk.Checkbutton(
            options_frame,
            text="Random Delays (Human-like)",
            variable=self.enable_random_delay,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary
        )
        delay_cb.pack(anchor=tk.W, pady=2)
        
        # Mouse latency
        latency_frame = tk.Frame(options_frame, bg=self.bg_secondary)
        latency_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            latency_frame,
            text="Mouse Latency (seconds)",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(anchor=tk.W)
        
        self.mouse_latency = tk.DoubleVar(value=0.0)
        self.mouse_latency_scale = tk.Scale(
            latency_frame,
            from_=0.0,
            to=15,
            resolution=0.2,
            orient=tk.HORIZONTAL,
            variable=self.mouse_latency,
            bg=self.bg_tertiary,
            fg=self.text_primary,
            troughcolor=self.bg_primary,
            highlightthickness=0,
            relief=tk.FLAT
        )
        self.mouse_latency_scale.pack(fill=tk.X)

    def create_stockfish_section(self, parent):
        """Create Stockfish parameters section"""
        self.create_section_header(parent, "STOCKFISH ENGINE")
        
        sf_frame = tk.Frame(parent, bg=self.bg_secondary)
        sf_frame.pack(fill=tk.X, padx=15, pady=5)
        
        # Engine selection first
        tk.Label(
            sf_frame,
            text="Engine Executable",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(anchor=tk.W, pady=(0, 5))
        
        self.stockfish_path = ""
        
        sf_button = tk.Button(
            sf_frame,
            text="📁 SELECT STOCKFISH ENGINE",
            command=self.on_select_stockfish_button_listener,
            font=("Segoe UI", 9, "bold"),
            bg=self.accent_color,
            fg="#1e1e2e",
            activebackground=self.accent_hover,
            relief=tk.FLAT,
            cursor="hand2",
            pady=8
        )
        sf_button.pack(fill=tk.X, pady=2)
        
        # Path display frame
        path_display_frame = tk.Frame(sf_frame, bg=self.bg_tertiary, relief=tk.FLAT)
        path_display_frame.pack(fill=tk.X, pady=(2, 10))
        
        self.stockfish_path_text = tk.Label(
            path_display_frame,
            text="⚠ No engine selected",
            font=("Segoe UI", 8),
            bg=self.bg_tertiary,
            fg=self.warning_color,
            wraplength=320,
            justify=tk.LEFT,
            padx=8,
            pady=8
        )
        self.stockfish_path_text.pack(fill=tk.X)
        
        # Divider
        tk.Frame(sf_frame, height=1, bg=self.accent_color).pack(fill=tk.X, pady=10)
        
        tk.Label(
            sf_frame,
            text="Engine Parameters",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(anchor=tk.W, pady=(0, 5))
        
        # Slow mover
        slow_frame = tk.Frame(sf_frame, bg=self.bg_secondary)
        slow_frame.pack(fill=tk.X, pady=3)
        
        tk.Label(
            slow_frame,
            text="Slow Mover:",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary,
            width=13,
            anchor=tk.W
        ).pack(side=tk.LEFT)
        
        self.slow_mover = tk.IntVar(value=100)
        slow_entry = tk.Entry(
            slow_frame,
            textvariable=self.slow_mover,
            font=("Segoe UI", 9),
            bg=self.bg_tertiary,
            fg=self.text_primary,
            width=10,
            relief=tk.FLAT,
            insertbackground=self.text_primary
        )
        slow_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(
            slow_frame,
            text="(10-1000)",
            font=("Segoe UI", 8),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(side=tk.LEFT)
        
        # Skill level
        skill_frame = tk.Frame(sf_frame, bg=self.bg_secondary)
        skill_frame.pack(fill=tk.X, pady=5)
        
        skill_label_frame = tk.Frame(skill_frame, bg=self.bg_secondary)
        skill_label_frame.pack(fill=tk.X)
        
        tk.Label(
            skill_label_frame,
            text="Skill Level:",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(side=tk.LEFT)
        
        self.skill_level_label = tk.Label(
            skill_label_frame,
            text="20",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_secondary,
            fg=self.accent_color
        )
        self.skill_level_label.pack(side=tk.LEFT, padx=5)
        
        self.skill_level = tk.IntVar(value=20)
        self.skill_level_scale = tk.Scale(
            skill_frame,
            from_=0,
            to=20,
            orient=tk.HORIZONTAL,
            variable=self.skill_level,
            bg=self.bg_tertiary,
            fg=self.text_primary,
            troughcolor=self.bg_primary,
            highlightthickness=0,
            relief=tk.FLAT,
            showvalue=0,
            command=lambda v: self.skill_level_label.config(text=str(int(float(v))))
        )
        self.skill_level_scale.pack(fill=tk.X)
        
        # Depth
        depth_frame = tk.Frame(sf_frame, bg=self.bg_secondary)
        depth_frame.pack(fill=tk.X, pady=5)
        
        depth_label_frame = tk.Frame(depth_frame, bg=self.bg_secondary)
        depth_label_frame.pack(fill=tk.X)
        
        tk.Label(
            depth_label_frame,
            text="Search Depth:",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(side=tk.LEFT)
        
        self.depth_level_label = tk.Label(
            depth_label_frame,
            text="15",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_secondary,
            fg=self.accent_color
        )
        self.depth_level_label.pack(side=tk.LEFT, padx=5)
        
        self.stockfish_depth = tk.IntVar(value=15)
        self.stockfish_depth_scale = tk.Scale(
            depth_frame,
            from_=1,
            to=20,
            orient=tk.HORIZONTAL,
            variable=self.stockfish_depth,
            bg=self.bg_tertiary,
            fg=self.text_primary,
            troughcolor=self.bg_primary,
            highlightthickness=0,
            relief=tk.FLAT,
            showvalue=0,
            command=lambda v: self.depth_level_label.config(text=str(int(float(v))))
        )
        self.stockfish_depth_scale.pack(fill=tk.X)
        
        # Memory
        mem_frame = tk.Frame(sf_frame, bg=self.bg_secondary)
        mem_frame.pack(fill=tk.X, pady=3)
        
        tk.Label(
            mem_frame,
            text="Memory (Hash):",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary,
            width=13,
            anchor=tk.W
        ).pack(side=tk.LEFT)
        
        self.memory = tk.IntVar(value=512)
        mem_entry = tk.Entry(
            mem_frame,
            textvariable=self.memory,
            font=("Segoe UI", 9),
            bg=self.bg_tertiary,
            fg=self.text_primary,
            width=8,
            relief=tk.FLAT,
            insertbackground=self.text_primary
        )
        mem_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(
            mem_frame,
            text="MB",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(side=tk.LEFT)
        
        # CPU Threads
        cpu_frame = tk.Frame(sf_frame, bg=self.bg_secondary)
        cpu_frame.pack(fill=tk.X, pady=3)
        
        tk.Label(
            cpu_frame,
            text="CPU Threads:",
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_secondary,
            width=13,
            anchor=tk.W
        ).pack(side=tk.LEFT)
        
        self.cpu_threads = tk.IntVar(value=1)
        cpu_entry = tk.Entry(
            cpu_frame,
            textvariable=self.cpu_threads,
            font=("Segoe UI", 9),
            bg=self.bg_tertiary,
            fg=self.text_primary,
            width=8,
            relief=tk.FLAT,
            insertbackground=self.text_primary
        )
        cpu_entry.pack(side=tk.LEFT, padx=5)

    def create_misc_section(self, parent):
        """Create miscellaneous settings section"""
        self.create_section_header(parent, "MISCELLANEOUS")
        
        misc_frame = tk.Frame(parent, bg=self.bg_secondary)
        misc_frame.pack(fill=tk.X, padx=15, pady=5)
        
        # Topmost
        self.enable_topmost = tk.IntVar(value=1)
        topmost_cb = tk.Checkbutton(
            misc_frame,
            text="Window Stays on Top",
            variable=self.enable_topmost,
            command=self.on_topmost_check_button_listener,
            font=("Segoe UI", 9),
            bg=self.bg_secondary,
            fg=self.text_primary,
            selectcolor=self.bg_tertiary,
            activebackground=self.bg_secondary
        )
        topmost_cb.pack(anchor=tk.W, pady=2)
        
        # Keyboard shortcuts info
        tk.Label(
            misc_frame,
            text="⌨ Keyboard Shortcuts",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_secondary,
            fg=self.text_secondary
        ).pack(anchor=tk.W, pady=(10, 5))
        
        shortcuts_info = tk.Frame(misc_frame, bg=self.bg_tertiary)
        shortcuts_info.pack(fill=tk.X, pady=2)
        
        shortcuts_text = """Press 1 - Start Bot
Press 2 - Stop Bot
Press 3 - Make Move (Manual Mode)"""
        
        tk.Label(
            shortcuts_info,
            text=shortcuts_text,
            font=("Segoe UI", 8),
            bg=self.bg_tertiary,
            fg=self.text_secondary,
            justify=tk.LEFT,
            padx=8,
            pady=8
        ).pack(anchor=tk.W)

    def create_moves_section(self, parent):
        """Create moves display section"""
        # Header
        header_frame = tk.Frame(parent, bg=self.bg_tertiary)
        header_frame.pack(fill=tk.X)
        
        tk.Label(
            header_frame,
            text="GAME MOVES",
            font=("Segoe UI", 12, "bold"),
            bg=self.bg_tertiary,
            fg=self.accent_color,
            pady=10
        ).pack()
        
        # Treeview container
        tree_container = tk.Frame(parent, bg=self.bg_secondary)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Style for Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background=self.bg_tertiary,
            foreground=self.text_primary,
            fieldbackground=self.bg_tertiary,
            borderwidth=0,
            relief=tk.FLAT
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=self.bg_primary,
            foreground=self.accent_color,
            relief=tk.FLAT
        )
        style.map("Custom.Treeview", background=[("selected", self.accent_color)])
        
        # Create Treeview
        self.tree = ttk.Treeview(
            tree_container,
            columns=("#", "White", "Black"),
            show="headings",
            height=23,
            selectmode="browse",
            style="Custom.Treeview"
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        self.vsb = ttk.Scrollbar(
            tree_container,
            orient="vertical",
            command=self.tree.yview
        )
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=self.vsb.set)
        
        # Configure columns
        self.tree.column("#1", anchor=tk.CENTER, width=50)
        self.tree.heading("#1", text="#")
        self.tree.column("#2", anchor=tk.CENTER, width=80)
        self.tree.heading("#2", text="White")
        self.tree.column("#3", anchor=tk.CENTER, width=80)
        self.tree.heading("#3", text="Black")
        
        # Export button
        self.export_pgn_button = tk.Button(
            parent,
            text="EXPORT TO PGN",
            command=self.on_export_pgn_button_listener,
            font=("Segoe UI", 10, "bold"),
            bg=self.accent_color,
            fg="#1e1e2e",
            activebackground=self.accent_hover,
            relief=tk.FLAT,
            cursor="hand2",
            pady=8
        )
        self.export_pgn_button.pack(fill=tk.X, padx=10, pady=(0, 10))

    def on_time_control_change(self):
        """Handle time control selection change"""
        selected = self.time_control.get()
        
        if selected == "blitz":
            # Blitz settings: faster, lighter
            self.enable_random_delay.set(True)
            self.mouse_latency.set(0.1)
            self.stockfish_depth.set(12)
            self.slow_mover.set(50)
            self.custom_delay_frame.pack_forget()
        elif selected == "rapid":
            # Rapid settings: moderate speed
            self.enable_random_delay.set(True)
            self.mouse_latency.set(0.2)
            self.stockfish_depth.set(15)
            self.slow_mover.set(80)
            self.custom_delay_frame.pack_forget()
        else:  # custom
            # Show custom delay configuration
            self.custom_delay_frame.pack(fill=tk.X, pady=5)

    def get_delay_range(self):
        """Get delay range based on time control"""
        time_ctrl = self.time_control.get()
        if time_ctrl == "blitz":
            return (1, 5)
        elif time_ctrl == "rapid":
            return (5, 10)
        else:
            return (self.custom_delay_min.get(), self.custom_delay_max.get())

    def start_background_threads(self):
        """Start all background monitoring threads"""
        threading.Thread(target=self.process_checker_thread, daemon=True).start()
        threading.Thread(target=self.browser_checker_thread, daemon=True).start()
        threading.Thread(target=self.process_communicator_thread, daemon=True).start()
        threading.Thread(target=self.keypress_listener_thread, daemon=True).start()

    def on_close_listener(self):
        """Handle window close event"""
        self.exit = True
        if self.stockfish_bot_process and self.stockfish_bot_process.is_alive():
            self.stockfish_bot_process.kill()
        if self.overlay_screen_process and self.overlay_screen_process.is_alive():
            self.overlay_screen_process.kill()
        self.master.destroy()

    def process_checker_thread(self):
        """Monitor Stockfish Bot process status"""
        while not self.exit:
            if (self.running and self.stockfish_bot_process is not None 
                and not self.stockfish_bot_process.is_alive()):
                self.on_stop_button_listener()
                if self.restart_after_stopping:
                    self.restart_after_stopping = False
                    self.on_start_button_listener()
            time.sleep(0.1)

    def browser_checker_thread(self):
        """Monitor browser status"""
        while not self.exit:
            try:
                if (self.opened_browser and self.chrome is not None 
                    and "target window already closed" in self.chrome.get_log("driver")[-1]["message"]):
                    self.opened_browser = False
                    self.open_browser_button["text"] = "OPEN BROWSER"
                    self.open_browser_button["state"] = "normal"
                    self.on_stop_button_listener()
                    self.chrome = None
            except (IndexError, Exception):
                pass
            time.sleep(0.1)

    def process_communicator_thread(self):
        """Handle communication with Stockfish Bot process"""
        while not self.exit:
            try:
                if self.stockfish_bot_pipe is not None and self.stockfish_bot_pipe.poll():
                    data = self.stockfish_bot_pipe.recv()
                    
                    if data == "START":
                        self.clear_tree()
                        self.match_moves = []
                        self.status_text["text"] = "RUNNING"
                        self.start_button["text"] = "STOP BOT"
                        self.start_button["bg"] = self.error_color
                        self.start_button["state"] = "normal"
                        self.start_button["command"] = self.on_stop_button_listener
                        
                    elif data == "RESTART":
                        self.restart_after_stopping = True
                        self.stockfish_bot_pipe.send("DELETE")
                        
                    elif data.startswith("S_MOVE"):
                        move = data[6:]
                        self.match_moves.append(move)
                        self.insert_move(move)
                        self.tree.yview_moveto(1)
                        
                    elif data.startswith("M_MOVE"):
                        moves = data[6:].split(",")
                        self.match_moves += moves
                        self.set_moves(moves)
                        self.tree.yview_moveto(1)
                        
                    elif data.startswith("EVAL|"):
                        parts = data.split("|")
                        if len(parts) >= 6:
                            eval_str, wdl_str, material_str, bot_acc, opp_acc = parts[1:6]
                            self.update_evaluation_display(eval_str, wdl_str, material_str, bot_acc, opp_acc)
                            
                    elif data.startswith("ERR_"):
                        error_messages = {
                            "ERR_EXE": "Stockfish path is not valid!",
                            "ERR_PERM": "Stockfish executable lacks permissions!",
                            "ERR_BOARD": "Cannot find chess board!",
                            "ERR_COLOR": "Cannot determine player color!",
                            "ERR_MOVES": "Cannot find moves list!",
                            "ERR_GAMEOVER": "Game has already finished!"
                        }
                        msg = error_messages.get(data[:12], "Unknown error occurred")
                        tk.messagebox.showerror("Error", msg)
                        
            except (BrokenPipeError, OSError):
                self.stockfish_bot_pipe = None
            time.sleep(0.1)

    def keypress_listener_thread(self):
        """Listen for keyboard shortcuts"""
        while not self.exit:
            time.sleep(0.1)
            if not self.opened_browser:
                continue
            if keyboard.is_pressed("1"):
                self.on_start_button_listener()
            elif keyboard.is_pressed("2"):
                self.on_stop_button_listener()

    def on_open_browser_button_listener(self):
        """Handle browser opening"""
        self.opening_browser = True
        self.open_browser_button["text"] = "Opening..."
        self.open_browser_button["state"] = "disabled"
        
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            chrome_install = ChromeDriverManager().install()
            folder = os.path.dirname(chrome_install)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")
            service = ChromeService(chromedriver_path)
            self.chrome = webdriver.Chrome(service=service, options=options)
        except WebDriverException:
            self.opening_browser = False
            self.open_browser_button["text"] = "OPEN BROWSER"
            self.open_browser_button["state"] = "normal"
            tk.messagebox.showerror("Error", "Chrome browser not found. Please install Chrome.")
            return
        except Exception as e:
            self.opening_browser = False
            self.open_browser_button["text"] = "OPEN BROWSER"
            self.open_browser_button["state"] = "normal"
            tk.messagebox.showerror("Error", f"Browser error: {e}")
            return
        
        url = "https://www.chess.com" if self.website.get() == "chesscom" else "https://www.lichess.org"
        self.chrome.get(url)
        
        self.chrome_url = self.chrome.service.service_url
        self.chrome_session_id = self.chrome.session_id
        
        self.opening_browser = False
        self.opened_browser = True
        self.open_browser_button["text"] = "BROWSER OPEN"
        self.open_browser_button["bg"] = self.success_color
        self.start_button["state"] = "normal"

    def on_start_button_listener(self):
        """Handle bot start"""
        if self.slow_mover.get() < 10 or self.slow_mover.get() > 1000:
            tk.messagebox.showerror("Error", "Slow Mover must be between 10 and 1000")
            return
        
        if self.stockfish_path == "":
            tk.messagebox.showerror("Error", "Please select Stockfish executable")
            return
        
        if self.enable_mouseless_mode.get() and self.website.get() == "chesscom":
            tk.messagebox.showerror("Error", "Mouseless mode only works on Lichess")
            return
        
        parent_conn, child_conn = multiprocess.Pipe()
        self.stockfish_bot_pipe = parent_conn
        st_ov_queue = multiprocess.Queue()
        
        # Get delay range based on time control
        delay_min, delay_max = self.get_delay_range()
        
        self.stockfish_bot_process = StockfishBot(
            self.chrome_url,
            self.chrome_session_id,
            self.website.get(),
            child_conn,
            st_ov_queue,
            self.stockfish_path,
            self.enable_manual_mode.get(),
            self.enable_mouseless_mode.get(),
            self.enable_non_stop_puzzles.get() == 1,
            self.enable_non_stop_matches.get() == 1,
            self.mouse_latency.get(),
            self.enable_bongcloud.get() == 1,
            self.slow_mover.get(),
            self.skill_level.get(),
            self.stockfish_depth.get(),
            self.memory.get(),
            self.cpu_threads.get(),
            self.enable_random_delay.get(),
            delay_min,
            delay_max
        )
        self.stockfish_bot_process.start()
        
        self.overlay_screen_process = multiprocess.Process(target=run, args=(st_ov_queue,))
        self.overlay_screen_process.start()
        
        self.running = True
        self.start_button["text"] = "Starting..."
        self.start_button["state"] = "disabled"

    def on_stop_button_listener(self):
        """Handle bot stop"""
        if self.stockfish_bot_process is not None:
            if self.overlay_screen_process is not None:
                self.overlay_screen_process.kill()
                self.overlay_screen_process = None
            if self.stockfish_bot_process.is_alive():
                self.stockfish_bot_process.kill()
            self.stockfish_bot_process = None
        
        if self.stockfish_bot_pipe is not None:
            self.stockfish_bot_pipe.close()
            self.stockfish_bot_pipe = None
        
        self.running = False
        self.status_text["text"] = "INACTIVE"
        
        # Reset evaluation displays
        self.eval_text["text"] = "-"
        self.wdl_text["text"] = "-"
        self.material_text["text"] = "-"
        self.bot_acc_text["text"] = "-"
        self.opp_acc_text["text"] = "-"
        
        if not self.restart_after_stopping:
            self.start_button["text"] = "START BOT"
            self.start_button["bg"] = self.success_color
            self.start_button["state"] = "normal"
            self.start_button["command"] = self.on_start_button_listener
        else:
            self.restart_after_stopping = False
            self.on_start_button_listener()

    def on_topmost_check_button_listener(self):
        """Toggle window topmost status"""
        self.master.attributes("-topmost", self.enable_topmost.get() == 1)

    def on_export_pgn_button_listener(self):
        """Export game to PGN file"""
        f = filedialog.asksaveasfile(
            initialfile="match.pgn",
            defaultextension=".pgn",
            filetypes=[("Portable Game Notation", "*.pgn"), ("All Files", "*.*")]
        )
        if f is None:
            return
        
        data = ""
        for i in range(len(self.match_moves) // 2 + 1):
            if len(self.match_moves) % 2 == 0 and i == len(self.match_moves) // 2:
                continue
            data += f"{i + 1}. "
            data += self.match_moves[i * 2] + " "
            if (i * 2) + 1 < len(self.match_moves):
                data += self.match_moves[i * 2 + 1] + " "
        f.write(data)
        f.close()

    def on_select_stockfish_button_listener(self):
        """Select Stockfish executable"""
        f = filedialog.askopenfilename(
            title="Select Stockfish Engine",
            filetypes=[
                ("Executable files", "*.exe"),
                ("All files", "*.*")
            ]
        )
        if f:
            self.stockfish_path = f
            # Show just the filename, but display full path on hover
            filename = os.path.basename(f)
            self.stockfish_path_text["text"] = f"✓ {filename}"
            self.stockfish_path_text["fg"] = self.success_color
            
            # Store full path as tooltip info
            self.stockfish_path_text.bind("<Enter>", lambda e: self.show_tooltip(e, f))
            self.stockfish_path_text.bind("<Leave>", lambda e: self.hide_tooltip())
    
    def show_tooltip(self, event, text):
        """Show tooltip with full path"""
        try:
            # Create tooltip window
            self.tooltip = tk.Toplevel()
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(
                self.tooltip,
                text=text,
                background=self.bg_primary,
                foreground=self.text_primary,
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 8),
                padx=5,
                pady=3
            )
            label.pack()
        except:
            pass
    
    def hide_tooltip(self):
        """Hide tooltip"""
        try:
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                del self.tooltip
        except:
            pass

    def clear_tree(self):
        """Clear moves treeview"""
        self.tree.delete(*self.tree.get_children())

    def insert_move(self, move):
        """Insert a move into the treeview"""
        cells_num = sum([len(self.tree.item(i)["values"]) - 1 for i in self.tree.get_children()])
        if cells_num % 2 == 0:
            rows_num = len(self.tree.get_children())
            self.tree.insert("", "end", values=(rows_num + 1, move))
        else:
            self.tree.set(self.tree.get_children()[-1], column=2, value=move)

    def set_moves(self, moves):
        """Set all moves in treeview"""
        self.clear_tree()
        pairs = list(zip(*[iter(moves)] * 2))
        for i, pair in enumerate(pairs):
            self.tree.insert("", "end", values=(str(i + 1), pair[0], pair[1]))
        if len(moves) % 2 == 1:
            self.tree.insert("", "end", values=(len(pairs) + 1, moves[-1]))

    def update_evaluation_display(self, eval_str, wdl_str, material_str, bot_acc, opp_acc):
        """Update evaluation display with colors"""
        self.eval_text["text"] = eval_str
        try:
            if eval_str.startswith("M"):
                mate_value = int(eval_str[1:])
                self.eval_text["fg"] = self.success_color if mate_value > 0 else self.error_color
            else:
                eval_value = float(eval_str)
                if eval_value > 0:
                    self.eval_text["fg"] = self.success_color
                elif eval_value < 0:
                    self.eval_text["fg"] = self.error_color
                else:
                    self.eval_text["fg"] = self.text_primary
        except ValueError:
            self.eval_text["fg"] = self.text_primary
        
        self.wdl_text["text"] = wdl_str
        self.material_text["text"] = material_str
        
        try:
            if material_str.startswith("+"):
                self.material_text["fg"] = self.success_color
            elif material_str.startswith("-"):
                self.material_text["fg"] = self.error_color
            else:
                self.material_text["fg"] = self.text_primary
        except:
            self.material_text["fg"] = self.text_primary
        
        self.bot_acc_text["text"] = bot_acc
        self.opp_acc_text["text"] = opp_acc


if __name__ == "__main__":
    window = tk.Tk()
    gui = ModernGUI(window)
    window.mainloop()
