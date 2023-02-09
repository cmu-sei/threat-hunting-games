# File to test making API requests to the GHOSTS API from the threat-hunting-games docker container
from requests import get, post
from uuid import uuid4
import logging

logging.basicConfig(filename='Logs/api-calls.log',
                    format='%(asctime)s %(filename)8s: [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Function to create a machine group within the environment
def create_machinegroup(name):
    req_status = ''
    machine_group_uuid = uuid4()
    machinegroup_req = {
        "name": name,
        "groupMachines": [
            {
                "id": 0,
                "groupId": 0,
                "machineId": machine_group_uuid
            }
        ]
    }
    try:
        req_status = post(url='http://ghosts-api:5000/api/', data=machinegroup_req)
        logger.debug(msg=f'Created machine {name}. | {req_status.content.decode("utf-8")}')
        print(f'Created machine {name}. | {req_status.content.decode("utf-8")}')
    except Exception as ex:
        logger.error(msg=f'Unable to create machine group. | {ex}')
        print(f'Unable to create machine group. | {ex}')
        exit(1)

    return {
        "machinegroup_name" : name,
        "machinegroup_uuid" : machine_group_uuid
    }


# Function to create a new machine within the environment
def create_machine(name, fqdn, domain, host, resolved_host, host_ip, ip, curr_username, client_ver,):
    machine_json_req = {
        "name": name,
        "fqdn": fqdn,
        "domain": domain,
        "host": host,
        "resolvedHost": resolved_host,
        "hostIp": host_ip,
        "ipAddress": ip,
        "currentUsername": curr_username,
        "clientVersion": client_ver,
        "status": 0,
        "statusUp": 0,
    }
    try:
        req_status = post(url='http://ghosts-api:5000/api/machines', data=machine_json_req)
        logger.debug(msg=req_status)
        print(req_status)
    except Exception as e:
        logger.error(msg=f'Unable to create machine {name}. {e}')
        print(f'Unable to create machine {name}. {e}')


# Function to confirm the connection of the threat-hunting-games container to the GHOSTS-API container
def confirm_connection():
    print('Confirming connection to GHOSTS_API....')
    try:
        test_data = get(url='http://ghosts-api:5000/api/home')
        logger.debug(msg=f'Connection Confirmation: {test_data.content}')
        print(f'Connection Confirmation: {test_data.content}')
    except Exception as e:
        logger.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {e}')
        print(f'GHOSTS-API is not currently responding, check the container status. | {e}')
        exit(1)


# Get a list of the machine groups as well as the machines in them
def list_machine_groups():
    try:
        test_data = get(url='http://ghosts-api:5000/api/machinegroups')
        print(f'List of Machine Groups: {test_data.content}')
        logger.debug(msg=f'List of Machine Groups: {test_data.content}')
    except Exception as e:
        print(f'GHOSTS-API is not currently responding, check the container status. | {e}')
        logger.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {e}')
        exit(1)


# Get a list of the machines that are in the environment currently
def list_machines():
    try:
        test_data = get(url='http://ghosts-api:5000/api/machines')
        print(f'List of Machines: {test_data.content}')
        logger.debug(msg=f'List of Machines: {test_data.content}')
    except Exception as e:
        print(f'GHOSTS-API is not currently responding, check the container status. | {e}')
        logger.error(msg=f'GHOSTS-API is not currently responding, check the container status. | {e}')
        exit(1)


if __name__ == '__main__':
    machine_groups = []
    machines = []
    confirm_connection()
    machine_groups.append(create_machinegroup('Test_Machine_Group'))
    list_machine_groups()
    list_machines()




