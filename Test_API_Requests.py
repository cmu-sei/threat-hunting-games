# File to test making API requests to the GHOSTS API from the threat-hunting-games docker container
from requests import get, post


def create_machinegroup(name, ):
    machinegroup_req = {
        "name": name,
        "groupMachines": [
            {
                "id": 0,
                "groupId": 0,
                "machineId": "machineId"
            }
        ]
    }


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
    req_status = post(url='ghosts-api:5000/api/machines', data=machine_json_req)
    print(req_status)


if __name__ == '__main__':
    test_data = get(url='ghosts-api:5000/api/home')
    if len(test_data.content) == 0:
        print("GHOSTS-API is not currently responding, check the container status")
        exit(1)
