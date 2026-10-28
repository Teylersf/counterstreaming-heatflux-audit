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
    pin = {'commit': commit, 'repository': 'https://github.com/Teylersf/counterstreaming-heatflux-audit',
           'verification_sha256': sha(ROOT / 'results/verification.json'),
           'source_files': result['environment']['source_files']}
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
             'The reported calculations use the immutable code commit',
             r'\href{' + pin['repository'] + '/tree/' + commit + r'}{\texttt{' + commit + '}}.',
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
              'Verification JSON SHA-256:', r'\begin{quote}\footnotesize\ttfamily',
              pin['verification_sha256'], r'\end{quote}']
    for entry in pin['source_files']:
        path = entry['path'].replace('_', r'\_')
        lines += [r'\noindent\texttt{' + path + '} SHA-256:',
                  r'\begin{quote}\footnotesize\ttfamily', entry['sha256'], r'\end{quote}']
    lines += ['The full log, input provenance, derived profiles and strict verification JSON are included in the repository.', '']
    (ROOT / 'paper/sections/execution.tex').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps({'code_commit': commit, 'groups': len(g), 'generated_table_rows': len(rows)}))


if __name__ == '__main__':
    main()
