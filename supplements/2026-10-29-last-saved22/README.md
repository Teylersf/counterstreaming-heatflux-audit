# Post-acceptance diagnostic of the failed run's last saved state

Author: **Taylor Kalin**. Prepared after acceptance of
[PF-261029.000001](https://publish.fun/papers/PF-261029.000001).

This supplement adds one read-only check of regular frame 22 from the failed
matched two-fluid attempt. It leaves the frozen 26-page v1.2.0 manuscript,
its code pin `b47a51608726b80931fc607f0f44a02ab4bfbfdd`, and its primary
comparison/admissibility records unchanged. It supplies no regular-frame-30
measurement, full failed-run pressure history or new solver evolution.

At saved time **220.00011000001655**, all conserved values are finite and all
densities are positive. Pressure eigenvalues use units of `m_e n_0 c^2`.

| State | Minimum density | Minimum pressure eigenvalue | Non-PSD cells |
|---|---:|---:|---:|
| Population 1 | 0.0289773868495 | -0.00032116040544036 | 6 |
| Population 2 | 0.0289426446807 | 0.00008680127993524 | 0 |
| Aggregate | 0.9193319669815 | 0.00787487650651346 | 0 |

Population 1's worst cell is native zero-based `[x,y]=[176,157]`, at
`(x/d_e,y/d_e)=(-6.35,-16.25)`. Its coordinate pressure diagonals are positive,
but its xz principal minor is approximately `-2.20064532945e-6`. Therefore
this is a **last saved snapshot**, not an established last valid state.
The exact assertion time, failing transient cell/population and loss-producing
operator remain unknown. An admissible aggregate does not repair an
inadmissible component covariance.

[Primary diagnostic](diagnostic.json) and
[independent verification](independent-verification.json) bind the failed
native receipt, raw BP hashes before/after reading, actual scalar frame/time,
pressure formula, reader versions, counts and small worst-cell witnesses.
The independent computation uses direct conserved-moment centering without
importing the primary analysis functions. Full raw native outputs remain on
the author's computer; this compact report is not independent human review
or external reproduction.

Primary JSON SHA-256:
`904142e46b066efca208b1f3fa8f2df2852e0c599291b2eac9baecbd9af28723`.
Independent JSON SHA-256:
`370e5160293417a45b82467a9d465df518e03f3ccc278da237d60571645f5d5c`.

For the one-fluid runs, the first observed non-PSD saved frame is 22 in
both cases. The matched run has more invalid saved snapshots and a more
negative minimum; those observations establish greater observed frequency
and severity, not an earlier first loss time.

The [descriptively named stability-spectrum image](stability-spectrum-verified.png)
is an exact copy of canonical Figure 6. All six journal-stored figure pixel
arrays and captions match the canonical content, as recorded in the
[round-3 verification](../../submissions/publishfun-image-verification-round3.json).
The journal's reused `figure-2.png` storage basename does not identify wrong
plotted content. This alias does not claim to rename the journal's stored URL.
