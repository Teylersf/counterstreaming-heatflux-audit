"""Reanalyze archived t=0 moments; this does not run PIC or Gkeyll."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def _read(raw: Path, filename: str, quantity: str, offset: tuple[float, float]) -> np.ndarray:
    with h5py.File(raw / filename, 'r') as f:
        assert float(f.attrs['TIME'][0]) == 0.0
        assert int(f.attrs['ITER'][0]) == 0
        assert np.array_equal(f.attrs['OFFSET_X'], offset), (filename, f.attrs['OFFSET_X'])
        assert np.array_equal(f['AXIS/AXIS1'][:], [-24.0, 24.0])
        assert np.array_equal(f['AXIS/AXIS2'][:], [-32.0, 32.0])
        values = np.asarray(f[quantity], dtype=np.float64)
        assert values.shape == (640, 480)
        assert np.isfinite(values).all()
    return values


def analyze_profiles(raw_dir: Path | None = None) -> dict[str, np.ndarray]:
    raw = Path(raw_dir) if raw_dir is not None else DATA / 'raw'
    manifest = json.loads((DATA / 'provenance.json').read_text(encoding='utf-8'))
    for entry in manifest['selected_members']:
        assert hashlib.sha256((raw / entry['filename']).read_bytes()).hexdigest() == entry['sha256']
    def moment(species: int, quantity: str) -> np.ndarray:
        return _read(raw, f'{quantity}-electrons{species}-000000.h5', quantity, (.5, .5))
    n1, n2 = -moment(1, 'charge'), -moment(2, 'charge')
    n = n1 + n2
    assert np.min(n1) >= 0 and np.min(n2) >= 0
    assert np.max(np.abs(n - 1.0)) < 2e-8
    vx = (n1 * moment(1, 'vfl1') + n2 * moment(2, 'vfl1')) / n
    vz = (n1 * moment(1, 'vfl3') + n2 * moment(2, 'vfl3')) / n
    pxx = moment(1, 'v1v1') + moment(2, 'v1v1') - n * vx**2
    pzz = moment(1, 'v3v3') + moment(2, 'v3v3') - n * vz**2
    assert np.min(pxx) > -1e-7 and np.min(pzz) > -1e-7
    bx = _read(raw, 'b1-000000.h5', 'b1', (.5, 1.0))
    by = _read(raw, 'b2-000000.h5', 'b2', (1.0, .5))
    _read(raw, 'b3-000000.h5', 'b3', (1.0, 1.0))
    dx, dy = .1, .1
    dbydx = (by - np.roll(by, 1, axis=1)) / dx
    dbxdy = (bx - np.roll(bx, 1, axis=0)) / dy
    required_current = dbydx - dbxdy
    moment_current = -n * vz
    x = -24 + (np.arange(480) + .5) * dx
    y = -32 + (np.arange(640) + .5) * dy
    xx, yy = np.meshgrid(x, y)
    b1_exact = .5 * (np.tanh(yy + 16) - np.tanh(yy - 16) - 1)
    b1_y = .5 * (1 / np.cosh(yy + 16)**2 - 1 / np.cosh(yy - 16)**2)
    b3_exact = np.sqrt(.5**2 + .05**2 - b1_exact**2)
    prescribed_vx = b1_exact * b1_y / b3_exact
    prescribed_vz = (b1_y - .005 * (2 * np.pi / 48) * np.cos(2 * np.pi * xx / 48)
                     + 2 * (xx + 12) / 36 * (.005 / 4) * np.exp(-((xx + 12) / 6)**2))
    cold_vz = prescribed_vz / np.sqrt(1 + prescribed_vx**2 + prescribed_vz**2)
    profiles = {
        'raw_y': y, 'paper_y': y + 32, 'pic_density': n.mean(axis=1),
        'pic_vz': vz.mean(axis=1), 'pic_jz': moment_current.mean(axis=1),
        'staggered_required_jz': required_current.mean(axis=1),
        'fluid_prescribed_vz': prescribed_vz.mean(axis=1),
        'cold_converted_vz': cold_vz.mean(axis=1),
        'pic_pxx': pxx.mean(axis=1), 'pic_pzz': pzz.mean(axis=1),
        'fluid_prescribed_pressure': np.full(640, .111803**2),
        'pic_pxx_over_fluid': pxx.mean(axis=1) / .111803**2,
        'pic_pzz_over_fluid': pzz.mean(axis=1) / .111803**2,
        'ampere_residual': (required_current - moment_current).mean(axis=1),
    }
    assert np.max(np.abs(dbydx.mean(axis=1))) < 1e-15
    return profiles


def write_profiles(profiles: dict[str, np.ndarray], output: Path | None = None) -> Path:
    output = Path(output) if output is not None else DATA / 'derived/initial-profiles.csv'
    output.parent.mkdir(parents=True, exist_ok=True)
    names = list(profiles)
    with output.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(names)
        writer.writerows(zip(*(profiles[name] for name in names)))
    return output


def run_checks(raw_dir: Path | None = None) -> dict:
    p = analyze_profiles(raw_dir)
    current, pressure = [], []
    for j in (159, 160, 479, 480):
        current.append({'row': j, 'raw_y': float(p['raw_y'][j]), 'paper_y': float(p['paper_y'][j]),
                        'PIC_moment_current': float(p['pic_jz'][j]),
                        'required_staggered_current': float(p['staggered_required_jz'][j]),
                        'relative_current_deficit': float(1 - p['pic_jz'][j] / p['staggered_required_jz'][j]),
                        'PIC_velocity': float(p['pic_vz'][j]),
                        'fluid_prescribed_velocity': float(p['fluid_prescribed_vz'][j]),
                        'relative_velocity_deficit': float(1 - p['pic_vz'][j] / p['fluid_prescribed_vz'][j]),
                        'cold_converted_velocity': float(p['cold_converted_vz'][j])})
        pressure.append({'row': j, 'paper_y': float(p['paper_y'][j]),
                         'PIC_Pxx': float(p['pic_pxx'][j]), 'PIC_Pzz': float(p['pic_pzz'][j]),
                         'fluid_prescribed_pressure': float(p['fluid_prescribed_pressure'][j]),
                         'Pxx_ratio': float(p['pic_pxx_over_fluid'][j]),
                         'Pzz_ratio': float(p['pic_pzz_over_fluid'][j])})
    assert np.allclose([r['PIC_moment_current'] for r in current[:2]],
                       [-.44098722932885703, -.4408766944657836], rtol=0, atol=1e-10)
    assert all(.11 < r['relative_current_deficit'] < .12 for r in current)
    assert np.allclose([r['PIC_Pzz'] for r in pressure[:2]],
                       [.007696529306960079, .007693028300607572], rtol=0, atol=1e-10)
    assert all(.60 < r['Pzz_ratio'] < .63 for r in pressure)
    return {
        'initial_current': {'passed': True, 'rows': current,
                            'definition': 'Jz_moment=-(n1<vz>1+n2<vz>2); curl uses recorded Yee offsets',
                            'native_charge_conserving_OSIRIS_current_used': False,
                            'new_PIC_or_Gkeyll_run': False},
        'initial_pressure': {'passed': True, 'rows': pressure,
                             'definition': 'Pii=sum_s integral f_s vi^2 d^3v - n*<vi>^2, me=1',
                             'fluid_comparison': 'prescribed input-deck thermal pressure, not a reloaded fluid snapshot'},
        'provenance': {'record': 'https://zenodo.org/records/21114117',
                       'snapshots': 't=0 only', 'members': 13,
                       'member_CRC32_and_SHA256_verified': True,
                       'full_archive_MD5_verified': False,
                       'numpy': np.__version__, 'h5py': h5py.__version__},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results/data-checks.json')
    parser.add_argument('--profiles', type=Path, default=DATA / 'derived/initial-profiles.csv')
    args = parser.parse_args()
    results = run_checks()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8', newline='\n')
    profiles = write_profiles(analyze_profiles(), args.profiles)
    print(json.dumps({'groups': ['initial_current', 'initial_pressure'], 'all_checks_passed': True,
                      'output': str(args.output), 'profiles': str(profiles)}))


if __name__ == '__main__':
    main()
