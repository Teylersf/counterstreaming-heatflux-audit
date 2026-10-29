"""Export aggregate PIC moments from a fully verified local archive; no network.

No solver is run. The ten-component binary is little-endian float64, C order
[y, x, component]: components fastest, then x, then y. Electron mass is one.
The optional smooth two-fluid split matches aggregate moments, NOT PIC tags.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
import zlib

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ('rho', 'rho_ux', 'rho_uy', 'rho_uz',
              'Mxx', 'Mxy', 'Mxz', 'Myy', 'Myz', 'Mzz')
SECOND = ('v1v1', 'v1v2', 'v1v3', 'v2v2', 'v2v3', 'v3v3')
QUANTITIES = ('charge', 'vfl1', 'vfl2', 'vfl3') + SECOND
SHAPE = (640, 480)
BOUNDS = ((-24.0, 24.0), (-32.0, 32.0))
FLUID2_DECK_SHA256 = 'f9cc244a6e52522d03aa1a127a1f79ff35506b0f9b98b1abe8973a3c6ff4bf69'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def digest_file(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def discover(inventory):
    """Discover exact member paths and filename frame tokens in saved inventory."""
    candidates = [a for a in inventory['archives'] if a['filename'].endswith('_PIC.zip')]
    require(len(candidates) == 1, 'Expected one PIC archive in inventory')
    archive = candidates[0]
    frames = {}
    for entry in archive['central_directory']['entries']:
        path = PurePosixPath(entry['name'])
        if '__MACOSX' in path.parts or path.name.startswith('._'):
            continue
        match = re.fullmatch(r'(.+)-electrons([12])-(\d+)\.h5', path.name)
        if not match:
            continue
        quantity, species, frame = match.groups()
        if quantity not in QUANTITIES + ('v1v1v1',):
            continue
        expected_parent = ('DENSITY' if quantity == 'charge' else 'UDIST',
                           f'electrons{species}', quantity)
        require(tuple(path.parts[-4:-1]) == expected_parent,
                f'Unexpected diagnostic directory: {path}')
        key = (int(species), quantity)
        target = frames.setdefault(frame, {})
        require(key not in target, f'Duplicate diagnostic for frame {frame}: {key}')
        target[key] = entry
    required = {(s, q) for s in (1, 2) for q in QUANTITIES}
    complete = {k: v for k, v in frames.items() if required <= v.keys()}
    require(bool(complete), 'No complete twenty-member frame in saved inventory')
    return archive, complete


def pinned_members(inventory, initial_provenance, verification):
    pins = {}
    for source in (inventory.get('selected_members', []),
                   initial_provenance.get('selected_members', []),
                   verification.get('selected_member_bindings', [])):
        for item in source:
            name = item.get('archive_member', item.get('exact_member_name'))
            if name and item.get('sha256'):
                require(name not in pins or pins[name] == item['sha256'],
                        f'Conflicting pinned SHA-256 for {name}')
                pins[name] = item['sha256']
    return pins


def verify_archive(path, inventory_archive, receipt):
    require(path.name == inventory_archive['filename'], 'Use the completed ZIP, not a .part file')
    rows = [a for a in receipt['archives'] if a['filename'] == path.name]
    require(len(rows) == 1, 'No unique full-archive verification receipt')
    row = rows[0]
    require(row.get('full_archive_checksum_verified') is True and
            row.get('size_and_publisher_MD5_match') is True,
            'PIC full-archive verification is not complete')
    require(path.stat().st_size == int(row['bytes']) == int(inventory_archive['bytes']),
            'Full archive byte count mismatch')
    declared = inventory_archive['publisher_declared_checksum'].split(':')[-1].lower()
    publisher = row['publisher_md5'].split(':')[-1].lower()
    require(publisher == declared, 'Receipt publisher MD5 disagrees with inventory')
    md5, sha = digest_file(path)
    require(md5 == declared == row['computed_md5'].split(':')[-1].lower(),
            'Local full archive MD5 mismatch')
    require(sha == row['computed_sha256'].lower(), 'Local full archive SHA-256 mismatch')
    return {'filename': path.name, 'bytes': path.stat().st_size,
            'publisher_md5': declared, 'computed_md5': md5,
            'computed_sha256': sha, 'full_archive_checksum_verified': True}


def verify_directory(zip_file, archive):
    listed = archive['central_directory']['entries']
    actual = zip_file.infolist()
    require(len(actual) == len(listed), 'ZIP entry count differs from saved inventory')
    require(len({x.filename for x in actual}) == len(actual), 'Duplicate ZIP member names')
    lookup = {x.filename: x for x in actual}
    for item in listed:
        info = lookup.get(item['name'])
        require(info is not None, f'Missing ZIP entry: {item["name"]}')
        require(info.file_size == item['uncompressed_bytes'] and
                info.compress_size == item['compressed_bytes'] and
                info.header_offset == item['local_offset'] and
                f'{info.CRC:08x}' == item['crc32'].lower() and
                info.compress_type == item['method'],
                f'ZIP directory binding mismatch: {info.filename}')
    return lookup


def scalar_attribute(attrs, name):
    value = np.asarray(attrs[name]).reshape(-1)
    require(value.size == 1, f'Expected scalar attribute {name}')
    return value.item()


def read_member(zip_file, info, quantity, pins):
    payload = zip_file.read(info)  # zipfile also verifies the complete member CRC.
    digest = sha_bytes(payload)
    require(len(payload) == info.file_size and zlib.crc32(payload) == info.CRC,
            f'Member CRC/length mismatch: {info.filename}')
    if info.filename in pins:
        require(digest == pins[info.filename], f'Pinned member SHA mismatch: {info.filename}')
    with h5py.File(io.BytesIO(payload), 'r') as source:
        require(quantity in source, f'Missing dataset {quantity}: {info.filename}')
        array = np.asarray(source[quantity], dtype=np.float64)
        require(array.shape == SHAPE and np.isfinite(array).all(),
                f'Invalid dataset shape/values: {info.filename}')
        require(np.array_equal(source.attrs['OFFSET_X'], [.5, .5]),
                f'Noncentered moment offset: {info.filename}')
        for axis, limits in enumerate(BOUNDS, 1):
            require(np.array_equal(source[f'AXIS/AXIS{axis}'][:], limits),
                    f'Axis bounds differ: {info.filename}')
        time = float(scalar_attribute(source.attrs, 'TIME'))
        iteration_value = scalar_attribute(source.attrs, 'ITER')
        iteration = int(iteration_value)
        require(np.isfinite(time) and iteration == iteration_value and iteration >= 0,
                f'Invalid snapshot metadata: {info.filename}')
    record = {'exact_member_name': info.filename, 'quantity': quantity,
              'uncompressed_bytes': info.file_size, 'compressed_bytes': info.compress_size,
              'crc32': f'{info.CRC:08x}', 'sha256': digest,
              'matched_preexisting_SHA256_pin': info.filename in pins,
              'TIME': time, 'ITER': iteration, 'OFFSET_X': [.5, .5],
              'shape_y_x': list(SHAPE)}
    return array, record


def pressure_tensor(state):
    n, momentum = state[..., 0], state[..., 1:4]
    pressure = np.empty(SHAPE + (3, 3), dtype=np.float64)
    for component, (i, j) in enumerate(((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2)), 4):
        value = state[..., component] - momentum[..., i] * momentum[..., j] / n
        pressure[..., i, j] = pressure[..., j, i] = value
    return pressure


def load_frame(zip_file, lookup, entries, frame, pins, expected_time, initial=False):
    values, records = {}, []
    for species in (1, 2):
        for quantity in QUANTITIES:
            entry = entries[(species, quantity)]
            value, record = read_member(zip_file, lookup[entry['name']], quantity, pins)
            values[species, quantity] = value
            records.append(record)
    times, iterations = {r['TIME'] for r in records}, {r['ITER'] for r in records}
    require(len(times) == len(iterations) == 1, 'Mixed snapshot times or iterations')
    time, iteration = next(iter(times)), next(iter(iterations))
    require(abs(time - expected_time) <= 1e-8, f'Expected time {expected_time}, found {time}')
    if initial:
        require(time == 0.0 and iteration == 0, 'Initial export must have TIME=ITER=0')
    densities = [-values[s, 'charge'] for s in (1, 2)]
    require(all(np.min(x) >= 0 for x in densities), 'Negative population number density')
    state = np.empty(SHAPE + (10,), dtype=np.float64)
    state[..., 0] = sum(densities)
    require(np.min(state[..., 0]) > 0, 'Aggregate density is not strictly positive')
    for i in range(3):
        state[..., i+1] = sum(densities[s-1] * values[s, f'vfl{i+1}'] for s in (1, 2))
    for i, quantity in enumerate(SECOND, 4):
        state[..., i] = sum(values[s, quantity] for s in (1, 2))
    require(np.isfinite(state).all(), 'Nonfinite aggregate conserved state')
    pressure = pressure_tensor(state)
    eigenvalues = np.linalg.eigvalsh(pressure)
    require(np.min(eigenvalues) > 0, 'Aggregate pressure is not positive definite; no clamping applied')
    observables = {'density': state[..., 0], 'Jz': -state[..., 3],
                   'Pxx': pressure[..., 0, 0], 'Pzz': pressure[..., 2, 2]}
    third_keys = [(s, 'v1v1v1') for s in (1, 2)]
    # The initial control reads exactly the twenty requested conserved-moment
    # members. Raw third moments are optional later-reference data only.
    third_available = not initial and all(key in entries for key in third_keys)
    if third_available:
        third = []
        for key in third_keys:
            raw, record = read_member(zip_file, lookup[entries[key]['name']], 'v1v1v1', pins)
            require(record['TIME'] == time and record['ITER'] == iteration, 'Third-moment snapshot mismatch')
            third.append(raw)
            records.append(record)
        ux = state[..., 1] / state[..., 0]
        observables['qxxx'] = sum(third) - 3*ux*state[..., 4] + 2*state[..., 0]*ux**3
    report = {'filename_frame_token': frame, 'TIME': time, 'ITER': iteration,
              'aggregate_moment_members': 20, 'raw_third_members': 2 if third_available else 0,
              'minimum_density': float(state[..., 0].min()),
              'maximum_density': float(state[..., 0].max()),
              'minimum_pressure_eigenvalue': float(eigenvalues.min()),
              'maximum_pressure_eigenvalue': float(eigenvalues.max()),
              'qxxx_available': third_available, 'members': records}
    return state, observables, report


def write_binary(path, array, component_names, overwrite):
    payload = np.ascontiguousarray(array, dtype='<f8').tobytes(order='C')
    if path.exists() and not overwrite:
        require(sha_bytes(path.read_bytes()) == sha_bytes(payload), f'Refusing to overwrite {path.name}')
    else:
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(payload)
        temporary.replace(path)
    return {'filename': path.name, 'shape': list(array.shape), 'components': list(component_names),
            'dtype': '<f8', 'order': 'C', 'bytes': len(payload), 'sha256': sha_bytes(payload),
            'linear_index': '((iy*nx+ix)*ncomponent+component)', 'byte_order': 'little-endian'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True, help='Completed, fully verified local PIC ZIP')
    parser.add_argument('--verification', type=Path, default=ROOT/'data/full-archive-verification.json')
    parser.add_argument('--inventory', type=Path, default=ROOT/'data/provenance-revision.json')
    parser.add_argument('--initial-provenance', type=Path, default=ROOT/'data/provenance.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'data/raw/pic-export')
    parser.add_argument('--metadata', type=Path, default=ROOT/'data/derived/pic-moment-export.json')
    parser.add_argument('--reference-frame', help='Exact later filename frame token discovered in inventory')
    parser.add_argument('--reference-time', type=float, help='Required physical TIME for the optional reference, e.g.300')
    parser.add_argument('--split-original-fluid-labels', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    require((args.reference_frame is None) == (args.reference_time is None),
            'Supply both --reference-frame and --reference-time, or neither')
    inventory, receipt = read_json(args.inventory), read_json(args.verification)
    archive, frames = discover(inventory)
    full_verification = verify_archive(args.archive, archive, receipt)
    pins = pinned_members(inventory, read_json(args.initial_provenance), receipt)
    initial_frame = min(frames, key=lambda value: int(value))
    require(args.reference_frame is None or args.reference_frame in frames,
            f'Unknown reference frame; complete tokens are {sorted(frames)}')
    if args.reference_frame is not None:
        require(args.reference_frame != initial_frame, 'Reference must be a distinct later frame')
        require(np.isfinite(args.reference_time) and args.reference_time > 0, 'Reference TIME must be positive')
    snapshots, outputs = [], []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive) as source:
        lookup = verify_directory(source, archive)
        initial, observables, report = load_frame(source, lookup, frames[initial_frame], initial_frame,
                                                 pins, 0.0, initial=True)
        snapshots.append(report)
        outputs.append(write_binary(args.output_dir/'aggregate-pic-t0.f64', initial, COMPONENTS, args.overwrite))
        if args.split_original_fluid_labels:
            deck = ROOT/'data/input-decks/input_2-e-Fluid.lua'
            require(sha_bytes(deck.read_bytes()) == FLUID2_DECK_SHA256, 'Original two-fluid deck changed')
            y = -32 + (np.arange(SHAPE[0])+.5)*.1
            w1 = .03 + .47*(np.tanh(y+16)-np.tanh(y-16))
            require(w1.min() >= .03-1e-15 and w1.max() <= .97+1e-15, 'Invalid fluid label weights')
            split = [w[:, None, None]*initial for w in (w1, 1-w1)]
            for i, state in enumerate(split, 1):
                require(np.linalg.eigvalsh(pressure_tensor(state)).min() > 0, 'Split pressure is not positive')
                outputs.append(write_binary(args.output_dir/f'aggregate-pic-t0-fluid{i}.f64',
                                            state, COMPONENTS, args.overwrite))
            report['smooth_fluid_label_control'] = {
                'definition': 'w1=.03+.47*(tanh(y+16)-tanh(y-16)); w2=1-w1; U_s=w_s*U_aggregate',
                'original_deck_sha256': FLUID2_DECK_SHA256,
                'maximum_aggregate_recombination_absolute_error': float(np.max(abs(sum(split)-initial))),
                'matches_PIC_tagged_populations': False,
                'matched_orders': 'Density, three momentum densities and six raw second moments only; no third-moment matching.',
                'scope': 'Aggregate moment matching; common velocity; no pressure clamping or smoothing.'}
        if args.reference_frame is not None:
            reference, observables, report = load_frame(source, lookup, frames[args.reference_frame],
                args.reference_frame, pins, args.reference_time)
            snapshots.append(report)
            prefix = f'reference-pic-frame-{args.reference_frame}'
            outputs.append(write_binary(args.output_dir/(prefix+'-conserved.f64'), reference, COMPONENTS, args.overwrite))
            outputs.append(write_binary(args.output_dir/(prefix+'-observables.f64'),
                np.stack(list(observables.values()), axis=-1), tuple(observables), args.overwrite))
    metadata = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Archived moment export; no PIC/Gkeyll evolution or nonlinear-effect claim.',
        'electron_mass': 1.0, 'electron_charge': -1.0,
        'moment_semantics': 'vfl is ordinary population mean; second/third diagnostics are unnormalized raw moments.',
        'grid': {'shape_y_x': list(SHAPE), 'bounds_x': list(BOUNDS[0]), 'bounds_y': list(BOUNDS[1]),
                 'spacing_x_y': [.1, .1], 'moment_offset_x_y': [.5, .5]},
        'binary_layout': '[y,x,component], component fastest, then x, then y; float64 little-endian; no header',
        'pressure_definition': 'P_ij=M_ij-momentum_i*momentum_j/rho; no clipping, clamping, filtering or smoothing',
        'qxxx_definition': 'sum_s raw_v1v1v1_s-3*u_x*Mxx+2*rho*u_x^3, unit electron mass',
        'archive': full_verification, 'snapshots': snapshots, 'binary_outputs': outputs,
        'available_complete_filename_frame_tokens': sorted(frames),
        'script_sha256': sha_bytes(Path(__file__).read_bytes()),
        'inventory_sha256': sha_bytes(args.inventory.read_bytes()),
        'verification_receipt_sha256': sha_bytes(args.verification.read_bytes()),
        'numpy': np.__version__, 'h5py': h5py.__version__}
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'exported', 'frames': [r['filename_frame_token'] for r in snapshots],
                      'binary_files': [r['filename'] for r in outputs], 'metadata': str(args.metadata)}))


if __name__ == '__main__':
    main()
