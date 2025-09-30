from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import urllib.request

# Ensure project root on sys.path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from config_loader import load_config
from secure_search import (
    QueryPlan,
    prepare_query_plan,
    combine_csp_responses,
    decrypt_matches,
    run_fx_hmac_verification,
)
from secure_search.indexing import load_index_artifacts


def http_post(url: str, obj: dict) -> dict:
    data = json.dumps(obj).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
        return json.loads(body.decode('utf-8'))


class ClientApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title('Secure Search Client GUI')

        default_aui = os.path.join(PROJ_ROOT, 'online_demo', 'aui.pkl')
        default_keys = os.path.join(PROJ_ROOT, 'online_demo', 'K.pkl')
        default_cfg = os.path.join(PROJ_ROOT, 'conFig.ini')
        default_dataset = os.path.join(PROJ_ROOT, 'us-colleges-and-universities.csv')

        self.aui_path_var = tk.StringVar(value=default_aui)
        self.keys_path_var = tk.StringVar(value=default_keys)
        self.config_path_var = tk.StringVar(value=default_cfg)
        self.dataset_path_var = tk.StringVar(value=default_dataset)
        self.endpoints_var = tk.StringVar(value='http://127.0.0.1:8001, http://127.0.0.1:8002, http://127.0.0.1:8003')
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value='Index not loaded')

        self._build_layout()

        self.aui: dict | None = None
        self.keys: tuple | None = None
        self.config: dict | None = None
        self.query_queue: queue.Queue = queue.Queue()
        self.root.after(100, self._process_queue)

    def _build_layout(self) -> None:
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def add_path_row(row: int, label: str, var: tk.StringVar, is_dir: bool = False) -> None:
            tk.Label(frame, text=label).grid(row=row, column=0, sticky='e', pady=2)
            entry = tk.Entry(frame, textvariable=var, width=60)
            entry.grid(row=row, column=1, sticky='we', pady=2)

            def browse() -> None:
                path = filedialog.askopenfilename(initialdir=PROJ_ROOT) if not is_dir else filedialog.askdirectory(initialdir=PROJ_ROOT)
                if path:
                    var.set(path)

            tk.Button(frame, text='Browse', command=browse).grid(row=row, column=2, padx=5)

        add_path_row(0, 'AUI path:', self.aui_path_var)
        add_path_row(1, 'Keys path:', self.keys_path_var)
        add_path_row(2, 'Config path:', self.config_path_var)
        add_path_row(3, 'Dataset path:', self.dataset_path_var)

        tk.Label(frame, text='CSP endpoints (comma separated):').grid(row=4, column=0, sticky='ne', pady=2)
        tk.Entry(frame, textvariable=self.endpoints_var, width=60).grid(row=4, column=1, sticky='we', pady=2)

        tk.Label(frame, text='Query:').grid(row=5, column=0, sticky='e', pady=2)
        tk.Entry(frame, textvariable=self.query_var, width=60).grid(row=5, column=1, sticky='we', pady=2)
        tk.Label(frame, text='Input: <KW1> <KW2> ...; optional R: lat_min,lon_min,lat_max,lon_max\n- Keywords separated by space => AND\n- Spatial range -> grid cells (OR), combined with keywords (AND).', fg='#555', justify='left', anchor='w', wraplength=520).grid(row=6, column=1, columnspan=2, sticky="we", pady=2)




        button_bar = tk.Frame(frame)
        button_bar.grid(row=7, column=0, columnspan=3, pady=5, sticky='w')
        tk.Button(button_bar, text='Load index', command=self.load_index).pack(side=tk.LEFT, padx=2)
        tk.Button(button_bar, text='Run query', command=self.run_query).pack(side=tk.LEFT, padx=2)
        tk.Button(button_bar, text='Examples', command=self.fill_example).pack(side=tk.LEFT, padx=2)

        tk.Label(frame, textvariable=self.status_var).grid(row=8, column=0, columnspan=3, sticky='w', pady=2)

        self.output_box = tk.Text(frame, height=18, width=80, state=tk.DISABLED)
        self.output_box.grid(row=9, column=0, columnspan=3, sticky='nsew', pady=5)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(9, weight=1)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def load_index(self) -> None:
        try:
            self.set_status('Loading index...')
            self.aui, self.keys = load_index_artifacts(self.aui_path_var.get(), self.keys_path_var.get())
            self.config = load_config(self.config_path_var.get())
        except Exception as exc:
            messagebox.showerror('Error', f'Failed to load index: {exc}')
            self.set_status('Index load failed')
            return
        self.set_status('Index loaded successfully')

    def run_query(self) -> None:
        if self.aui is None or self.keys is None or self.config is None:
            self.load_index()
            if self.aui is None:
                return
        query = self.query_var.get().strip()
        if not query:
            messagebox.showwarning('Warning', 'Please enter a query string.')
            return
        endpoints = [ep.strip() for ep in self.endpoints_var.get().split(',') if ep.strip()]
        if not endpoints:
            messagebox.showwarning('Warning', 'Please provide at least one CSP endpoint.')
            return
        self.set_status('Running query...')
        threading.Thread(target=self._query_worker, args=(query, endpoints), daemon=True).start()

    def _query_worker(self, query: str, endpoints: list[str]) -> None:
        try:
            plan = prepare_query_plan(query, self.aui, self.config)
            if len(endpoints) != plan.num_parties:
                raise ValueError(f'Expected {plan.num_parties} CSP endpoints, got {len(endpoints)}')
            responses = []
            for party_id, base in enumerate(endpoints):
                body = {
                    'party_id': party_id,
                    'tokens': plan.payloads[party_id],
                    'security_param': plan.security_param,
                }
                responses.append(http_post(base + '/eval', body))
            combined_vecs, combined_proofs = combine_csp_responses(plan, responses, self.aui)
            _, hits = decrypt_matches(plan, combined_vecs, self.aui, self.keys)
            ok_verify = run_fx_hmac_verification(plan, combined_vecs, combined_proofs, self.aui, self.keys)
            dataset_path = self.dataset_path_var.get()
            rows: list[str] = []
            try:
                import pandas as pd
                raw_df = pd.read_csv(dataset_path, sep=';')
                view = raw_df[raw_df['IPEDSID'].astype(str).isin([str(x) for x in hits])].head(20)
                for idx, row in enumerate(view.to_dict('records'), 1):
                    rows.append(f"{idx}. [{row['IPEDSID']}] {row['NAME']} - {row['ADDRESS']}, {row['CITY']}, {row['STATE']} ({row.get('Geo Point', '')})")
            except Exception as exc:
                rows.append(f'Failed to load dataset: {exc}')
            result = {
                'verify': ok_verify,
                'hits': hits,
                'rows': rows,
            }
            self.query_queue.put(('result', result))
        except Exception as exc:
            self.query_queue.put(('error', str(exc)))

    def _process_queue(self) -> None:
        try:
            while True:
                kind, payload = self.query_queue.get_nowait()
                if kind == 'error':
                    messagebox.showerror('Error', payload)
                    self.set_status('Query failed')
                elif kind == 'result':
                    self.set_status('Query finished')
                    self.output_box.configure(state=tk.NORMAL)
                    self.output_box.delete('1.0', tk.END)
                    verify_text = 'pass' if payload['verify'] else 'fail'
                    self.output_box.insert(tk.END, f"Verify: {verify_text}\n")
                    self.output_box.insert(tk.END, f"Matches: {len(payload['hits'])}\n\n")
                    for line in payload['rows']:
                        self.output_box.insert(tk.END, line + "\n")
                    self.output_box.configure(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_queue)

    def fill_example(self) -> None:
        self.query_var.set('ORLANDO UNIVERSITY; R: 28.2,-81.6,28.8,-81.1')

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = ClientApp()
    app.run()


if __name__ == '__main__':
    main()
