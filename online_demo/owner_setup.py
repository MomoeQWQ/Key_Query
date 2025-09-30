import os
import sys

# Make project root importable regardless of CWD
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from secure_search import build_index_from_csv, save_index_artifacts


def main() -> None:
    config_path = os.path.join(PROJ_ROOT, "conFig.ini")
    csv_file = os.path.join(PROJ_ROOT, "us-colleges-and-universities.csv")
    aui, keys = build_index_from_csv(csv_file, config_path)
    aui_path, key_path = save_index_artifacts(aui, keys, THIS_DIR)
    print(f"[owner_setup] Wrote {aui_path} and {key_path}")


if __name__ == "__main__":
    main()
