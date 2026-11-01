# Cough model training runbook

For the day CODA TB and the GPU are both ready. Commands run from `ml/` unless noted.

## 1. Before anything else

- [ ] Read the CODA TB data terms. Confirm they allow storing the data on the college
      server, and whether trained weights can be shared. Until then, keep weights private.
- [ ] Limit who can read the data folder: `chmod -R o-rwx ../data/raw/CODA_TB`.
- [ ] Never commit CODA data, and don't copy it anywhere else.

## 2. Set up the GPU server

```bash
git clone https://github.com/nanJR/TBC2 && cd TBC2/ml
# Delete the [tool.uv.sources] torch lines and the [[tool.uv.index]] block in pyproject.toml,
# so uv installs the CUDA build of PyTorch. Don't commit this change.
uv sync
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
uv run python cough/train_cnn.py --smoke   # needs data/raw/Cough_Audio on the server
```

If the college server isn't available, Colab's GPU can run the same scripts, but only if the
CODA terms allow uploading the data there.

## 3. Map the data

Put the download in `data/raw/CODA_TB/`, then fill in `coda_manifest()` in `cough/manifest.py`
using `CODA TB Challenge data dictionary.xlsx`.

Check these before training:

- [ ] Patient counts match the challenge page: 1,105 clinical, 1,082 solicited (9,772 files).
- [ ] No person appears in more than one split.
- [ ] **Does the download include a labelled test set?** The published study had 2,143 people. If
      the rest aren't included, use `assign_person_splits`, and say that scores aren't directly
      comparable to the published ones.
- [ ] **Do TBscreen and CODA share participants?** Both include South African sites. If overlap
      can't be ruled out, don't call TBscreen an external test.
- [ ] Clinical inputs are limited to what an ASHA can really collect.

## 4. Train

```bash
uv run python cough/train_cnn.py --dataset coda --name cough_only
uv run python cough/train_cnn.py --dataset coda --name with_clinical --with-clinical
```

Stopping and rerunning continues from the last epoch. Use `tmux` so a dropped connection doesn't
end the run. Add `--wandb` to log runs.

**Longitudinal coughs** (31.6 GB, 714,922 files, 565 patients, training only): leave these out at
first. `Prepared` holds all clips in memory, so they would need a streaming loader, and each person
needs equal weight. Add them only if solicited results suggest more data would help.

## 5. Compare with what's been published

CODA TB DREAM Challenge ([doi:10.1093/ofid/ofaf572](https://doi.org/10.1093/ofid/ofaf572)):

| Model | AUROC | Best specificity at 80% sensitivity |
| --- | --- | --- |
| Cough only | 0.69-0.74 | 55.5% |
| Cough plus clinical | 0.78-0.83 | 73.8% |

If ours is much higher than these, assume a mistake or a shortcut until proven otherwise.

## 6. Serve it

```bash
uv run python export/export_cough_cnn.py --name cough_only --out ../services/api/models/cough
```

Restart the API. The model stays experimental. `log_mel_clinical` models can't be served until the
clinical questions are added to `/screen` and the ASHA page, using the fields chosen in step 3.

## 7. Before setting `counts_towards_referral: true`

Only a person changes this, by hand, in `model.json`. All of these must hold:

- [ ] Test results come from people the model never saw, scored once.
- [ ] Results reported by country, sex and HIV status, with confidence intervals.
- [ ] It meets WHO's 2025 target for the first of two screening steps, at least 90% sensitivity and
      60% specificity, on the test set. Published models haven't reached this.
- [ ] Tested on real phone recordings from the app's recording path.
- [ ] Someone other than the person who trained it has checked the results.

Even if every box is ticked, symptoms still go to NAAT, and a low cough score never cancels a referral.
If the model doesn't pass, it stays experimental. That's still a valid result to report.
