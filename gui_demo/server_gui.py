from __future__ import annotations

import os
import pickle
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from http.server import HTTPServer

# Ensure project root on sys.path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
ONLINE_DEMO_DIR = os.path.join(PROJ_ROOT, 'online_demo')
if ONLINE_DEMO_DIR not in sys.path:
    sys.path.insert(0, ONLINE_DEMO_DIR)
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from csp_server import Handler, CSPState


class ServerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title('Secure Search CSP GUI')

        default_aui = os.path.join(PROJ_ROOT, 'online_demo', 'aui.pkl')
        self.aui_path_var = tk.StringVar(value=default_aui)
        self.ports_var = tk.StringVar(value='8001,8002,8003')
        self.status_var = tk.StringVar(value='Servers stopped')

        self._build_layout()

        self.servers: list[HTTPServer] = []
        self.threads: list[threading.Thread] = []
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

    def _build_layout(self) -> None:
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(frame, text='AUI path:').grid(row=0, column=0, sticky='e', pady=2)
        tk.Entry(frame, textvariable=self.aui_path_var, width=60).grid(row=0, column=1, sticky='we', pady=2)

        def browse() -> None:
            path = filedialog.askopenfilename(initialdir=PROJ_ROOT)
            if path:
                self.aui_path_var.set(path)

        tk.Button(frame, text='Browse', command=browse).grid(row=0, column=2, padx=5)

        tk.Label(frame, text='Ports (comma separated):').grid(row=1, column=0, sticky='e', pady=2)
        tk.Entry(frame, textvariable=self.ports_var, width=60).grid(row=1, column=1, sticky='we', pady=2)

        button_bar = tk.Frame(frame)
        button_bar.grid(row=2, column=0, columnspan=3, pady=5, sticky='w')
        tk.Button(button_bar, text='Start servers', command=self.start_servers).pack(side=tk.LEFT, padx=2)
        tk.Button(button_bar, text='Stop servers', command=self.stop_servers).pack(side=tk.LEFT, padx=2)

        tk.Label(frame, textvariable=self.status_var).grid(row=3, column=0, columnspan=3, sticky='w', pady=2)

        self.log_box = tk.Text(frame, height=18, width=80, state=tk.DISABLED)
        self.log_box.grid(row=4, column=0, columnspan=3, sticky='nsew', pady=5)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def append_log(self, text: str) -> None:
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def start_servers(self) -> None:
        if self.servers:
            messagebox.showinfo('Info', 'Servers are already running.')
            return
        try:
            with open(self.aui_path_var.get(), 'rb') as f:
                aui = pickle.load(f)
            CSPState.aui = aui
        except Exception as exc:
            messagebox.showerror('Error', f'Failed to load AUI: {exc}')
            return
        ports = []
        for item in self.ports_var.get().split(','):
            item = item.strip()
            if not item:
                continue
            try:
                ports.append(int(item))
            except ValueError:
                messagebox.showerror('Error', f'Invalid port: {item}')
                return
        if not ports:
            messagebox.showwarning('Warning', 'Provide at least one port.')
            return
        started = []
        try:
            for port in ports:
                server = HTTPServer(('0.0.0.0', port), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                self.servers.append(server)
                self.threads.append(thread)
                started.append(port)
                self.append_log(f'Started CSP server on port {port}')
        except Exception as exc:
            self.append_log(f'Failed to start server: {exc}')
            messagebox.showerror('Error', f'Failed to start server: {exc}')
            self.stop_servers()
            return
        self.status_var.set(f'Servers running on: {", ".join(str(p) for p in started)}')

    def stop_servers(self) -> None:
        for server in self.servers:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
        if self.servers:
            self.append_log('Servers stopped')
        self.servers.clear()
        self.threads.clear()
        self.status_var.set('Servers stopped')

    def on_close(self) -> None:
        self.stop_servers()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = ServerApp()
    app.run()


if __name__ == '__main__':
    main()
