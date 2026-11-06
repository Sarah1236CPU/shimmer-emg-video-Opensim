# Shimmer3R · EMG + vidéo synchronisés dans le navigateur

Acquisition **EMG / IMU multi-capteurs Shimmer3R en Bluetooth, directement depuis le navigateur**, synchronisée avec **deux caméras Intel RealSense**, puis export des enveloppes musculaires au format **`.sto` pour OpenSim / CEINMS**.

Le projet s'appuie sur le [**Shimmer Web SDK**](https://github.com/ShimmerResearch/shimmer-web-sdk) (TypeScript, Web Bluetooth / Web Serial) de Shimmer Research, auquel il ajoute une chaîne complète d'acquisition et de traitement pour la biomécanique.

```
 Shimmer3R (BLE) ──┐
 Shimmer3R (BLE) ──┼─► Interface web ──► emg.csv ─┐
        …          ┘      │ bouton T0              ├─► align_emg_video.py ─► _aligned.csv ─► emg_to_sto.py ─► .sto (OpenSim / CEINMS)
                          ▼                        │                     └─► _per_frame.csv
              camera_server.py ──► cam01/cam02 .mp4 + _timestamps.csv ─┘
                (2 × RealSense)
```

Toutes les données (EMG et images) sont horodatées dans la **même base de temps absolue** (`unix_s`), ce qui permet de les aligner a posteriori sans boîtier de synchronisation matériel.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Utilisation pas à pas](#utilisation-pas-à-pas)
- [Formats de fichiers](#formats-de-fichiers)
- [Traitement du signal EMG](#traitement-du-signal-emg)
- [Utiliser le SDK dans son propre code](#utiliser-le-sdk-dans-son-propre-code)
- [Structure du dépôt](#structure-du-dépôt)
- [Limites connues](#limites-connues)
- [Licence et crédits](#licence-et-crédits)

---

## Fonctionnalités

**Interface web (`shimmer3r-web-live1.html`)**

- Connexion de **plusieurs Shimmer3R en parallèle** via Web Bluetooth, sans logiciel à installer
- Choix des capteurs : accéléromètre low-noise et wide-range, gyroscope, magnétomètre, pression/température, GSR
- Module **ExG** : EMG 2 voies, ECG ou signal de test, avec conversion en mV
- **Calibration IMU** intégrée : accéléromètre en m/s² (± 2 à 16 g), gyroscope en °/s (± 125 à 2000 °/s)
- Oscilloscope temps réel multi-appareils, affichage CH1 / CH2 au choix
- Bouton **T0** qui démarre en un clic l'enregistrement EMG **et** les caméras
- Export de l'intervalle enregistré en **CSV**

**Scripts Python**

| Script | Rôle |
|---|---|
| `camera_server.py` | Serveur local (Flask) qui pilote 2 caméras RealSense : aperçu live, enregistrement `.mp4` et horodatage de chaque image |
| `align_emg_video.py` | Aligne le CSV EMG sur les timestamps d'une caméra (t = 0 à la première image vidéo) |
| `emg_to_sto.py` | Calcule les enveloppes EMG normalisées 0–1 et les écrit au format `.sto` |

> `shimmer3r-web-live.html` est la variante **sans caméras** (EMG / IMU seuls).

---

## Prérequis

| Élément | Détail |
|---|---|
| Capteurs | Un ou plusieurs **Shimmer3R** (module ExG pour l'EMG) |
| Navigateur | **Chrome ou Edge** sur ordinateur (Web Bluetooth n'est pas disponible sous Firefox ni Safari) |
| Node.js | Version 18 ou plus, pour compiler le SDK |
| Python | Version 3.9 ou plus |
| Caméras *(optionnel)* | 2 × **Intel RealSense**, branchées en USB 3 |

---

## Installation

### 1. Cloner et compiler le SDK

```bash
git clone https://github.com/Sarah1236CPU/shimmer-emg-video-Opensim.git
cd shimmer-emg-video-Opensim
npm install
npm run build        # génère dist/shimmer-web-sdk.esm.js
```

Le dossier `dist/` n'est pas versionné : cette étape est obligatoire, sinon la page affiche « Impossible de charger le SDK ».

### 2. Installer les dépendances Python

```bash
# Traitement (alignement + export .sto)
pip install numpy pandas scipy

# Serveur caméras (uniquement si tu utilises les RealSense)
pip install flask pyrealsense2 opencv-python
```

---

## Utilisation pas à pas

### 1. Lancer le serveur caméras *(optionnel)*

Dans `camera_server.py`, adapte si besoin le dossier de sortie (`OUT`, par défaut `C:\test\videos`), la cadence (`FPS = 30`) et la résolution (`640 × 480`), puis :

```bash
python camera_server.py
```

Deux fenêtres d'aperçu s'ouvrent. Le serveur écoute sur `http://127.0.0.1:8000`. Appuyer sur `q` dans une fenêtre caméra arrête le serveur.

### 2. Servir l'interface web

Web Bluetooth exige un contexte sécurisé : la page doit être servie en **`localhost`** (pas ouverte en `file://`).

```bash
npx http-server -p 8080
# ou : python -m http.server 8080
```

Puis ouvre **http://localhost:8080/shimmer3r-web-live1.html** dans Chrome ou Edge.

### 3. Enregistrer

1. **+ Ajouter un appareil** pour chaque Shimmer3R (sélection dans la fenêtre Bluetooth du navigateur). Chaque capteur peut être renommé (`S1`, `S2`…).
2. Choisis les capteurs, le mode ExG (**EMG · 2 voies**), la fréquence d'échantillonnage et les plages IMU.
3. **Démarrer tout** lance le streaming et l'oscilloscope.
4. **● T0** démarre l'enregistrement de l'EMG et des caméras en même temps.
5. **■ Fin de l'intervalle** arrête l'enregistrement.
6. **⤓ Télécharger le CSV** récupère les données.

Si le serveur caméras n'est pas lancé, l'interface le signale et continue en mode EMG seul.

### 4. Aligner l'EMG sur la vidéo

```bash
python align_emg_video.py emg.csv cam01_<session>_timestamps.csv

# si tu as mesuré la latence Bluetooth (par exemple avec un geste de synchronisation) :
python align_emg_video.py emg.csv cam01_<session>_timestamps.csv --offset 0.03
```

Le script indique la durée de recouvrement EMG / vidéo, et prévient si les deux ne se chevauchent pas (T0 pressé avant le démarrage des caméras, par exemple).

### 5. Exporter pour OpenSim / CEINMS

```bash
# normalisation sur le maximum de l'essai
python emg_to_sto.py emg_aligned.csv

# en nommant les voies comme les muscles du modèle OpenSim
python emg_to_sto.py emg_aligned.csv --map "S1_Exg1_CH1=bflh_r;S1_Exg1_CH2=recfem_r"

# normalisation sur un essai de contraction maximale volontaire (MVC)
python emg_to_sto.py emg_aligned.csv --mvc mvc_aligned.csv
```

Le temps du `.sto` est relatif à la première image vidéo : il est donc dans la même base que la cinématique obtenue à partir des vidéos (par exemple avec Pose2Sim).

---

## Formats de fichiers

**CSV exporté par l'interface** (format long, une ligne par échantillon et par voie) :

```
device,t_rel_ms,unix_s,channel,value,unit
S1,0.00,1749651234.1234,Exg1_CH1_16Bit,0.0123,mV
```

**Timestamps caméra** (`camXX_<session>_timestamps.csv`) :

```
frame,host_s,unix_s,rs_ms
0,0.0012,1749651234.2001,123456.789
```

**Sorties de `align_emg_video.py`**

| Fichier | Contenu |
|---|---|
| `<emg>_aligned.csv` | EMG en format large (une colonne par voie, nommée `<appareil>_<voie>`), pleine cadence, avec `time_s` relatif à la 1re image |
| `<emg>_per_frame.csv` | Une ligne par image vidéo, chaque voie interpolée à l'instant de l'image (pratique pour superposer EMG et cinématique) |

**Sortie de `emg_to_sto.py`** : un fichier `.sto` OpenSim (en-tête `endheader`, colonne `time` puis une colonne par muscle).

---

## Traitement du signal EMG

`emg_to_sto.py` applique la chaîne classique utilisée avec CEINMS / MOtoNMS :

1. Rééchantillonnage sur une grille uniforme (les timestamps Bluetooth sont irréguliers)
2. Filtre **passe-bande 20–450 Hz** (Butterworth d'ordre 4, zéro-phase), borne haute limitée par Nyquist
3. **Redressement** (valeur absolue)
4. Filtre **passe-bas 6 Hz** (Butterworth d'ordre 4, zéro-phase) pour obtenir l'enveloppe linéaire
5. **Normalisation** par la MVC si elle est fournie, sinon par le maximum de l'essai
6. Écrêtage entre 0 et 1

Seules les voies EMG (`Exg*_CH*`) sont traitées ; l'accéléromètre et le gyroscope sont ignorés.

> Avec une fréquence d'échantillonnage faible (par exemple 51,2 Hz), la bande 20–450 Hz est fortement tronquée. Pour de l'EMG exploitable, choisis une fréquence élevée dans l'interface (512 Hz ou plus).

---

## Utiliser le SDK dans son propre code

Le SDK expose notamment `Shimmer3RClient` (Shimmer3R en Bluetooth) et `VerisenseBleDevice` (Verisense IMU / Pulse+, en Bluetooth ou en série).

```html
<script type="module">
  import { Shimmer3RClient, SensorBitmapShimmer3 } from './dist/shimmer-web-sdk.esm.js';

  const client = new Shimmer3RClient({ timestampFmt: 'u24' });
  client.onStreamFrame = (oc) => console.log(oc.get('GYRO_Z', 'raw')?.value);

  document.getElementById('btnConnect').addEventListener('click', async () => {
    await client.connect();
    await client.setSamplingRate(51.2);
    await client.setSensors(SensorBitmapShimmer3.SENSOR_GYRO | SensorBitmapShimmer3.SENSOR_A_ACCEL);
    await client.startStreaming();
  });
</script>
```

Commandes de développement :

```bash
npm run build     # compile dist/ (ESM, CJS, UMD + types)
npm test          # tests unitaires (Vitest, sans navigateur)
npm run lint      # ESLint
npm run docs      # documentation de l'API (TypeDoc)
```

La documentation complète du SDK est sur le [dépôt officiel de Shimmer Research](https://github.com/ShimmerResearch/shimmer-web-sdk).

---

## Structure du dépôt

```
.
├── shimmer3r-web-live1.html   ← interface EMG + caméras (bouton T0)
├── shimmer3r-web-live.html    ← interface EMG seule
├── camera_server.py           ← serveur caméras RealSense (Flask, port 8000)
├── align_emg_video.py         ← alignement EMG / vidéo
├── emg_to_sto.py              ← enveloppes EMG → .sto OpenSim / CEINMS
├── src/                       ← code source TypeScript du SDK
│   ├── core/                  ← types, ObjectCluster, statistiques de flux
│   └── devices/
│       ├── shimmer3r/         ← client BLE Shimmer3R, calibration, protocole
│       └── verisense/         ← client Verisense et décodeurs de capteurs
├── tests/                     ← tests Vitest
├── dist/                      ← SDK compilé (généré par npm run build)
└── build-local-sdk.ps1        ← script de build Windows
```

---

## Limites connues

- **Navigateurs** : Chrome et Edge sur ordinateur uniquement (Web Bluetooth).
- **Latence Bluetooth** : les échantillons sont horodatés à la réception, avec un léger retard variable. Mesure-le avec un geste de synchronisation visible sur la vidéo et l'EMG, puis corrige-le avec `--offset`.
- **Caméras** : le serveur attend exactement **2** RealSense. Si elles ne sont pas détectées, ferme les autres programmes qui les utilisent (RealSense Viewer, autre `python`) et rebranche-les sur un port USB 3.
- **Chemin de sortie vidéo** codé en dur dans `camera_server.py` (`C:\test\videos`) : à adapter à ta machine.
- **Calibration IMU** : la plage choisie dans l'interface doit correspondre à celle configurée sur l'appareil. Le magnétomètre reste en valeurs brutes.

---

## Licence et crédits

- Le SDK (`src/`, `tests/`, configuration de build) est © **Shimmer Research Ltd.**, distribué sous licence **BSD-3-Clause** (voir [`LICENSE`](LICENSE)).
- L'interface web multi-appareils, le serveur caméras et les scripts d'alignement et d'export EMG ont été ajoutés dans ce dépôt.

Projet indépendant, non affilié à Shimmer Research.
