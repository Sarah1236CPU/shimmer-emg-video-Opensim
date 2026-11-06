#!/usr/bin/env python3
"""
Aligne l'EMG (CSV de l'interface Shimmer) avec les caméras (camXX_..._timestamps.csv)
via la colonne de temps absolu unix_s partagée.

Sorties :
  <emg>_aligned.csv    -> EMG en format large (1 colonne par voie), avec time_s = temps
                          relatif au DÉBUT DE LA VIDÉO (t=0 à la 1re image). Pleine cadence EMG.
  <emg>_per_frame.csv  -> 1 ligne par image vidéo, chaque voie EMG interpolée à l'instant
                          de l'image (pratique pour superposer EMG et cinématique Pose2Sim).

Usage :
  pip install pandas numpy
  python align_emg_video.py emg.csv cam01_<session>_timestamps.csv
  # si tu as mesuré la latence BLE (geste de synchro) :
  python align_emg_video.py emg.csv cam01_<session>_timestamps.csv --offset 0.03
"""

import argparse, os
import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("emg_csv", help="CSV EMG téléchargé depuis l'interface")
    ap.add_argument("cam_csv", help="camXX_<session>_timestamps.csv d'une caméra")
    ap.add_argument("--offset", type=float, default=0.0,
                    help="latence BLE à soustraire à l'EMG, en secondes (défaut 0)")
    ap.add_argument("--out", default=None, help="préfixe de sortie (défaut = nom de l'EMG)")
    a = ap.parse_args()

    cam = pd.read_csv(a.cam_csv)
    video_start = float(cam["unix_s"].iloc[0])        # t=0 commun = 1re image vidéo
    if len(cam) > 1:
        fps = 1.0 / float(np.median(np.diff(cam["unix_s"])))
        print(f"Vidéo : {len(cam)} images, ~{fps:.1f} fps, début unix_s={video_start:.4f}")

    emg = pd.read_csv(a.emg_csv)
    # nom de colonne = appareil + voie (ex. S1_Exg1_CH1_16Bit)
    emg["col"] = emg["device"].astype(str) + "_" + emg["channel"].astype(str)
    emg["unix_corr"] = emg["unix_s"] - a.offset      # correction latence BLE

    # passage en format large : index = temps absolu, 1 colonne par voie
    wide = emg.pivot_table(index="unix_corr", columns="col",
                           values="value", aggfunc="mean").sort_index()
    wide.insert(0, "time_s", wide.index.values - video_start)

    base = a.out or os.path.splitext(a.emg_csv)[0]
    full_path = base + "_aligned.csv"
    wide.to_csv(full_path, index_label="unix_s")
    print(f"  -> {full_path}  ({len(wide)} échantillons EMG, {wide.shape[1]-1} voies)")

    # version 1 valeur par image vidéo (interpolation linéaire à l'instant de chaque image)
    chans = [c for c in wide.columns if c != "time_s"]
    emg_t = wide.index.values
    cam_u = cam["unix_s"].values
    perframe = {"frame": cam["frame"].values,
                "time_s": cam_u - video_start,
                "unix_s": cam_u}
    for c in chans:
        perframe[c] = np.interp(cam_u, emg_t, wide[c].values)
    frame_path = base + "_per_frame.csv"
    pd.DataFrame(perframe).to_csv(frame_path, index=False)
    print(f"  -> {frame_path}  (EMG rééchantillonné sur {len(cam)} images)")

    # contrôle de recouvrement temporel
    overlap = (max(emg_t.min(), cam_u.min()), min(emg_t.max(), cam_u.max()))
    if overlap[1] <= overlap[0]:
        print("  ⚠ ATTENTION : EMG et vidéo ne se recouvrent pas dans le temps "
              "(T0 pressé avant le démarrage des caméras ?).")
    else:
        print(f"  Recouvrement EMG/vidéo : {overlap[1]-overlap[0]:.2f} s")


if __name__ == "__main__":
    main()