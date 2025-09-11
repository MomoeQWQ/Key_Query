import os
import sys
import pickle

# Make project root importable regardless of CWD
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

import prepare_dataset  # noqa: E402
from config_loader import load_config  # noqa: E402
from convert_dataset import convert_dataset  # noqa: E402
from SetupProcess import Setup  # noqa: E402


def main():
    cfg = load_config(os.path.join(PROJ_ROOT, "conFig.ini"))
    csv_file = os.path.join(PROJ_ROOT, "us-colleges-and-universities.csv")
    dict_list = prepare_dataset.load_and_transform(csv_file)
    db = convert_dataset(dict_list, cfg)
    aui, K = Setup(db, cfg)

    out_dir = THIS_DIR
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "aui.pkl"), "wb") as f:
        pickle.dump(aui, f)
    with open(os.path.join(out_dir, "K.pkl"), "wb") as f:
        pickle.dump(K, f)
    print("[owner_setup] Wrote aui.pkl and K.pkl to", out_dir)


if __name__ == "__main__":
    main()
