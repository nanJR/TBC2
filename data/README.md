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

**JU-TB has exact duplicate images**, some across splits (103 test and 229
val images also sit in train). `ml/cxr/find_duplicates.py` writes
`ml/cxr/exclude.txt` (1,361 files), and training and evaluation skip
everything in it. Nothing in `data/raw` is deleted. Cleaned X-ray sizes:

| Split | TB | Normal | Total |
| --- | --- | --- | --- |
| train | 19,003 | 27,014 | 46,017 |
| val | 2,160 | 3,139 | 5,299 |
| test | 1,083 | 1,576 | 2,659 |

Near-duplicates (same X-ray, resized or re-saved) are not checked yet.

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

## Official figures for calibration

Use these when replacing placeholder rates. Page numbers are PDF pages.

**Treatment outcomes of drug-sensitive TB patients notified in 2022**, from the
[India TB Report 2024](https://tbcindia.mohfw.gov.in/wp-content/uploads/2024/10/TB-Report_for-Web_08_10-2024-1.pdf)
Annexure tables 3.1 to 3.3 (pp. 218-223):

| Group | Notified | Success | Died | Lost to follow-up | Failed | Regimen changed |
| --- | --- | --- | --- | --- | --- | --- |
| India, total | 23,60,036 | 87.6% | 3.6% | 2.1% | 0.5% | 1.4% |
| India, public sector | 18,00,258 | 86.9% | 3.9% | 1.9% | 0.5% | 1.6% |
| India, private sector | 5,59,778 | 89.5% | 2.7% | 2.6% | 0.4% | 0.8% |
| Karnataka, total | 76,687 | 84.6% | 6.7% | 2.1% | 0.5% | 2.5% |
| Karnataka, public sector | 64,794 | 83.9% | 7.3% | 2.3% | 0.5% | 2.7% |
| Karnataka, private sector | 11,893 | 88.0% | 3.0% | 0.9% | 0.3% | 1.0% |

- **More patients die than are lost to follow-up**, nationally and in Karnataka.
- Lost to follow-up varies by state, from 0.1% (Andhra Pradesh) to 7.5%
  (Arunachal Pradesh), with Delhi and Nagaland at 4.7% and Bihar at 4.5% (pp. 222-223).
- Drug-resistant TB is much worse (p. 58). On the shorter MDR/RR regimen (2022
  cohort, 21,285 patients): 75% success, 10% died, 10% lost to follow-up. On all
  MDR/RR treatment (2021 cohort, 33,555 patients): 74%, 12% and 9%.
- 95% of diagnosed drug-sensitive patients started treatment in 2023 (p. 57).
- 7.1% of the TB patients screened for alcohol use in 2023 were identified as users
  (Section 7.6), while the studies it cites give 20.3-31.5%.

**Screening and care rules**, from the
[TB Mukt Bharat Abhiyaan 2026 campaign document](https://tbcindia.mohfw.gov.in/wp-content/uploads/2026/03/TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf):

- 7 Dec 2024 to 30 Dec 2025: 27.28 lakh new TB cases, of which 9.48 lakh had no
  symptoms (pp. 3-4).
- **Vulnerable groups (p. 7):** over 60, BMI under 18.5, diabetes, HIV, smokers,
  alcohol use, past TB, household contacts of TB patients.
- **Symptoms (p. 8, "10-S"):** cough over 2 weeks (any duration if vulnerable), fever,
  night sweats, coughing blood, chest pain, shortness of breath, weight loss, loss of
  appetite, fatigue, lymph node swelling or other extrapulmonary signs.
- **Patient care (pp. 12-13):** differentiated care assessment for all patients, BMI
  check, energy-dense supplements if BMI is under 18.5 for the first 2 months,
  nutrition payment within 15 days, 99DOTS-lite missed calls for adherence, call
  centre checks, ASHA visits weekly and CHO visits fortnightly.
- **Tracked indicators (pp. 54-55):** vulnerable people reached, X-ray screening, NAAT
  for presumptive cases, high-risk assessment, nutrition and Ni-kshay Mitra linkage,
  preventive treatment.

**Accuracy targets**, from WHO:

| Source | Test type | Minimum sensitivity / specificity | Optimal |
| --- | --- | --- | --- |
| [2025 target profiles](https://www.who.int/publications/i/item/9789240113572) | One-step screening | 90% / 80% | 95% / 95% |
| 2025 target profiles | First step of two-step screening | 90% / 60% | 95% / 85% |
| 2025 target profiles | High-specificity screening | 60% / 98% | 70% / 98% |
| Older triage target (the one our results files check) | Triage | 90% / 70% | |

The same 2025 document says people with TB symptoms should go straight to diagnostic
evaluation without further screening.

[WHO's June 2025 CAD assessment](https://www.who.int/publications/i/item/9789240110373)
required partial AUC of at least 0.9 in the 40-60% specificity range (the upper
confidence limit could reach it) and at least 40% specificity at 90% sensitivity.
CAD4TB v7, DrAid v2.4.4-6, Genki Edge v3.4.2, InferRead DR Chest v1.0.1.1, Insight CXR
v3.1 and qXR v4.0 met this. JVIEWER-X v5.0.0 and Radify Chest v3.8.0 did not.

**Figures that disagree:** PIB reports 90% treatment success under the campaign, while
the India TB Report gives 87.6% for the 2022 cohort. These cover different periods, and
the PIB releases don't state a cohort, so use the report's table for calibration.

## Synthetic patients

```bash
python data/synthetic/generate_patients.py --n 5000
```

This writes `data/processed/synthetic_patients.csv`, which git ignores. The
rates in the script are placeholders until they are replaced with cited India
TB Report figures. Dropout labels come from a rule we wrote ourselves, so any
model accuracy on this data only shows that the pipeline works.
