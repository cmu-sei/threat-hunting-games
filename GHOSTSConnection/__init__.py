import os
import sys

from requests import get, post, put, delete
from uuid import uuid4
import logging
import json
from datetime import datetime, timezone
import random

logging.basicConfig(filename='/var/log/threat-hunting-games/GHOSTSConnection.log',
                    format='%(asctime)s %(filename)8s: [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M')
logger_ghosts = logging.getLogger(__name__)
logger_ghosts.setLevel(logging.DEBUG)


class GHOSTSConnection:
    SIMULATION_ID = ''
    NUM_ATTACKERS = 0
    NUM_DEFENDERS = 0
    defender_Machine_Ids = []
    attacker_Machine_Ids = []
    # Matrix reads { 'system_id' : ['Machine with admin', 'machine2 with admin']
    admin_matrix = {}
    num_current_groups = 0
    CONN_URL = 'ghosts-api:5000'

    def __init__(self, num_attackers: int = 1, num_defenders: int = 1, local_session: str = False):
        # If not being run in the threat-hunting-games container then use localhost address and port
        if local_session:
            self.CONN_URL = 'localhost:8080'
        self.NUM_ATTACKERS = num_attackers
        self.NUM_DEFENDERS = num_defenders
        self.SIMULATION_ID = str(uuid4())[0:8]
        self.SESSION_IP = ".".join(map(str, (random.randint(0,255) for _ in range(4))))
        with open(f'/var/spool/threat-hunting-games/{self.SIMULATION_ID}_{str(datetime.now().strftime("%d_%m"))}.txt') as sim_file:
            sim_file.write(f"TIME OF SIMULATION: {datetime.now().time().strftime('%H:%M:%S')}")
            sim_file.write(f'NUMBER OF ATTACKERS: {self.NUM_ATTACKERS}')
            sim_file.write(f'NUMBER OF DEFENDERS: {self.NUM_DEFENDERS}')
        logging.basicConfig(filename=f'/var/spool/threat-hunting-games/{self.SIMULATION_ID}_{str(datetime.now().strftime("%d_%m"))}',
                            format='[%(levelname)s] %(message)s',
                            datefmt='%Y-%m-%d %H:%M')
        self.logger_sim = logging.getLogger(__name__)
        self.logger_sim.setLevel(logging.DEBUG)
        self.create_machinegroup('Attackers')
        self.create_machinegroup('Defenders')
        for a in range(0, self.NUM_ATTACKERS):
            self.logger_sim.info(f'Creating Attacker_{a}')
            ret_dict = self.create_machine(f'Attacker{a}', 'Attacker')
            if ret_dict[0] is 'None':
                self.logger_sim.error(f'Unable to create Attacker_{a}.')
        for d in range(0, self.NUM_DEFENDERS):
            self.logger_sim.info(f'Creating Defender_{d}')
            ret_dict = self.create_machine(f'Defender_{d}', 'Defender')
            if ret_dict[0] is 'None':
                self.logger_sim.error(f'Unable to create Defender_{d}.')

    # Function to create a machine group within the environment
    def create_machinegroup(self, name: str) -> str:
        req_status = ''
        machine_group_uuid = str(uuid4())
        logger_ghosts.debug(msg=f'UUID of {name}: {machine_group_uuid}')
        logger_ghosts.debug(msg=f'GroupID')
        machinegroup_req = {
            "name": name,
            "groupMachines": [
                {
                    "id": 1,
                    "groupId": self.num_current_groups,
                    "machineId": machine_group_uuid
                }
            ]
        }
        logger_ghosts.debug(msg=machinegroup_req)
        try:
            req_status = post(url=f'http://{self.CONN_URL}/api/', data=machinegroup_req)
            logger_ghosts.debug(msg=f'Created machine {name}. | {req_status.content.decode("utf-8")}')
            print(f'Created machine {name}. | {req_status.content.decode("utf-8")}')
        except Exception as ex:
            logger_ghosts.error(msg=f'Unable to create machine group. | {ex}')
            print(f'Unable to create machine group. | {ex}')
            exit(1)

        return machine_group_uuid

    # Function to create a new machine within the environment
    def create_machine(self, name: str, machine_type: str) -> dict:
        machine_json_req = {
            "name": name,
            "fqdn": 'https://threat-hunting-games.net',
            "domain": 'threat-hunting-games.net',
            "host": 'threat-hunting-games.host',
            "resolvedHost": "https://threat-hunting-games.net",
            "hostIp": "000.000.0.00",
            "ipAddress": "000.000.0.01",
            "currentUsername": "admin",
            "clientVersion": '1',
            "status": 0,
            "statusUp": 0,
        }
        try:
            req_status = post(url=f'http://{self.CONN_URL}/api/machines', data=machine_json_req)
            if req_status.status_code == 201:
                req_data = json.loads(req_status.content.decode('utf-8'))
                logger_ghosts.debug(msg=f'New Machine created with id {req_data["id"]}')
                if machine_type == 'Attacker':
                    self.attacker_Machine_Ids.append(req_data['id'])
                else:
                    self.defender_Machine_Ids.append(req_data['id'])
                return {name: str(req_data['id'])}
            print(f"Issue creating machine {name}. {str(req_status.content.decode('utf-8'))}")
            return {'None': 'None'}
        except Exception as e:
            logger_ghosts.error(msg=f'Unable to create machine {name}. {str(e)}')
            print(f'Unable to create machine {name}. {str(e)}')
            return {'None': 'None'}

    # Function to confirm the connection of the threat-hunting-games container to the GHOSTS-API container
    def confirm_connection(self) -> bool:
        print('Confirming connection to GHOSTS_API....')
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/home')
            logger_ghosts.debug(msg=f'Connection Confirmation: {str(test_data.content)}')
            return True
        except Exception as e:
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            return False

    #TODO - RETURN A DICT CONTAINING { 'Attackers' : [], 'Defenders': [] }
    # Get a list of the machine groups as well as the machines in them
    def list_machine_groups(self) -> dict:
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/machinegroups')
            logger_ghosts.debug(msg=f'List of Machine Groups: {str(test_data.content)}')
            return json.loads(test_data.content.decode('utf-8'))
        except Exception as e:
            print(f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            return {}

    # TODO - RETURN A LIST INSTEAD OF A DICT
    # Get a list of the machines that currently exist in the simulation
    def list_machines(self) -> dict:
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/')
            logger_ghosts.debug(msg=f'List of Machines: {str(test_data.content)}')
            return json.loads(test_data.content.decode('utf-8'))
        except Exception as e:
            print(f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')

    # Run the actions of the attacker that is passed in to the method on the machine id that is passed in
    def attacker_action(self, machine_id: str, target_id: str, action_name: str) -> bool:
        # Check the connection to the GHOSTS API
        machines = self.list_machines()
        if target_id in machines:
            if machine_id in machines:
                try:
                    with open('Attacker_Actions.json') as json_f:
                        attacker_actions_json = json.load(json_f)
                        if action_name not in attacker_actions_json["Actions List"]:
                            logger_ghosts.info(msg=f"{action_name} does exist in list of attacker actions")
                        # Check that the action exists in the action set from the .json file
                        for a in attacker_actions_json["Actions List"]:
                            if a["Name"] == action_name:
                                # Call the run_action function
                                return self.run_action(a, machine_id, target_id)

                except Exception as e:
                    logger_ghosts.error(msg=f"Issue reading attacker json file. {str(e)}")
                    return False
            else:
                logger_ghosts.info(msg=f"Machine ID: {machine_id} could not be found in the current machines")
                return False
        else:
            logger_ghosts.info(msg=f"Target Machine ID: {target_id} could not be found in the current machines")
            return False

    # Run the actions of the defender that is passed in to the method on the machine id that is passed in
    def defender_action(self, machine_id: str, action_name: str) -> bool:
        # Check the connection to the GHOSTS API
        machines = self.list_machines()
        if machine_id in machines:
            try:
                with open('Defender_Actions.json.json') as json_f:
                    defender_actions_json = json.load(json_f)
                    if action_name not in defender_actions_json["Actions List"]:
                        logger_ghosts.info(msg=f"{action_name} does exist in list of defender actions")
                    # Check that the action exists in the action set from the .json file
                    for a in defender_actions_json["Actions List"]:
                        if a["Name"] == action_name:
                            # Call run_action with both arguments as the system itself due to being defender
                            return self.run_action(a, machine_id, machine_id)

            except Exception as e:
                logger_ghosts.error(msg=f"Issue reading defender json file. {str(e)}")
                return False
        else:
            logger_ghosts.info(msg=f"Machine ID: {machine_id} could not be found in the current machines")
            return False

    # Run an action with the passed in action data and the machine ID to run it on
    def run_action(self, action_data: dict, machine_id: str, target_id: str) -> bool:
        self.logger_sim.info(msg=f"Attempting to run action {action_data['Name']}")
        has_privileges = True
        if action_data['Requires Admin'] == "True":
            if machine_id not in self.admin_matrix[target_id]:
                has_privileges = False
        if self.confirm_connection() and has_privileges:
            # Check if admin is required to preform the action
            try:
                utc_time = list(str(datetime.now(timezone.utc)))
                utc_time = str[0:24]
                utc_time[10] = 'T'
                utc_time[23] = 'Z'
                timeline_action = {
                    'machineId': target_id,
                    'type': 10,
                    'activeUtc': ''.join(utc_time),
                    'status': 0,
                    'update': {
                        "TimeLineHandlers": [
                            {
                                "HandlerType": "Command",
                                "Initial": "",
                                "UtcTimeOn": "00:00:00",
                                "UtcTimeOff": "24:00:00",
                                "Loop": False,
                                "TimeLineEvents": [
                                    action_data["Action"]
                                ]
                            }
                        ]
                    }
                }
                ret_data = post(url=f'http://{self.CONN_URL}/api/timelines', data=timeline_action)
                if ret_data.status_code == 200:
                    # Succeeded in adding actions
                    if action_data['Name'] == 'Gain Admin':
                        self.admin_matrix[target_id] += [machine_id]
                    self.logger_sim.info(msg=f"Action {action_data['Name']} was run by {machine_id} on target {target_id}")
                    return True
                else:
                    logger_ghosts.error(f'Unable to send action {action_data["Name"]} from machine {machine_id}. {ret_data.status_code} was thrown')
                    return False
            except Exception as e:
                logger_ghosts.error(f'Unable to send action {action_data["Name"]} from machine {machine_id}. {str(e)}')
                return False
        else:
            return False

    # Attempt to remove a machine from GHOSTS
    def remove_machine(self, machine_id: str) -> bool:
        if self.confirm_connection():
            try:
                ret_data = delete(f'http://{self.CONN_URL}/api/machines/{machine_id}')
                if ret_data.status_code == 200:
                    self.logger_sim.info(f'Removed machine {machine_id} from GHOSTS')
                    logger_ghosts.info(f'Successfully removed machine {machine_id}')
                    return True
                self.logger_sim.error(f'Unable to remove machine {machine_id} from GHOSTS.')
                logger_ghosts.error(f'Unable to remove machine {machine_id} from GHOSTS. {ret_data.content.decode("utf-8")}')
                return False
            except Exception as e:
                self.logger_sim.error(f'Unable to remove machine {machine_id} from GHOSTS.')
                logger_ghosts.error(f'Unable to remove machine {machine_id} from GHOSTS. {e}')
                return False
        else:
            self.logger_sim.error(f'Unable to remove machine {machine_id} from GHOSTS.')
            logger_ghosts.error(msg=f'Unable to remove machine {machine_id} due to failed connection')
            return False

    # Attempt to remove a machinegroup from GHOSTS
    def remove_machinegroups(self):
        if self.confirm_connection():
            group_names = ['Attackers', 'Defenders']
            for g in group_names:
                try:
                    ret_data = delete(f'http://{self.CONN_URL}/api/machinegroup/{g}')
                    if ret_data.status_code == 200:
                        self.logger_sim.info(f'Removed machinegroup {g} from GHOSTS')
                        logger_ghosts.info(f'Successfully removed machinegroup {g}')
                        return True
                    self.logger_sim.error(f'Unable to remove machinegroup {g} from GHOSTS.')
                    logger_ghosts.error(f'Unable to remove machinegroup {g} from GHOSTS. {ret_data.content.decode("utf-8")}')
                    return False
                except Exception as e:
                    self.logger_sim.error(f'Unable to remove machinegroup {g} from GHOSTS.')
                    logger_ghosts.error(f'Unable to remove machinegroup {g} from GHOSTS. {e}')
                    return False
        else:
            self.logger_sim.error(f'Unable to remove machinegroups from GHOSTS.')
            logger_ghosts.error(msg=f'Unable to remove machinegroups due to failed connection')
            return False

    # End the simulation due to either error or completion
    def end_simulation(self, reason: str = "", maintain_env: bool = False, save_file: bool = True):
        success_teardown = True
        self.logger_sim.error(msg=f'Ending SIMUATION {self.SIMULATION_ID} due to the following reason: {reason}')
        if not maintain_env:
            self.remove_machinegroups()
            for d in self.defender_Machine_Ids:
                if not self.remove_machine(d):
                    success_teardown = False
            for a in self.attacker_Machine_Ids:
                if not self.remove_machine(a):
                    success_teardown = False
            if not success_teardown:
                logger_ghosts.error(msg='WARNING: Teardown was not 100% successful, there may be remaining machines/machinegroups')
        if not save_file:
            sim_files = os.listdir('/var/spool/threat-hunting-games')
            for f in sim_files:
                sim_id = f.split('_')[0]
                if sim_id == self.SIMULATION_ID:
                    os.remove(f'/var/spool/threat-hunting-games/{f}')
        self.logger_sim.info(msg='SIMULATION ENDING')
        sys.exit(0)

# TODO - Implement timer into logging to be able to see time duration
# TODO - Figure out how to add machine to machinegroups correctly either via createMachine or in create_machinegroup