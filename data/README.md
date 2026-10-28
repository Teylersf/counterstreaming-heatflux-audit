# Archived initial-moment reanalysis

The original data are from Madox C. McGrae-Menge's dataset accompanying
McGrae-Menge et al., *Counter-streaming heat-flux closure for electron-only
collisionless magnetic reconnection* (2026):
[Zenodo 21114117](https://zenodo.org/records/21114117),
DOI [10.5281/zenodo.21114117](https://doi.org/10.5281/zenodo.21114117).
The record declares **CC BY 4.0**. Original input decks retain that license and
attribution. The CSV is a derived reanalysis by Taylor Kalin with the original
data credited; it is not a new PIC or Gkeyll run.

## Reproduce

From the repository root, using the versions in `requirements.txt`:

```sh
python -m pip install -r requirements.txt
python experiments/fetch_data.py
python experiments/fetch_data.py --check-only
python experiments/data_checks.py
```

Only the first download command needs network access. It retrieves 13 selected
HDF5 members from the 1,238,114,672-byte PIC ZIP using ordinary HTTP Range
requests. The selected compressed member payload totals **4,475,130 bytes**;
local headers and input decks add small overhead. Every request must return
HTTP 206 with the exact requested `Content-Range`; response reads and DEFLATE
output are bounded. The downloader refuses a full-archive HTTP 200 fallback.
Each member must match both its ZIP CRC32 and the pinned SHA-256 before it is
written. Downloads are serialized and an already verified file is reused.

The complete ZIP's `md5:89f8256fe66809412f3814dd8663c833` is **declared by
Zenodo, not verified by this partial retrieval**. No claim of full-archive
checksum verification is made. The three small input decks are checked against
their published MD5 and pinned SHA-256. `provenance.json` records exact member
names, byte offsets, lengths, checksums and public URLs.

`raw/` contains the local HDF5 cache and must remain Git-ignored. The repository
contains the small derived profile, provenance, input decks and downloader;
it does not redistribute the full PIC archive or raw-particle files.

## Definitions and coordinates

The original authors' Zenodo description defines `vfl_i` as the density-normalized
ordinary velocity moment, `(1/n) integral f v_i d^3v`, and `v_i v_j` as the
unnormalized moment `integral f v_i v_j d^3v`. This matters: the second moments
must not be multiplied by density a second time. At `m_e=1`,

```text
n_s = -charge_s
n = n_1 + n_2
v_i = (n_1*vfl_i1 + n_2*vfl_i2)/n
P_ii = M_ii1 + M_ii2 - n*v_i^2
J_z(moment) = -(n_1*vfl_31 + n_2*vfl_32)
```

All selected files have `TIME=0`, `ITER=0`, shape `(640, 480)` in `(y, x)` order,
with axes `x=[-24,24]`, `y=[-32,32]` and spacing `0.1`. Their recorded
`OFFSET_X` values are:

| Quantity | Offset `(x,y)` |
|---|---|
| Density and velocity moments | `(0.5,0.5)` |
| `b1` | `(0.5,1.0)` |
| `b2` | `(1.0,0.5)` |
| `b3` | `(1.0,1.0)` |

Backward differences of the staggered `b2` and `b1` therefore evaluate
`(curl B)_z` on moment-cell centers. The x derivative has exactly zero x mean
under periodic differencing. The code compares this curl with the physical
moment current. It does **not** read the native charge-conserving OSIRIS current,
whose deposition rule can differ from a simple `q*v` moment diagnostic.

Raw coordinates place the lower sheet at `y=-16`; the paper uses `Y=y+32`,
placing it at `Y=16`. Thus array rows 159 and 160 correspond to `Y=15.95` and
`16.05`. A printed y-coordinate shift is not an initialization discrepancy.

The Gkeyll comparison uses the ordinary velocity and isotropic thermal pressure
prescribed by the posted Lua initializers, including their rounded
`vth_e=0.111803`. It does not reload the archived `.bp` fluid fields. The cold
proper-to-ordinary velocity curve is an explanatory limiting calculation, not
a fitted finite-temperature prediction.

## Outputs

- `derived/initial-profiles.csv`: 640 x-averaged profile rows in raw and paper
  coordinates, including PIC current, magnetic-curl current, input-prescribed
  fluid velocity, and `Pxx`, `Pzz` relative to prescribed fluid pressure.
- `../results/data-checks.json`: measurement tables, named `initial_current`
  and `initial_pressure` checks, software versions and explicit limitations.
- `experiments.data_checks.analyze_profiles()`: NumPy profile arrays for figures.
- `experiments.data_checks.run_checks()`: JSON-serializable results for the
  publication's complete verification suite.
