import os
from sys import platform

from requests import get, post, put, delete
from uuid import uuid4
import logging
import json
from datetime import datetime, timezone
import random
import toml

POST_HEADER = {
    'Content-Type': 'application/json'
}

logger_ghosts = logging.getLogger()


def setup_logger(logger_name: str, log_file: str, format_str: str, level=logging.DEBUG):
    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter(format_str)
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(file_handler)
    return logger


class GHOSTSConnection:
    config_data = toml.load('./pyproject.toml')
    config_data = config_data['config']
    SIMULATION_ID = ''
    NUM_ATTACKERS = 0
    NUM_DEFENDERS = 0
    defender_Machine_Ids = []
    attacker_Machine_Ids = []
    # Matrix reads { 'system_id' : ['Machine with admin', 'machine2 with admin']
    admin_matrix = {}
    CONN_URL = config_data['prod-ghosts-uri']
    SIM_FILE_PATH = ''
    TEST_SESSION = False

    def __init__(self, num_attackers: int = 1, num_defenders: int = 1, local_session: bool = False,
                 test_session: bool = False):
        # If not being run in the threat-hunting-games container then use localhost address and port
        ghosts_log_path = self.config_data['unix-ghosts-path']
        if local_session:
            self.CONN_URL = self.config_data['local-ghosts-uri']
        if test_session:
            self.TEST_SESSION = True
        if platform == "darwin":
            self.SIM_FILE_PATH = self.config_data['unix-sim-path']
            ghosts_log_path = self.config_data['unix-ghosts-path']
        elif platform == 'win32' or platform == 'cygwin':
            self.SIM_FILE_PATH = self.config_data['windows-sim-path']
            ghosts_log_path = self.config_data['windows-ghosts-path']
        try:
            print(os.getcwd())
            os.mkdir(os.path.join(os.getcwd(), self.SIM_FILE_PATH))
        except FileExistsError:
            pass
        try:
            open(os.path.join(os.getcwd(), ghosts_log_path), 'x')
        except FileExistsError:
            pass

        global logger_ghosts
        logger_ghosts = setup_logger(logger_name='logger_ghosts',
                                     log_file=os.path.join(os.getcwd(), ghosts_log_path),
                                     format_str='%(asctime)s: [%(levelname)s] %(message)s')
        self.NUM_ATTACKERS = num_attackers
        self.NUM_DEFENDERS = num_defenders
        self.SIMULATION_ID = str(uuid4())[0:8]
        self.SESSION_IP = ".".join(map(str, (random.randint(0,255) for _ in range(4))))

        self.sim_file_loc = os.path.join(self.SIM_FILE_PATH,
                                         f'THREAT-SIM-{self.SIMULATION_ID}_{str(datetime.now().strftime("%m_%d"))}.log')
        with open(self.sim_file_loc, 'x') as sim_file:
            sim_file.close()
        self.sim_file_path_full = os.path.join(os.getcwd(), self.sim_file_loc)
        self.logger_sim = setup_logger(logger_name='sim_logger',
                                       log_file=self.sim_file_loc,
                                       format_str='[%(levelname)s] %(message)s',)
        self.logger_sim.info(msg=f"TIME OF SIMULATION: {datetime.now().time().strftime('%H:%M:%S')}")
        self.logger_sim.info(msg=f'NUMBER OF ATTACKERS: {self.NUM_ATTACKERS}')
        self.logger_sim.info(msg=f'NUMBER OF DEFENDERS: {self.NUM_DEFENDERS}')
        self.logger_sim.info(msg='Beginning creation of Machinegroups')
        # Begin creating machinegroups
        attacker_group = self.create_machinegroup('Attackers')
        if attacker_group[0] == 'Error':
            self.end_simulation(reason=attacker_group[1])
        else:
            self.logger_sim.info(msg=f'Created Machinegroup Attackers: {attacker_group}')
        defender_group = self.create_machinegroup('Defenders')
        if defender_group[0] == 'Error':
            self.end_simulation(reason=defender_group[0])
        else:
            self.logger_sim.info(msg=f'Created Machinegroup Defenders: {defender_group}')
        self.create_attacker_machines()
        self.create_defender_machines()

    # Function to confirm the connection of the threat-hunting-games container to the GHOSTS-API container
    def confirm_connection(self) -> bool:
        logger_ghosts.info(f'Attempting to confirm connection to GHOSTS_API | http://{self.CONN_URL}/api/home')
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/home', timeout=3)
            if test_data.status_code == 200:
                logger_ghosts.debug(msg=f'Connection Confirmation: {str(test_data.content.decode("utf-8"))}')
                return True
            else:
                logger_ghosts.debug(msg=f'Could not confirm connection to GHOSTS API {test_data.content.decode("utf-8")}')
                return False
        except Exception as e:
            logger_ghosts.error(
                msg=f'GHOSTS-API is not currently responding, check the container status. | {e}')
            return False

    # Create the specified number of attacker machines
    def create_attacker_machines(self):
        for a in range(0, self.NUM_ATTACKERS):
            self.logger_sim.info(f'NUM ATTACKERS {self.NUM_ATTACKERS}')
            self.logger_sim.info(f'Creating Attacker_{a}')
            ret_dict = self.create_machine(f'Attacker{a}', 'Attacker')
            if ret_dict is None:
                self.logger_sim.error(f'Unable to create Attacker_{a}.')

    # Create the specified number of defender machines
    def create_defender_machines(self):
        for d in range(0, self.NUM_DEFENDERS):
            self.logger_sim.info(f'Creating Defender_{d}')
            ret_dict = self.create_machine(f'Defender_{d}', 'Defender')
            if ret_dict is None:
                self.logger_sim.error(f'Unable to create Defender_{d}.')

    # Function to create a machine group within the environment
    def create_machinegroup(self, name: str) -> []:
        req_status = ''
        machine_group_uuid = str(uuid4())
        machinegroup_req = {
            "name": name,
            "groupMachines": []
        }
        machinegroup_req = json.dumps(machinegroup_req)
        if self.confirm_connection():
            try:
                req_status = post(url=f'http://{self.CONN_URL}/api/machinegroups',
                                  data=machinegroup_req,
                                  headers=POST_HEADER,
                                  timeout=3)
                if req_status.status_code != 201:
                    logger_ghosts.error(msg=f'Unable to create MachineGroup {name}| {req_status.content.decode("utf-8")}')
                    return ['Error', f'Could not create machinegroup {req_status.content.decode("utf-8")}']
                else:
                    logger_ghosts.debug(msg=f'UUID of {name}: {machine_group_uuid}')
                    logger_ghosts.debug(msg=machinegroup_req)
                    self.logger_sim.info(msg=f'CREATED MACHINEGROUP {name}')
            except Exception as ex:
                logger_ghosts.error(msg=f'Unable to create machine group. | {ex}')
                return ['Error', f'Unable to create machine group. | {ex}']
        else:
            return ['Error', 'GHOSTS API is currently not responding']
        return ['UUID', machine_group_uuid]

    # Function to create a new machine within the environment
    def create_machine(self, name: str, machine_type: str) -> dict:
        machine_json_req = {
            "name": name,
            "fqdn": "https://threat-hunting-games.net",
            "domain": "threat-hunting-games.net",
            "host": "threat-hunting-games.host",
            "resolvedHost": "https://threat-hunting-games.net",
            "hostIp": "000.000.0.00",
            "ipAddress": "000.000.0.01",
            "currentUsername": "admin",
            "clientVersion": "1",
            "status": 0,
            "statusUp": 0
        }
        machine_json_req = json.dumps(machine_json_req)
        try:
            req_status = post(url=f'http://{self.CONN_URL}/api/machines',
                              data=machine_json_req,
                              headers=POST_HEADER,
                              timeout=3)
            if req_status.status_code == 201:
                req_data = json.loads(req_status.content.decode('utf-8'))
                logger_ghosts.debug(msg=f'New Machine created with id {req_data["id"]}')
                if machine_type == 'Attacker':
                    self.attacker_Machine_Ids.append(req_data['id'])
                else:
                    self.defender_Machine_Ids.append(req_data['id'])
                return {name: str(req_data['id'])}
            else:
                logger_ghosts.error(msg=f"Issue creating machine {name}. {str(req_status.content.decode('utf-8'))}")
                self.logger_sim.error(msg=f"Unable to create {name}")
                return {}
        except Exception as e:
            logger_ghosts.error(msg=f'Unable to create machine {name}. {str(e)}')
            print(f'Unable to create machine {name}. {str(e)}')
            return {}

    # Get a list of the machine groups as well as the machines in them
    def list_machinegroup_machines(self) -> dict:
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/machinegroups')
            machine_group_data = json.loads(test_data.content.decode('utf-8'))
            ret_data = {'Attackers': [],
                        'Defenders': []}
            for m in machine_group_data:
                if m['name'] == 'Attackers':
                    ret_data['Attackers'] = m['groupMachines']
                elif m['name'] == 'Defenders':
                    ret_data['Defenders'] = m['groupMachines']
            logger_ghosts.debug(msg=f'List of Machine Group Machines: {str(ret_data)}')
            return ret_data
        except Exception as e:
            print(f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            return {}

    # Get an in depth report about a machine
    def get_machine_information(self, machine_id: str) -> dict:
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/machines/{machine_id}')
            if test_data.status_code == 200:
                return json.loads(test_data.content.decode('utf-8'))
            return {}
        except Exception as e:
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            return {}

    # Full data output of listing all of the possible machine groups
    def list_machine_groups(self) -> list:
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/machinegroups')
            if test_data.status_code == 200:
                logger_ghosts.debug(msg=f'List of Machinegroups: {test_data.content.decode("utf-8")}')
                return json.loads(test_data.content.decode("utf-8"))
            else:
                logger_ghosts.error(msg=f'Unable to list Machinegroups: {test_data.content.decode("utf-8")}')
                return {}
        except Exception as e:
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            return {}

    # Get a list of the machines that currently exist in the simulation
    def list_machines(self) -> list:
        ret_list = []
        try:
            test_data = get(url=f'http://{self.CONN_URL}/api/machines/list')
            if test_data.status_code == 200:
                machine_list = json.loads(test_data.content.decode('utf-8'))
                logger_ghosts.debug(msg=f'List of Machines: {str(test_data.content.decode("utf-8"))}')
                for m in machine_list:
                    machine_info = self.get_machine_information(m["id"])
                    if machine_info['status'] == "Active":
                        ret_list.append(m)
            else:
                logger_ghosts.debug(f'Error listing machines in GHOSTS-API. | {test_data.content.decode("utf-8")}')
            return ret_list
        except Exception as e:
            print(f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
            logger_ghosts.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {str(e)}')
        return ret_list

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
                timeline_action = json.dumps(timeline_action)
                ret_data = post(url=f'http://{self.CONN_URL}/api/timelines',
                                data=timeline_action,
                                headers=POST_HEADER,
                                timeout=3)
                if ret_data.status_code == 200:
                    # Succeeded in adding actions
                    if action_data['Name'] == 'Gain Admin':
                        self.admin_matrix[target_id] += [machine_id]
                    self.logger_sim.info(msg=f"Action {action_data['Name']} was run by {machine_id} on target {target_id}")
                    return True
                else:
                    logger_ghosts.error(f'Unable to send action {action_data["Name"]} '
                                        f'from machine {machine_id}. {ret_data.status_code} was thrown')
                    return False
            except Exception as e:
                logger_ghosts.error(f'Unable to send action {action_data["Name"]} from machine {machine_id}. {str(e)}')
                return False
        else:
            return False

    # Send a stop command to the machine (only used for removing machine from simulation as of now)
    def stop_machine(self, machine_id: str) -> bool:
        logger_ghosts.info(f'Stopping machine {machine_id}')
        if self.confirm_connection():
            try:
                utc_time = list(str(datetime.now(timezone.utc)))
                utc_time = str[0:24]
                utc_time[10] = 'T'
                utc_time[23] = 'Z'
                timeline_action = {
                    "machineId": machine_id,
                    "type": 10,
                    "activeUtc": "".join(utc_time),
                    "status": 0,
                    "update": {
                        "TimeLineHandlers": [
                            {
                                "HandlerType": "NpcSystem",
                                "Initial": "",
                                "UtcTimeOn": "00:00:00",
                                "UtcTimeOff": "24:00:00",
                                "Loop": 'false',
                                "TimeLineEvents": [
                                    {
                                        "Command": "Stop",
                                        "CommandArgs": [],
                                        "DelayAfter": 0,
                                        "DelayBefore": 0
                                    }
                                ]
                            }
                        ]
                    }
                }
                timeline_action = json.dumps(timeline_action)
                ret_data = post(url=f'http://{self.CONN_URL}/api/timelines',
                                data=timeline_action,
                                headers=POST_HEADER,
                                timeout=3)
                if ret_data.status_code == 200:
                    self.logger_sim.info(msg=f"Action Stop_Machine was run on {machine_id}")
                    return True
                else:
                    logger_ghosts.error(f'Unable to Stop machine {machine_id}. {ret_data.status_code} was thrown')
                    return False
            except Exception as e:
                logger_ghosts.error(f'Unable to send Stop Action to machine {machine_id}. {str(e)}')
                return False

    # Send a start command to the machine (Not used yet)
    def restart_machine(self, machine_id: str) -> bool:
        logger_ghosts.info(f'Restarting machine {machine_id}')
        if self.confirm_connection():
            try:
                utc_time = list(str(datetime.now(timezone.utc)))
                utc_time = str[0:24]
                utc_time[10] = 'T'
                utc_time[23] = 'Z'
                timeline_action = {
                    'machineId': machine_id,
                    'type': 10,
                    'activeUtc': ''.join(utc_time),
                    'status': 0,
                    'update': {
                        "TimeLineHandlers": [
                            {
                                "HandlerType": "NpcSystem",
                                "Initial": "",
                                "UtcTimeOn": "00:00:00",
                                "UtcTimeOff": "24:00:00",
                                "Loop": False,
                                "TimeLineEvents": [
                                    {
                                        "Command": "Start",
                                        "CommandArgs": [],
                                        "DelayAfter": 0,
                                        "DelayBefore": 0
                                    }
                                ]
                            }
                        ]
                    }
                }
                timeline_action = json.dumps(timeline_action)
                ret_data = post(url=f'http://{self.CONN_URL}/api/timelines',
                                data=timeline_action,
                                headers=POST_HEADER,
                                timeout=3)
                if ret_data.status_code == 200:
                    self.logger_sim.info(msg=f"Action Restart_Machine was run on {machine_id}")
                    return True
                else:
                    logger_ghosts.error(f'Unable to Restart machine {machine_id}. {ret_data.status_code} was thrown')
                    return False
            except Exception as e:
                logger_ghosts.error(f'Unable to send Restart Action to machine {machine_id}. {str(e)}')
                return False

    # Attempt to remove a machine from GHOSTS
    def remove_machine(self, machine_id: str) -> bool:
        if self.confirm_connection() and self.stop_machine(machine_id):
            try:
                ret_data = delete(f'http://{self.CONN_URL}/api/machines/{machine_id}')
                if ret_data.status_code == 204:
                    self.logger_sim.info(f'Removed machine {machine_id} from GHOSTS')
                    logger_ghosts.info(f'Successfully removed machine {machine_id}')
                    return True
                self.logger_sim.error(f'Unable to remove machine {machine_id} from GHOSTS.')
                logger_ghosts.error(f'Unable to remove machine {machine_id} '
                                    f'from GHOSTS. {ret_data.content.decode("utf-8")}')
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
            try:
                machine_groups = self.list_machine_groups()
                if len(machine_groups) > 0:
                    for mg in machine_groups:
                        ret_data = delete(f'http://{self.CONN_URL}/api/machinegroups/{mg["id"]}')
                        if ret_data.status_code == 204:
                            self.logger_sim.info(f'Removed machinegroup {mg["name"]} from GHOSTS')
                            logger_ghosts.info(f'Successfully removed machinegroup {mg["name"]}')
                            return True
                    self.logger_sim.error(f'Unable to remove machinegroup {mg["name"]} from GHOSTS.')
                    logger_ghosts.error(f'Unable to remove machinegroup {mg["name"]} '
                                        f'from GHOSTS. {ret_data.content.decode("utf-8")}')
                return False
            except Exception as e:
                self.logger_sim.error(f'Unable to remove all machinegroups from GHOSTS.')
                logger_ghosts.error(f'Unable to remove machinegroups from GHOSTS. {e}')
                return False
        else:
            self.logger_sim.error(f'Unable to remove machinegroups from GHOSTS.')
            logger_ghosts.error(msg=f'Unable to remove machinegroups due to failed connection')
            return False

    # End the simulation due to either error or completion
    def end_simulation(self, reason: str = "End of Simulation", maintain_env: bool = False, save_file: bool = True):
        success_teardown = True
        self.logger_sim.error(msg=f'ENDING SIMULATION {self.SIMULATION_ID} due to the following reason: {reason}')
        if not maintain_env:
            if not self.remove_machinegroups():
                success_teardown = False
            for d in self.defender_Machine_Ids:
                if not self.remove_machine(d):
                    success_teardown = False
                self.defender_Machine_Ids.remove(d)
            for a in self.attacker_Machine_Ids:
                if not self.remove_machine(a):
                    success_teardown = False
                self.attacker_Machine_Ids.remove(a)
        if not success_teardown:
            logger_ghosts.error(msg='WARNING: Teardown was not 100% successful, '
                                    'there may be remaining machines/machinegroups')
        if not save_file or self.TEST_SESSION:
            os.remove(self.sim_file_path_full)
        self.logger_sim.info(F'=-=-=-=-= END OF SIMULATION {self.SIMULATION_ID} -=-=-=-=-=-')
        if reason != "End of Simulation":
            exit(reason)

# TODO - Implement timer into logging to be able to see time duration
# TODO - Figure out how to add machine to machinegroups correctly either via createMachine or in create_machinegroup