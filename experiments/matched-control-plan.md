# Planned aggregate-matched fluid controls

Prepared before control-run execution on 28 October 2026, Pacific time.
This protocol is a plan, not evidence that a solver has run or reproduced the
historical calculation. Results and executable provenance will be recorded
separately.

## Cases and intervention

Run the one- and two-electron-fluid models with their posted initialization,
then run both with a measured aggregate PIC initialization. All four cases
must use the same conforming executable and numerical model settings.

The matched ten-component vector contains density, three ordinary-velocity
momentum densities and six uncentered velocity second moments. It is read
from the complete, checksum-verified PIC archive. No smoothing, pressure
clamping or fitted drift correction is allowed. The exporter must verify
grid locations, snapshot time, positive density and positive-definite pressure.

For two fluids retain the posted smooth density-label weights `w1(y)` and
`w2=1-w1`, each bounded below by 0.03. Multiply the entire aggregate vector
by each weight. This preserves aggregate density, momentum and pressure,
with common velocity and `P_s=w_s P`. It does **not** match the PIC's sharp
population labels, full distributions or intrinsic third moments.

The intervention changes the full initial velocity/pressure fields and imports
their sampled spatial variations. A later difference cannot be attributed to
the current deficit, proper-momentum convention or thermal spread alone.

## Solver conformance and time control

Check the original Lua API and closure/source semantics before selecting an
executable. The archived dirty Gkeyll identifier is not a uniquely recoverable
executable. A public legacy binary or clean source base must be identified
precisely, and its unmatched result compared with the archive. Compatibility
does not establish identity with the original build.

Before long runs, require a full-grid startup, finite states, positive density
and pressure, and saved initial arrays that match the intended conserved
vectors and original fields. Record timestep behavior and measured runtime.

Preserve posted grid, boundaries, 4-by-4 decomposition, CFL, limiters,
electromagnetic parameters, source closure, `tEnd=600` and `nFrame=60`.
The after-step output trigger does not force exact output times. Use the
native stop mechanism after regular frame 30; distinguish a forced final
frame from that regular frame. Report every actual snapshot time.

The archived one-fluid frame 30 is at `300.0001500000136`; the two-fluid frame
is at `300.0499847996274`. Do not describe every comparison as being at exactly
the same time. Preserve and discuss any new run's output-time offset.

## Prespecified measurements

Report current `Jz`, total density, `Pxx` and `Pzz` on the full grid, with
relative L2 errors against the archived PIC state and paired differences
between matched and unmatched cases. Report x-averaged profiles separately;
a profile norm is not a two-dimensional field norm. Compare the unmatched
solver results with the original fluid archive before interpreting the control.

For two fluids reconstruct the counter-streaming contribution `qCSxxx` from
the conserved moments and compare it with the PIC central third moment.
Label it as that reconstructed contribution. The finite isotropization model
specifies a divergence and does not identify a unique complete heat-flux
tensor. One-fluid `qCS=0` is a definition, not a measurement of its full modeled
heat flux. Never divide a paired relative difference by a zero norm.

Publish all case outcomes, timings and conformance failures. If compatibility
or initial-state checks fail, do not relabel a substitute toy model as a
Gkeyll rerun. No nonlinear-effect bound follows from the initial mismatch
alone, and no new reconnection-rate claim is prespecified.
