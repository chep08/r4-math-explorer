# r4-math-explorer

**Phase Transition of Library Reuse in Formal Theorem Proving: A Falsifiable Framework and Its Empirical Boundary**

This repository contains the reproducible experiments behind the above manuscript
(by Pan Che, Independent Researcher, Xinjiang, China). It implements a
*closed, zero-token-at-inference, Lean-hard-verified* pipeline for testing whether
library reuse in formal theorem proving exhibits a *percolation phase transition*:
the library's fragment-coverage density `ρ` is the control parameter, the held-out
target close probability `P(ρ)` is the order parameter, and a critical density `ρ_c`
is predicted.

The empirical conclusion is a **boundary**: the phase-transition hypothesis is
*confirmed in a controlled synthetic domain* (H2, H3, H5) but *not observed on
three real corpora* (miniF2F, ProofNet, Lean-Workbook). On real data the library
provides no marginal value, consistent with a *concept-closure barrier*.

---

## What makes this different

Unlike LLM-driven library-learning provers (LEGO-Prover, TroVE, DynaSaur,
CircuitProver), **no large language model is queried during any evaluation step.**
Every closing judgment is decided solely by the local Lean 4 / Mathlib verifier
(gold-standard single verification, sorry-free). Thus the reported numbers are
independent of any particular LLM and its sampling. (An AI coding assistant was
used *during development* to write these scripts, but not at runtime — fully
disclosed in the manuscript's AI-assistance statement.)

---

## Contents

```
r4-math-explorer/
├── README.md
├── LICENSE
├── src/                      core Lean verification modules
│   ├── lean_verifier.py      LeanVerifier.verify() — the gold-standard single verifier
│   ├── lean_batch.py         batch_verify_many() — amortized import, single-shot compile
│   └── goal_parser.py        parser for leftover (unsolved) goals from Lean errors
├── code/                     experiment scripts + result data
│   ├── lw_build_lib.py       build the Lean-Workbook fragment library (n=50)
│   ├── lw_build_lib_big.py   enlarge baseline to n=150 + build pure-rw library
│   ├── lw_h1_rho.py          real-domain P(ρ) density scan (H1)
│   ├── lw_h245_real.py       real-domain H2/H4/H5 combined measurement
│   ├── lw_h2_rho.py          real-domain reuse-rate threshold r_dir/r_soft (H2)
│   ├── lw_h5_real.py         real-domain equal-compute L/D crossover (H5)
│   ├── stage1_synthetic.py   synthetic bridge-dependent P(ρ) (H2-A mainline)
│   ├── stage1_rho_eff.py     ρ_eff generalization shift (H3)
│   ├── stage1_h245.py        synthetic-domain H2/H4/H5 (full data)
│   ├── stage1_real_gen.py    real generalization operator (H3)
│   ├── stage1_real_baseline.py  real deep-gap baseline P(ρ)
│   ├── gen_fig1.py           regenerate Fig. 1 (synthetic P(ρ)/χ(ρ), H1)
│   ├── gen_fig3.py           regenerate Fig. 3 (equal-compute L/D crossover, H5)
│   ├── gen_fig4.py           regenerate Fig. 4 (flat real P(ρ) vs synthetic rise)
│   └── *.json / *.jsonl      the gold-standard result data reported in the paper
└── data/                     (lean workbook; not committed — see "Data")
```

---

## Data

The real corpus used in the manuscript is **Lean-Workbook** (Lean v4.8.0-rc1 +
Mathlib4 v4.8.0-rc1). It is **not** committed to this repository (it is a
third-party dataset). To reproduce the real-domain experiments, download it and
point the scripts at it via the `LEAN_WORKBOOK_DIR` environment variable (the
scripts fall back to `data/Lean-Workbook` under the repo root):

- Dataset: `InternLM/Lean-Workbook` on HuggingFace — https://huggingface.co/datasets/InternLM/Lean-Workbook
- The scripts read `wkbk_1009.parquet` (fields: `status`, `formal_statement`, `id`).

The pre-computed library and target snapshots that **are** committed (under `code/`,
e.g. `lw_lib_full.jsonl`, `lw_targets_proved_dedup.jsonl`) were produced from that
dataset with the reported seeds, so the published result JSONs are reproducible
from the committed snapshot without re-downloading the corpus.

miniF2F ([Zheng, Han, Polu](https://arxiv.org/abs/2109.00110), ICLR 2022) and
ProofNet ([Azerbayev et al.](https://arxiv.org/abs/2302.12433), 2023) are cited in
the paper; the reported numbers on these two corpora are bounded by small samples
(n=15 for miniF2F) as disclosed in the manuscript.

---

## Environment

- **Lean 4.8.0-rc1** with **Mathlib4 v4.8.0-rc1** (matching the dataset README).
  Clone Mathlib at tag `v4.8.0-rc1`.
- Point the verifier at it via the `MATHLIB4_DIR` environment variable:

  ```powershell
  $env:MATHLIB4_DIR = "D:\path\to\mathlib4-4.8.0-rc1"
  ```

- Python 3.11 with: `pandas`, `numpy`, `scikit-learn`, `pyarrow` (parquet).
  `matplotlib` is needed only for `gen_fig4.py`.

---

## Reproduction

Scripts resolve `src/` relative to the script's own location, so you can run them
from any directory. Set the two env vars above, then run from a shell:

```powershell
cd code
```

**Build the real fragment library (Lean-Workbook):**

```powershell
python lw_build_lib.py          # n=50 baseline -> lw_close50_result.json, lw_lib_full.jsonl
python lw_build_lib_big.py      # n=150 -> lw_close150_result.json (18/150 = 12.0%)
```

**Real-domain density scan / hypotheses (the core negative finding):**

```powershell
python lw_h1_rho.py             # -> lw_h1_rho.json    (P(ρ) flat at 0.267 over 30 targets)
python lw_h2_rho.py             # -> lw_h2_rho.json    (r_dir=0, r_soft≤0.033)
python lw_h245_real.py          # -> lw_h245_real.json (H4: real vs random)
python lw_h5_real.py            # -> lw_h5_real.json   (L=0.267 > D=0.133, no crossover)
```

**Synthetic-domain phase transition (confirmed):**

```powershell
python stage1_synthetic.py --n-lemmas 40 --k 3 --density-points 10 --out report_stage1_synth.json
python stage1_rho_eff.py --n-classes 10 --variants-per-class 5 --n-targets 200
python stage1_h245.py --n-lemmas 40 --k 3 --n-targets 60 --density-points 20 --out report_stage1_h245.json
python stage1_real_gen.py --n-classes 10 --targets-per-class 5 --out report_stage1_rho_c.json
python stage1_real_baseline.py --library stage1_library.jsonl --targets stage1_targets_samedomain.jsonl --max-targets 12
```

**Regenerate the manuscript figures (all read the real result JSONs):**

```powershell
python gen_fig1.py   # reads report_stage1_synth.json  -> fig1_phase_transition.pdf
python gen_fig3.py   # reads report_stage1_h245.json   -> fig3_equal_compute_crossover.pdf
python gen_fig4.py   # reads lw_h1_rho.json + report_stage1_rho_c.json -> fig4_real_datasets_absent.pdf
```

> **Note on `LeanVerifier.verify` vs `batch_verify_many`:** `batch_verify_many`
> amortizes the `import Mathlib` cost across many candidates. The manuscript
> *found and fixed a batch false positive* (`exact <lib-fragment-name>` mis-reported
> as success) and therefore reports final numbers computed by the gold-standard
> `LeanVerifier.verify` (single verification). The batch path is retained here as the
> fast pre-filter; the committed result JSONs reflect the gold-standard verdicts.

---

## Correspondence to the manuscript's hypotheses

| Hypothesis | Claim | Domain | Result |
|---|---|---|---|
| H1 | P(ρ) steepens / transition | synthetic | confirms (ρ_c≈0.9) |
| H1 | P(ρ) transition | real | **not observed** (flat) |
| H2 | density-threshold reuse | synthetic | supported |
| H2 | reuse-rate threshold | real | **not observed** |
| H3 | generalized ρ_c much smaller | synthetic | **Lean-verified** |
| H4 | structure beats random | synthetic/real | not strongly confirmed |
| H5 | equal-compute L/D crossover | synthetic | **confirmed** (ρ≈0.85) |
| H5 | equal-compute crossover | real | **not observed** |

The central claim — "valid in controlled settings, **bounded** on real data" — is
the paper's principal contribution.

---

## License

Code and scripts in `src/` and `code/` are released under the **Apache-2.0**
license (see the manuscript for the author's attribution). The committed derived
data products (`*.json`, `*.jsonl`) carry the same license. The Lean-Workbook
dataset is licensed Apache-2.0 by its authors (HuggingFace: InternLM/Lean-Workbook).
