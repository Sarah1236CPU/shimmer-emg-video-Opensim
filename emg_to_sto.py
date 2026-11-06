#!/usr/bin/env python3
"""
EMG aligné  ->  enveloppe d'activation normalisée 0-1  ->  fichier .sto pour CEINMS / OpenSim.

Traitement (standard CEINMS/MOtoNMS) :
  passe-bande 20-450 Hz  ->  redressement (|x|)  ->  passe-bas 6 Hz  (Butterworth ordre 4, zéro-phase)
  ->  normalisation (MVC si fournie, sinon max de l'essai)  ->  clip 0-1.

Entrée : le _aligned.csv produit par align_emg_video.py (colonnes : unix_s, time_s, <voies>).
Le temps de sortie (time_s) est relatif à la 1re image vidéo -> même base que ta cinématique Pose2Sim.

Usage :
  pip install numpy pandas scipy
  python emg_to_sto.py essai_aligned.csv
  # avec correspondance voie->muscle (noms du modèle OpenSim) :
  python emg_to_sto.py essai_aligned.csv --map "Exg1_CH1=bflh_r;Exg1_CH2=recfem_r"
  # avec une MVC (autre _aligned.csv d'un essai de contraction max) :
  python emg_to_sto.py essai_aligned.csv --mvc mvc_aligned.csv
"""

import argparse, os, re
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

EMG_RE = re.compile(r"Exg\d_CH\d")          # ne traite que les voies EMG (pas accel/gyro)


def envelope(x, fs, band=(20.0, 450.0), env_fc=6.0):
    ny = fs / 2.0
    hi = min(band[1], 0.45 * fs)            # respecte Nyquist
    b, a = butter(4, [band[0] / ny, hi / ny], btype="band")
    bp = filtfilt(b, a, x)                  # passe-bande, zéro-phase
    rect = np.abs(bp)                       # redressement
    bl, al = butter(4, env_fc / ny, btype="low")
    return filtfilt(bl, al, rect)           # passe-bas -> enveloppe linéaire


def load_emg(path):
    df = pd.read_csv(path)
    t = df["time_s"].values.astype(float)
    cols = [c for c in df.columns if EMG_RE.search(c)]
    if not cols:
        raise SystemExit(f"Aucune voie EMG (Exg*_CH*) trouvée dans {path}.")
    # rééchantillonnage sur grille uniforme (les timestamps BLE sont irréguliers)
    fs = 1.0 / np.median(np.diff(t))
    grid = np.arange(t[0], t[-1], 1.0 / fs)
    data = {c: np.interp(grid, t, df[c].values.astype(float)) for c in cols}
    return grid, fs, data


def write_sto(path, time, data, name="EMG envelopes"):
    cols = list(data.keys())
    with open(path, "w") as f:
        f.write(f"{name}\n")
        f.write("version=1\n")
        f.write(f"nRows={len(time)}\n")
        f.write(f"nColumns={len(cols)+1}\n")
        f.write("inDegrees=no\n")
        f.write("endheader\n")
        f.write("time\t" + "\t".join(cols) + "\n")
        for i in range(len(time)):
            f.write("\t".join([f"{time[i]:.6f}"] + [f"{data[c][i]:.6f}" for c in cols]) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("aligned_csv", help="_aligned.csv de l'essai")
    ap.add_argument("--mvc", default=None, help="_aligned.csv d'un essai MVC (sinon max de l'essai)")
    ap.add_argument("--map", default="", help='ex. "Exg1_CH1=bflh_r;Exg1_CH2=recfem_r"')
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    t, fs, raw = load_emg(a.aligned_csv)
    print(f"EMG : {len(t)} échantillons, fs≈{fs:.0f} Hz, {len(raw)} voie(s)")
    env = {c: envelope(x, fs) for c, x in raw.items()}

    # normalisation
    if a.mvc:
        _, fsm, rawm = load_emg(a.mvc)
        norm = {c: envelope(rawm[c], fsm).max() for c in env if c in rawm}
        print(f"Normalisation par MVC ({a.mvc})")
    else:
        norm = {c: env[c].max() for c in env}
        print("Normalisation par le max de l'essai")
    act = {c: np.clip(env[c] / (norm.get(c, env[c].max()) or 1.0), 0.0, 1.0) for c in env}

    # correspondance voie -> nom de muscle du modèle
    mapping = {}
    for pair in a.map.replace(";", ",").split(","):
        if "=" in pair:
            k, v = pair.split("="); mapping[k.strip()] = v.strip()

    def muscle_name(col):
        for k, v in mapping.items():
            if k in col:
                return v
        return col

    out_data = {muscle_name(c): act[c] for c in act}
    out = a.out or (os.path.splitext(a.aligned_csv)[0] + "_emg.sto")
    write_sto(out, t, out_data)
    print(f"  -> {out}  (colonnes : time, {', '.join(out_data.keys())})")
    if not mapping:
        print("  NB : pas de --map fourni, les colonnes gardent les noms de voies. "
              "Pour CEINMS, renomme-les avec les muscles du modèle (--map).")


if __name__ == "__main__":
    main()