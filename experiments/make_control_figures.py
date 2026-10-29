"""Plot verified archived or completed control metrics; never invent pending runs.

Default controls mode requires all six archived/clean/matched cases. Source
mode is only for the actual archived outputs and uses different output names.
The input profile hash and every plotted profile norm are checked first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
QUANTITIES = ('rho', 'Jz', 'Pxx', 'Pzz')
SYMBOLS = (r'$n$', r'$J_z$', r'$P_{xx}$', r'$P_{zz}$')
UNITS = (r'$n/n_0$', r'$J_z/(e n_0 c)$',
         r'$P_{xx}/(m_e n_0 c^2)$', r'$P_{zz}/(m_e n_0 c^2)$')
GROUPS = ('archived', 'baseline', 'matched')
GROUP_LABELS = ('Archived source', 'Clean baseline', 'PIC-matched')
COLORS = {'one_fluid': '#D55E00', 'two_fluid': '#0072B2'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def save(figure, directory, name, title):
    paths = []
    for extension in ('pdf', 'png'):
        path = directory / (name + '.' + extension)
        metadata = {'Author': 'Taylor Kalin', 'Title': title}
        if extension == 'pdf':
            metadata.update(CreationDate=None, ModDate=None)
        figure.savefig(path, dpi=220, metadata=metadata)
        paths.append(path)
    plt.close(figure)
    return paths


def validate(report, profiles_path, groups):
    require(report.get('all_actual_cases_passed') is True,
            'Comparison report must pass all actual cases before plotting')
    require(report.get('profile_export_sha256') == sha(profiles_path),
            'Profile CSV hash does not match comparison report')
    cases = {case['id']: case for case in report['cases']}
    require(len(cases) == len(report['cases']), 'Duplicate case identifiers')
    pic_time = report['PIC_reference']['snapshot']['TIME']
    require(np.isfinite(pic_time), 'Nonfinite PIC reference time')
    required = [group + '_' + model for group in groups
                for model in ('one_fluid', 'two_fluid')]
    for name in required:
        require(cases.get(name, {}).get('status') == 'compared',
                'Required actual case is not compared: ' + name)
        case = cases[name]
        group = name.split('_', 1)[0]
        require(case['kind'] == ('archived_source' if group == 'archived' else 'solver_control')
                and case['role'] == ('source_reference' if group == 'archived' else group)
                and case['population_count'] == (1 if name.endswith('one_fluid') else 2),
                'Case provenance label differs: ' + name)
        require(case['frame'] == 30 and np.isfinite(case['actual_time'])
                and case['actual_time'] >= 300, 'Invalid comparison frame/time: ' + name)
    profiles = np.genfromtxt(profiles_path, delimiter=',', names=True)
    require(len(profiles) == 640, 'Expected complete 640-row profile')
    require(np.allclose(profiles['raw_y'], -32 + (np.arange(640) + .5) * .1,
                        rtol=0, atol=1e-12), 'Unexpected profile coordinates')
    for name in required:
        for quantity in QUANTITIES:
            model, reference = profiles[name + '_' + quantity], profiles['PIC_' + quantity]
            require(np.isfinite(model).all() and np.isfinite(reference).all(),
                    'Nonfinite profile values')
            norm = np.linalg.norm(reference)
            require(norm > 0, 'Unexpected zero reference profile norm')
            measured = np.linalg.norm(model - reference) / norm
            expected = cases[name]['metrics'][quantity]['x_averaged_profile']['relative_L2']
            require(np.isclose(measured, expected, rtol=2e-12, atol=2e-14),
                    'Profile norm disagrees with report: ' + name + ':' + quantity)
            value = cases[name]['metrics'][quantity]['full_2D_grid']['relative_L2']
            require(value is not None and np.isfinite(value) and value >= 0,
                    'Invalid full-grid error: ' + name + ':' + quantity)
        if name.endswith('two_fluid'):
            quantity = 'qCSxxx_contribution_vs_tagged_PIC'
            model, reference = profiles[name + '_' + quantity], profiles['PIC_qCSxxx']
            require(np.isfinite(model).all() and np.isfinite(reference).all(),
                    'Nonfinite contribution profile values')
            require(np.linalg.norm(reference) > 0, 'Unexpected zero tagged contribution norm')
            measured = np.linalg.norm(model - reference) / np.linalg.norm(reference)
            expected = cases[name]['metrics'][quantity]['x_averaged_profile']['relative_L2']
            require(np.isclose(measured, expected, rtol=2e-12, atol=2e-14),
                    'Contribution profile norm disagrees with report: ' + name)
    return cases, profiles, pic_time


def metric_bars(cases, groups, output, prefix):
    fig, axes = plt.subplots(2, 2, figsize=(6.7, 4.9), layout='constrained')
    x = np.arange(len(groups))
    for ax, quantity, symbol in zip(axes.flat, QUANTITIES, SYMBOLS):
        for offset, model, label in ((-.18, 'one_fluid', 'One fluid'),
                                     (.18, 'two_fluid', 'Two fluids')):
            values = [100 * cases[group + '_' + model]['metrics'][quantity]
                      ['full_2D_grid']['relative_L2'] for group in groups]
            bars = ax.bar(x + offset, values, width=.34, color=COLORS[model],
                          label=label, zorder=3)
            ax.bar_label(bars, fmt='%.2f', padding=3, fontsize=6.8)
        ax.set_title(symbol)
        ax.set_xticks(x, [GROUP_LABELS[GROUPS.index(group)] for group in groups])
        ax.set_ylabel('Full-grid relative L2 error (%)')
        ax.set_ylim(bottom=0, top=ax.get_ylim()[1] * 1.17)
        ax.grid(axis='y', alpha=.2, zorder=0)
    axes.flat[0].legend(frameon=False, fontsize=7)
    return save(fig, output, prefix + '-errors',
                'Full-grid moment errors against the archived PIC snapshot')


def profile_panels(cases, profiles, groups, output, prefix):
    fig, axes = plt.subplots(2, 2, figsize=(6.7, 5.15))
    y = profiles['raw_y'] + 32
    plotted_groups = [g for g in groups if g != 'archived'] or ['archived']
    for ax, quantity, symbol, unit in zip(axes.flat, QUANTITIES, SYMBOLS, UNITS):
        ax.plot(y, profiles['PIC_' + quantity], color='#222222', lw=1.4, label='PIC')
        for group in plotted_groups:
            for model, model_label in (('one_fluid', 'one fluid'), ('two_fluid', 'two fluids')):
                label = GROUP_LABELS[GROUPS.index(group)] + ', ' + model_label
                ax.plot(y, profiles[group + '_' + model + '_' + quantity],
                        color=COLORS[model], lw=1.05,
                        linestyle='--' if group == 'baseline' else '-', label=label)
        for center in (16, 48):
            ax.axvline(center, color='#aaaaaa', lw=.55, linestyle=':')
        ax.set(title=symbol, xlabel=r'$Y/d_e$', ylabel=unit, xlim=(0, 64))
        ax.grid(alpha=.18)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, frameon=False,
               bbox_to_anchor=(.5, .005), fontsize=7)
    fig.subplots_adjust(left=.09, right=.985, top=.95, bottom=.17,
                        hspace=.36, wspace=.28)
    return save(fig, output, prefix + '-profiles',
                'Full-domain x-averaged moment profiles at recorded comparison times')


def qcs_panel(cases, profiles, groups, output, prefix):
    fig, ax = plt.subplots(figsize=(6.7, 3.0))
    y = profiles['raw_y'] + 32
    ax.plot(y, profiles['PIC_qCSxxx'], color='#222222', lw=1.4,
            label='PIC tags')
    for group in groups:
        name = group + '_two_fluid'
        require('qCSxxx_contribution_vs_tagged_PIC' in cases[name]['metrics'],
                'Missing documented tagged-contribution comparison')
        column = name + '_qCSxxx_contribution_vs_tagged_PIC'
        ax.plot(y, profiles[column], color='#777777' if group == 'archived' else '#0072B2',
                linestyle={'archived': ':', 'baseline': '--', 'matched': '-'}[group],
                lw=1.1, label=GROUP_LABELS[GROUPS.index(group)] + ', two fluids')
    ax.set(xlabel=r'$Y/d_e$', ylabel=r'$q^{\rm CS}_{xxx}/(m_e n_0 c^3)$',
           title='Population-recentering contribution; not the complete heat flux', xlim=(0, 64))
    ax.grid(alpha=.18)
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2, frameon=False,
               bbox_to_anchor=(.5, .005), fontsize=6.8)
    fig.subplots_adjust(left=.11, right=.985, top=.86, bottom=.28)
    return save(fig, output, prefix + '-qcs',
                'Decomposition-dependent counter-streaming contribution from first and second moments')


def fidelity_rows(report, cases):
    rows = report.get('clean_unmatched_vs_archived_source', [])
    expected = {('baseline_one_fluid', 'archived_one_fluid'),
                ('baseline_two_fluid', 'archived_two_fluid')}
    require(len(rows) == 2 and {(r.get('clean'), r.get('archived')) for r in rows} == expected,
            'Both distinct clean-versus-archived baseline comparisons are required')
    for row in rows:
        require(row['status'] == 'computed' and row['native_frame'] == 30
                and row['time_interpolation_performed'] is False,
                'Baseline fidelity comparison is not a computed regular-frame result')
        require(row['clean_actual_time'] == cases[row['clean']]['actual_time']
                and row['archived_actual_time'] == cases[row['archived']]['actual_time']
                and row['clean_minus_archived_time'] == row['clean_actual_time'] - row['archived_actual_time'],
                'Baseline fidelity times differ from the actual case times')
        values = [row['moment_quantities'][q]['full_2D_grid']['relative_L2'] for q in QUANTITIES]
        values += [row['all_eight_stored_field_components']['full_2D_grid']['relative_L2']]
        require(all(v is not None and np.isfinite(v) and v >= 0 for v in values),
                'Invalid baseline fidelity norm')
    return sorted(rows, key=lambda row: row['clean'])


def fidelity_table(rows, output, prefix):
    lines = [r'\begin{table}[tbp]', r'\centering\small',
             r'\caption{Clean unmatched versus archived source-fluid output. Relative complete-grid $\ell^2$ differences are percentages, with the archived state as denominator. The final column is the combined norm of all eight stored field components, not an electromagnetic energy error. $\Delta t$ is the actual clean-minus-archived time. These norms are not uniform pointwise bounds.}',
             r'\label{tab:baseline-fidelity}', r'\begin{tabular}{lrrrrrr}', r'\toprule',
             r'Fluids & $\Delta t$ & $n$ & $J_z$ & $P_{xx}$ & $P_{zz}$ & Stored fields \\', r'\midrule']
    for row in rows:
        values = [100 * row['moment_quantities'][q]['full_2D_grid']['relative_L2'] for q in QUANTITIES]
        values += [100 * row['all_eight_stored_field_components']['full_2D_grid']['relative_L2']]
        label = 'One' if row['clean'].endswith('one_fluid') else 'Two'
        lines.append(label + f" & {row['clean_minus_archived_time']:.9g} & " +
                     ' & '.join(f'{value:.4f}' for value in values) + r' \\')
    lines.extend([r'\bottomrule', r'\end{tabular}', r'\end{table}', ''])
    path = output / (prefix + '-fidelity-table.tex')
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return path


def table(cases, groups, output, prefix, pic_time):
    lines = [r'\begin{table}[tbp]', r'\centering\small',
             r'\caption{Complete-grid relative $\ell^2$ errors (percent) against the archived PIC snapshot at $t=' + f'{pic_time:.10g}' + r'$. Every actual fluid output time is retained; no temporal interpolation is applied.}',
             r'\label{tab:control-errors}', r'\begin{tabular}{lrrrrr}', r'\toprule',
             r'Case & Actual $t$ & $n$ & $J_z$ & $P_{xx}$ & $P_{zz}$ \\', r'\midrule']
    for group in groups:
        for model, suffix in (('one_fluid', 'one'), ('two_fluid', 'two')):
            case = cases[group + '_' + model]
            values = [100 * case['metrics'][q]['full_2D_grid']['relative_L2'] for q in QUANTITIES]
            label = GROUP_LABELS[GROUPS.index(group)].replace('PIC-matched', 'Matched')
            lines.append(label + ', ' + suffix + f" & {case['actual_time']:.6f} & " +
                         ' & '.join(f'{value:.3f}' for value in values) + r' \\')
    lines.extend([r'\bottomrule', r'\end{tabular}', r'\end{table}', ''])
    path = output / (prefix + '-table.tex')
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('controls', 'source'), default='controls')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    groups = GROUPS if args.mode == 'controls' else ('archived',)
    prefix = 'matched-controls' if args.mode == 'controls' else 'archived-final-diagnostics'
    cases, profiles, pic_time = validate(report, args.profiles, groups)
    fidelity = fidelity_rows(report, cases) if args.mode == 'controls' else None
    plt.rcParams.update({'font.size': 8, 'axes.titlesize': 9, 'axes.labelsize': 8,
                         'xtick.labelsize': 7, 'ytick.labelsize': 7,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = metric_bars(cases, groups, args.output_dir, prefix)
    paths += profile_panels(cases, profiles, groups, args.output_dir, prefix)
    paths += qcs_panel(cases, profiles, groups, args.output_dir, prefix)
    paths.append(table(cases, groups, args.output_dir, prefix, pic_time))
    if fidelity is not None:
        paths.append(fidelity_table(fidelity, args.output_dir, prefix))
    receipt = {'mode': args.mode, 'scope': report['scope'],
               'simulation_performed_by_this_script': False,
               'script_sha256': sha(Path(__file__)),
               'input_report_sha256': sha(args.report), 'PIC_reference_actual_time': pic_time,
               'input_profiles_sha256': sha(args.profiles),
               'actual_cases_plotted': [g + '_' + m for g in groups for m in ('one_fluid', 'two_fluid')],
               'outputs': [{'filename': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths]}
    (args.output_dir / (prefix + '-figure-manifest.json')).write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'mode': args.mode, 'actual_cases': len(receipt['actual_cases_plotted']),
                      'figures': 3, 'outputs': len(paths)}))


if __name__ == '__main__':
    main()
