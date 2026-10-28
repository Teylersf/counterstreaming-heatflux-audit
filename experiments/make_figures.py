"""Create two analysis figures from archived profiles and the explicit model."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from closure_checks import growth, linear_matrix

ROOT = Path(__file__).resolve().parents[1]


def save(figure, name: str, title: str) -> list[Path]:
    out = ROOT / 'figures'
    out.mkdir(exist_ok=True)
    pdf, png = out / (name + '.pdf'), out / (name + '.png')
    figure.savefig(pdf, metadata={'Author': 'Taylor Kalin', 'Title': title,
                                 'CreationDate': None, 'ModDate': None})
    figure.savefig(png, dpi=220, metadata={'Author': 'Taylor Kalin', 'Title': title})
    plt.close(figure)
    return [pdf, png]


def main() -> None:
    plt.rcParams.update({'font.size': 8, 'axes.titlesize': 9,
                         'axes.labelsize': 8.5, 'legend.fontsize': 7,
                         'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42})
    profiles = np.genfromtxt(ROOT / 'data/derived/initial-profiles.csv',
                             delimiter=',', names=True)
    y = profiles['paper_y']
    mask = (y >= 10) & (y <= 22)
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.7, 3.15), layout='constrained')
    left.plot(y[mask], -profiles['staggered_required_jz'][mask],
              color='#222222', linewidth=1.7, label='Magnetic curl')
    left.plot(y[mask], profiles['fluid_prescribed_vz'][mask],
              color='#D55E00', linewidth=1.0, linestyle='--', label='Fluid input')
    left.plot(y[mask], -profiles['pic_jz'][mask],
              color='#0072B2', linewidth=1.6, label='PIC moments')
    left.set(title='(a) Initial current', xlabel=r'Paper coordinate $Y/d_e$',
             ylabel=r'$-J_z/(e n_0 c)$', xlim=(10, 22), ylim=(-.015, .54))
    left.legend(loc='upper left', frameon=False)
    right.plot(y[mask], profiles['pic_pxx_over_fluid'][mask],
               color='#009E73', linewidth=1.6, label=r'Archived PIC $P_{xx}$')
    right.plot(y[mask], profiles['pic_pzz_over_fluid'][mask],
               color='#0072B2', linewidth=1.6, label=r'Archived PIC $P_{zz}$')
    right.axhline(1, color='#222222', linestyle='--', linewidth=1,
                   label='Fluid pressure prescription')
    right.set(title='(b) Initial thermal pressure', xlabel=r'Paper coordinate $Y/d_e$',
              ylabel=r'$P_{ii}/p_{\mathrm{fl}}$', xlim=(10, 22), ylim=(.5, 1.08))
    right.legend(loc='lower left', frameon=False)
    for axis in (left, right):
        axis.axvline(16, color='#999999', linewidth=.6, linestyle=':')
        axis.grid(alpha=.18)
    paths = save(fig, 'initial-state', 'Archived initial moment and fluid-prescription comparison')

    speed, wave, rate = 1.2, .2, 1 / (40 * math.sqrt(5))
    ideal = np.linalg.eigvals(linear_matrix(speed, wave, 0))
    finite = np.linalg.eigvals(linear_matrix(speed, wave, rate))
    ideal = ideal[np.abs(ideal) > 1e-9]
    finite = finite[np.abs(finite) > 1e-9]
    rates = np.linspace(0, .03, 181)
    growths = np.array([growth(speed, wave, float(value)) for value in rates])
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.7, 3.15), layout='constrained')
    left.axvline(0, color='#777777', linewidth=.8)
    left.scatter(ideal.real, ideal.imag, marker='x', s=25, color='#777777',
                  linewidths=1.2, label=r'Ideal $\nu=0$')
    left.scatter(finite.real, finite.imag, marker='o', s=24, facecolors='none',
                  edgecolors='#D55E00', linewidths=1.3, label=r'Finite $\nu=\nu_0$')
    limit = max(abs(float(finite.real.min())), float(finite.real.max())) * 1.28
    left.set(title='(a) Longitudinal fluid spectra', xlabel=r'$\operatorname{Re}\lambda/\omega_{pe}$',
             ylabel=r'$\operatorname{Im}\lambda/\omega_{pe}$', xlim=(-limit, limit))
    left.legend(loc='upper right', frameon=False)
    right.plot(rates, growths, color='#D55E00', linewidth=1.7)
    reference_growth = growth(speed, wave, rate)
    right.scatter([rate], [reference_growth], color='#D55E00', s=21, zorder=3)
    right.axvline(rate, color='#777777', linestyle='--', linewidth=.8,
                   label=r'Reference rate $\nu_0$')
    right.axhline(0, color='#222222', linewidth=.8)
    right.set(title='(b) Growth versus relaxation', xlabel=r'$\nu/\omega_{pe}$',
              ylabel=r'$\max\operatorname{Re}\lambda/\omega_{pe}$',
              xlim=(0, .0305), ylim=(-.0005, float(growths.max()) * 1.18))
    right.legend(loc='lower right', frameon=False)
    for axis in (left, right):
        axis.grid(alpha=.18)
    paths += save(fig, 'stability', 'Finite-relaxation modes for a longitudinally stable kinetic reference')
    manifest = {
        'author': 'Taylor Kalin', 'numpy': np.__version__,
        'matplotlib': matplotlib.__version__,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'input_profiles_sha256': hashlib.sha256((ROOT / 'data/derived/initial-profiles.csv').read_bytes()).hexdigest(),
        'initial_state_scope': 'Derived from archived t=0 moments and supplied input functions; no new simulation.',
        'stability_scope': 'Homogeneous nonrelativistic longitudinal electrostatic benchmark; not a reconnection run or a claim of global electromagnetic stability.',
        'figures': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                     'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    (ROOT / 'results/figure-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'figures_created': len(paths), 'files': [p.relative_to(ROOT).as_posix() for p in paths]}))


if __name__ == '__main__':
    main()
