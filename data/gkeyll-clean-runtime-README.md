# Reproducing the clean-base Gkeyll runtime

This recipe records the clean Gkeyll source base used for this study's native
controls. The archived executable identifies `9663ea594e80+` and an October 2023
build date. Its unidentified dirty changes and original binary remain
unavailable. Rebuilding the exact clean base does not recover that executable.

The portable helper is [`experiments/build_clean_gkeyll.py`](../experiments/build_clean_gkeyll.py).
It accepts caller-selected cache/work directories, does not modify system or
bundled runtimes, and never starts a model integration. Its default action is
a read-only plan. Canonical locks/manifests are read without rewriting their
bytes; derived files and logs go only into a new work directory.

## Exact inputs

The clean source commit is
`9663ea594e80f68eb305378e14512db390440e6b`, preserved in the maintainer's fork:

- Source: <https://codeload.github.com/liangwang0734/gkyl/tar.gz/9663ea594e80f68eb305378e14512db390440e6b>
- Size: 30,034,051 bytes.
- SHA-256: `28a23b3729f6d79c6351fca444db7866f039e8e2d01b220e81d009c5486af588`.

The author bootstrapped with Micromamba **2.10.0, build 0**, as verified from
the cached archive's `info/index.json` and executable `--version`:

- Original request: <https://micro.mamba.pm/api/micromamba/linux-64/latest>.
- Versioned package address used by the portable helper:
  <https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.10.0-0.tar.bz2>.
- Historical cache filename: `micromamba-linux-64-latest.tar.bz2`; its name does
  not authorize substitution of whatever is currently latest.
- Size: 7,317,886 bytes.
- SHA-256: `9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b`.

The versioned package address follows the name/version/build recovered from
the verified archive. It was not downloaded again while the controls were
running. Any retrieved bootstrap must match the recorded size and SHA-256;
an unavailable or different artifact is a blocker, not a reason to choose a
different version silently.

[`gkeyll-clean9663-dependencies.json`](gkeyll-clean9663-dependencies.json)
lists all **51** exact Conda artifacts: URL, filename, version/build, size,
publisher MD5 and SHA-256. Their total size is **159,828,558 bytes**. Source,
bootstrap and dependency archives together total **197,180,495 bytes**.
The author verified all sizes and all available MD5/SHA-256 values before the
offline dependency-prefix installation. No new dependency solve is needed.

The exact published raw-byte SHA-256 values are
`486c0ddcb4b06333365eb14f767a10430bf5f32207fdf1dbdccd3669456f4232`
for the dependency lock and
`a29f66bbf1c0651d58d748e85cb9350490bfbb1b146bd44cdd6c3e574695d8f3`
for the source/runtime file manifest. The helper requires these values even
when the files are relocated. JSON line endings are part of these artifacts;
the repository's `*.json -text` attribute preserves their committed bytes.
Do not reformat or normalize them.

Key entries in that full lock are:

| Component | Actual version/build |
|---|---|
| GCC/G++ implementation | `12.3.0 he2b93b0_5` |
| Conda target/sysroot | `x86_64-conda-linux-gnu`; `sysroot_linux-64 2.17 h0157908_18` |
| Prefix Python | `3.10.22 h267e890_0_cpython` |
| OpenMPI | `4.1.6 hc5af2df_101` |
| MPI-enabled ADIOS | `1.13.1 mpi_openmpi_h0e4b0de_1023` |
| LuaJIT | `2.1.1744318430 h280c20c_0` |
| Eigen | `3.3.9 h4bd325d_1` |
| SQLite/libsqlite | `3.54.1`, exact builds in the lock |
| GNU OpenMP runtime/mutex | `libgomp 16.2.0 he0feb66_7`; `_openmp_mutex 4.5 20_gnu` |

The compiler implementation and newer compiler-support runtime packages have
different version numbers in the actual resolved lock. Preserve those exact
entries; replacing them with a fresh solve changes the recorded environment.
In particular, a non-MPI ADIOS variant is not equivalent to the selected build.

## Cache and isolated prefix creation

Use x86_64 Linux with a compatible glibc and a host Python that supports
`tarfile`'s data-filter extraction (the author used Ubuntu 24.04.1 under WSL2).
The helper uses only Python's standard library to plan, fetch and verify
archives. Prefix Python 3.10 is installed afterward from the lock. The separate
BP-analysis environment uses host Python 3.12 and ADIOS2; it is not the ADIOS1
native build dependency. Postgkyl was not needed or installed.

Run from the repository root. These are reproduction examples; choose a new
work directory rather than the directory of an existing experiment:

```sh
GKYL_REPRO_CACHE="$HOME/gkeyll-build-cache"
GKYL_REPRO_WORK="$HOME/gkeyll-clean9663-reproduction"

python3 experiments/build_clean_gkeyll.py plan \
  --cache-root "$GKYL_REPRO_CACHE" --work-root "$GKYL_REPRO_WORK"

# Explicit network action; transfers are serial and checked before use.
# Skip fetch when the following exact artifacts already exist in the cache.
python3 experiments/build_clean_gkeyll.py fetch \
  --cache-root "$GKYL_REPRO_CACHE" --work-root "$GKYL_REPRO_WORK"

python3 experiments/build_clean_gkeyll.py verify \
  --cache-root "$GKYL_REPRO_CACHE" --work-root "$GKYL_REPRO_WORK"
python3 experiments/build_clean_gkeyll.py prepare \
  --cache-root "$GKYL_REPRO_CACHE" --work-root "$GKYL_REPRO_WORK"
python3 experiments/build_clean_gkeyll.py build \
  --cache-root "$GKYL_REPRO_CACHE" --work-root "$GKYL_REPRO_WORK" --jobs 4
```

The cache layout is the two source/bootstrap filenames above at its root and
the 51 dependency filenames under `compiler-packages/`. Existing final files
must verify; they are not overwritten. Failed partial downloads remain
untrusted evidence and are never used as complete packages.

`prepare` requires a new or empty whitespace/colon-free work root. It extracts only
the bootstrap executable and safely extracts the pinned source archive. It
then writes an `@EXPLICIT` file containing local `file:` URIs and MD5 fragments
for the already verified 51 packages. Micromamba performs the package
extraction, prefix relocation and installation; merely unpacking `.conda`
archives into a compiler prefix is not an equivalent installation.

The recorded dependency-install argv, with path prefixes replaced by
variables, was:

```sh
"$BOOTSTRAP/bin/micromamba" create --offline --yes --json --no-rc \
  -p "$DEPS" --file "$EXPLICIT_LOCAL_FILE"
```

This argv was recovered from the installed prefix's `conda-meta/history`.
The original package-link records locate its dedicated extraction cache under
`package-cache/`. That history does not record every original shell variable.
The portable helper explicitly sets `MAMBA_ROOT_PREFIX` and `CONDA_PKGS_DIRS`
to private children of the new work root, preventing dependence on a user's
existing Conda configuration/cache. Its `--offline`, `--no-rc` and complete
explicit list prevent a new dependency resolution.

The helper's prefix layout is `dependencies/`, `solver/`, `bootstrap/` and
`source/gkyl-<commit>/`. The author's recorded prefix basenames were
`build-9663/`, `clean-9663/`, `bootstrap/` and `source-9663/gkyl-<commit>/`.
The path substitution changes no configure flag or model source, but can
change embedded paths and binary hashes.

## Actual compiler environment and Waf commands

The observed configure process prepended `DEPS/bin` to `PATH` and set:

```sh
export LD_LIBRARY_PATH="$DEPS/lib"
export CC="$DEPS/bin/x86_64-conda-linux-gnu-gcc"
export CXX="$DEPS/bin/x86_64-conda-linux-gnu-g++"
export PATH="$DEPS/bin:$PATH"
```

`gcc -dumpfullversion` reports `12.3.0`; `gcc -dumpmachine` reports
`x86_64-conda-linux-gnu`. The observed `gcc -print-sysroot` resolves to
`DEPS/bin/../x86_64-conda-linux-gnu/sysroot`, supplied by the locked sysroot
2.17 package. No explicit `CONDA_BUILD_SYSROOT`, `CMAKE_SYSROOT`, `--sysroot`
override or native-CPU optimization flag was recorded. The portable helper
removes inherited compiler/linker/sysroot override variables before invoking
the recorded commands so a host's activated environment cannot silently add
different flags. This cleanup is reproduction scaffolding, not a model edit.

Run in the extracted Gkeyll source root. The actual configure/build/install
argv, with only absolute prefix paths replaced by `DEPS` and `SOLVER`, was:

```sh
"$DEPS/bin/python" waf configure \
 --prefix="$SOLVER" --disable-cuda --enable-mpi \
 --luajit-inc-dir="$DEPS/include/luajit-2.1" \
 --luajit-lib-dir="$DEPS/lib" \
 --luajit-share-dir="$DEPS/share/luajit-2.1" \
 --mpi-inc-dir="$DEPS/include" --mpi-lib-dir="$DEPS/lib" \
 --adios-inc-dir="$DEPS/include" --adios-lib-dir="$DEPS/lib" \
 --eigen-inc-dir="$DEPS/include/eigen3" \
 --extra-link-libs=blosc,z,bz2
"$DEPS/bin/python" waf build -j4
"$DEPS/bin/python" waf install
```

The actual Waf cache records `CFLAGS=['-O3','-Wall']` and
`CXXFLAGS=['-O3','-Wall','-std=c++17']`. CUDA alone was disabled with its
documented flag. No fluid equation, closure or numerical kernel was removed
or patched. The default SQLite support remained enabled. `-j4` means four
concurrent compile workers; it is not an OpenMP or MPI runtime setting.

The author built on a Ryzen 7 5800X host, but did not request `-march=native`
or assert a CPU-specific target. This is not an instruction-set compatibility
guarantee for every external Conda library. The lock includes `libgomp` as a
compiler-support dependency; the recorded Gkeyll flags contain no `-fopenmp`
and do not establish that Gkeyll uses OpenMP or BLAS.

## Source audit, installed files and runtime probes

[`gkeyll-clean9663-file-manifest.json`](gkeyll-clean9663-file-manifest.json)
contains SHA-256 values for exactly **1,998 original C/C++/header/Lua files**.
The author checked those bytes before and after the successful build: the
changed-original-source list was empty. The helper repeats those checks
around compilation/install and stops on any difference. New generated files
inside `build/` are not represented as changes to original model sources.

The observed successful compilation took 885.4594 seconds. This is a host
observation, not a promised build time. The codeload archive has no `.git`, so
Waf's `git describe` emitted a nonfatal message and the new executable's
embedded changeset string is blank. The source archive/commit and original
file audit establish its clean base; no changeset string is fabricated.

The recorded source extraction was outside a Git checkout. To keep this
metadata behavior when a caller chooses a work directory beneath a different
checkout, the portable wrapper removes inherited Git-directory overrides and
sets `GIT_CEILING_DIRECTORIES` to its work root. This prevents Waf from
mislabeling the extracted archive with an unrelated parent repository's commit.
It is metadata isolation added by the portable wrapper, not a model change.

The author executable SHA-256 is
`8207720b3fa7a1fee47041374b8e6935b7f51cb1792a9875e1d239922e1f32d7`.
The same file manifest records all observed installed solver files, 403
dependency-runtime files and seven actually linked system libraries/loader
files. Those are reference digests for the author's run. Prefix relocation,
build date, toolchain behavior and host libraries can change new binary
digests; this recipe does **not** promise bit-reproducible binaries across
hosts. Original source/archive identity is required. A new build's own
executable and dependency digests must be recorded for its experiment.

The recorded native runtime environment was:

```sh
export PATH="$DEPS/bin:$PATH"
export LD_LIBRARY_PATH="$SOLVER/lib64:$DEPS/lib"
export OPAL_PREFIX="$DEPS"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export OMPI_MCA_btl=self,vader,tcp
```

`OMP_NUM_THREADS` and `OPENBLAS_NUM_THREADS` constrain libraries that honor
those variables; they are not evidence that the native model uses those
threading APIs or that its CPU architecture was pinned. The OpenMPI transport
selection uses local/shared-memory/TCP communication. An optional InfiniBand
plugin was unavailable and ignored on WSL; no RDMA/UCX/GPU feature was enabled.

The helper's final probe executes only the native API factory:

```sh
"$SOLVER/bin/gkyl" -e \
 'local M=require("App.PlasmaOnCartGrid").Moments; assert(type(M)=="function"); local A=M(); assert(A.Species and A.App); print("CLEAN9663_MOMENTS_FACTORY_OK")'
```

It requires the success marker and does not instantiate or integrate a model.
The author separately ran native `gkyl INPUT init` on the unchanged full-grid
posted decks with 16 MPI ranks and the original 4-by-4 cuts. All five original
initial fluid/field arrays were bitwise identical to the archive. Matched
initial-state conformance has its separate public receipts. Initialization
agreement, API success or the existence of this recipe alone does not prove
completion of a dynamical control; final regular-frame-30 receipts and actual
comparison records are required.

## Logs and the portable wrapper's scope

The helper records exact argv, exit code, elapsed time and log hashes under
its new `logs/` directory, plus `recipe-state.json`. It refuses to overwrite
an existing installed solver or a prior log. Failed attempts remain available
for inspection; no automatic source repair, dependency substitution, model
change or restart is performed. The helper's own bytes must remain identical
between preparation and build. A transfer that exceeds its pinned byte count
is stopped, with its partial retained as untrusted evidence.

The original setup used transient orchestration for serial download/hash
checks, safe source/bootstrap extraction, offline Micromamba creation and
source-audited Waf commands. Private `finish_clean_build.py` then installed and
probed that build. The public helper makes those operations explicit without
private hardcoded paths. The separate private `stage_runtime.py` concerned the
rejected 2020 binary and is not the clean-source recipe: that binary had an
incompatible noncallable `Moments` API and was never used for a simulation.

During preparation of this public recipe the helper was checked in read-only
plan/cache-verification modes and with isolated guard fixtures. A second
prefix installation or full compile was not run while the authorized controls
were active. The recorded author build, source audit and startup probes are
documented in [`results/gkeyll-runtime-conformance.json`](../results/gkeyll-runtime-conformance.json).

## A fresh build's own manifest and startup gate

A new executable is expected to have its own digest. Do not replace the
author's reference hashes or reuse the author's init gate for a differing
runtime. [`qualify_clean_gkeyll.py`](../experiments/qualify_clean_gkeyll.py)
provides the concrete route below. Its default `plan` action is read-only.

`register` reads the completed portable builder's state and command/log
receipts, verifies the exact source archive and every original regular source
file (including build scripts), repeats the 1,998-file numerical/Lua audit,
and inventories this build's installed solver, dependency shared libraries and
actual linked system libraries. It writes its own `runtime-manifest.json`
only into a new caller directory. It does not borrow the author's installed
binary/library digests or claim bit-reproducible binaries.

`init` is a separate explicit action: it runs exactly four native init-only
jobs on 16 MPI ranks, with the unchanged 600/60 controls, in new copied case
directories. It performs no time integration. Each pre-launch/final receipt
binds the own-manifest SHA, executable, full input hashes, prepared-case
record, actual command and runtime environment; files are checked again after
each probe. A timeout/failure aborts the remaining probes and preserves the
attempt. Existing or partial destinations are refused.

`check` independently decodes the recorded BP files, reloads the serialized
metadata JSON, and verifies frame0/time0 only, all ten conserved components,
all eight field components, the positive original fluid label weights, and
strictly positive density/pressure without clipping. It compares both
unmatched originals with the archive and both matched cases with the exact
PIC target/weighted splits. A successful new gate includes the actual own
runtime-manifest SHA and executable digest. These are startup/initial-output
checks, not certification of nonlinear evolution or the historical dirty build.

### Prepare immutable scientific inputs in a new cache

Use a host Python environment with the packages in `requirements-bp.txt` for
the reader/checker, separate from the native dependency-prefix Python.
The complete original simulation ZIPs must already be downloaded and verified
against `data/full-archive-verification.json`; see their source URLs there.
Keep new files outside the repository, build prefixes and any active run tree.

The following example extracts only the five archived initial BP members into
a new cache and decodes them without updating any author provenance file:

```sh
export GKYL_DATA_ARCHIVES="$HOME/original-zenodo-zips"
export GKYL_QUAL_ROOT="$HOME/gkeyll-startup-qualification"
export GKYL_BASELINES="$GKYL_QUAL_ROOT/archived-initial"
python3 - <<'PY'
from pathlib import Path
import hashlib, json, os, zipfile
from experiments.read_gkeyll_bp import read_file
archive_dir = Path(os.environ['GKYL_DATA_ARCHIVES'])
destination = Path(os.environ['GKYL_BASELINES'])
members = json.loads(Path('data/provenance-revision.json').read_text())['selected_members']
pins = {p['filename']: p for p in json.loads(Path('data/full-archive-verification.json').read_text())['archives']}
def digest(path, algorithm):
    h = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()
for name in {m['archive'] for m in members}:
    archive, pin = archive_dir/name, pins[name]
    if (archive.stat().st_size != pin['bytes'] or digest(archive, 'sha256') != pin['computed_sha256']
            or digest(archive, 'md5') != pin['publisher_md5']):
        raise ValueError('Complete source archive differs: '+name)
destination.mkdir(parents=True, exist_ok=False)
for item in members:
    with zipfile.ZipFile(archive_dir/item['archive']) as archive:
        data = archive.read(item['archive_member'])
    if len(data) != item['uncompressed_bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        raise ValueError('Selected initial member differs')
    raw = destination/item['local_filename']
    with raw.open('xb') as output:
        output.write(data)
    read_file(raw, destination)
PY
```

Derive the aggregate target from the complete PIC ZIP into a new location:

```sh
python3 experiments/export_pic_moments.py \
 --archive "$GKYL_DATA_ARCHIVES/BgBr0point1-Beta0point1_PIC.zip" \
 --output-dir "$GKYL_QUAL_ROOT/pic-target" \
 --metadata "$GKYL_QUAL_ROOT/new-export-receipt.json"
python3 experiments/prepare_matched_control.py \
 --export-metadata data/derived/pic-moment-export.json \
 --aggregate-binary "$GKYL_QUAL_ROOT/pic-target/aggregate-pic-t0.f64" \
 --output-dir "$GKYL_QUAL_ROOT/jobs"
```

For this exact-data reproduction, the preparer intentionally uses the
immutable **canonical export metadata** while verifying that the newly
derived binary matches its size/SHA. A newly generated export receipt has
different timestamps/environment metadata and is retained separately. Using
it in the prepared-job identity is a different input record and will not match
the control runner's pinned preparation SHA. Do not edit those pins to accept
a changed target, scientific input or preparation record.

### Register, initialize, check and preflight the new runtime

After the portable build has completed, use Bash variables for its actual
paths. None of these paths refers to the author's active run:

```sh
GKYL_NEW_SOURCE="$GKYL_REPRO_WORK/source/gkyl-9663ea594e80f68eb305378e14512db390440e6b"
GKYL_NEW_ARGS=(--source-root "$GKYL_NEW_SOURCE"
 --source-archive "$GKYL_REPRO_CACHE/gkyl-9663ea594e80f68eb305378e14512db390440e6b.tar.gz"
 --solver-prefix "$GKYL_REPRO_WORK/solver"
 --dependency-prefix "$GKYL_REPRO_WORK/dependencies")
python3 experiments/qualify_clean_gkeyll.py plan
python3 experiments/qualify_clean_gkeyll.py register "${GKYL_NEW_ARGS[@]}" \
 --build-state "$GKYL_REPRO_WORK/recipe-state.json" \
 --output-root "$GKYL_QUAL_ROOT/registered"
python3 experiments/qualify_clean_gkeyll.py init "${GKYL_NEW_ARGS[@]}" \
 --runtime-manifest "$GKYL_QUAL_ROOT/registered/runtime-manifest.json" \
 --jobs-root "$GKYL_QUAL_ROOT/jobs" --output-root "$GKYL_QUAL_ROOT/probes"
python3 experiments/qualify_clean_gkeyll.py check "${GKYL_NEW_ARGS[@]}" \
 --runtime-manifest "$GKYL_QUAL_ROOT/registered/runtime-manifest.json" \
 --jobs-root "$GKYL_QUAL_ROOT/jobs" --probe-root "$GKYL_QUAL_ROOT/probes" \
 --baseline-directory "$GKYL_BASELINES" \
 --pic-export-directory "$GKYL_QUAL_ROOT/pic-target" \
 --output-root "$GKYL_QUAL_ROOT/initial-checks"
```

Successful `check` writes
`$GKYL_QUAL_ROOT/initial-checks/qualification-gate.json`. Only then use the
read-only preflight below, setting the actual checked-out code commit:

```sh
GKYL_NEW_CODE_PIN="$(git rev-parse HEAD)"
python3 experiments/qualify_clean_gkeyll.py preflight "${GKYL_NEW_ARGS[@]}" \
 --runtime-manifest "$GKYL_QUAL_ROOT/registered/runtime-manifest.json" \
 --jobs-root "$GKYL_QUAL_ROOT/jobs" \
 --qualification-gate "$GKYL_QUAL_ROOT/initial-checks/qualification-gate.json" \
 --controls-output-root "$GKYL_QUAL_ROOT/full-controls" \
 --research-code-revision "$GKYL_NEW_CODE_PIN"
```

The wrapper first enforces the new gate/manifest binding, then calls the
existing runner with its supported `--runtime-manifest`, `--matched-conformance`
and `--preflight-only` options. No guard is disabled and no control is launched
by this preflight. It prints the same full-control argv without the final
preflight flag for a separate, intentional dynamical experiment. The runner
will continue checking this experiment's exact runtime files between cases.

### Historical readback and validation performed here

The original qualification used the recorded transient launchers, not this
new portable wrapper. Their old receipts lack the wrapper's pre-launch
own-manifest binding. Therefore `--author-reference` registration accepts only
the exact complete published author runtime maps, and `readback` accepts only
the recorded historical init receipts. That mode writes
`historical-readback.json` with `all_data_checks_passed` as its data verdict,
but **always** sets `all_checks_passed=false` and
`fresh_startup_qualified=false`. It never writes a fresh qualification gate and
cannot qualify a differing executable/library set. No old receipt is rewritten
to add absent provenance fields.

During preparation of this wrapper, `plan`, read-only registration and
independent historical readback of all four retained init datasets were
tested in new caller directories. Full-grid data checks passed. Negative
runtime/binding/output-directory/frame fixtures were checked separately.
No new installation, build, MPI launch or model probe was performed in that
validation. The future `init` route is explicit and bounded; it was not run
against another newly compiled runtime during the active author controls.
