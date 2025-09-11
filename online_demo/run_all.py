import os
import subprocess
import sys
import time


def main():
    # Start 3 CSP servers
    ports = [8001, 8002, 8003]
    procs = []
    try:
        this_dir = os.path.dirname(os.path.abspath(__file__))
        csp_path = os.path.join(this_dir, 'csp_server.py')
        aui_path = os.path.join(this_dir, 'aui.pkl')
        for p in ports:
            procs.append(subprocess.Popen([sys.executable, csp_path, "--port", str(p), "--aui", aui_path]))
        time.sleep(1.5)
        # Run client
        client_path = os.path.join(this_dir, 'client.py')
        query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
        if query:
            subprocess.run([sys.executable, client_path, "--query", query])
        else:
            subprocess.run([sys.executable, client_path])
    finally:
        for p in procs:
            p.terminate()


if __name__ == '__main__':
    main()
