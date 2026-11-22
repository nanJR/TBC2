# TBC² demo kit

Everything you need to show every feature of TBC² (TB Care Coordinator): test files,
ABHA IDs, logins, step-by-step scenarios, a pre-demo checklist, troubleshooting, and
honest answers for evaluators. All patients, ABHA records, ASHA names and van schedules
are simulated. The cough and X-ray scores come from the real models.

## 0. Get the files

```bash
cd services/api && uv run python ../../demo-kit/build_demo_kit.py
```

This copies 6 cough clips and 6 chest X-rays from `data/raw` into `demo-kit/media/`
(git-ignored: the datasets are never re-uploaded, see Credits) and writes the error test
files into `demo-kit/test-files/` (made by us, committed). From Windows the folder is
`\\wsl.localhost\Ubuntu-24.04\home\panni\code\TBC2\demo-kit`.

## 1. Where and who

| | |
| --- | --- |
| Website | https://tbc-2.vercel.app |
| API status | https://tbc-2.vercel.app/api/status → `{"status":"ok"}` |
| Pharmacist (counter portal) | `counter.hanur@example.com` |
| ASHA (ASHA portal) | `asha.hanur@example.com` |
| Admin, both portals (coordinator) | `coordinator.tbc2@example.com` |

Passwords are in `services/api/.env` (`DEMO_PASSWORD_PRACTITIONER`, `DEMO_PASSWORD_ASHA`,
`DEMO_PASSWORD_COORDINATOR`). They are never committed.

Show two roles side by side with **two separate browser windows** (normal + Incognito):
tabs in one window share one login.

### ABHA demo numbers (tick consent first)

| ABHA number | Fills in | Use it to show |
| --- | --- | --- |
| `91-5528-7340-1196` | Male, 45 · diabetes, smoker | the main presumptive-TB journey |
| `91-6043-2817-5502` | Female, 63 · past TB, underweight (+ over 60) | high-risk group without symptoms |
| `91-7712-0459-8834` | Female, 34 · HIV on ART | a short cough counts for vulnerable people |
| `91-3386-9021-4470` | Male, 28 · no history | low risk / cough false alarm |
| `91-0000-0000-0000` | (not on record) | "No record found" |

## 2. Test files and what they give

Checked through the real API with no symptoms and no history ticked (22 Nov 2026).

| File (`demo-kit/media/`) | Truth | Score shown | Result alone |
| --- | --- | --- | --- |
| `cough-1_TB_high-96.wav` | TB | 96%, High | Refer for chest X-ray |
| `cough-2_TB_high-67.wav` | TB | 67%, High | Refer for chest X-ray |
| `cough-3_TB_moderate-44.wav` | TB | 44%, Moderate | No referral (ticks decide) |
| `cough-4_TB_missed-1.wav` | TB | 1%, Low | No referral: **the cough model missed it** |
| `cough-5_notTB_low-7.wav` | not TB | 7%, Low | No referral |
| `cough-6_notTB_false-alarm-91.wav` | not TB | 91%, High | Refer for chest X-ray (**false alarm**) |
| `xray-1_TB_100.jpg` | TB | 100% | NAAT |
| `xray-2_TB_99.jpg` | TB | 99% | NAAT |
| `xray-3_TB_68.jpg` | TB | 68% | NAAT (a less certain read) |
| `xray-4_normal_0.jpg` | normal | 0% | clear |
| `xray-5_normal_24.jpg` | normal | 24% | clear |
| `xray-6_normal_20.jpg` | normal | 20% | clear |

Any symptom ticked (cough > 2 weeks, fever, …) always gives **Refer for NAAT Test**,
whatever the cough score. A short cough counts too if the person is in a high-risk group.

| Error test (`demo-kit/test-files/`) | Where | Message |
| --- | --- | --- |
| `error_silent-recording.wav` | counter cough upload | "The recording is too short or too quiet…" |
| `error_not-audio.wav` | counter cough upload | "Could not read the cough file" |
| `error_colour-photo.jpg` | ASHA X-ray upload | "This looks like a colour photo, not an X-ray" |

All X-rays are grey 640×640 JU-TB test images the model never trained on, so neither
JU-TB shortcut (tinted images, image size) explains the result.

## 3. Before you present (5 minutes)

- [ ] Open https://tbc-2.vercel.app. The pill top right goes from **Waking Up…** to
      **● Back End: Running** (the free API sleeps after 15 idle minutes).
- [ ] Sign in as the pharmacist and run one screening (first one after waking takes
      ~30 s; then 2–3 s). Dismiss it with "Other".
- [ ] Stop any local servers (`./scripts/dev.sh`): one API at a time on the shared database.
- [ ] Open a second, Incognito window for the ASHA.
- [ ] Have `demo-kit/media/` open in File Explorer for uploads.
- [ ] If an ad blocker is on, it's fine: API calls go through the site's own domain.

## 4. Scenarios (each shows different features)

### A. Presumptive TB, full journey (the main demo, ~4 min)
1. **Counter**: ABHA `91-5528-7340-1196`, tick consent → Fetch History (history chips fill
   in, conditions listed). Tick **Cough > 2 Weeks**. Upload `cough-2_TB_high-67.wav` →
   Get Risk Score → **67% High Risk, Refer for NAAT Test** with the reason.
2. Tick contact consent → **Forward to ASHA**. Show **Print Referral Slip** (only the slip
   prints; it has the helpline and never says "you have TB").
3. **ASHA window**: the case is at the top of Forwarded Cases. Open it:
   Reached → **Sputum Sent to TB Unit** (presumptive TB: don't wait for the van) → book a
   van visit → upload `xray-2_TB_99.jpg` (**99%**) → **Get Combined Risk Score** (99%, NAAT)
   → NAAT **MTB Detected, RR Not Detected** → Start Treatment (any MO name, PHC Ramapura,
   50–64 kg, tick notified).
4. **Open Patient**: Month 1 of 6 · Intensive Phase · 2HRZE/4HRE. Record **Today's Dose:
   Taken**, then record an **IsoScreen** test (INH Detected, 12 hours since dose).
5. Point at the Patient Journey numbers going up.

### B. Cough false alarm, X-ray settles it (~2 min)
Counter: ABHA `91-3386-9021-4470`, no symptoms, upload `cough-6_notTB_false-alarm-91.wav`
→ **91% High, Refer for Chest X-Ray** (the cough model can add an X-ray, never a NAAT).
Forward. ASHA: Reached → book van → upload `xray-4_normal_0.jpg` (0%) → Get Combined Risk
Score → **No Referral Needed** → **Close Case: X-Ray Clear** (shows as a ticked last step).

### C. High-risk group without symptoms, drug-resistant TB (~2 min)
Counter: ABHA `91-6043-2817-5502` (63, past TB, underweight), no symptoms, upload
`cough-5_notTB_low-7.wav` → 7% Low but **Refer for Chest X-Ray** (high-risk group).
Forward. ASHA: Reached → Sputum → book van → instead of an image, use the van's reading
**Abnormal** → Combined → NAAT **MTB Detected, RR Detected** → note "refer to the DR-TB
centre" → Start Treatment. Open the patient: DR-TB regimen, **IsoScreen not used** (no
isoniazid in the regimen).

### D. Symptoms always win, even when the model misses TB (~1 min)
Counter, no ABHA (enter age 30, Female by hand). Tick **Fever**. Upload
`cough-4_TB_missed-1.wav` → **1% Low, but Refer for NAAT Test** because of the symptom.
Say: the model only adds referrals, it can never cancel one.

### E. Vulnerable person with a short cough (~1 min)
ABHA `91-7712-0459-8834` (HIV). Tick **Cough < 2 Weeks** only → **Refer for NAAT Test**:
for high-risk people any cough counts (TB Mukt Bharat rule).

### F. Low risk, dismissed (~30 s)
ABHA `91-3386-9021-4470`, no symptoms, `cough-5_notTB_low-7.wav` → No Referral Needed →
**Dismiss → Low Risk, No Symptoms**. It appears in Recent Screenings with that reason.

### G. ASHA follow-up details (~2 min)
- A **New / Overdue** case: press **Not Reached** twice → "Not Reached, 2 Tries"; then
  **Close This Case → Not Reached After Several Tries**.
- NAAT **Inconclusive** → it asks for a fresh sputum sample before the repeat test.
- **Likely to Stop Treatment**: open a red (≥60%) patient → reasons, missed-dose ladder
  (call at 3 days, visit at 7), IsoScreen history with **INH Not Detected**.
- **Suggested by TBC²**: Approve one ("Approved · Sent to ASHA"), Reject another. Nothing
  is sent without approval, and a decision can't be changed.

### H. Errors handled cleanly (~1 min)
Counter: upload `error_silent-recording.wav`, then `error_not-audio.wav`. ABHA without the
consent tick (button stays off) and `91-0000-0000-0000` ("No record found"). ASHA X-ray
step: upload `error_colour-photo.jpg`.

### I. Security, roles and design (~1 min)
- ASHA window: only the **ASHA Portal** tab; typing `/counter` sends you back.
- Pharmacist: only **Counter**. Admin (`coordinator.tbc2@example.com`): both tabs.
- Sign out → back to the home page. `/login` has a **Back** button.
- Toggle **dark mode**; show the phone layout (F12 → Ctrl+Shift+M → 360 px).

## 5. Honest numbers (for questions)

- **X-ray**: 95% accuracy, 90.4% sensitivity, 98.5% specificity on a deduplicated JU-TB
  test set (n = 2,659); grey images only 88.1% sensitivity. **Outside test** (other
  hospitals): Shenzhen AUROC 0.78, Montgomery 0.67, so it doesn't generalise yet. Next:
  fine-tune on mixed sources. Details: `data/README.md`.
- **Cough**: clinic-only (TBscreen) cross-validated AUROC 0.67. It may only add an X-ray,
  never a NAAT (scenarios B and D show why). Next: retrain on CODA TB once access arrives.
- **Combined score**: the higher of the two rescaled scores, a simple rule, not a trained
  model (no dataset has both a cough and an X-ray for the same person).
- **Dropout risk**: rule-based on synthetic patients; it shows the pipeline, not real
  performance.

## 6. Likely questions

- *Is any real patient data used?* No. Synthetic records only; uploads are scored in memory
  and never stored; ABHA is simulated and only a keyed hash of the number is kept.
- *Where is data stored?* Supabase (Postgres) in Mumbai. Row-level security is forced on
  every table; the browser can't read any table; only the API's server key can, and it
  can't delete anything; every change is in an append-only audit log.
- *Does it connect to Ni-kshay or ABDM?* No. Notification is recorded by hand.
- *Why ASHA + van + NAAT?* NTEP: presumptive TB goes to NAAT; X-ray vans and handheld
  X-rays are used in TB Mukt Bharat campaigns; the Medical Officer starts treatment.
- *What's IsoScreen?* A urine strip that detects isoniazid; a spot check that self-reported
  doses were taken (99DOTS self-reports alone are ~70% sensitive).

## 7. If something goes wrong

| Symptom | Fix |
| --- | --- |
| "Waking Up…" for a while | Normal for ~1 min after idle. Open `/api/status` in a tab. |
| Stuck on "Checking Your Login…" | The API is asleep; wait a minute and reload. |
| Sign-in fails with an ad blocker | Allow the site in the blocker (sign-in goes to supabase.co). |
| Old colours/layout | Ctrl+Shift+R. |
| No internet at the venue | Run locally: comment out `SUPABASE_SECRET_KEY` in `services/api/.env` and the two lines in `apps/web/.env.local`, then `./scripts/dev.sh` (in memory, no login). |
| Too many test records | Ask for a reset of the data tables (logins stay; demo data reseeds on restart). |

## 8. Credits

- Cough clips: Kaggle TB cough set built from TBscreen and Coswara recordings (CC BY 4.0;
  see `data/README.md` for the citations).
- Chest X-rays: JU-TB, Ghosh and Singh, Mendeley Data, DOI 10.17632/g46k8s49hj.3 (CC BY 4.0).
- Outside test sets: Shenzhen and Montgomery, U.S. National Library of Medicine (Jaeger et al.
  2014).

Prototype for demonstration only, not for clinical use.
