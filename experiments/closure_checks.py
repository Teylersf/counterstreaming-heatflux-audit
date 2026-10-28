"""Deterministic moment, transport and linear-closure checks.

No PIC/Gkeyll reconnection rerun is performed.  The linear benchmark is a
homogeneous nonrelativistic longitudinal limit of the stated moment closure.
Only NumPy and the Python standard library are required.
"""
from __future__ import annotations

from fractions import Fraction
import math
import numpy as np


def moments(velocity: np.ndarray, weight: np.ndarray, mass: float = 1.0):
    """Direct centered moments of a positive finite quadrature/atomic law."""
    velocity = np.asarray(velocity, dtype=float)
    weight = np.asarray(weight, dtype=float)
    assert velocity.ndim == 2 and velocity.shape[1] == 3
    assert weight.shape == (velocity.shape[0],) and np.all(weight > 0)
    density = float(weight.sum())
    mean = np.einsum("a,ai->i", weight, velocity) / density
    centered = velocity - mean
    pressure = mass * np.einsum("a,ai,aj->ij", weight, centered, centered)
    third = mass * np.einsum(
        "a,ai,aj,ak->ijk", weight, centered, centered, centered)
    return density, mean, pressure, third


def mixture_prediction(moment1, moment2, mass: float = 1.0):
    """Source's exact two-population identities, independent of quadrature."""
    n1, u1, p1, q1 = moment1
    n2, u2, p2, q2 = moment2
    n = n1 + n2
    du = u1 - u2
    dt = p1 / n1 - p2 / n2
    pressure_cs = mass * n1 * n2 / n * np.outer(du, du)
    thermal_cs = n1 * n2 / n * (
        np.einsum("i,jk->ijk", du, dt)
        + np.einsum("j,ik->ijk", du, dt)
        + np.einsum("k,ij->ijk", du, dt))
    cubic_cs = -mass * n1 * n2 * (n1 - n2) / n**2 * np.einsum(
        "i,j,k->ijk", du, du, du)
    return p1 + p2 + pressure_cs, q1 + q2 + thermal_cs + cubic_cs, thermal_cs + cubic_cs


def gaussian_quadrature(mean, variance: float, density: float, order: int = 4):
    """Positive product-Gauss-Hermite quadrature, exact through third order."""
    x, w = np.polynomial.hermite.hermgauss(order)
    grid = np.meshgrid(x, x, x, indexing="ij")
    v = np.stack([a.ravel() for a in grid], axis=1)
    weights = np.einsum("i,j,k->ijk", w, w, w).ravel() / math.pi**1.5
    return np.asarray(mean) + math.sqrt(2 * variance) * v, density * weights


def _mixture_checks():
    rng = np.random.default_rng(20261028)
    mass = 2.3
    pressure_errors, third_errors, scalar_errors = [], [], []
    for _ in range(32):
        laws = []
        for _population in range(2):
            transform = rng.normal(size=(3, 3))
            velocity = rng.normal(size=(47, 3)) @ transform.T + rng.normal(size=3)
            weight = rng.uniform(0.1, 1.0, 47)
            weight *= rng.uniform(0.2, 1.8) / weight.sum()
            laws.append((velocity, weight))
        m1, m2 = [moments(v, w, mass) for v, w in laws]
        combined = moments(
            np.concatenate([a[0] for a in laws]),
            np.concatenate([a[1] for a in laws]), mass)
        predicted_p, predicted_q, _ = mixture_prediction(m1, m2, mass)
        pressure_errors.append(float(np.max(np.abs(combined[2] - predicted_p))))
        third_errors.append(float(np.max(np.abs(combined[3] - predicted_q))))
        n1, u1, p1, q1 = m1
        n2, u2, p2, q2 = m2
        n, du = n1 + n2, u1[0] - u2[0]
        scalar = (
            q1[0, 0, 0] + q2[0, 0, 0]
            + 3 * n1 * n2 / n * du * (p1[0, 0] / n1 - p2[0, 0] / n2)
            - mass * n1 * n2 / n**2 * (n1 - n2) * du**3)
        scalar_errors.append(float(abs(combined[3][0, 0, 0] - scalar)))
        np.testing.assert_allclose(combined[2], predicted_p, rtol=2e-12, atol=2e-12)
        np.testing.assert_allclose(combined[3], predicted_q, rtol=2e-11, atol=2e-11)
        assert abs(combined[3][0, 0, 0] - scalar) < 2e-11
    return {
        "cases": 32, "seed": 20261028, "mass": mass,
        "max_pressure_absolute_error": max(pressure_errors),
        "max_full_third_tensor_absolute_error": max(third_errors),
        "max_scalar_source_equation_error": max(scalar_errors),
        "scope": "Exact identities confirmed, not errors in source Eqs.3,4,B1,B2.",
    }


def continuity_density(y, t: float, a: float = 0.4, n0: float = 1.3):
    return n0 / (np.cosh(a * t) - np.cos(y) * np.sinh(a * t))


def _continuity_checks():
    n0, a, t = 1.3, 0.4, 0.8
    size = 2048
    y = 2 * np.pi * np.arange(size) / size
    velocity = -a * np.sin(y)
    density = continuity_density(y, t, a, n0)
    mass = float(density.mean() * 2 * np.pi)
    wave = 2 * np.pi * np.fft.fftfreq(size, d=2 * np.pi / size)
    divergence = np.fft.ifft(1j * wave * np.fft.fft(density * velocity)).real
    residuals = []
    for step in (2e-4, 1e-4):
        dt = (continuity_density(y, t + step, a, n0)
              - continuity_density(y, t - step, a, n0)) / (2 * step)
        residuals.append(float(np.max(np.abs(dt + divergence))))
    center = float(continuity_density(0.0, t, a, n0))
    assert abs(mass - 2 * np.pi * n0) < 2e-12
    assert velocity[0] == 0 and center > n0
    assert abs(center - n0 * math.exp(a * t)) < 2e-14
    assert residuals[-1] < 2e-8 and residuals[-1] < residuals[0]
    return {
        "n0": n0, "a": a, "time": t,
        "center_velocity": float(velocity[0]), "center_density": center,
        "center_density_exact": n0 * math.exp(a * t),
        "initial_center_density_time_derivative": n0 * a,
        "integrated_mass": mass, "mass_error": mass - 2 * np.pi * n0,
        "pde_residuals_dt_refinement": residuals,
        "scope": "Exact kinematic continuity solution, not a self-consistent Maxwell reconnection solution.",
    }


def _skew_law(mean: float, width: float, density: float):
    centers = np.array([-1 / math.sqrt(2), math.sqrt(2)])
    probabilities = np.array([2 / 3, 1 / 3])
    x = mean + width * centers
    weights = density * probabilities
    v = np.zeros((len(x), 3))
    v[:, 0] = x
    return v, weights


def _near_gaussian_law(mean: float, width: float, density: float,
                       epsilon: float = 0.01, eta: float = 0.3):
    """A (1-epsilon) Gaussian plus epsilon positive smooth perturbation.

    The dimensionless centered law has exactly zero mean and covariance I.
    Its total-variation distance from N(0,I) is at most epsilon. The x third
    moment is epsilon/[sqrt(2)*(1+eta**2)**1.5]; all other third entries vanish.
    """
    baseline_v, baseline_w = gaussian_quadrature(
        [mean, 0, 0], width**2, density * (1 - epsilon))
    centers = np.array([-1 / math.sqrt(2), math.sqrt(2)])
    probabilities = np.array([2 / 3, 1 / 3])
    gx, gw = np.polynomial.hermite.hermgauss(24)
    transverse, tw = np.polynomial.hermite.hermgauss(4)
    center_grid, x_grid, y_grid, z_grid = np.meshgrid(
        centers, gx, transverse, transverse, indexing="ij")
    perturbed_v = np.stack([
        (mean + width * (center_grid + math.sqrt(2) * eta * x_grid)
         / math.sqrt(1 + eta**2)).ravel(),
        (math.sqrt(2) * width * y_grid).ravel(),
        (math.sqrt(2) * width * z_grid).ravel()], axis=1)
    perturbed_w = density * epsilon * np.einsum(
        "i,j,k,l->ijkl", probabilities, gw, tw, tw).ravel() / math.pi**1.5
    return (np.concatenate([baseline_v, perturbed_v]),
            np.concatenate([baseline_w, perturbed_w]))


def _conditioning_checks():
    mass, n, w1, w2, drift = 2.3, 1.4, 0.3, 0.7, 2.0
    widths = (0.2, 0.3)
    laws = [
        _skew_law(w2 * drift, widths[0], n * w1),
        _skew_law(-w1 * drift, widths[1], n * w2),
    ]
    pop = [moments(v, w, mass) for v, w in laws]
    combined = moments(np.concatenate([x[0] for x in laws]),
                       np.concatenate([x[1] for x in laws]), mass)
    _, _, cs = mixture_prediction(*pop, mass)
    true_q = float(combined[3][0, 0, 0])
    cs_q = float(cs[0, 0, 0])
    theta1, theta2 = [(s / drift)**2 for s in widths]
    coefficient = w1 * w2 * (3 * (theta1 - theta2) - (w1 - w2))
    # Each selected law has standardized third moment 1/sqrt(2) < 1.
    error_bound = w1 * (widths[0] / drift)**3 + w2 * (widths[1] / drift)**3
    assert error_bound < abs(coefficient)
    actual_relative_error = abs(true_q - cs_q) / abs(true_q)
    sufficient_bound = error_bound / (abs(coefficient) - error_bound)
    np.testing.assert_allclose(cs_q, mass * n * drift**3 * coefficient,
                               rtol=1e-12, atol=1e-12)
    assert actual_relative_error <= sufficient_bound
    counterexamples = []
    epsilon, eta = 0.01, 0.3
    standardized_third = epsilon / (math.sqrt(2) * (1 + eta**2)**1.5)
    for width in (0.2, 0.1, 0.05, 0.025):
        parts = [_near_gaussian_law(sign, width, 0.5, epsilon, eta)
                 for sign in (1.0, -1.0)]
        ms = [moments(v, w) for v, w in parts]
        for pop_moments in ms:
            np.testing.assert_allclose(pop_moments[2] / pop_moments[0],
                                       width**2 * np.eye(3), atol=2e-13, rtol=2e-12)
        total = moments(np.concatenate([x[0] for x in parts]),
                        np.concatenate([x[1] for x in parts]))
        _, _, predicted = mixture_prediction(*ms)
        q, q_cs = float(total[3][0, 0, 0]), float(predicted[0, 0, 0])
        expected = width**3 * standardized_third
        assert abs(q - expected) < 3e-13
        assert abs(q_cs) < 3e-13
        relative = abs(q - q_cs) / abs(q)
        assert abs(relative - 1) < 2e-7
        counterexamples.append({
            "width_parameter_over_beam_speed": width,
            "actual_thermal_speed_over_beam_speed": width,
            "q_total": q, "q_cs": q_cs, "q_analytic": expected,
            "relative_error": relative,
        })
    return {
        "conditioned_example": {
            "mass": mass, "density": n, "weights": [w1, w2], "drift_difference": drift,
            "intrinsic_widths": list(widths), "C": coefficient, "E_upper": error_bound,
            "true_q": true_q, "q_cs": cs_q, "relative_error": actual_relative_error,
            "sufficient_relative_error_bound": sufficient_bound,
        },
        "smooth_positive_counterexamples": counterexamples,
        "total_variation_distance_from_matching_maxwellian_upper_bound": epsilon,
        "standardized_intrinsic_third_moment": standardized_third,
        "smoothing_shape_parameter_eta": eta,
        "quadrature": "4x4x4 baseline and 24x4x4 per perturbing Gaussian, all positive; degree <=3 exact.",
        "scope": "No universal speed-ratio-only relative bound; does not disprove source's empirical scan.",
    }


def _nonidentifiability_checks():
    cases = []
    moment_data = []
    for weight1 in (0.5, 0.25):
        weight2 = 1 - weight1
        difference = math.sqrt(0.25 / (weight1 * weight2))
        mean1, mean2 = [weight2 * difference, 0, 0], [-weight1 * difference, 0, 0]
        laws = [gaussian_quadrature(mean1, 0.75, weight1),
                gaussian_quadrature(mean2, 0.75, weight2)]
        total = moments(np.concatenate([v for v, _ in laws]),
                        np.concatenate([w for _, w in laws]))
        moment_data.append(total)
        q_analytic = -weight1 * weight2 * (weight1 - weight2) * difference**3
        np.testing.assert_allclose(total[2], np.diag([1, 0.75, 0.75]), atol=2e-14)
        assert abs(total[3][0, 0, 0] - q_analytic) < 2e-14
        cases.append({"weight1": weight1, "drift_difference": difference,
                      "mean1_x": mean1[0], "mean2_x": mean2[0],
                      "density": total[0], "mean": total[1].tolist(),
                      "pressure": total[2].tolist(),
                      "q_xxx": float(total[3][0, 0, 0]), "q_analytic": q_analytic})
    a, b = moment_data
    np.testing.assert_allclose(a[0], b[0], atol=2e-14)
    np.testing.assert_allclose(a[1], b[1], atol=2e-14)
    np.testing.assert_allclose(a[2], b[2], atol=2e-14)
    assert abs(a[3][0, 0, 0] - b[3][0, 0, 0]) > 0.1
    return {"cases": cases,
            "scope": "Preserves the genuine insufficiency of an arbitrary memoryless algebraic n,u,P closure."}


def dawson(x: float, order: int = 96) -> float:
    """D(x)=exp(-x*x)*integral_0^x exp(t*t)dt, by positive Gauss-Legendre."""
    points, weights = np.polynomial.legendre.leggauss(order)
    t = float(x) * (points + 1) / 2
    return float(x / 2 * np.dot(weights, np.exp(t*t - x*x)))


def penrose_quantity(U: float, sigma: float = 1.0, order: int = 96) -> float:
    """Return sigma**2 * integral f0'(v)/v dv for equal Maxwellian beams."""
    z = abs(U) / (math.sqrt(2) * sigma)
    return float(2 * z * dawson(z, order) - 1)


def penrose_integral(U: float, sigma: float = 1.0, order: int = 96) -> float:
    return penrose_quantity(U, sigma, order) / sigma**2


def linear_matrix(U: float, k: float, nu: float, sigma: float = 1.0) -> np.ndarray:
    """Nine-variable longitudinal moment matrix, total plasma frequency one.

    Per beam state is (delta n, delta u_x, delta P_xx, delta Tr P); last
    variable is E_x. Set total density=mass=charge magnitude=epsilon_0=1.
    Gauss law is i*k*E + delta n_plus + delta n_minus = 0.
    U and sigma share velocity units; k*U, k*sigma and nu are in omega_p units.
    """
    matrix = np.zeros((9, 9), dtype=complex)
    for beam, beam_speed in enumerate((U, -U)):
        offset = 4 * beam
        density = 0.5
        pressure = density * sigma**2
        matrix[offset, offset] = -1j * k * beam_speed
        matrix[offset, offset + 1] = -1j * k * density
        matrix[offset + 1, offset + 1] = -1j * k * beam_speed
        matrix[offset + 1, offset + 2] = -1j * k / density
        matrix[offset + 1, 8] = -1
        matrix[offset + 2, offset + 2] = -1j * k * beam_speed - nu
        matrix[offset + 2, offset + 1] = -3j * k * pressure
        matrix[offset + 2, offset + 3] = nu / 3
        matrix[offset + 3, offset + 3] = -1j * k * beam_speed
        matrix[offset + 3, offset + 1] = -5j * k * pressure
        matrix[8, offset] = beam_speed
        matrix[8, offset + 1] = density
    return matrix


def growth(U: float, k: float, nu: float, sigma: float = 1.0) -> float:
    """Largest eigenvalue real part, floored at zero (neutral entropy modes)."""
    return max(0.0, float(np.linalg.eigvals(linear_matrix(U, k, nu, sigma)).real.max()))


def fluid_dielectric(omega: complex, U: float, k: float, nu: float,
                     sigma: float = 1.0) -> complex:
    response = 0j
    for beam_speed in (U, -U):
        shifted = omega - k * beam_speed
        d = -1j * shifted
        gamma = 3.0 if nu == 0 else 5 / 3 + 4 * d / (3 * (d + nu))
        response += 0.5 / (shifted**2 - k**2 * sigma**2 * gamma)
    return 1 - response


def _mode_data(U: float, k: float, nu: float, sigma: float = 1.0):
    matrix = linear_matrix(U, k, nu, sigma)
    values, vectors = np.linalg.eig(matrix)
    index = int(np.argmax(values.real))
    value, vector = values[index], vectors[:, index]
    matrix_residual = float(np.linalg.norm(matrix @ vector - value * vector))
    gauss_residual = float(abs(1j * k * vector[8] + vector[0] + vector[4]))
    dielectric_residual = float(abs(fluid_dielectric(1j * value, U, k, nu, sigma)))
    return {"U_over_sigma": U / sigma, "k_sigma_over_omega_p": k * sigma,
            "nu_over_omega_p": nu, "growth": float(value.real),
            "oscillation_frequency_abs": float(abs(value.imag)),
            "eigenvalue_imaginary_part": float(value.imag),
            "matrix_residual": matrix_residual, "gauss_residual": gauss_residual,
            "independent_dielectric_residual": dielectric_residual}


def _stability_checks():
    U, k, nu = 1.2, 0.2, 1 / (40 * math.sqrt(5))
    numeric_penrose = penrose_quantity(U)
    refined_penrose = penrose_quantity(U, order=128)
    upper = Fraction(36, 25) - Fraction(432, 625) + Fraction(15552, 78125) - 1
    assert upper == Fraction(-4073, 78125) and numeric_penrose <= float(upper) < 0
    assert abs(numeric_penrose - refined_penrose) < 2e-14
    finite = _mode_data(U, k, nu)
    assert finite["growth"] > 0.005
    assert max(finite[name] for name in (
        "matrix_residual", "gauss_residual", "independent_dielectric_residual")) < 2e-10
    rounded = _mode_data(U, k, 0.0111803)
    assert rounded["growth"] > 0.005
    assert abs(rounded["growth"] - finite["growth"]) < 1e-6
    assert max(rounded[name] for name in (
        "matrix_residual", "gauss_residual", "independent_dielectric_residual")) < 2e-10
    ideal_values = np.linalg.eigvals(linear_matrix(U, k, 0))
    assert np.max(ideal_values.real) < 2e-12
    a, b = (k * U)**2, 3 * k**2
    discriminant = 1 + 8 * a + 16 * a * b
    w_squared = np.array([(2*(a+b)+1-sign*math.sqrt(discriminant))/2
                          for sign in (1, -1)])
    assert np.min(w_squared) > 0
    for frequency in np.sqrt(w_squared):
        assert np.min(np.abs(ideal_values - 1j * frequency)) < 2e-12
        assert np.min(np.abs(ideal_values + 1j * frequency)) < 2e-12
    omega0 = math.sqrt((847 - 5 * math.sqrt(24553)) / 1250)
    shifted = np.array([omega0 - k * U, omega0 + k * U])
    denominators = shifted**2 - 3 * k**2
    slope = float(-2 * k**2 / 3 * np.sum(1 / (shifted * denominators**2))
                  / np.sum(shifted / denominators**2))
    assert 0.225 < omega0 < 0.226 and slope > 0
    small_rates = []
    for small_nu in (1e-5, 1e-6):
        g = growth(U, k, small_nu)
        small_rates.append({"nu": small_nu, "growth": g, "growth_over_nu": g / small_nu})
        assert g > 0 and abs(g / small_nu - slope) < 2e-4
    sigma_physical = 1 / math.sqrt(80)
    grid_k = sigma_physical * (2 * math.pi * 14 / 48)
    grid = _mode_data(U, grid_k, nu)
    assert grid["growth"] > 0.005
    assert max(grid[name] for name in (
        "matrix_residual", "gauss_residual", "independent_dielectric_residual")) < 2e-10
    grid.update({"mode_number": 14, "box_length_de": 48, "wavelength_de": 48 / 14,
                 "cells_per_wavelength_at_dx_0_1_de": 480 / 14})
    return {
        "penrose_quantity": numeric_penrose,
        "penrose_exact_upper_bound": str(upper),
        "kinetic_longitudinal_electrostatic_equilibrium_stable_all_k": True,
        "finite_relaxation_mode": finite,
        "rounded_literal_fluid_input_rate_mode": rounded,
        "ideal_zero_relaxation_max_growth_roundoff": float(ideal_values.real.max()),
        "ideal_lower_frequency": omega0, "small_nu_growth_derivative": slope,
        "small_nu_checks": small_rates, "source_box_compatible_mode": grid,
        "scope": "Continuum homogeneous nonrelativistic benchmark, not a reconnection simulation.",
    }


def _entropy_checks():
    density = 1.0
    initial = np.diag([2.0, 0.5, 0.5])
    mean_pressure = float(np.trace(initial) / 3)
    nu = 1 / (40 * math.sqrt(5))
    identity = np.eye(3)

    def pressure(t):
        return mean_pressure * identity + math.exp(-nu * t) * (
            initial - mean_pressure * identity)

    def entropy(t):
        sign, logdet = np.linalg.slogdet(pressure(t))
        assert sign > 0
        return float(0.5 * logdet - 2.5 * math.log(density))

    times = np.linspace(0, 300, 31)
    traces = [float(np.trace(pressure(t))) for t in times]
    entropies = [entropy(t) for t in times]
    assert max(abs(t - 3 * mean_pressure) for t in traces) < 2e-14
    assert np.all(np.diff(entropies) > 0)
    test_time, step = 37.0, 1e-3
    tensor = pressure(test_time)
    production = nu / 2 * (mean_pressure * np.trace(np.linalg.inv(tensor)) - 3)
    difference = (entropy(test_time + step) - entropy(test_time - step)) / (2 * step)
    assert production > 0 and abs(difference - production) < 2e-11
    anisotropy_ratio = float(np.linalg.norm(pressure(300) - mean_pressure * identity)
                             / np.linalg.norm(initial - mean_pressure * identity))
    assert abs(anisotropy_ratio - math.exp(-nu * 300)) < 2e-14
    return {
        "initial_pressure": initial.tolist(), "density": density,
        "nu_over_omega_p": nu, "duration_omega_p": 300.0, "nu_times_duration": nu * 300,
        "trace": 3 * mean_pressure, "maximum_trace_error": max(
            abs(t - 3 * mean_pressure) for t in traces),
        "anisotropy_remaining_fraction": anisotropy_ratio,
        "gaussian_entropy_change_per_particle": entropies[-1] - entropies[0],
        "entropy_production_at_time_37": float(production),
        "entropy_derivative_finite_difference_error": float(abs(difference - production)),
        "scope": "Homogeneous anisotropic example; no external energy input or measured PIC entropy is claimed.",
    }


def run_checks() -> dict:
    """Return named assertion-checked groups; all returned values are JSON-safe."""
    return {
        "mixture_identities": _mixture_checks(),
        "continuity_symmetry": _continuity_checks(),
        "conditioning_counterexample": _conditioning_checks(),
        "singlefluid_nonidentifiability": _nonidentifiability_checks(),
        "finite_relaxation_stability": _stability_checks(),
        "isotropization_entropy": _entropy_checks(),
    }
