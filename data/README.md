# Data

**No dataset files go into git.** They are large, and some licences (CODA TB)
forbid sharing them. Download each one into `data/raw/<name>/` on your own
machine; that folder is ignored by git.

| Dataset | Used for | Where to get it | Notes |
| --- | --- | --- | --- |
| CODA TB DREAM | Cough model | Synapse (request access) | Do not redistribute |
| TBX11K | X-ray model | Public download | Check licence before use |
| Shenzhen + Montgomery CXR | X-ray model | U.S. National Library of Medicine | Public |
| Synthetic patients | Dropout model, dashboard | `data/synthetic/` generator | Built from India TB Report statistics |

All patients in this project are either from these public research datasets
or fully synthetic. Never add real patient records.

## Synthetic patients

```bash
python data/synthetic/generate_patients.py --n 5000
```

This writes `data/processed/synthetic_patients.csv`, which git ignores. The
rates in the script are placeholders until they are replaced with cited India
TB Report figures. Dropout labels come from a rule we wrote ourselves, so any
model accuracy on this data only shows that the pipeline works.
