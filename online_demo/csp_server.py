import argparse
import base64
import json
import os
import sys
import pickle
from http.server import BaseHTTPRequestHandler, HTTPServer

# Ensure project root in path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)


class CSPState:
    aui = None


def bytes_xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, obj=None):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        if obj is not None:
            self.wfile.write(json.dumps(obj).encode('utf-8'))

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode('utf-8'))
        except Exception as e:
            return self._send(400, {"error": f"invalid json: {e}"})

        if self.path == '/load_index':
            # Accept base64 pickle or file path
            try:
                if 'aui_b64' in payload:
                    aui = pickle.loads(base64.b64decode(payload['aui_b64']))
                elif 'aui_path' in payload:
                    with open(payload['aui_path'], 'rb') as f:
                        aui = pickle.load(f)
                else:
                    return self._send(400, {"error": "aui_b64 or aui_path required"})
                CSPState.aui = aui
                return self._send(200, {"status": "ok"})
            except Exception as e:
                return self._send(500, {"error": f"load_index failed: {e}"})

        if self.path == '/eval':
            try:
                aui = CSPState.aui
                if aui is None:
                    return self._send(400, {"error": "AUI not loaded"})
                party_id = int(payload.get('party_id', 0))
                tokens = payload.get('tokens', [])
                lam = int(payload.get('security_param', aui['security_param']))
                n = len(aui['ids'])
                byte_len = aui['segment_length']

                result_shares = []
                proof_shares = []
                for tok in tokens:
                    typ = tok.get('type', 'kw')
                    buckets = tok.get('buckets', [])
                    vec_total = [b"\x00" * byte_len for _ in range(n)]
                    proof_total = b"\x00" * lam
                    if typ == 'kw':
                        mat = aui['I_tex']
                    else:
                        mat = aui['I_spa']
                    for binfo in buckets:
                        cols = binfo['columns']
                        bits = binfo['bits']  # list[int 0/1] for this party
                        for local_idx, col_idx in enumerate(cols):
                            if int(bits[local_idx]) == 1:
                                col_cells = [row[col_idx] for row in mat['EbW' if typ == 'kw' else 'Ebp']]
                                for i in range(n):
                                    vec_total[i] = bytes_xor(vec_total[i], col_cells[i])
                                proof_total = bytes_xor(proof_total, mat['sigma'][col_idx])
                    # encode
                    result_shares.append([base64.b64encode(v).decode('utf-8') for v in vec_total])
                    proof_shares.append(base64.b64encode(proof_total).decode('utf-8'))

                return self._send(200, {"result_shares": result_shares, "proof_shares": proof_shares})
            except Exception as e:
                return self._send(500, {"error": f"eval failed: {e}"})

        return self._send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8001)
    ap.add_argument('--aui', type=str, default=os.path.join(THIS_DIR, 'aui.pkl'), help='path to pickled AUI')
    args = ap.parse_args()

    with open(args.aui, 'rb') as f:
        CSPState.aui = pickle.load(f)
    print(f"[csp_server] AUI loaded. Port={args.port}")

    httpd = HTTPServer(('0.0.0.0', args.port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
