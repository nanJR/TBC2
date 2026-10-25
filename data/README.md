# Data

**No dataset files go into git.** They are large, and even open-licence data
must not be re-uploaded from this repo. Each dataset lives in `data/raw/` on
your own machine (git ignores that folder):

```
data/raw/
├── Cough_Audio/   # cough model
└── CXR/           # chest X-ray model
```

On WSL, keep them inside the Linux filesystem (`~/code/TBC2/data/raw`), not
under `/mnt/c`, which is far too slow for tens of thousands of files. From
Windows Explorer the folder is `\\wsl.localhost\Ubuntu-24.04\home\panni\code\TBC2\data\raw`.

| Dataset | Used for | Where to get it | Notes |
| --- | --- | --- | --- |
| [Tuberculosis Cough Acoustics Curated Dataset](https://www.kaggle.com/datasets/elffff/tuberculosis-cough-acoustics-curated-dataset) → `Cough_Audio/` | Cough model | Kaggle | 1,267 WAV clips from 198 people, plus CWT scalogram PNGs and `metadata_kaggle.csv`. TB coughs (GeneXpert/culture confirmed) and clinic non-TB coughs come from TBscreen (`PID_*` files); extra healthy coughs come from Coswara (`COSWARA_*`). CC BY 4.0 |
| [JU-TBv1](https://data.mendeley.com/datasets/g46k8s49hj/3) → `CXR/` | X-ray model | Mendeley Data, DOI 10.17632/g46k8s49hj.3 | 55,336 JPG chest X-rays, TB vs Normal (about 42% TB). Jadavpur University. CC BY 4.0, cite Ghosh and Singh |
| Synthetic patients | Dropout model, dashboard | `data/synthetic/` generator | Built from India TB Report statistics |

All patients in this project are either from these public research datasets
or fully synthetic. Never add real patient records.

## Folder layout

Both datasets come already split. Use these splits as they are.

| Folder | train | val | test |
| --- | --- | --- | --- |
| `Cough_Audio/audio_wav/<split>/{Healthy,TB}/*.wav` | 839 clips / 137 people | 229 / 30 | 199 / 31 |
| `CXR/<split>/{Normal,tb}/*.jpg` | 47,035 | 5,533 | 2,768 |

`Cough_Audio/cwt_scalograms/` has the same splits as images. In `train` only,
each clip appears twice, as `_clean` and `_noisy` (added noise for training).

## Watch out for

- **Don't reshuffle the cough clips.** One person has many clips, and the
  provided splits keep each person in one split only (checked). Mixing clips
  at random would put the same person in train and test and inflate the score.
- **Evaluate on clean audio.** The `_noisy` scalograms are only for training.
- **Recording source can leak the label.** Coswara coughs were recorded at
  home on people's phones, and they are all labelled Healthy. A model can
  learn "home recording = healthy" instead of TB. Also report results on the
  TBscreen clips alone (`PID_*`, or `source_dataset` in `metadata_kaggle.csv`).
- **The cough test set is small** (31 people), so report confidence intervals.
- **JU-TB doesn't say where its images came from**, so its test score may be
  higher than real-world performance.
- **No person has both a cough and an X-ray.** The two models are trained
  separately and their scores are combined in
  `services/api/app/routers/screen.py`.

## Synthetic patients

```bash
python data/synthetic/generate_patients.py --n 5000
```

This writes `data/processed/synthetic_patients.csv`, which git ignores. The
rates in the script are placeholders until they are replaced with cited India
TB Report figures. Dropout labels come from a rule we wrote ourselves, so any
model accuracy on this data only shows that the pipeline works.
