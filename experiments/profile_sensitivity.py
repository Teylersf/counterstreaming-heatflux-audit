"""Full archived PIC profiles and deterministic diagnostic sensitivities.

No simulation is run. Spatial scatter and block means are descriptive; they
are not confidence intervals for independent particles or independent cells.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from data_checks import ROOT, _read, analyze_profiles


def run() -> dict:
    profiles = analyze_profiles()
    raw = ROOT / 'data/raw'
    def m(s, q):
        return _read(raw, f'{q}-electrons{s}-000000.h5', q, (.5, .5))
    n1, n2 = -m(1, 'charge'), -m(2, 'charge')
    n = n1 + n2
    vx = (n1*m(1, 'vfl1') + n2*m(2, 'vfl1'))/n
    vz = (n1*m(1, 'vfl3') + n2*m(2, 'vfl3'))/n
    jm = -n*vz
    bx = _read(raw, 'b1-000000.h5', 'b1', (.5, 1.0))
    by = _read(raw, 'b2-000000.h5', 'b2', (1.0, .5))
    # Correct Yee curl is the primary comparison. The second comparison is a
    # deliberately collocated, smoothed second-order representation, not a
    # competing interpretation of the recorded offsets.
    bxc = .5*(bx + np.roll(bx, 1, axis=0))
    byc = .5*(by + np.roll(by, 1, axis=1))
    jc = ((np.roll(byc, -1, axis=1)-np.roll(byc, 1, axis=1))
          -(np.roll(bxc, -1, axis=0)-np.roll(bxc, 1, axis=0)))/.2
    current = profiles['pic_jz']
    yee = profiles['staggered_required_jz']
    collocated = jc.mean(axis=1)
    prescribed = -profiles['fluid_prescribed_vz']
    y = profiles['paper_y']
    pressure = {}
    for label, vel, quantity in [('xx', vx, 'v1v1'), ('zz', vz, 'v3v3')]:
        raw2 = m(1, quantity) + m(2, quantity)
        local = (raw2-n*vel**2).mean(axis=1)
        global_center = raw2.mean(axis=1) - (n*vel).mean(axis=1)**2/n.mean(axis=1)
        flow_variance = (n*(vel-(n*vel).mean(axis=1)[:, None]/n.mean(axis=1)[:, None])**2).mean(axis=1)
        assert np.allclose(global_center-local, flow_variance, atol=1e-15, rtol=1e-10)
        pressure[label] = {'local': local, 'global': global_center, 'flow_variance': flow_variance}
    region_masks = {
        'full_domain': np.ones(640, dtype=bool),
        'lower_sheet_Y14_to18': abs(y-16) <= 2,
        'upper_sheet_Y46_to50': abs(y-48) <= 2,
        'current_carrying_abs_Yee_ge0.05': abs(yee) >= .05,
    }
    regions = {}
    for name, mask in region_masks.items():
        reference_norm = np.linalg.norm(yee[mask])
        regions[name] = {
            'rows': int(mask.sum()),
            'PIC_minus_Yee_relative_L2': float(np.linalg.norm(current[mask]-yee[mask])/reference_norm),
            'collocated_minus_Yee_relative_L2': float(np.linalg.norm(collocated[mask]-yee[mask])/reference_norm),
            'prescription_minus_Yee_relative_L2': float(np.linalg.norm(prescribed[mask]-yee[mask])/reference_norm),
            'max_absolute_PIC_minus_Yee': float(np.max(abs(current[mask]-yee[mask]))),
        }
    rows = []
    for j in (159, 160, 479, 480):
        blocks = jm[j].reshape(8, 60).mean(axis=1)
        rows.append({
            'row': j, 'Y': float(y[j]),
            'moment_current': float(current[j]), 'Yee_current': float(yee[j]),
            'collocated_current': float(collocated[j]),
            'current_deficit_Yee': float(1-current[j]/yee[j]),
            'current_deficit_collocated': float(1-current[j]/collocated[j]),
            'current_deficit_prescription': float(1-current[j]/prescribed[j]),
            'per_x_current_standard_deviation': float(jm[j].std()),
            'eight_spatial_block_mean_currents': blocks.tolist(),
            'block_mean_range': [float(blocks.min()), float(blocks.max())],
            'Pxx_center_before_average': float(pressure['xx']['local'][j]),
            'Pxx_average_before_center': float(pressure['xx']['global'][j]),
            'Pzz_center_before_average': float(pressure['zz']['local'][j]),
            'Pzz_average_before_center': float(pressure['zz']['global'][j]),
        })
    out = {
        'scope': 'Reanalysis of the same archived t=0 PIC files, not an independent simulation or independent validation of custom diagnostics.',
        'grid_shape': [640, 480], 'TIME': 0.0, 'ITER': 0,
        'norm_definition': 'L2 norms of the selected rows of x-averaged one-dimensional profiles, not norms of the full two-dimensional fields.',
        'scatter_scope': 'Spatial variations and eight contiguous block means are descriptive. No independence assumption, standard-error confidence interval, or new sampling error bar is claimed.',
        'pressure_scope': 'The source definition centers each local cell before x averaging. Reversing the order adds resolved bulk-flow variance and changes the diagnostic.',
        'regions': regions, 'adjacent_sheet_rows': rows,
    }
    target = ROOT / 'results/profile-sensitivity.json'
    target.write_text(json.dumps(out, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    columns = {'paper_y': y, 'PIC_Jz': current, 'Yee_Jz': yee,
               'collocated_Jz': collocated, 'prescribed_Jz': prescribed,
               'Pxx_local_center': pressure['xx']['local'], 'Pxx_global_center': pressure['xx']['global'],
               'Pzz_local_center': pressure['zz']['local'], 'Pzz_global_center': pressure['zz']['global']}
    with (ROOT/'data/derived/profile-sensitivity.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(columns); w.writerows(zip(*columns.values()))
    plt.rcParams.update({'font.size': 10, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.4), constrained_layout=True)
    axes[0].plot(y, yee, label='Staggered magnetic curl', color='black', lw=1.7)
    axes[0].plot(y, current, label='PIC ordinary-velocity moment', color='#1864ab')
    axes[0].set_ylabel('Normalized current $J_z$'); axes[0].legend(fontsize=8)
    pref = .111803**2
    axes[1].plot(y, pressure['xx']['local']/pref, label='$P_{xx}/p_{input}$', color='#1864ab')
    axes[1].plot(y, pressure['zz']['local']/pref, label='$P_{zz}/p_{input}$', color='#c92a2a')
    axes[1].axhline(1, color='black', ls='--', lw=.8); axes[1].set_ylabel('Ratio to fluid pressure prescription'); axes[1].legend(fontsize=8)
    for ax in axes:
        ax.set_xlabel('Paper coordinate $Y/d_e$'); ax.set_xlim(0, 64); ax.grid(alpha=.15)
        ax.axvline(16, color='grey', ls=':', lw=.6); ax.axvline(48, color='grey', ls=':', lw=.6)
    fig.savefig(ROOT/'figures/profile-sensitivity.pdf', metadata={'Author': 'Taylor Kalin', 'CreationDate': None})
    fig.savefig(ROOT/'figures/profile-sensitivity.png', dpi=150, metadata={'Author': 'Taylor Kalin'})
    plt.close(fig)
    assert all(np.isfinite(v).all() for v in columns.values())
    return out


if __name__ == '__main__':
    result = run()
    print(json.dumps({'regions': result['regions'], 'rows': result['adjacent_sheet_rows']}, allow_nan=False))
