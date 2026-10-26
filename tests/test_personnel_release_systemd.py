from copy import deepcopy
from pathlib import Path
import pytest
from scripts import personnel_release_systemd as service

SHA='a'*40
OLD='/opt/projects/corpsite/releases/'+'b'*40


def fixture(tmp_path):
    root=tmp_path/'systemd';state={}
    for unit in service.UNITS:
        folder=root/(unit+'.d');folder.mkdir(parents=True)
        files=[]
        for name in ('90-frontend-release.conf','zzzz-070c423e-release.conf','zzzzzz-12985ba1-release.conf'):
            path=folder/name;path.write_text('existing '+name);files.append(str(path))
        state[unit]={'paths':files,'directory':OLD,'argv':['/old/program']}
    return root,state


def test_real_priority_conflict_is_detected_and_last_dropin_fixes_both_services(tmp_path):
    root,state=fixture(tmp_path);inspect=lambda unit:deepcopy(state[unit])
    plan=service.prepare(SHA,inspect=inspect,config_root=root)
    before={p:Path(p).read_bytes() for e in plan['units'].values() for p in e['files']}
    service.install(plan,config_root=root)
    # Former 90-personnel plan leaves old effective settings; never accept it.
    with pytest.raises(RuntimeError,match='priority mismatch'):
        service.verify(plan,inspect=inspect,config_root=root)
    for unit,entry in plan['units'].items():
        assert Path(entry['target']).name>'zzzzzz-12985ba1-release.conf'
        state[unit]={'paths':sorted(entry['original']['paths']+[entry['target']]),
            'directory':entry['desired']['directory'],'argv':entry['desired']['argv']}
    assert service.verify(plan,inspect=inspect,config_root=root)['verified']
    # Correct directory alone does not prove correct executable/arguments.
    state[service.UNITS[1]]['argv']=['/usr/bin/node','/old/next','start']
    with pytest.raises(RuntimeError,match='ExecStart mismatch'):
        service.verify(plan,inspect=inspect,config_root=root)
    service.remove(plan,config_root=root)
    assert all(Path(p).read_bytes()==body for p,body in before.items())
    state={u:e['original'] for u,e in plan['units'].items()}
    assert service.verify(plan,original=True,inspect=lambda u:state[u],config_root=root)['verified']


def test_install_rejects_source_drift_and_never_overwrites_existing_file(tmp_path):
    root,state=fixture(tmp_path);plan=service.prepare(SHA,inspect=lambda u:state[u],config_root=root)
    path=Path(state[service.UNITS[0]]['paths'][-1]);path.write_text('edited by another operator')
    with pytest.raises(RuntimeError,match='Existing drop-in changed'):service.install(plan,config_root=root)
    assert not any(Path(e['target']).exists() for e in plan['units'].values())


def test_remove_refuses_changed_new_file_and_preserves_other_service(tmp_path):
    root,state=fixture(tmp_path);plan=service.prepare(SHA,inspect=lambda u:state[u],config_root=root)
    service.install(plan,config_root=root)
    target=Path(plan['units'][service.UNITS[0]]['target']);target.write_text('external edit')
    with pytest.raises(RuntimeError,match='modified release'):service.remove(plan,config_root=root)
    assert all(Path(e['target']).exists() for e in plan['units'].values())


def test_install_does_not_overwrite_existing_target_or_partially_write_other_service(tmp_path):
    root,state=fixture(tmp_path);plan=service.prepare(SHA,inspect=lambda u:state[u],config_root=root)
    target=Path(plan['units'][service.UNITS[1]]['target']);target.write_text('preexisting configuration')
    with pytest.raises(RuntimeError,match='overwrite'):service.install(plan,config_root=root)
    assert target.read_text()=='preexisting configuration'
    assert not Path(plan['units'][service.UNITS[0]]['target']).exists()


def test_execstart_parses_systemctl_without_ignoring_wrong_arguments():
    assert service.exec_argv('{ path=/usr/bin/node ; argv[]=/usr/bin/node /new/next start --port 3000 ; ignore_errors=no ; pid=0 ; }')==['/usr/bin/node','/new/next','start','--port','3000']
    with pytest.raises(RuntimeError):service.exec_argv('{ path=/old ; argv[]=/new ; }')
