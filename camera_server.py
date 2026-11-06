#!/usr/bin/env python3
"""
Serveur caméras RealSense piloté par l'interface EMG.

Le navigateur (page shimmer3r-web-multi.html) appelle :
  POST http://127.0.0.1:8000/start  -> démarre l'enregistrement vidéo
  POST http://127.0.0.1:8000/stop   -> arrête et sauvegarde

=> un seul bouton T0 dans la page lance l'EMG ET les caméras.

Aperçu live affiché en continu ; l'écriture sur disque ne se fait qu'entre start et stop.
Chaque image est horodatée en temps absolu (unix_s) -> même base de temps que l'EMG.

Prérequis :  pip install flask pyrealsense2 opencv-python numpy
Lancer     :  python camera_server.py     (puis appuyer T0 dans le navigateur)
'q' dans une fenêtre caméra = quitter le serveur.
"""

import pyrealsense2 as rs
import numpy as np
import cv2, os, time, csv, threading
from flask import Flask, jsonify

OUT = r"C:\test\videos"
FPS = 30
W, H = 640, 480
os.makedirs(OUT, exist_ok=True)

app = Flask(__name__)
lock = threading.Lock()
state = {"recording": False, "writers": [], "logw": [], "logf": [],
         "unix_start": None, "session": None, "frame": 0, "quit": False}

# --- ouverture des 2 caméras (une seule fois) ---
ctx = rs.context()
devs = ctx.query_devices()
for attempt in range(10):                 # réessaie ~10 s (utile après un rebranchement)
    devs = ctx.query_devices()
    if len(devs) >= 2:
        break
    print(f"  …{len(devs)} caméra(s) détectée(s), attente de 2… ({attempt+1}/10)")
    time.sleep(1)
if len(devs) < 2:
    raise RuntimeError(
        f"2 caméras requises, {len(devs)} détectée(s). "
        "Ferme tout python.exe / RealSense Viewer encore ouvert, "
        "débranche-rebranche les caméras (port USB 3 bleu, câble data), puis relance."
    )
pipes = []
for d in devs[:2]:
    s = d.get_info(rs.camera_info.serial_number)
    p, c = rs.pipeline(), rs.config()
    c.enable_device(s)
    c.enable_stream(rs.stream.color, W, H, rs.format.bgr8, FPS)
    p.start(c)
    pipes.append(p)
print("Caméras prêtes. Lance l'enregistrement avec le bouton T0 du navigateur.")


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/start", methods=["POST", "GET"])
def start():
    with lock:
        if state["recording"]:
            return jsonify(ok=True, already=True, unix_start=state["unix_start"])
        ses = time.strftime("%Y%m%d_%H%M%S")
        writers, logw, logf = [], [], []
        for k in (1, 2):
            vw = cv2.VideoWriter(os.path.join(OUT, f"cam0{k}_{ses}.mp4"),
                                 cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
            fh = open(os.path.join(OUT, f"cam0{k}_{ses}_timestamps.csv"), "w", newline="")
            wr = csv.writer(fh); wr.writerow(["frame", "host_s", "unix_s", "rs_ms"])
            writers.append(vw); logw.append(wr); logf.append(fh)
        state.update(recording=True, writers=writers, logw=logw, logf=logf,
                     unix_start=time.time(), session=ses, frame=0)
        print(f"  >> REC démarré (session {ses})")
    return jsonify(ok=True, unix_start=state["unix_start"], session=ses)


@app.route("/stop", methods=["POST", "GET"])
def stop():
    with lock:
        if not state["recording"]:
            return jsonify(ok=True, already=False)
        state["recording"] = False
        for vw in state["writers"]:
            vw.release()
        for fh in state["logf"]:
            fh.close()
        ses = state["session"]
        state.update(writers=[], logw=[], logf=[])
        print(f"  >> REC arrêté (session {ses})")
    return jsonify(ok=True, session=ses)


def capture_loop():
    """Tourne sur le thread principal (GUI OpenCV). Aperçu continu, écriture si recording."""
    while not state["quit"]:
        cfs = [p.wait_for_frames().get_color_frame() for p in pipes]
        unix = time.time()
        frames = [np.asanyarray(cf.get_data()) for cf in cfs]
        with lock:
            if state["recording"]:
                host = unix - state["unix_start"]
                for k, (cf, fr) in enumerate(zip(cfs, frames)):
                    state["writers"][k].write(fr)
                    state["logw"][k].writerow([state["frame"], f"{host:.4f}",
                                               f"{unix:.4f}", f"{cf.get_timestamp():.3f}"])
                state["frame"] += 1
                rec = True
            else:
                rec = False
        for k, fr in enumerate(frames):
            disp = fr
            if rec:
                disp = fr.copy()
                cv2.circle(disp, (20, 20), 8, (0, 0, 255), -1)  # point rouge = REC
            cv2.imshow(f"cam0{k+1}", disp)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break

    # nettoyage
    with lock:
        if state["recording"]:
            for vw in state["writers"]:
                vw.release()
            for fh in state["logf"]:
                fh.close()
    for p in pipes:
        p.stop()
    cv2.destroyAllWindows()
    print("Serveur caméras arrêté.")
    os._exit(0)


if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=8000, threaded=True, use_reloader=False),
        daemon=True,
    ).start()
    capture_loop()