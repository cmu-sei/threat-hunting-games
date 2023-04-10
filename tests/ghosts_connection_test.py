import os.path

import pytest
from GHOSTSConnection import GHOSTSConnection
from datetime import datetime

def test_api_connection():
    ghosts_connect = GHOSTSConnection(1, 1)
    assert ghosts_connect.confirm_connection()


# Test that a GHOSTSConnection object is correctly created
def test_sim_file_creation():
    ghosts_connect = GHOSTSConnection(num_attackers=1, num_defenders=1)
    assert os.path.exists(f'/var/spool/threat-hunting-games/{ghosts_connect.SIMULATION_ID}_{str(datetime.now().strftime("%d_%m"))}')
    ghosts_connect.end_simulation(save_file=False)


# Test that the data is correctly being written to the file
def test_sim_file_write():
    ghosts_connect = GHOSTSConnection(1, 1)
    ghosts_connect.logger_sim.debug('TEST CASE')
    with open(f'/var/spool/threat-hunting-games/{ghosts_connect.SIMULATION_ID}_{str(datetime.now().strftime("%d_%m"))}') as f:
        for line in f:
            pass
        assert line == '[Debug] TEST CASE'
    ghosts_connect.end_simulation(save_file=False)


# Test that an attacker machine is created via method call with the correct specifications
def test_attacker_machine_created():
    ghosts_connect = GHOSTSConnection(num_defenders=0, num_attackers=1)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 1
    machine_group_lists = ghosts_connect.list_machine_groups()
    assert len(machine_group_lists['Attackers']) == 1
    ghosts_connect.end_simulation(save_file=False)


# Test that a defender machine is created via method call with the correct specifications
def test_defender_machine_created():
    ghosts_connect = GHOSTSConnection(num_defenders=1, num_attackers=0)
    machine_list = ghosts_connect.list_machines()
    assert len(machine_list) == 1
    machine_group_lists = ghosts_connect.list_machine_groups()
    assert len(machine_group_lists['Defenders']) == 1
    ghosts_connect.end_simulation(save_file=False)




