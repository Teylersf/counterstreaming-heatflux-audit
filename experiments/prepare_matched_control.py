"""Prepare four legacy-Gkeyll control jobs without launching any solver.

The full-run protocol retains the posted tEnd600/nFrame60 controls. A native
stop request after regular frame30 is handled separately by the run operator.
All original physical and numerical settings remain in the byte-pinned deck.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DECKS = {
    1: 'a716823d81a8abdb119326537b2289e819381683919803a35c50c24765884a7d',
    2: 'f9cc244a6e52522d03aa1a127a1f79ff35506b0f9b98b1abe8973a3c6ff4bf69',
}
COMPONENTS = ['rho','rho_ux','rho_uy','rho_uz','Mxx','Mxy','Mxz','Myy','Myz','Mzz']

def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()

def checked_write(path,content):
    if path.exists():
        if path.read_bytes()!=content:
            raise ValueError('Refusing to overwrite different prepared input: '+str(path))
    else:
        path.write_bytes(content)

def main():
    if not __debug__:
        raise RuntimeError('Do not run preparation with Python -O; validation assertions are required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-metadata',type=Path,required=True)
    parser.add_argument('--aggregate-binary',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    metadata=json.loads(args.export_metadata.read_text(encoding='utf-8'))
    assert metadata['archive']['full_archive_checksum_verified'] is True
    assert metadata['script_sha256']==sha256(ROOT/'experiments/export_pic_moments.py'), 'Exporter source changed'
    grid=metadata['grid']
    assert grid['shape_y_x']==[640,480]
    assert grid['bounds_x']==[-24.,24.] and grid['bounds_y']==[-32.,32.]
    assert grid['spacing_x_y']==[.1,.1] and grid['moment_offset_x_y']==[.5,.5]
    assert metadata['electron_mass']==1 and metadata['electron_charge']==-1
    initial_rows=[s for s in metadata['snapshots'] if s['TIME']==0]
    assert len(initial_rows)==1, 'A unique t0 snapshot is required'
    initial=initial_rows[0]
    assert initial['ITER']==0 and initial['aggregate_moment_members']==20
    assert initial['minimum_density']>0 and initial['minimum_pressure_eigenvalue']>0
    expected_rows=[item for item in metadata['binary_outputs']
                   if item['filename']=='aggregate-pic-t0.f64']
    assert len(expected_rows)==1, 'A unique aggregate t0 binary is required'
    expected=expected_rows[0]
    assert expected['shape']==[640,480,10] and expected['components']==COMPONENTS
    assert expected['dtype']=='<f8' and expected['order']=='C'
    assert args.aggregate_binary.stat().st_size==expected['bytes']==24576000
    assert sha256(args.aggregate_binary)==expected['sha256']
    helper=ROOT/'experiments/matched_initializer.lua'
    records=[]
    for species in (1,2):
        original=ROOT/f'data/input-decks/input_{species}-e-Fluid.lua'
        assert sha256(original)==EXPECTED_DECKS[species], 'Posted deck changed'
        for matched in (False,True):
            case=f'{species}-fluid-'+('aggregate-matched' if matched else 'unmatched')
            directory=args.output_dir/case
            directory.mkdir(parents=True,exist_ok=True)
            checked_write(directory/'posted-input.lua',original.read_bytes())
            wrapper='-- Prepared control wrapper; original posted deck is unchanged.\n'
            if matched:
                checked_write(directory/'matched_initializer.lua',helper.read_bytes())
                binary=directory/'aggregate-pic-t0.f64'
                if binary.exists():
                    assert sha256(binary)==expected['sha256'], 'Different existing aggregate binary'
                else:
                    shutil.copyfile(args.aggregate_binary,binary)
                wrapper+=('dofile("matched_initializer.lua").install {\n'
                          '   aggregateFile = "aggregate-pic-t0.f64",\n'
                          f'   expectedSpecies = {species},\n'+'}\n')
            wrapper+='dofile("posted-input.lua")\n'
            checked_write(directory/'case.lua',wrapper.encode('utf-8'))
            record={'case':case,'species':species,'aggregate_matched':matched,
                    'original_deck_sha256':EXPECTED_DECKS[species],
                    'wrapper_sha256':sha256(directory/'case.lua'),
                    'original_deck_is_byte_identical':True,
                    'time_controls':{'tEnd':600,'nFrame':60},
                    'initialization_intervention':'Species.init only' if matched else 'none',
                    'field_intervention':'none','equation_or_closure_intervention':'none',
                    'PIC_tag_matching_claimed':False,'solver_executed':False,
                    'matched_initializer_sha256':sha256(helper) if matched else None,
                    'aggregate_binary_sha256':expected['sha256'] if matched else None}
            checked_write(directory/'prepared-case.json',(json.dumps(record,indent=2)+'\n').encode('utf-8'))
            records.append(record)
    manifest={'status':'prepared_not_executed','protocol':'experiments/matched-control-plan.md',
              'export_metadata_sha256':sha256(args.export_metadata),
              'preparer_sha256':sha256(Path(__file__)),
              'cases':records,
              'required_before_run':'Conforming runtime, saved-initial-state checks and measured cost report.',
              'comparison_time':'Regular frame30 actual metadata; distinguish final forced stop output.'}
    checked_write(args.output_dir/'prepared-controls.json',(json.dumps(manifest,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'status':manifest['status'],'case_names':[r['case'] for r in records],
                      'output_dir':str(args.output_dir)},indent=2))

if __name__=='__main__':main()
