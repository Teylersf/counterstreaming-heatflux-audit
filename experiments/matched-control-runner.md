# Portable preparation of the planned controls

This is preparation code, not a result or evidence that a solver has run.
Follow `matched-control-plan.md`; retain all failures and executable provenance.

After the complete PIC archive is verified and `export_pic_moments.py` has
produced its metadata and `aggregate-pic-t0.f64`, prepare the four jobs with:

```sh
python experiments/prepare_matched_control.py \
  --export-metadata PATH/TO/pic-moment-export.json \
  --aggregate-binary PATH/TO/aggregate-pic-t0.f64 \
  --output-dir PATH/TO/control-jobs
```

The preparer verifies original-deck hashes, exported metadata, binary size,
shape, component order and SHA-256. It copies the posted decks byte for byte.
It does not invoke an executable or install software. Existing prepared inputs
with different content cause an error rather than being overwritten.

For matched cases, `matched_initializer.lua` intercepts only the next
`Moments()` call, then wraps its species initializer callbacks. Its App proxy
validates the original grid, decomposition, periodicity, method and time/output
controls without changing them. The original field, equations, source closures,
and all other controls remain in the unchanged posted input.

The state has float64 little-endian layout `[y,x,component]`, component fastest,
with 640 by 480 cells and ten components. A Lua string keeps the complete
24,576,000-byte file alive behind its FFI pointer. Indices wrap periodically
because the order-zero projection also initializes ghost cells. Missing or
malformed input is fatal; there is no analytic fallback, smoothing or clamping.

For two fluids each original init callback's first return supplies its positive
smooth label weight, since the hash-pinned input has `n0=mass=1`. The entire
aggregate vector is multiplied by that weight. The original formulas are
mathematically `w1=.03+.47*(tanh(y+16)-tanh(y-16))`, `w2=1-w1`; their written
floating-point evaluations can differ from exact recombination at roundoff.
This is aggregate matching, not PIC species-tag or third-moment matching.

Do not launch long jobs from this preparation step. First verify the runtime
on the unchanged decks, report measured short-run cost, and read back saved
initial data. The initial-output check must establish the full aggregate
ten-component target and all original field components within numerical
roundoff, with finite states and positive density/pressure. Matched results
must not be interpreted as isolating a current correction or noise mechanism.

Use the same identified executable and runtime configuration for all cases.
Run with the posted 4-by-4 decomposition (16 MPI ranks). Retain `tEnd=600` and
`nFrame=60`. Request a native `<output-prefix>.stop` only after regular frame 30
has been completed; retain that regular frame and distinguish any forced final
snapshot. Record actual times and baseline error against each archived fluid
reference. The historical plus-marked 2023 build remains unidentified even if
a public executable accepts the input and reproduces initial arrays.
