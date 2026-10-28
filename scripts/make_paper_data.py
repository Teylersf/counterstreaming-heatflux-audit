"""Generate the numerical summary and immutable-code execution appendix."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((ROOT / 'results/verification.json').read_text())
    assert result['all_assertions_passed']
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    for entry in result['environment']['source_files']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
        committed = subprocess.check_output(['git', 'show', commit + ':' + entry['path']], cwd=ROOT)
        assert hashlib.sha256(committed).hexdigest() == entry['sha256'], entry['path']
    provenance = json.loads((ROOT / 'data/provenance.json').read_text())
    for entry in provenance['input_decks']:
        relative = 'data/input-decks/' + entry['file']
        committed = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=ROOT)
        assert hashlib.sha256(committed).hexdigest() == entry['sha256'], relative
    source_files = list(result['environment']['source_files'])
    for name in ('profile_sensitivity.py', 'revision_data.py', 'thermal_loading.py'):
        relative = 'experiments/' + name
        digest = sha(ROOT / relative)
        committed = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=ROOT)
        assert hashlib.sha256(committed).hexdigest() == digest, relative
        source_files.append({'path': relative, 'sha256': digest})
    revision_results = ['results/profile-sensitivity.json', 'results/revision-data.json',
                        'results/thermal-loading.json', 'data/provenance-revision.json']
    revision_data = json.loads((ROOT / 'results/revision-data.json').read_text())
    assert revision_data['all_checks_passed']
    assert revision_data['revision_script_sha256'] == sha(ROOT / 'experiments/revision_data.py')
    pin = {'commit': commit, 'repository': 'https://github.com/Teylersf/counterstreaming-heatflux-audit',
           'verification_sha256': sha(ROOT / 'results/verification.json'),
           'source_files': source_files,
           'revision_outputs': [{'path': name, 'sha256': sha(ROOT / name)} for name in revision_results],
           'original_eight_group_code_bytes_unchanged': True}
    (ROOT / 'results/code-pin.json').write_text(json.dumps(pin, indent=2) + '\n', encoding='utf-8', newline='\n')
    g = result['groups']
    stability = g['finite_relaxation_stability']['finite_relaxation_mode']
    current = g['initial_current']['rows'][1]
    pressure = g['initial_pressure']['rows'][1]
    bound = g['conditioning_counterexample']['conditioned_example']
    rows = [
        ('Initial moment current at $Y=16.05d_e$', f"{100*current['relative_current_deficit']:.4f}\\% below staggered curl"),
        ('Initial $P_{zz}/p_{\\rm fl}$ at that row', f"{pressure['Pzz_ratio']:.9f}"),
        ('Exact mixture identities', 'All scalar and tensor checks pass'),
        ('Symmetry-plane continuity', 'Zero normal velocity; increasing density'),
        ('Conditioned relative-error example', f"{bound['relative_error']:.6f} $\\le$ {bound['sufficient_relative_error_bound']:.6f}"),
        ('Identical one-fluid lower moments', 'Different third moments'),
        ('Finite-relaxation mode growth', f"${stability['growth']:.9f}\\,\\omega_{{pe}}$"),
        ('Homogeneous relaxation over $300/\\omega_{pe}$', f"{100*g['isotropization_entropy']['anisotropy_remaining_fraction']:.4f}\\% anisotropy remains"),
    ]
    table = ['\\begin{table}[tbp]', '\\centering', '\\small',
             '\\caption{Selected verification outcomes. The code, data definitions and scope limits distinguish initial-state reanalysis from independent continuum tests.}',
             '\\label{tab:verification}', '\\begin{tabular}{p{.48\\linewidth}p{.43\\linewidth}}',
             '\\toprule', 'Check & Outcome \\\\', '\\midrule']
    table += [a + ' & ' + b + r' \\' for a, b in rows]
    table += ['\\bottomrule', '\\end{tabular}', '\\end{table}', '']
    (ROOT / 'paper/results-table.tex').write_text('\n'.join(table), encoding='utf-8', newline='\n')
    environment = result['environment']
    lines = [r'\section{Pinned execution record}', r'\label{app:execution}',
             'The reported calculations use the immutable code commit:',
             r'\begin{quote}\small',
             r'\href{' + pin['repository'] + '/tree/' + commit + r'}{\texttt{' + commit + '}}',
             r'\end{quote}',
             'This pins the numerical code and inputs; the final release also contains the manuscript source.',
             r'\begin{verbatim}',
             'git clone https://github.com/Teylersf/counterstreaming-heatflux-audit.git',
             'cd counterstreaming-heatflux-audit', 'git checkout ' + commit,
             'python -m pip install -r requirements.txt',
             'python experiments/fetch_data.py', 'python experiments/data_checks.py',
             'python -X utf8 experiments/verify.py', 'python -X utf8 experiments/make_figures.py',
             r'\end{verbatim}',
             'This is an author-environment execution record, not third-party certification or independent human peer review.',
             r'\begin{verbatim}', 'Started UTC: ' + environment['started_at_utc'],
             'Python: ' + environment['python'].splitlines()[0],
             'NumPy: ' + environment['numpy'], 'h5py: ' + environment['h5py']]
    lines += ['PASS: ' + name for name in g]
    lines += ['All assertions passed: true', 'Exit status: 0', r'\end{verbatim}',
              r'\begin{center}', r'\scriptsize',
              r'\begin{tabular}{@{}p{.34\linewidth}p{.63\linewidth}@{}}',
              r'\toprule', r'File & SHA-256 \\', r'\midrule']
    hash_rows = [{'path': 'results/verification.json', 'sha256': pin['verification_sha256']},
                 *pin['source_files'], *pin['revision_outputs']]
    for entry in hash_rows:
        path = entry['path'].replace('_', r'\_')
        lines += [r'\texttt{' + path + r'} & \texttt{' + entry['sha256'] + r'} \\']
    lines += [r'\bottomrule', r'\end{tabular}', r'\end{center}']
    lines += ['The full log, input provenance, derived profiles and strict verification JSON are included in the repository.',
              r'\paragraph{Revision analyses.}',
              'The original eight-group execution record is retained, with its four code files byte-identical. The pinned commit also contains the separate full-profile sensitivity, archived-fluid corroboration and conditional thermal-loading calculations.',
              r'\begin{verbatim}',
              'python experiments/profile_sensitivity.py',
              'python experiments/revision_data.py --inventory --fetch',
              '# Decode BP in a separate Linux ADIOS2 environment:',
              'python experiments/revision_data.py --decode-bp',
              'python experiments/revision_data.py --compare',
              'python experiments/thermal_loading.py',
              r'\end{verbatim}',
              'The BP reader used ADIOS2 2.13.0.1001 and NumPy 2.3.5 under Linux Python 3.12.3. Portable reader setup and exact member/export hashes are provided in the data documentation. No native deposited-current comparison, full-archive checksum verification, matched-state reconnection rerun or sheet eigenanalysis is claimed.', '']
    (ROOT / 'paper/sections/execution.tex').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps({'code_commit': commit, 'groups': len(g), 'generated_table_rows': len(rows)}))


if __name__ == '__main__':
    main()
