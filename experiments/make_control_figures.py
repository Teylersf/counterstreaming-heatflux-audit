"""Plot verified archived or completed control metrics; never invent pending runs.

Default controls mode requires all six archived/clean/matched cases. Source
mode is only for the actual archived outputs and uses different output names.
The input profile hash and every plotted profile norm are checked first.
Explicit subset mode additionally binds all four native outcomes and saved
histories; its figures describe numerical endpoints, not physical validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

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
GROUP_LABELS = ('Archived source', 'Clean baseline', 'Aggregate-matched')
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


def validate(report, profiles_path, groups, required_cases=None):
    require(report.get('all_actual_cases_passed') is True,
            'Comparison report must pass all actual cases before plotting')
    require(report.get('profile_export_sha256') == sha(profiles_path),
            'Profile CSV hash does not match comparison report')
    cases = {case['id']: case for case in report['cases']}
    require(len(cases) == len(report['cases']), 'Duplicate case identifiers')
    pic_time = report['PIC_reference']['snapshot']['TIME']
    require(np.isfinite(pic_time), 'Nonfinite PIC reference time')
    required = required_cases if required_cases is not None else [group + '_' + model for group in groups
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


def metric_bars(cases, groups, output, prefix, subset=False):
    fig, axes = plt.subplots(2, 2, figsize=(6.7, 4.9), layout='constrained')
    if subset:
        fig.suptitle('Numerical endpoints; saved-state admissibility is reported separately', fontsize=8)
    x = np.arange(len(groups))
    for ax, quantity, symbol in zip(axes.flat, QUANTITIES, SYMBOLS):
        for offset, model, label in ((-.18, 'one_fluid', 'One fluid'),
                                     (.18, 'two_fluid', 'Two fluids')):
            selected = [i for i, group in enumerate(groups)
                        if cases[group + '_' + model].get('status') == 'compared']
            require(subset or len(selected) == len(groups), 'A strict plot case is missing')
            values = [100 * cases[groups[i] + '_' + model]['metrics'][quantity]
                      ['full_2D_grid']['relative_L2'] for i in selected]
            bars = ax.bar(x[selected] + offset, values, width=.34, color=COLORS[model],
                          label=label, zorder=3)
            ax.bar_label(bars, fmt='%.2f', padding=3, fontsize=6.8)
            for i in set(range(len(groups))) - set(selected):
                ax.text(x[i] + offset, .035, 'Not compared', rotation=90,
                        ha='center', va='bottom', fontsize=6.3, color='#777777',
                        transform=ax.get_xaxis_transform())
        ax.set_title(symbol)
        ax.set_xticks(x, [GROUP_LABELS[GROUPS.index(group)] for group in groups])
        ax.set_ylabel('Full-grid relative L2 error (%)')
        ax.set_ylim(bottom=0, top=ax.get_ylim()[1] * 1.17)
        ax.grid(axis='y', alpha=.2, zorder=0)
    axes.flat[0].legend(frameon=False, fontsize=7)
    return save(fig, output, prefix + '-errors',
                'Full-grid moment errors against the archived PIC snapshot')


def profile_panels(cases, profiles, groups, output, prefix, subset=False):
    fig, axes = plt.subplots(2, 2, figsize=(6.7, 5.15))
    if subset:
        fig.suptitle('Numerical endpoints; saved-state admissibility is reported separately', fontsize=8)
    y = profiles['raw_y'] + 32
    plotted_groups = [g for g in groups if g != 'archived'] or ['archived']
    for ax, quantity, symbol, unit in zip(axes.flat, QUANTITIES, SYMBOLS, UNITS):
        ax.plot(y, profiles['PIC_' + quantity], color='#222222', lw=1.4, label='PIC')
        for group in plotted_groups:
            for model, model_label in (('one_fluid', 'one fluid'), ('two_fluid', 'two fluids')):
                if cases[group + '_' + model].get('status') != 'compared':
                    require(subset, 'A strict profile case is missing')
                    continue
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
    fig.subplots_adjust(left=.09, right=.985, top=.89 if subset else .95, bottom=.17,
                        hspace=.36, wspace=.28)
    return save(fig, output, prefix + '-profiles',
                'Full-domain x-averaged moment profiles at recorded comparison times')


def qcs_panel(cases, profiles, groups, output, prefix, subset=False):
    fig, ax = plt.subplots(figsize=(6.7, 3.0))
    if subset:
        fig.suptitle('Eligible numerical endpoints; no physical trajectory validation', fontsize=8)
    y = profiles['raw_y'] + 32
    ax.plot(y, profiles['PIC_qCSxxx'], color='#222222', lw=1.4,
            label='PIC tags')
    for group in groups:
        name = group + '_two_fluid'
        if cases[name].get('status') != 'compared':
            require(subset, 'A strict contribution case is missing')
            continue
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
    fig.subplots_adjust(left=.11, right=.985, top=.78 if subset else .86, bottom=.28)
    return save(fig, output, prefix + '-qcs',
                'Decomposition-dependent counter-streaming contribution from first and second moments')


def fidelity_rows(report, cases, subset=False):
    rows = report.get('clean_unmatched_vs_archived_source', [])
    expected = {('baseline_one_fluid', 'archived_one_fluid'),
                ('baseline_two_fluid', 'archived_two_fluid')}
    require(len(rows) == 2 and {(r.get('clean'), r.get('archived')) for r in rows} == expected,
            'Both distinct clean-versus-archived baseline comparisons are required')
    rows = [r for r in rows if r.get('status') == 'computed'] if subset else rows
    require(rows, 'No actual clean-versus-archived endpoint comparison')
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
             r'\caption{Clean unmatched versus archived source-fluid output at eligible endpoints. Relative complete-grid $\ell^2$ differences are percentages, with the archived state as denominator. The final column is the combined norm of all eight stored field components, not an electromagnetic energy error. $\Delta t$ is the actual clean-minus-archived time. These norms are neither uniform pointwise bounds nor trajectory-admissibility certificates.}',
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


def table(cases, groups, output, prefix, pic_time, outcomes=None):
    lines = [r'\begin{table}[tbp]', r'\centering\small',
             r'\caption{Numerical endpoint complete-grid relative $\ell^2$ errors (percent) against the archived PIC snapshot at $t=' + f'{pic_time:.10g}' + r'$. Every actual fluid output time is retained; no temporal interpolation is applied. Endpoint agreement does not validate a physical trajectory. Withheld entries are not zero errors.}',
             r'\label{tab:control-errors}', r'\begin{tabular}{lrrrrr}', r'\toprule',
             r'Case & Actual $t$ & $n$ & $J_z$ & $P_{xx}$ & $P_{zz}$ \\', r'\midrule']
    for group in groups:
        for model, suffix in (('one_fluid', 'one'), ('two_fluid', 'two')):
            case = cases[group + '_' + model]
            label = GROUP_LABELS[GROUPS.index(group)].replace('Aggregate-matched', 'Matched')
            if case.get('status') == 'compared':
                values = [100 * case['metrics'][q]['full_2D_grid']['relative_L2'] for q in QUANTITIES]
                lines.append(label + ', ' + suffix + f" & {case['actual_time']:.6f} & " +
                             ' & '.join(f'{value:.3f}' for value in values) + r' \\')
            else:
                require(outcomes is not None and case['id'] in outcomes, 'A strict table case is missing')
                stamp = outcomes[case['id']].get('actual_regular30_time')
                text = f'{stamp:.6f}' if stamp is not None else '---'
                lines.append(label + ', ' + suffix + r' (withheld) & ' + text +
                             r' & --- & --- & --- & --- \\')
    lines.extend([r'\bottomrule', r'\end{tabular}', r'\end{table}', ''])
    path = output / (prefix + '-table.tex')
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return path


def outcome_table(outcomes, output, prefix):
    lines = [r'\begin{table}[tbp]', r'\centering\small',
             r'\caption{Native outcomes and saved-state admissibility. Endpoint eligibility uses the unchanged initial/final covariance checks. Non-PSD counts are population--snapshot instances out of $31N_s$, not distinct spatial cells or every accepted timestep. A numerical endpoint contrast does not validate a physical trajectory. Withheld errors are not zero errors.}',
             r'\label{tab:control-outcomes}', r'\begin{tabular}{lrrrr}', r'\toprule',
             r'Case & Actual $t$ & Endpoint & Non-PSD samples & Minimum $\lambda(P_s)$ \\', r'\midrule']
    for group in ('baseline', 'matched'):
        for model, suffix in (('one_fluid', 'one'), ('two_fluid', 'two')):
            item = outcomes[group + '_' + model]
            label = ('Unmatched' if group == 'baseline' else 'Matched') + ', ' + suffix
            stamp = item.get('actual_regular30_time')
            stamp_text = f'{stamp:.6f}' if stamp is not None else '---'
            eligible = item.get('endpoint_metrics_eligible')
            require(eligible in (True, False), 'Unresolved endpoint eligibility')
            history = item['saved_snapshot_diagnostic']
            require(history['status'] == 'completed_regular0_through30', 'Unresolved saved-state scan')
            populations = [v for k, v in history['summary'].items() if k.startswith('population')]
            require(len(populations) == item['population_count'], 'Saved-state population count differs')
            count = sum(p['saved_snapshots_not_PSD'] for p in populations)
            total = sum(p['saved_snapshots_scanned'] for p in populations)
            minimum = min(p['minimum_pressure_eigenvalue_over_saved_snapshots'] for p in populations)
            require(total == 31 * item['population_count'] and np.isfinite(minimum), 'Invalid saved-state summary')
            minimum_text = f'{minimum:.6g}'
            if 'e' in minimum_text:
                mantissa, exponent = minimum_text.split('e')
                minimum_text = mantissa + r'\times10^{' + str(int(exponent)) + '}'
            lines.append(label + ' & ' + stamp_text + ' & ' + ('eligible' if eligible else 'rejected') +
                         f' & {count}/{total} & $' + minimum_text + '$' + r' \\')
    lines.extend([r'\bottomrule', r'\end{tabular}', r'\end{table}', ''])
    path = output / (prefix + '-outcomes-table.tex')
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return path


def pressure_history_plot(outcomes, scan_directory, output, prefix):
    fig, axes = plt.subplots(1, 2, figsize=(6.7, 3.15), layout='constrained')
    for ax, model, title in zip(axes, ('one_fluid', 'two_fluid'), ('One fluid', 'Two fluids')):
        all_times = [0.0]
        for group, label in (('baseline', 'Unmatched'), ('matched', 'Aggregate-matched')):
            item = outcomes[group + '_' + model]
            entry = item['saved_snapshot_diagnostic']
            name = entry['filename']
            require(Path(name).name == name, 'Saved-scan filename must be portable')
            scan_path = scan_directory / name
            require(sha(scan_path) == entry['sha256'], 'Saved-scan hash changed before plotting')
            scan = json.loads(scan_path.read_text(encoding='utf-8'))
            require(scan['native_case'] == item['native_case'] and len(scan['frames']) == 31
                    and [f['frame'] for f in scan['frames']] == list(range(31)),
                    'Saved-scan case/frame identity differs')
            populations = ['population' + str(i) for i in range(1, item['population_count'] + 1)]
            times, minima, undefined_times = [], [], []
            for frame, pinned in zip(scan['frames'], entry['actual_saved_times']):
                require(frame['frame'] == pinned['frame'] and frame['actual_time'] == pinned['actual_time'],
                        'Saved-scan times differ from the bound outcome record')
                all_times.append(frame['actual_time'])
                values = [frame[p].get('minimum_pressure_eigenvalue') for p in populations]
                defined = all(v is not None and np.isfinite(v) for v in values)
                defined = defined and all(frame[p]['covariance_undefined_cell_count'] == 0
                                          and frame[p]['nonfinite_conserved_cell_count'] == 0 for p in populations)
                if defined:
                    times.append(frame['actual_time']); minima.append(min(values))
                else:
                    undefined_times.append(frame['actual_time'])
            color = '#777777' if group == 'baseline' else COLORS[model]
            ax.scatter(times, minima, marker='o' if group == 'baseline' else 'x',
                       s=16, color=color, linewidths=.9, label=label, zorder=3)
            for stamp in undefined_times:
                ax.text(stamp, .98, 'Undefined', rotation=90, ha='center', va='top',
                        fontsize=6, color=color, transform=ax.get_xaxis_transform())
        ax.axhline(0, color='#a63333', lw=.8)
        ax.set(title=title, xlabel=r'Actual saved $t\omega_{pe}$',
               ylabel=r'$\min_{s,\mathrm{cells}}\lambda(P_s)/(m_e n_0 c^2)$', xlim=(-3, max(all_times) + 3))
        ax.grid(alpha=.18)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 2), useMathText=True)
        ax.legend(frameon=False, fontsize=7)
    return save(fig, output, prefix + '-pressure-history',
                'Pressure covariance minima at actual regular saved snapshots; no interpolation or continuous-admissibility claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--mode', choices=('controls', 'source', 'numerical-endpoint-subset'), default='controls')
    parser.add_argument('--admissibility', type=Path,
                        help='Required complete bound outcome/history record for explicit numerical-endpoint-subset mode')
    parser.add_argument('--decoding-receipt', type=Path,
                        default=ROOT / 'results/gkeyll-control-decoding.json')
    parser.add_argument('--scan-directory', type=Path,
                        default=ROOT / 'results/gkeyll-saved-state-scans',
                        help='Bound compact scans used only by explicit numerical subset mode')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    subset = args.mode == 'numerical-endpoint-subset'
    subset_state, outcomes, required_cases = None, None, None
    if subset:
        require(args.admissibility is not None, 'Explicit subset mode requires an admissibility record')
        sys.path.insert(0, str(ROOT / 'scripts'))
        from make_paper_data import validate_numerical_subset_evidence
        subset_state = validate_numerical_subset_evidence(args.report, [args.decoding_receipt], args.admissibility)
        require(subset_state['numerical_endpoint_subset_evidence_bound'] is True
                and subset_state['all_four_native_outcomes_completed'] is True
                and subset_state['all_four_saved_snapshot_scans_complete'] is True
                and subset_state['valid_endpoint_pair_ids'],
                'All four outcomes/scans and an actual eligible endpoint pair are required')
        outcome_record = json.loads(args.admissibility.read_text(encoding='utf-8'))
        outcomes = {c['analysis_case_id']: c for c in outcome_record['native_outcomes']}
        expected_native_ids = {group + '_' + model for group in ('baseline', 'matched')
                               for model in ('one_fluid', 'two_fluid')}
        require(len(outcome_record['native_outcomes']) == 4 and set(outcomes) == expected_native_ids,
                'All four distinct native outcomes are required')
        require(all(c.get('native_outcome_terminal') is True
                    and c.get('collector_decision_resolved') is True
                    and c.get('saved_snapshot_diagnostic_resolved') is True
                    and isinstance(c.get('endpoint_metrics_eligible'), bool)
                    for c in outcomes.values()), 'An endpoint decision or saved-history diagnostic is unresolved')
        required_cases = ['archived_one_fluid', 'archived_two_fluid'] + sorted(subset_state['eligible_endpoint_analysis_case_ids'])
        require({c['id'] for c in report['cases'] if c.get('status') == 'compared'} == set(required_cases),
                'Compared cases differ from eligible endpoints plus archived references')
    groups = ('archived',) if args.mode == 'source' else GROUPS
    prefix = {'controls': 'matched-controls', 'source': 'archived-final-diagnostics',
              'numerical-endpoint-subset': 'numerical-endpoints'}[args.mode]
    cases, profiles, pic_time = validate(report, args.profiles, groups, required_cases)
    fidelity = fidelity_rows(report, cases, subset) if args.mode != 'source' else None
    plt.rcParams.update({'font.size': 8, 'axes.titlesize': 9, 'axes.labelsize': 8,
                         'xtick.labelsize': 7, 'ytick.labelsize': 7,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'pdf.fonttype': 42})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = metric_bars(cases, groups, args.output_dir, prefix, subset)
    paths += profile_panels(cases, profiles, groups, args.output_dir, prefix, subset)
    paths += qcs_panel(cases, profiles, groups, args.output_dir, prefix, subset)
    paths.append(table(cases, groups, args.output_dir, prefix, pic_time, outcomes))
    if fidelity is not None:
        paths.append(fidelity_table(fidelity, args.output_dir, prefix))
    if subset:
        paths.append(outcome_table(outcomes, args.output_dir, prefix))
        paths += pressure_history_plot(outcomes, args.scan_directory, args.output_dir, prefix)
    receipt = {'mode': args.mode, 'scope': report['scope'],
               'simulation_performed_by_this_script': False,
               'script_sha256': sha(Path(__file__)),
               'input_report_sha256': sha(args.report), 'PIC_reference_actual_time': pic_time,
               'input_profiles_sha256': sha(args.profiles),
               'actual_cases_plotted': required_cases if subset else [g + '_' + m for g in groups for m in ('one_fluid', 'two_fluid')],
               'numerical_endpoint_subset_state': subset_state,
               'admissibility_record_sha256': sha(args.admissibility) if subset else None,
               'physical_trajectory_validation_claimed': False,
               'outputs': [{'filename': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths]}
    (args.output_dir / (prefix + '-figure-manifest.json')).write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'mode': args.mode, 'actual_cases': len(receipt['actual_cases_plotted']),
                      'figures': 4 if subset else 3, 'outputs': len(paths)}))


if __name__ == '__main__':
    main()
