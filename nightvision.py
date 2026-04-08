import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import keyboard
import ctypes
import sys
import os
import datetime
import urllib.request
import urllib.parse
import json
import threading
import webbrowser
import time
import http.server
from PIL import Image, ImageTk, ImageSequence

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20

API_BASE_URL = "https://researcharea01.onrender.com/api"

# ==== DISCORD OAUTH2 SETTINGS ====
# Replace this with your App's Client ID and ensure http://localhost:31337/callback is in your Redirect URIs!
DISCORD_CLIENT_ID = "1491544017534586980"
DISCORD_REDIRECT_URI = "http://localhost:31337/callback"

class RadioApp:
    def __init__(self, root, username="Administrator"):
        self.root = root
        self.username = username
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.geometry("550x330+300+200")
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.75)
        self.window.configure(bg="#000000", highlightthickness=1, highlightbackground="#aaaaaa")
        self.window.withdraw()
        
        self.base_channels = [
            ("Broadcasts", "CH0"),
            ("Personnel", "CH1"),
            ("Security Defense", "CH2"),
            ("Special Response Unit", "CH3"),
            ("Administration", "CH4")
        ]
        self.channels = self.base_channels.copy()
        self.chat_histories = {ch[1]: [] for ch in self.base_channels}
        self.last_raw_data = {}
        self.current_ch_idx = 1 # Start on Personnel
        
        self.broadcast_enabled = True
        self.settings_open = False
        self.is_enabled = False
        
        self.build_ui()
        self.update_channels_list()
        self.register_radio_hotkeys()
        self.poll_messages()

    def build_ui(self):
        self.top_frame = tk.Frame(self.window, bg="#000000", height=35)
        self.top_frame.pack(fill=tk.X, side=tk.TOP)
        self.top_frame.pack_propagate(False)

        def start_move(event): self.window.x = event.x; self.window.y = event.y
        def stop_move(event): self.window.x = None; self.window.y = None
        def do_move(event):
            x = (event.x_root - self.window.x)
            y = (event.y_root - self.window.y)
            self.window.geometry(f"+{x}+{y}")

        self.top_frame.bind("<ButtonPress-1>", start_move)
        self.top_frame.bind("<ButtonRelease-1>", stop_move)
        self.top_frame.bind("<B1-Motion>", do_move)

        tk.Label(self.top_frame, text="🔊 🔇", bg="#000000", fg="#888888").pack(side=tk.LEFT, padx=10)

        center_frame = tk.Frame(self.top_frame, bg="#000000")
        center_frame.pack(side=tk.LEFT, expand=True)

        self.ch_name_lbl = tk.Label(center_frame, text="Personnel", bg="#2b3b22", fg="#a4e473", borderwidth=1, relief="solid", font=("Segoe UI", 9))
        self.ch_name_lbl.pack(side=tk.LEFT, pady=4, padx=5)
        
        tk.Label(center_frame, text="🔒", bg="#000000", fg="#aa4444").pack(side=tk.LEFT, padx=2)

        self.ch_frame = tk.Frame(self.top_frame, bg="#2b3b22", highlightbackground="#555555", highlightthickness=1)
        self.ch_frame.pack(side=tk.RIGHT, padx=15, pady=4)
        
        self.settings_btn = tk.Label(self.ch_frame, text=" ⚙ ", bg="#000000", fg="#ffffff", cursor="hand2", font=("Segoe UI", 10))
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 2))
        self.settings_btn.bind("<Button-1>", lambda e: self.toggle_settings())
        
        btn_next = tk.Label(self.ch_frame, text=" > ", bg="#000000", fg="#ffffff", cursor="hand2", font=("Segoe UI", 10, "bold"))
        btn_next.pack(side=tk.RIGHT)
        btn_next.bind("<Button-1>", lambda e: self.change_ch(1))

        self.ch_label = tk.Label(self.ch_frame, text=" CH1 ", bg="#2b3b22", fg="#a4e473", font=("Segoe UI", 9, "bold"))
        self.ch_label.pack(side=tk.RIGHT)

        btn_prev = tk.Label(self.ch_frame, text=" < ", bg="#000000", fg="#ffffff", cursor="hand2", font=("Segoe UI", 10, "bold"))
        btn_prev.pack(side=tk.RIGHT)
        btn_prev.bind("<Button-1>", lambda e: self.change_ch(-1))

        self.content_frame = tk.Frame(self.window, bg="#000000")
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_frame = tk.Frame(self.content_frame, bg="#000000")
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.settings_frame = tk.Frame(self.content_frame, bg="#111111", highlightbackground="#333333", highlightthickness=1)
        
        tk.Label(self.settings_frame, text="SETTINGS", bg="#111111", fg="#ffffff", font=("Verdana", 9, "bold")).pack(pady=10)
        
        cb_frame = tk.Frame(self.settings_frame, bg="#111111")
        cb_frame.pack(fill=tk.X, padx=20, pady=5)
        self.broadcast_var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(cb_frame, text="Enable Broadcast Messages (CH 0)", variable=self.broadcast_var, command=self.update_channels_list,
                            bg="#111111", fg="#dddddd", selectcolor="#2b3b22", activebackground="#111111", activeforeground="#dddddd")
        cb.pack(side=tk.LEFT)
        
        self.entry_frame = tk.Frame(self.chat_frame, bg="#000000")
        self.entry_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=10)
        
        self.inner_frame = tk.Frame(self.entry_frame, bg="#1a1a1a", highlightbackground="#444444", highlightthickness=1)
        self.inner_frame.pack(fill=tk.X)
        
        tk.Label(self.inner_frame, text=" Type message... ", bg="#1a1a1a", fg="#aaaaaa", font=("Verdana", 8)).pack(side=tk.LEFT)
        
        self.chat_entry = tk.Entry(self.inner_frame, bg="#1a1a1a", fg="#ffffff", font=("Verdana", 9), bd=0, highlightthickness=0, insertbackground="#ffffff")
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)
        self.chat_entry.bind("<Return>", self.send_message)

        self.chat_text = tk.Text(self.chat_frame, bg="#000000", fg="#ffffff", font=("Verdana", 9), bd=0, highlightthickness=0, state="disabled")
        self.chat_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=(5, 0))
        
        self.update_ch_labels()
        
    def toggle_settings(self):
        self.settings_open = not self.settings_open
        if self.settings_open:
            self.chat_frame.pack_forget()
            self.settings_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        else:
            self.settings_frame.pack_forget()
            self.chat_frame.pack(fill=tk.BOTH, expand=True)
            
    def register_radio_hotkeys(self):
        import keyboard
        keyboard.on_press_key('[', lambda e: self.root.after(0, lambda: self.change_ch(-1)))
        keyboard.on_press_key(']', lambda e: self.root.after(0, lambda: self.change_ch(1)))
        
    def update_channels_list(self):
        if self.broadcast_var.get():
            self.channels = self.base_channels.copy()
        else:
            self.channels = [ch for ch in self.base_channels if ch[1] != "CH0"]
            
        # Reposition active channel safely
        if self.current_ch_idx >= len(self.channels):
            self.current_ch_idx = len(self.channels) - 1
        self.update_ch_labels()

    def change_ch(self, direction):
        if not self.is_enabled:
            return
        self.current_ch_idx = (self.current_ch_idx + direction) % len(self.channels)
        self.update_ch_labels()
        
    def update_ch_labels(self):
        name, ch_id = self.channels[self.current_ch_idx]
        self.ch_name_lbl.config(text=f"  {name}  ")
        self.ch_label.config(text=f" {ch_id.replace('CH', '')} ")
        
        if ch_id == "CH0":
            self.inner_frame.pack_forget()
        else:
            self.inner_frame.pack(fill=tk.X)
            self.chat_entry.config(state="normal")
        
        self.chat_text.config(state="normal")
        self.chat_text.delete(1.0, tk.END)
        for header, text in self.chat_histories[ch_id]:
            self.insert_chat_raw(header, text)
        self.chat_text.see(tk.END)
        self.chat_text.config(state="disabled")

    def get_user_color(self, username):
        import hashlib
        colors = [
            "#a4e473", "#73c2e4", "#e47373", "#e4b473", 
            "#c473e4", "#73e4b4", "#ff8a65", "#ba68c8", 
            "#4fc3f7", "#81c784", "#ffd54f", "#f06292"
        ]
        # Hash the username so they always get the *same* color back reliably
        hash_val = int(hashlib.md5(username.encode('utf-8')).hexdigest(), 16)
        return colors[hash_val % len(colors)]

    def insert_chat_raw(self, header, text):
        start_idx = self.chat_text.index(tk.INSERT)
        self.chat_text.insert(tk.END, header + "\n")
        end_idx = self.chat_text.index(tk.INSERT)
        
        username = header.split(" SEC ", 1)[-1] if " SEC " in header else header
        user_color = self.get_user_color(username)
        tag_name = f"user_tag_{username}"
        
        # Apply the dark-green background, but dynamically set their name's specific foreground color
        self.chat_text.tag_configure(tag_name, background="#2b3b22", foreground=user_color, font=("Verdana", 9, "bold"))
        self.chat_text.tag_add(tag_name, start_idx, end_idx + "-1c")
        
        self.chat_text.insert(tk.END, text + "\n\n")

    def send_message(self, event):
        msg = self.chat_entry.get().strip()
        ch_id = self.channels[self.current_ch_idx][1]
        
        if msg and ch_id != "CH0":
            now = datetime.datetime.now().strftime("%H%M SEC")
            header = f"{now} {self.username}"
            self.chat_entry.delete(0, tk.END)
            
            # Predictively render it for the user
            self.append_chat(header, msg)
            
            # Send securely without blocking
            def send():
                try:
                    payload = json.dumps({"ch": ch_id, "header": header, "text": msg}).encode('utf-8')
                    req = urllib.request.Request(API_BASE_URL + "/radio", data=payload, headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=3)
                except Exception:
                    pass
                    
            threading.Thread(target=send, daemon=True).start()

    def append_chat(self, header, text):
        ch_id = self.channels[self.current_ch_idx][1]
        self.chat_histories[ch_id].append((header, text))
        self.chat_text.config(state="normal")
        self.insert_chat_raw(header, text)
        self.chat_text.see(tk.END)
        self.chat_text.config(state="disabled")

    def toggle(self):
        self.is_enabled = True
        if self.window.state() == "withdrawn":
            self.window.deiconify()
        else:
            self.window.withdraw()

    def poll_messages(self):
        def fetch():
            try:
                ch_id = self.channels[self.current_ch_idx][1]
                url = f"{API_BASE_URL}/radio?ch={ch_id}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    # Instead of length limits failing at 50 capacity, we strictly execute deep delta validation
                    if data != self.last_raw_data.get(ch_id, []):
                        self.last_raw_data[ch_id] = data
                        self.chat_histories[ch_id] = [(m['header'], m['text']) for m in data]
                        
                        # Only trigger an aggressive visual rebuild if the user is physically looking at it
                        if ch_id == self.channels[self.current_ch_idx][1]:
                            self.root.after(0, self.refresh_active_ui_layer)
            except Exception:
                pass
            finally:
                self.root.after(1000, self.poll_messages)
                
        threading.Thread(target=fetch, daemon=True).start()

    def refresh_active_ui_layer(self):
        ch_id = self.channels[self.current_ch_idx][1]
        self.chat_text.config(state="normal")
        self.chat_text.delete(1.0, tk.END)
        for header, text in self.chat_histories[ch_id]:
            self.insert_chat_raw(header, text)
        self.chat_text.see(tk.END)
        self.chat_text.config(state="disabled")

    def render_polled_chat(self, header, text):
        self.chat_text.config(state="normal")
        self.insert_chat_raw(header, text)
        self.chat_text.see(tk.END)
        self.chat_text.config(state="disabled")

class TerminalApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Standard Operations Terminal")
        self.root.geometry("850x520")
        
        self.root.overrideredirect(True)
        self.root.configure(bg="#121212", highlightthickness=1, highlightbackground="#444444")
        self.root.attributes("-topmost", True)
        self.root.withdraw() # Hide terminal during boot sequence

        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        self.overlay.attributes("-topmost", True)
        self.overlay.config(bg='#39ff14')
        self.overlay.attributes("-alpha", 0.0)
        
        self.is_active = False
        self.toggle_key = None
        self.awaiting_rebind = False
        
        self.setup_clickthrough()
        self.build_ui()
        self.radio = None
        
        self.start_auth_sequence()

    def start_auth_sequence(self):
        self.auth_screen = tk.Toplevel(self.root)
        self.auth_screen.overrideredirect(True)
        self.auth_screen.attributes("-topmost", True)
        
        bg_col = "#1d1e22"
        self.auth_screen.config(bg=bg_col, highlightthickness=1, highlightbackground="#ffffff")
        
        sw = self.auth_screen.winfo_screenwidth()
        sh = self.auth_screen.winfo_screenheight()
        w, h = 420, 240
        x = (sw//2) - (w//2)
        y = (sh//2) - (h//2)
        self.auth_screen.geometry(f"{w}x{h}+{x}+{y}")
        
        # Making the auth screen draggable
        def start_move(event):
            self.auth_screen.x = event.x
            self.auth_screen.y = event.y

        def stop_move(event):
            self.auth_screen.x = None
            self.auth_screen.y = None

        def do_move(event):
            x = (event.x_root - self.auth_screen.x)
            y = (event.y_root - self.auth_screen.y)
            self.auth_screen.geometry(f"+{x}+{y}")

        self.auth_screen.bind("<ButtonPress-1>", start_move)
        self.auth_screen.bind("<ButtonRelease-1>", stop_move)
        self.auth_screen.bind("<B1-Motion>", do_move)
        
        self.status_lbl = tk.Label(self.auth_screen, text="Zeta Security Services", bg=bg_col, fg="#cccccc", font=("Consolas", 11, "bold"))
        self.status_lbl.pack(pady=(45, 30))
        
        def do_auth():
            login_btn.config(state="disabled", text="Authenticating...")
            try:
                self.status_lbl.config(text="Browser opened. Awaiting callback...")
                
                auth_data = {"token": None}
                class OAuthHandler(http.server.BaseHTTPRequestHandler):
                    def do_GET(self):
                        parsed_path = urllib.parse.urlparse(self.path)
                        if parsed_path.path == '/callback':
                            self.send_response(200)
                            self.send_header("Content-type", "text/html")
                            self.end_headers()
                            html = """
                            <html><body style='background:#111;color:#aaa;font-family:sans-serif;text-align:center;padding-top:50px;'>
                            <h2 id='msg'>Authenticating... please wait.</h2>
                            <script>
                                const params = new URLSearchParams(window.location.hash.slice(1));
                                const token = params.get('access_token');
                                if (token) {
                                    fetch('/capture?token=' + token).then(() => {
                                        document.getElementById('msg').innerHTML = '<span style="color:#0f0;">Authorized! You may close this tab.</span>';
                                        setTimeout(window.close, 2000);
                                    });
                                } else {
                                    document.getElementById('msg').innerHTML = '<span style="color:#f00;">Error: No token received.</span>';
                                    fetch('/capture?token=ERROR');
                                }
                            </script>
                            </body></html>
                            """
                            self.wfile.write(html.encode('utf-8'))
                        elif parsed_path.path == '/capture':
                            query_params = urllib.parse.parse_qs(parsed_path.query)
                            if 'token' in query_params and query_params['token'][0] != 'ERROR':
                                auth_data['token'] = query_params['token'][0]
                            
                            self.send_response(200)
                            self.end_headers()
                            
                            # Shutdown server asynchronously
                            threading.Thread(target=self.server.shutdown, daemon=True).start()
                        else:
                            self.send_response(404)
                            self.end_headers()
                            
                    def log_message(self, format, *args):
                        pass # keep console clean
                
                server = http.server.HTTPServer(('127.0.0.1', 31337), OAuthHandler)
                
                auth_url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={urllib.parse.quote(DISCORD_REDIRECT_URI)}&response_type=token&scope=identify"
                webbrowser.open(auth_url)
                
                server.serve_forever() # Blocks until OAuth code is received
                
                if not auth_data['token']:
                    self.root.after(0, lambda: self.status_lbl.config(text="Authorization failed.", fg="#ff4444"))
                    self.root.after(0, lambda: login_btn.config(state="normal", text="Login"))
                    return
                
                self.root.after(0, lambda: self.status_lbl.config(text="Token received. Fetching profile..."))
                
                user_req = urllib.request.Request("https://discord.com/api/v10/users/@me")
                user_req.add_header('Authorization', f"Bearer {auth_data['token']}")
                user_req.add_header('User-Agent', 'ZetaTerminal (http://localhost, 1.0)')
                
                with urllib.request.urlopen(user_req) as response:
                    user_data = json.loads(response.read().decode('utf-8'))
                    
                self.username = user_data['username']
                self.root.after(0, self.finish_auth)
                        
            except Exception as e:
                err_msg = str(e)
                self.root.after(0, lambda: self.status_lbl.config(text=f"API Error: {err_msg}", fg="#ff4444"))
                self.root.after(0, lambda: login_btn.config(state="normal", text="Login"))

        button_frame = tk.Frame(self.auth_screen, bg=bg_col)
        button_frame.pack(fill=tk.X, padx=60)
        
        login_btn = tk.Button(button_frame, text="Login", bg="#2a3a2e", fg="#ffffff", font=("Consolas", 11, "bold"), 
                              bd=0, activebackground="#3a4a3e", activeforeground="#ffffff", cursor="hand2", 
                              command=lambda: threading.Thread(target=do_auth, daemon=True).start())
        login_btn.pack(fill=tk.X, pady=(0, 10), ipady=5)
        
        exit_btn = tk.Button(button_frame, text="Exit", bg="#4a2c2c", fg="#ffffff", font=("Consolas", 11, "bold"),
                             bd=0, activebackground="#5a3c3c", activeforeground="#ffffff", cursor="hand2", command=self.close)
        exit_btn.pack(fill=tk.X, ipady=5)

    def finish_auth(self):
        self.auth_screen.destroy()
        self.radio = RadioApp(self.root, self.username)
        self.play_startup_gif()

    def play_startup_gif(self):
        gif_path = resource_path("Images/zeta_startup.gif")
        if not os.path.exists(gif_path):
            self.finish_splash()
            return
            
        self.splash = tk.Toplevel(self.root)
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        self.splash.config(bg="black")
        
        try:
            self.frames = []
            img = Image.open(gif_path)
            for frame in ImageSequence.Iterator(img):
                # Convert frame to RGBA to ensure transparency and palette compatibility is handled securely
                frame_rgba = frame.copy().convert("RGBA")
                self.frames.append(ImageTk.PhotoImage(frame_rgba))
                
            if not self.frames:
                self.finish_splash()
                return

            w = self.frames[0].width()
            h = self.frames[0].height()
            sw = self.splash.winfo_screenwidth()
            sh = self.splash.winfo_screenheight()
            x = (sw//2) - (w//2)
            y = (sh//2) - (h//2)
            self.splash.geometry(f"{w}x{h}+{x}+{y}")
            
            self.lbl = tk.Label(self.splash, bg="black", borderwidth=0)
            self.lbl.pack(fill=tk.BOTH, expand=True)
            self.frame_index = 0
            
            def update_frame():
                self.lbl.config(image=self.frames[self.frame_index])
                self.frame_index += 1
                if self.frame_index < len(self.frames):
                    self.root.after(50, update_frame) # Playback speed
                else:
                    self.root.after(0, self.finish_splash) # Instant cut to terminal
            
            update_frame()
        except Exception as e:
            self.finish_splash()

    def finish_splash(self):
        try:
            self.splash.destroy()
        except:
            pass
        self.root.deiconify() # Reveal operational terminal
        self.register_hotkeys() # Enable functionality

    def setup_clickthrough(self):
        self.overlay.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.overlay.winfo_id())
        if hwnd == 0:
            hwnd = self.overlay.winfo_id()
        current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)

    def register_hotkeys(self):
        import keyboard
        try:
            if hasattr(self, 'toggle_key') and self.toggle_key:
                keyboard.unhook_key(self.toggle_key)
            keyboard.unhook_key('home')
        except Exception:
            pass
            
        if self.toggle_key is not None:
            keyboard.on_press_key(self.toggle_key, lambda e: self.root.after(0, self.toggle_overlay))
        keyboard.on_press_key('home', lambda e: self.root.after(0, self.close))

    def build_ui(self):
        title_bar = tk.Frame(self.root, bg="#3b3b3b", relief="flat", bd=0)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        
        def start_move(event):
            self.root.x = event.x
            self.root.y = event.y

        def stop_move(event):
            self.root.x = None
            self.root.y = None

        def do_move(event):
            x = (event.x_root - self.root.x)
            y = (event.y_root - self.root.y)
            self.root.geometry(f"+{x}+{y}")

        title_bar.bind("<ButtonPress-1>", start_move)
        title_bar.bind("<ButtonRelease-1>", stop_move)
        title_bar.bind("<B1-Motion>", do_move)

        icon_label = tk.Label(title_bar, text="🖵", bg="#3b3b3b", fg="#dddddd", font=("Segoe UI", 11))
        icon_label.pack(side=tk.LEFT, padx=(8, 4), pady=4)
        
        title_label = tk.Label(title_bar, text="Standard Operations Terminal", bg="#3b3b3b", fg="#dddddd", font=("Segoe UI", 9))
        title_label.pack(side=tk.LEFT, pady=4)
        
        close_btn = tk.Label(title_bar, text="✕", bg="#3b3b3b", fg="#dddddd", font=("Segoe UI", 10), width=4)
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#e81123", fg="white"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#3b3b3b", fg="#dddddd"))
        close_btn.bind("<Button-1>", lambda e: self.close())

        self.term_frame = tk.Frame(self.root, bg="#121212")
        self.term_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Vertical.TScrollbar", gripcount=0,
                        background="#555555", darkcolor="#555555", lightcolor="#555555",
                        troughcolor="#1e1e1e", bordercolor="#1e1e1e", arrowcolor="#aaaaaa")
        
        self.scrollbar = ttk.Scrollbar(self.term_frame, style="Vertical.TScrollbar")
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        term_font = tkfont.Font(family="Consolas", size=10)
        self.text_widget = tk.Text(self.term_frame, bg="#121212", fg="#cccccc", font=term_font, 
                                   insertbackground="#cccccc", bd=0, highlightthickness=0,
                                   yscrollcommand=self.scrollbar.set)
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8,0), pady=4)
        self.scrollbar.config(command=self.text_widget.yview)

        self.text_widget.tag_configure("cmd", foreground="#84f686")
        self.text_widget.tag_configure("error", foreground="#ff5555")
        self.text_widget.tag_configure("system", foreground="#00ccff")
        self.text_widget.tag_configure("warning", foreground="#ffaa00")
        
        self.text_widget.bind("<Return>", self.handle_return)
        self.text_widget.bind("<BackSpace>", self.handle_backspace)
        self.text_widget.bind("<Key>", self.handle_key)
        self.text_widget.bind("<Button-1>", self.handle_click)
        
        self.clear_terminal()

    def print_text(self, text, tag=None):
        self.text_widget.insert(tk.END, text, tag)
        self.text_widget.see(tk.END)

    def print_prompt(self):
        self.print_text("C:\\Users\\Administrator> ")
        self.text_widget.mark_set("input_start", "insert")
        self.text_widget.mark_gravity("input_start", "left")
        self.text_widget.see(tk.END)

    def clear_terminal(self):
        self.text_widget.delete("1.0", tk.END)
        header_text = ("Zeta OS [Version 1.6.2]\n"
                       "(c) 2025 Zeta Medical Corporation. All rights reserved.\n")
        self.print_text(header_text)
        self.print_prompt()

    def handle_return(self, event):
        if self.awaiting_rebind:
            return "break"
            
        input_start = self.text_widget.index("input_start")
        cmd_text = self.text_widget.get(input_start, "end-1c")
        
        self.text_widget.delete(input_start, "end-1c")
        self.print_text(cmd_text + "\n", "cmd")
        
        self.process_command(cmd_text.strip())
        return "break"

    def handle_backspace(self, event):
        if self.awaiting_rebind:
            return "break"
        if self.text_widget.compare("insert", "<=", "input_start"):
            return "break"

    def handle_key(self, event):
        if self.awaiting_rebind:
            return "break"
        if self.text_widget.compare("insert", "<", "input_start"):
            self.text_widget.mark_set("insert", "end")

    def handle_click(self, event):
        self.root.after(10, lambda: self.enforce_cursor_position())

    def enforce_cursor_position(self):
        if self.text_widget.compare("insert", "<", "input_start"):
            self.text_widget.mark_set("insert", "end")

    def process_command(self, cmd_line):
        if not cmd_line:
            self.print_prompt()
            return

        parts = cmd_line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "help":
            help_text = """uploadsample | Accessible by: Zeta Labs
    Uploads sample data to the central network.

date | Accessible by: All
    Displays the current date and time

ping | Accessible by: All
    Pings the ZetaOS network to check if it is online

exit | Accessible by: all
    Closes terminal instance

echo | Accessible by: All
    Prints the specified message to the terminal

clear | Accessible by: All
    Clears terminal

restart | Accessible by: all
    Restarts current system

nvg toggle | Accessible by: all
    Rebinds the nightvision toggle key

radio toggle | Accessible by: all
    Toggles the Radio communication overlay unit"""
            self.print_text(help_text + "\n\n")
            self.print_prompt()

        elif cmd == "date":
            now = datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Y")
            self.print_text(f"{now}\n\n")
            self.print_prompt()

        elif cmd == "ping":
            self.print_text("Pinging ZetaOS network...\nReply from 192.168.1.1: bytes=32 time=14ms TTL=60\nNetwork is online.\n\n")
            self.print_prompt()

        elif cmd == "exit":
            self.close()

        elif cmd == "echo":
            self.print_text(" ".join(args) + "\n\n")
            self.print_prompt()

        elif cmd == "clear":
            self.clear_terminal()

        elif cmd == "restart":
            self.text_widget.delete("1.0", tk.END)
            self.root.after(500, lambda: self.print_text("Restarting system...\nBooting Zeta OS v1.6.2...\n", "system"))
            self.root.after(1500, self.clear_terminal)

        elif cmd == "uploadsample":
            self.print_text("Uploading sample data...\n[||||||||||||||||||||] 100%\nSample data uploaded successfully to Zeta Labs.\n\n")
            self.print_prompt()
            
        elif cmd == "nvg" and len(args) > 0 and args[0].lower() == "toggle":
            self.start_rebind()
            
        elif cmd == "radio" and len(args) > 0 and args[0].lower() == "toggle":
            self.radio.toggle()
            self.print_text("Toggled Radio overlay unit.\n\n", "system")
            self.print_prompt()
            
        else:
            self.print_text(f"'{cmd}' is not recognized as an internal or external command,\noperable program or batch file.\n\n")
            self.print_prompt()

    def start_rebind(self):
        self.print_text("AWAITING KEYBOARD INPUT: Press the new key to rebind the NVG toggle...\n", "warning")
        self.text_widget.see(tk.END)
        self.awaiting_rebind = True
        
        def hook_callback(event):
            if event.event_type == keyboard.KEY_DOWN:
                keyboard.unhook(hook_callback)
                self.root.after(0, lambda: self.update_key(event.name))

        keyboard.hook(hook_callback)

    def update_key(self, new_key):
        self.toggle_key = new_key
        self.print_text(f"[SYS] Toggle key successfully rebounded to -> {self.toggle_key.upper()}\n\n", "system")
        self.print_prompt()
        self.register_hotkeys()
        self.awaiting_rebind = False

    def toggle_overlay(self):
        self.is_active = not self.is_active
        if self.is_active:
            self.overlay.attributes("-alpha", 0.15)
        else:
            self.overlay.attributes("-alpha", 0.0)

    def close(self):
        keyboard.unhook_all()
        self.root.destroy()
        sys.exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TerminalApp()
    app.run()
