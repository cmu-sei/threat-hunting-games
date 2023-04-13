import os.path

import pytest
from GHOSTSConnection import GHOSTSConnection
from datetime import datetime


@pytest.fixture(scope='session')
def local(pytestconfig) -> bool:
    if pytestconfig.getoption('local'):
        return True
    else:
        return False


def test_api_connection(local):
    ghosts_connect = GHOSTSConnection(1, 1, local_session=local)
    assert ghosts_connect.confirm_connection()
    ghosts_connect.end_simulation(save_file=False)


# Test that a GHOSTSConnection object is correctly created
def test_sim_file_creation(local):
    ghosts_connect = GHOSTSConnection(num_attackers=1, num_defenders=1, local_session=local)
    assert os.path.exists(ghosts_connect.sim_file_loc)
    ghosts_connect.end_simulation(save_file=False)


# Test that the data is correctly being written to the file
def test_sim_file_write(local):
    ghosts_connect = GHOSTSConnection(1, 1, local_session=local)
    ghosts_connect.logger_sim.debug('TEST CASE')
    with open(ghosts_connect.sim_file_loc) as f:
        for line in f:
            pass
        assert line.__contains__('TEST CASE')
    ghosts_connect.end_simulation(save_file=False)


# Test that an attacker machine is created via method call with the correct specifications
def test_attacker_machine_created(local):
    ghosts_connect = GHOSTSConnection(num_defenders=0, num_attackers=1, local_session=local)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 1
    machine_group_lists = ghosts_connect.list_machinegroup_machines()
    assert len(machine_group_lists['Attackers']) == 1
    ghosts_connect.end_simulation(save_file=False)


# Test that a defender machine is created via method call with the correct specifications
def test_defender_machine_created(local):
    ghosts_connect = GHOSTSConnection(num_defenders=1, num_attackers=0, local_session=local)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 1
    machine_group_lists = ghosts_connect.list_machinegroup_machines()
    assert len(machine_group_lists['Defenders']) == 1
    ghosts_connect.end_simulation(save_file=False)

@pytest.mark.skip
def test_multiple_machines_created(local):
    ghosts_connect = GHOSTSConnection(num_defenders=1, num_attackers=1, local_session=local)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 2
    machine_group_lists = ghosts_connect.list_machinegroup_machines()
    assert len(machine_group_lists['Defenders']) == 1
    assert len(machine_group_lists['Attackers']) == 1
    ghosts_connect.end_simulation(save_file=False)





