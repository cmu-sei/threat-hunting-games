import os.path
import pytest
from GHOSTSConnection import GHOSTSConnection


@pytest.fixture(scope='session')
def local(pytestconfig) -> bool:
    if pytestconfig.getoption('local'):
        return True
    else:
        return False


def test_api_connection(local):
    ghosts_connect = GHOSTSConnection(0, 0, local_session=local, test_session=True)
    try:
        assert ghosts_connect.confirm_connection() == True
    finally:
        ghosts_connect.end_simulation()


# Test that a GHOSTSConnection object is correctly created
def test_sim_file_creation(local):
    ghosts_connect = GHOSTSConnection(num_attackers=0, num_defenders=0, local_session=local, test_session=True)
    try:
        assert os.path.exists(ghosts_connect.sim_file_path_full)
    finally:
        ghosts_connect.end_simulation()


# Confirm that when the sim file is created that it is deleted when the option is selected
def test_sim_file_deletion(local):
    ghosts_connect = GHOSTSConnection(num_attackers=0, num_defenders=0, local_session=local, test_session=True)
    ghosts_connect.end_simulation()
    assert not os.path.exists(ghosts_connect.sim_file_path_full)


# Test that the data is correctly being written to the file
def test_sim_file_write(local):
    ghosts_connect = GHOSTSConnection(0, 0, local_session=local, test_session=True)
    ghosts_connect.logger_sim.debug('TEST CASE')
    with open(ghosts_connect.sim_file_loc) as f:
        line = ""
        for line in f:
            pass
        try:
            assert line.__contains__('TEST CASE')
        finally:
            ghosts_connect.end_simulation()
            f.close()


# Test that an attacker machine is created via method call with the correct specifications
def test_attacker_machine_created(local):
    ghosts_connect = GHOSTSConnection(num_defenders=0, num_attackers=1, local_session=local, test_session=True)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 1
    ghosts_connect.end_simulation()

# Test that a defender machine is created via method call with the correct specifications
def test_defender_machine_created(local):
    ghosts_connect = GHOSTSConnection(num_defenders=1, num_attackers=0, local_session=local, test_session=True)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 1
    ghosts_connect.end_simulation()
    assert len(machine_list) == 0


def test_multiple_machines_created(local):
    ghosts_connect = GHOSTSConnection(num_defenders=1, num_attackers=1, local_session=local, test_session=True)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 2
    ghosts_connect.end_simulation()
    assert len(machine_list) == 0

# ACTION TESTING PORTION

'''
# Check that the privilege matrix is correctly updated after an action
def test_attacker_gained_privileges(local):
    ghosts_connect = GHOSTSConnection(num_attackers=2, num_defenders=2, local_session=local, test_session=True)
    machinegroup_machines = ghosts_connect.list_machinegroup_machines()
    attacker_num = random.randint(0, len(machinegroup_machines['Attackers']) - 1)
    defender_num = random.randint(0, len(machinegroup_machines['Defenders']) - 1)
'''


