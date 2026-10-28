# Archived fluid corroboration for the revision

The source is Madox McGrae-Menge's CC BY 4.0 deposit accompanying
*Counter-streaming heat-flux closure for electron-only collisionless magnetic
reconnection*. The **version DOI** is
[10.5281/zenodo.21114117](https://doi.org/10.5281/zenodo.21114117); the
**concept DOI** is
[10.5281/zenodo.21114116](https://doi.org/10.5281/zenodo.21114116).
These identify a specific deposit and its version family, respectively.

`provenance-revision.json` contains the complete central directories of all
three posted archives, selected-member hashes, exact diagnostic availability,
and numeric-export hashes. The PIC directory has **223 entries**, including
94 scientific files after excluding directories and macOS resource metadata.
No native deposited-current diagnostic is identifiable in that complete list.
Velocity moments are not presented as a substitute for that missing diagnostic.

Only five fluid members were retrieved: the one-fluid electron and field
snapshots, and the two-fluid two-electron and field snapshots, all at t=0.
Their compressed member payload totals **24,768,013 bytes**. Requests are
serialized, bounded and require exact HTTP 206 ranges. Each extracted member
passes its ZIP CRC32; its SHA-256 is pinned and checked on reuse. This does
**not** verify the complete archives' publisher-declared MD5 values.

## Portable reproduction

Run from the repository root. Retrieval and comparison use the ordinary core
Python requirements; they do not require ADIOS2 to be installed in Windows:

```sh
python experiments/fetch_data.py
python experiments/revision_data.py --inventory --fetch
```

BP decoding is a separate, optional reader step. On Linux, use a dedicated
environment rather than altering an existing scientific runtime:

```sh
python3 -m venv ../heatflux-bp-reader
. ../heatflux-bp-reader/bin/activate
python -m pip install -r requirements-bp.txt
python experiments/revision_data.py --decode-bp
```

The tested reader was **ADIOS2 2.13.0.1001**, **NumPy 2.3.5**, and **Python
3.12.3** on Ubuntu under WSL. The official Linux wheels were checked against
their PyPI SHA-256 values and unpacked into an isolated task-local directory;
the bundled Windows runtime and Linux system packages were not changed. A
normal Linux virtual environment is the portable route above. Windows users
can run the reader against the same checkout through WSL, with its mounted
repository path. The scientific script contains no private reader-install path.

After decoding, run comparison in the core environment (or a separate Linux
environment with the core requirements):

```sh
python experiments/revision_data.py --compare
```

The script uses the official ADIOS2 reader rather than a custom BP parser.
It checks source BP and decoded NPZ hashes, snapshot time/frame, grid metadata,
and the exact embedded input files before comparing moments. Raw BP, NPZ and
their full metadata remain in **`data/raw/revision/`**, covered by the existing
`data/raw/` Git ignore rule. Do not commit this cache.

## Component order and output checks

The BP variable `CartGridField` has dimensions `[480,640,10]` for electron
moments, interpreted as `[x,y,component]`. Metadata give bounds
`[-24,24] × [-32,32]`, zero ghosts, mass 1, charge −1 and polynomial order 0.
The component order comes from each snapshot's embedded `inputfile`, decoded
from base64 and found **byte-identical** to the separately published Lua deck:

```text
rho, rho*ux, rho*uy, rho*uz, Mxx, Mxy, Mxz, Myy, Myz, Mzz
```

Every component is checked against the posted analytical initializer at all
480×640 cell centers; the largest moment-component error is below 4.38e−16.
The two-fluid total state agrees with one-fluid output within 1.12e−16.
The fields' first six components agree with their initializer within 1.12e−15.
The two extra field components are not used or assigned unverified meanings.

For mass 1, aggregate covariance pressure is obtained by adding the stored raw
second moments and subtracting the aggregate bulk momentum product. This is
done in each cell before x averaging. The authors' PIC data dictionary defines
the `vfl` diagnostics as ordinary density-normalized velocity moments and the
`v_i v_j` diagnostics as unnormalized second moments; the same definitions as
the original audit are retained.

All five BP files record **time=0, frame=0 and one available step**. All 13
selected PIC HDF5 files record **TIME=0 and ITER=0**. No explicit averaging
attribute was found. These are checks of archived metadata, not certification
that an undocumented operation in an unavailable executable is impossible.
BP metadata also record changeset **`9663ea594e80+`** and build date
`Oct 23 2023 21:19:55`. The plus-marked identifier is partial/dirty build
provenance, not a verified clean source tree or exact executable certification.

## Results and limits

The full 640-row x-averaged PIC-minus-archived-fluid relative L2 differences
are **9.867534% for Jz**, **8.316864% for Pxx**, and **9.543957% for Pzz**;
the two fluid models give the same comparisons to numerical precision. Near
the lower-sheet center, rows 159/160 give actual archived fluid pressure
`0.012499910809`, PIC/fluid Pzz ratios `0.615727/0.615447`, and moment-current
deficits `11.58196%/11.60412%` relative to the archived fluid moment current.

These corroborate an initial moment mismatch using actual fluid output. They
do not supply the missing native PIC deposited current, a new matched-state
run, an electric-field transient measurement or a causal effect on the
reported nonlinear comparison.

- [`derived/revision-fluid-profiles.csv`](derived/revision-fluid-profiles.csv):
  complete 640-row profile export.
- [`../results/revision-data.json`](../results/revision-data.json): component
  checks, actual snapshot metadata, four center rows, global and sheet-region
  norms, and export hash.
- [`provenance-revision.json`](provenance-revision.json): exact inventory and
  selected-member/numeric-export provenance.

The CSV SHA-256 is
`9c42755c1f7b6073b6f49f627eeaf8f736f4de46aa3cdc35f9629dacdd565ded`.
Reproduction checks numerical fields and recorded source hashes; new local
execution timestamps may differ.

Reader sources: [ADIOS2 Python API](https://adios2.readthedocs.io/en/latest/api_python/api_python.html),
[BP3 compatibility](https://adios2.readthedocs.io/en/v2.11.0/engines/engines.html),
[versioned ADIOS2 package metadata](https://pypi.org/pypi/adios2/2.13.0.1001/json).
