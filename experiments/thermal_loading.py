"""Conditional finite-temperature predictions for the posted OSIRIS PIC deck.

This is not an OSIRIS run or a reconstruction of its original private build.
The public loader's Gaussian-momentum/boost rule is compared with two distinct
semantics. Standard quadratic deposition is an explicitly conditional sensitivity
test: the original custom velocity-diagnostic implementation is unavailable.
No parameter is fitted to the archived moments. NumPy is the only dependency
additional to the already-pinned data_checks input reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from numpy.polynomial import chebyshev as cheb
from numpy.polynomial.hermite import hermgauss
from numpy.polynomial.laguerre import laggauss

from data_checks import analyze_profiles

ROOT = Path(__file__).resolve().parents[1]
SIGMA = 0.111803
COMMIT = 'a858fe1da3d6dbf3652b16556af87f7dad7881eb'
U_MAX = 0.51
NX, PARTICLES_PER_AXIS, DX = 480, 25, 0.1
ROWS = (159, 160, 479, 480)
MODES = ('public_loader_pushforward', 'invariant_scalar_distribution',
         'classical_momentum_addition')
SOURCES = [
    ('source/spec/os-spec-udist.f03',
     '1aa7964b2dc5070f92c85199c5d76d783a984d461e257472a3f7db6a4827cf06',
     {'defaults': [121, 137], 'Gaussian_draws': [573, 580],
      'spatial_boost': [752, 789]}),
    ('source/random/os-random-class.f03',
     'a4c639e8f685ecf180ee674f92400f196898780c44e9ec8c3fd6992c72e17d54',
     {'Gaussian_generator': [348, 392]}),
    ('source/spec/psource/os-psource-std.f03',
     '3e2d29b97120c79b18439231f62deccb013b384d937fe91965af55b3ee0e88c2',
     {'position_origin': [814, 822], 'particle_lattice': [839, 858],
      'charges_before_momentum_loading': [987, 1003],
      'momentum_loading_call': [1113, 1116]}),
    ('source/spec/os-spec-v3dep.f90',
     'e7ce270c4164b478b259f6e9846acc2c5f22af2f870077dc57df93a520808e59',
     {'quadratic_shape': [55, 71], 'quadratic_dispatch': [162, 169],
      'tensor_product_deposition': [349, 374]}),
]


def scan_full_deck() -> dict:
    path = ROOT / 'data/input-decks/input_PIC.2d'
    text = path.read_text(encoding='utf-8')
    # A comment begins at ! outside a quoted mathematical expression.
    active = []
    for line in text.splitlines():
        quoted, output = None, []
        for character in line:
            if character in ('"', "'"):
                quoted = None if quoted == character else character if quoted is None else quoted
            if character == '!' and quoted is None:
                break
            output.append(character)
        active.append(''.join(output))
    source = '\n'.join(active)
    controls = {}
    for name in ('use_classical_uadd', 'uth_type', 'use_spatial_uth',
                 'n_accelerate', 'n_q_incr', 'use_particle_uacc',
                 'use_spatial_ufl', 'uth', 'num_par_x', 'interpolation'):
        occurrences = [{'line': i + 1, 'text': line.strip()}
                       for i, line in enumerate(active)
                       if re.search(r'\b' + name + r'\b', line)]
        controls[name] = occurrences
    udist = re.findall(r'\budist\s*\{(.*?)\}', source, re.S)
    assert len(udist) == 2
    for block in udist:
        assert re.search(r'use_spatial_ufl\s*=\s*\.true\.', block, re.I)
        values = re.search(r'uth\(1:3\)\s*=([^\n]+)', block).group(1)
        assert [float(x) for x in values.strip().strip(',').split(',')] == [SIGMA] * 3
    for name in ('use_classical_uadd', 'uth_type', 'use_spatial_uth',
                 'n_accelerate', 'n_q_incr', 'use_particle_uacc'):
        assert not controls[name], (name, controls[name])
    assert not re.search(r'^\s*(?:#\s*include|include\b)', source, re.M | re.I)
    return {
        'path': path.relative_to(ROOT).as_posix(),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'total_lines': len(text.splitlines()), 'udist_blocks': len(udist),
        'active_control_occurrences': controls,
        'use_classical_uadd_override_found': False,
        'thermal_distribution_override_found': False,
        'include_directive_found': False,
        'scope': 'Complete posted deck; does not establish private executable defaults.',
    }


def source_provenance(cache: Path | None) -> dict:
    records = []
    for path, digest, lines in SOURCES:
        if cache is not None:
            local = cache / Path(path).name
            assert hashlib.sha256(local.read_bytes()).hexdigest() == digest, path
        records.append({'path': path, 'sha256': digest, 'line_spans': lines,
                        'url': f'https://raw.githubusercontent.com/osiris-code/osiris/{COMMIT}/{path}'})
    if cache is not None:
        loader = (cache / 'os-spec-udist.f03').read_text(encoding='utf-8')
        routine = re.search(r'(?is)^subroutine set_momentum\b(.*?)^end subroutine set_momentum', loader, re.M).group(1)
        assert 'species%q' not in routine.lower()
        assert 'use_classical_uadd = .false.' in loader
    return {
        'repository': 'https://github.com/osiris-code/osiris', 'commit': COMMIT,
        'files': records, 'source_cache_hashes_checked': cache is not None,
        'documentation': 'https://osiris-code.github.io/osiris/reference/udist',
        'original_simulation_executable_identified': False,
        'original_custom_velocity_diagnostic_source_available': False,
        'finding': ('In this public implementation independent thermal Gaussian momenta are '
                    'drawn and individually boosted. set_momentum does not alter particle '
                    'charges; the standard Cartesian source sets charges from spatial '
                    'density before that call. No loader Jacobian reweighting is applied.'),
    }


def scalar_moments(magnitudes: np.ndarray, order: int, mode: str) -> np.ndarray:
    """Return E[v_parallel]/U, E[v_perp_component^2], E[v_parallel^2].

    Independent isotropic Gaussian proper momenta permit one Hermite integral
    parallel to U and one Laguerre integral in the squared perpendicular radius.
    """
    magnitudes = np.atleast_1d(np.asarray(magnitudes, dtype=float))
    assert np.all((magnitudes > 0) & (magnitudes <= U_MAX))
    z, wh = hermgauss(order)
    r, wl = laggauss(order)
    p = np.sqrt(2) * SIGMA * z[:, None]
    r2 = 2 * SIGMA**2 * r[None, :]
    probability = wh[:, None] * wl[None, :] / np.sqrt(np.pi)
    gamma0 = np.sqrt(1 + p*p + r2)
    U = magnitudes[:, None, None]
    G = np.sqrt(1 + U*U)
    if mode in MODES[:2]:
        gamma1 = G * gamma0 + U * p
        vp = (G * p + U * gamma0) / gamma1
        jacobian_weight = gamma1 / (G * gamma0) if mode == MODES[1] else 1.0
        if mode == MODES[0]:
            # Pair opposite rest-frame parallel momenta for numerical stability
            # at U close to zero; this also proves the mean is below U/G.
            beta = U / G
            rest_v = p / gamma0
            expectation = np.sum(probability * rest_v**2 / (1-beta**2*rest_v**2), axis=(1, 2))
            factor = (1/np.sqrt(1+magnitudes**2)
                      * (1-expectation/(1+magnitudes**2)))
        else:
            factor = np.sum(probability * jacobian_weight * vp, axis=(1, 2)) / magnitudes
            assert np.max(np.abs(factor - 1/np.sqrt(1+magnitudes**2))) < 3e-13
    elif mode == MODES[2]:
        gamma1 = np.sqrt(1 + (p + U)**2 + r2)
        vp = (p + U) / gamma1
        jacobian_weight = 1.0
        factor = np.sum(probability * vp, axis=(1, 2)) / magnitudes
    else:
        raise ValueError(mode)
    second_parallel = np.sum(probability * jacobian_weight * vp*vp, axis=(1, 2))
    second_perpendicular = np.sum(probability * jacobian_weight * r2/(2*gamma1**2), axis=(1, 2))
    return np.stack([factor, second_perpendicular, second_parallel], axis=1)


def interpolant(order=32, degree=40, mode=MODES[0]):
    nodes = np.cos(np.pi * (np.arange(degree + 1) + 0.5)/(degree + 1))
    U = U_MAX * (nodes + 1)/2
    coefficients = cheb.chebfit(nodes, scalar_moments(U, order, mode), degree)
    def evaluate(vector):
        magnitude = np.linalg.norm(vector, axis=-1)
        assert np.max(magnitude) <= U_MAX
        factor, perp, parallel = cheb.chebval(2*magnitude/U_MAX - 1, coefficients)
        direction = np.divide(vector, magnitude[..., None], out=np.zeros_like(vector),
                              where=magnitude[..., None] != 0)
        mean = factor[..., None] * vector
        raw_second_diagonal = perp[..., None] + (parallel-perp)[..., None] * direction**2
        return mean, raw_second_diagonal
    test_U = np.linspace(0.0001, U_MAX, 257)
    discrepancy = np.max(np.abs(cheb.chebval(2*test_U/U_MAX-1, coefficients).T
                                - scalar_moments(test_U, order, mode)))
    assert discrepancy < 2e-11, (mode, order, degree, discrepancy)
    return evaluate, float(discrepancy)


def prescribed_proper_momentum(x, y):
    """Literal posted spatial_ufl expressions, including its rounded pi."""
    pi = 3.14159265
    b1 = .5 * (np.tanh(y+16) - np.tanh(y-16) - 1)
    derivative = .5 * (np.cosh(y+16)**(-2) - np.cosh(y-16)**(-2))
    b3 = np.sqrt(.5**2 + .05**2 - b1*b1)
    ux = b1 * derivative / b3
    uz = (derivative - .005*(2*pi/48)*np.cos(2*pi*x/48)
          + 2*(x+12)/36*(.005/4)*np.exp(-((x+12)/6)**2))
    ux, uz = np.broadcast_arrays(ux, uz)
    return np.stack([ux, np.zeros_like(ux), uz], axis=-1)


def b2(distance):
    distance = np.abs(np.asarray(distance))
    return np.where(distance < .5, .75-distance**2,
                    np.where(distance < 1.5, .5*(1.5-distance)**2, 0))


def predict_row(row: int, evaluate, model_name: str) -> dict:
    M, N, h = PARTICLES_PER_AXIS, NX, DX
    y = -32 + (row+.5)*h
    nodes = -24 + (np.arange(N)+.5)*h
    U = prescribed_proper_momentum(nodes, y)
    point_mean, point_raw = evaluate(U)
    point_variance = point_raw-point_mean**2
    zero = {'mean': point_mean.mean(axis=0).tolist(),
            'centered_covariance_diagonal': point_variance.mean(axis=0).tolist(),
            'ordinary_cold_vz': float(np.mean(U[:, 2]/np.sqrt(1+np.sum(U*U, axis=1)))),
            'mean_input_proper_momentum': U.mean(axis=0).tolist()}
    # This is a declared sensitivity model, not a verified custom-vfl routine.
    q = (np.arange(M)+.5)/M-.5
    positions_x = (nodes[:, None] + q[None, :]*h).ravel()
    offsets_y = (np.arange(-1, 2)[:, None]+q[None, :]).ravel()
    wy = b2(offsets_y)/M
    assert abs(np.sum(wy)-1) < 1e-14
    local_U = prescribed_proper_momentum(positions_x[None, :], y+offsets_y[:, None]*h)
    mean, raw = evaluate(local_U)
    variance = raw-mean**2
    assert np.min(variance) > 0
    y_mean = np.einsum('j,jki->ki', wy, mean).reshape(N, M, 3)
    y_raw = np.einsum('j,jki->ki', wy, raw).reshape(N, M, 3)
    y_variance_weight_squared = np.einsum('j,jki->ki', wy*wy, variance).reshape(N, M, 3)
    node_mean = np.zeros((N, 3))
    node_raw = np.zeros((N, 3))
    estimator_bias = np.zeros((N, 3))
    for neighbor in (-1, 0, 1):
        wx = b2(neighbor+q)/M
        node_mean += np.einsum('q,iqk->ik', wx, np.roll(y_mean, -neighbor, axis=0))
        node_raw += np.einsum('q,iqk->ik', wx, np.roll(y_raw, -neighbor, axis=0))
        estimator_bias += np.einsum('q,iqk->ik', wx*wx,
                                    np.roll(y_variance_weight_squared, -neighbor, axis=0))
    covariance = np.mean(node_raw-node_mean**2, axis=0)
    bias = np.mean(estimator_bias, axis=0)
    # x-averaging commutes with periodic deposition, and the x shape partitions
    # unity. Each contributing particle's row-average weight is wy/(N*M).
    row_mean_variance = np.einsum('j,jki->i', wy*wy, variance)/(N*M)**2
    max_weight = float(np.max(wy)/(N*M))
    log_factor = np.log(40.0)
    # Weighted Bernstein bound for independent, bounded velocity components.
    # |v_i-E v_i| <= 2, hence b = 2*max_weight.
    b = 2*max_weight
    bernstein = log_factor*b/3 + np.sqrt(2*row_mean_variance*log_factor+(log_factor*b/3)**2)
    return {'row': row, 'raw_y': y, 'paper_y': y+32, 'model': model_name,
            'zero_shape': zero,
            'conditional_standard_quadratic_deposition': {
                'mean': node_mean.mean(axis=0).tolist(),
                'centered_covariance_diagonal_infinite_sample': covariance.tolist(),
                'finite_particle_mean_square_bias': bias.tolist(),
                'expected_sample_covariance_diagonal': (covariance-bias).tolist(),
                'ideal_independent_sampler_row_mean_standard_error': np.sqrt(row_mean_variance).tolist(),
                'ideal_independent_sampler_row_mean_Bernstein_95_halfwidth': bernstein.tolist(),
                'max_row_average_particle_weight': max_weight,
                'parameters_fitted': 0,
            }}


def independent_three_dimensional_check() -> dict:
    x, w = hermgauss(24)
    x, w = np.sqrt(2)*SIGMA*x, w/np.sqrt(np.pi)
    p = np.stack(np.meshgrid(x, x, x, indexing='ij'), axis=-1).reshape(-1, 3)
    probability = np.einsum('i,j,k->ijk', w, w, w).ravel()
    U = np.array([0., 0., .5])
    G = np.sqrt(1+U@U)
    gamma0 = np.sqrt(1+np.sum(p*p, axis=1))
    lab_p = p + (gamma0+(p@U)/(G+1))[:, None]*U
    v = lab_p/(G*gamma0+p@U)[:, None]
    mean = probability@v
    raw = probability@(v*v)
    scalar = scalar_moments(np.array([.5]), 48, MODES[0])[0]
    expected_mean = np.array([0., 0., .5*scalar[0]])
    expected_raw = np.array([scalar[1], scalar[1], scalar[2]])
    error = max(float(np.max(abs(mean-expected_mean))), float(np.max(abs(raw-expected_raw))))
    assert error < 2e-12
    return {'three_dimensional_Hermite_order': 24, 'two_dimensional_order': 48,
            'maximum_mean_or_raw_second_difference': error}


def run(source_cache: Path | None = None) -> dict:
    archive = analyze_profiles()
    predictions, convergence, interpolation_errors = [], [], {}
    # Convergence concerns quadrature accuracy, separately from whether the
    # conditional public-loader/deposition model describes the original build.
    for order, degree in ((12, 24), (20, 32), (32, 40), (48, 48)):
        evaluate, error = interpolant(order, degree, MODES[0])
        row = predict_row(159, evaluate, MODES[0])
        dep = row['conditional_standard_quadratic_deposition']
        convergence.append({'Hermite_and_Laguerre_order': order, 'Chebyshev_degree': degree,
                            'interpolation_validation_max_abs_difference': error,
                            'zero_shape_mean_vz': row['zero_shape']['mean'][2],
                            'TSC_mean_vz': dep['mean'][2],
                            'TSC_covariance_diagonal': dep['centered_covariance_diagonal_infinite_sample']})
    assert abs(convergence[-1]['TSC_mean_vz']-convergence[-2]['TSC_mean_vz']) < 2e-12
    for mode in MODES:
        evaluate, error = interpolant(48, 48, mode)
        interpolation_errors[mode] = error
        for j in ROWS:
            row = predict_row(j, evaluate, mode)
            dep = row['conditional_standard_quadratic_deposition']
            observed = {'mean_vz': float(archive['pic_vz'][j]),
                        'Pxx': float(archive['pic_pxx'][j]),
                        'Pzz': float(archive['pic_pzz'][j])}
            expected_pressure = dep['expected_sample_covariance_diagonal']
            row['archived_moments'] = observed
            row['conditional_residuals_observed_minus_prediction'] = {
                'zero_shape_mean_vz': observed['mean_vz']-row['zero_shape']['mean'][2],
                'TSC_mean_vz': observed['mean_vz']-dep['mean'][2],
                'TSC_mean_vz_in_ideal_sampling_standard_errors':
                    (observed['mean_vz']-dep['mean'][2])/dep['ideal_independent_sampler_row_mean_standard_error'][2],
                'TSC_expected_sample_Pxx': observed['Pxx']-expected_pressure[0],
                'TSC_expected_sample_Pzz': observed['Pzz']-expected_pressure[2],
            }
            predictions.append(row)
    fixed_drift = {}
    for mode in MODES:
        value = scalar_moments(np.array([.5]), 48, mode)[0]
        mean = .5*value[0]
        fixed_drift[mode] = {'U': [0., 0., .5], 'mean_vz': float(mean),
                            'covariance_diagonal': [float(value[1]), float(value[1]), float(value[2]-mean**2)]}
    return {
        'scope': 'Conditional public-loader calculation and no-fit deposition sensitivity, not a new PIC run or exact original-executable reconstruction.',
        'experiment': {'path': 'experiments/thermal_loading.py',
                       'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       'numpy': np.__version__},
        'deck_audit': scan_full_deck(), 'public_source': source_provenance(source_cache),
        'thermal_proper_momentum_standard_deviation': SIGMA,
        'theory': {
            'rest_momentum': 'u ~ N(0,sigma^2 I), gamma0=sqrt(1+|u|^2), G=sqrt(1+|U|^2)',
            'public_loader': 'p=u+U*(gamma0+(u dot U)/(G+1)); gamma_lab=G*gamma0+u dot U; v=p/gamma_lab; unchanged particle weights',
            'mean_identity': 'E[v_parallel]=beta*[1-(1-beta^2)*E[w^2/(1-beta^2*w^2)]], beta=|U|/G, w=u_parallel/gamma0',
            'strict_cold_deficit': 'For beta>0 and nonzero thermal spread the bracket is strictly below 1, so E[v_parallel]<beta.',
            'distinct_invariant_scalar_measure': 'Jacobian dp/du=gamma_lab/gamma0. A scalar rest distribution at equal lab time uses normalized pullback weight gamma_lab/(G*gamma0)=1+beta*w, and has E[v]=U/G exactly. This is not the unweighted sample-boost loader.',
            'classical_alternative': 'p=u+U, v=p/sqrt(1+|p|^2); an alternative only, since no deck override was found.',
            'TSC_sensitivity': 'B2(r)=3/4-r^2 for |r|<1/2, (3/2-|r|)^2/2 for 1/2<=|r|<3/2, 0 otherwise. h=.1;25 regular subcell sites per axis; recorded moment node offsets(.5,.5).',
            'covariance_definition': 'At each spatial diagnostic node, deposit raw v_i^2 and v_i, then form raw_second-mean^2; x-average only after centering, matching the archived-data analysis.',
            'sample_mean_square_bias': 'For deterministic density and independent particle velocities, E[estimated centered variance]=deposited E[v_i^2]-(deposited E[v_i])^2-sum_a w_a^2 Var(v_ia).',
        },
        'error_controls': {
            'quadrature': 'Positive Gaussian-Hermite x Gaussian-Laguerre quadrature in parallel momentum and squared perpendicular radius; order refinement12,20,32,48.',
            'quadrature_convergence': convergence,
            'quadrature_error_is_formally_certified': False,
            'qualification': 'Order differences and independent coordinate quadrature are numerical convergence controls, not a rigorous a priori integration-error bound. Model/build uncertainty is separate and larger.',
            'interpolant_validation_257_magnitudes_max_errors': interpolation_errors,
            'independent_coordinate_check': independent_three_dimensional_check(),
            'spatial_sum': 'All480*25 x sites and3*25 y sites in quadratic support are explicitly summed, using the complete posted perturbation expressions; no spatial quadrature fitting.',
            'sampling_bound': 'Displayed Bernstein95 bounds assume independent ideal Gaussian draws, deterministic weights and the specified TSC diagnostic; they are not confidence claims about an unidentified executable or its exact PRNG sequence.',
        },
        'unperturbed_center_comparison': {'cold_mean_vz': float(.5/np.sqrt(1.25)), 'finite_temperature_models': fixed_drift},
        'row_predictions': predictions,
        'limitations': [
            'The original simulation executable and custom vfl/velocity-second-moment diagnostic source were not identified.',
            'The standard quadratic sensitivity follows the deck interpolation order and current public generic deposit_v3 shape, but that does not verify the authors custom diagnostic implementation.',
            'Zero-shape and quadratic sensitivity predictions are reported separately; no deposition parameter was calibrated against archived values.',
            'An invariant scalar distribution and an unweighted Lorentz-transformed sample ensemble are different probability measures; the latter matches the inspected public thermal branch.',
            'No causal claim about later nonlinear reconnection results follows from these initial-loading checks.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-cache', type=Path, help='Optional cached pinned public source files for SHA-256 verification; never downloads files.')
    parser.add_argument('--output', type=Path, default=ROOT/'results/thermal-loading.json')
    args = parser.parse_args()
    result = run(args.source_cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    rows = [r for r in result['row_predictions'] if r['model'] == MODES[0] and r['row'] in (159, 160)]
    print(json.dumps({'output': str(args.output), 'scope': result['scope'],
                      'rows': [{'row': r['row'], 'archived_vz': r['archived_moments']['mean_vz'],
                                'zero_shape_vz': r['zero_shape']['mean'][2],
                                'conditional_TSC_vz': r['conditional_standard_quadratic_deposition']['mean'][2],
                                'residual_in_sampling_SE': r['conditional_residuals_observed_minus_prediction']['TSC_mean_vz_in_ideal_sampling_standard_errors']}
                               for r in rows]}, indent=2))


if __name__ == '__main__':
    main()
