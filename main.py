from typing import Union


from colored import fg
from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every

from utils import scan_dict

import json
import requests
import subprocess


BASE_URL = "http://localhost:61208/api/3"
MAX_USAGE_PCT = 90
STATUS_OK = 0
STATUS_WARN = MAX_USAGE_PCT/2
STATUS_CRITICAL = MAX_USAGE_PCT
VERBOSE = False
#USAGE_LEVEL_RATINGS = {0: "Ok", 40: "Warning", 80: "Critical"}

app = FastAPI()

healthy = True
health_data = {}
usage_data = {}
all_block_devices = []
smart_stats = {}
error_stats = {}

@app.get("/health")
def read_root():
    return {
        "healthy": healthy,
        "details": {
            'health': health_data,
            'usage': usage_data
        }
    }


@app.on_event("startup")
@repeat_every(seconds=5)  # 1 hour
def refresh_health_status() -> None:
    """
    Query for disk health
    """
    global healthy
    global usage_data
    global health_data
    global all_block_devices
    global smart_stats
    global error_stats

    all_block_devices = get_block_devices()
    usage_data = get_usage()
    status_values = [usage_data.get(device).get(partition).get('status') for device in usage_data for partition in usage_data.get(device).keys()]
    status_ok = "Ok" if all(value == 'Ok' for value in status_values) else None
    status_warn = "Warn" if not status_ok and "Warn" in status_values and "Critical" not in status_values else None
    status_critical = "Critical" if not status_ok and not status_warn else None
    usage_healthy = True if status_ok or status_warn else False

    smart_stats = get_device_stats(report_type='smart-log')
    error_stats = get_device_stats(report_type='error-log')
    smart_healthy = all([stat.get('healthy') == True for stat in smart_stats.values()])
    error_healthy = all([stat.get('healthy') == True for stat in error_stats.values()])

    healthy = usage_healthy and smart_healthy and error_healthy
    health_data = {'smart_stats': smart_stats, 'error_stats': error_stats}

    message = "\033[0;32m All devices are healthy!" if healthy else "\033[0;31m Some devices are not healthy!"
    color = "green" if healthy else "yellow"
    color = "yellow" if not healthy and status_warn == "Warn" else color
    color = "red" if not healthy and status_critical == "Critical" else color
    if not VERBOSE and healthy:
        return
    for device, device_data in usage_data.items():
        for partition in device_data.keys():
            usage_status = device_data[partition]['status']
            if  usage_status == 'Critical':
                #message = f"\033[0;31m Partition {partition} on {device} is critically low on space!"
                message = f"{fg('white')}Partition {fg('yellow')}{partition}{fg('white')} on {fg('yellow')}{device}{fg('white')} is {fg('red')}critically low on space!"
                print(fg("red") + message)
            elif VERBOSE:
                message = fg("white") + f"Partition {fg('yellow')}{partition}{fg('white')} on {fg('yellow')}{device}{fg('white')} has " + f"{fg('green')}Ok{fg('white')} status"
                print(message)
        if not smart_stats.get(device).get('healthy'):
            message = f"{fg('white')}Device {fg('yellow')}{device}{fg('white')} has {fg('red')}critical warnings{fg('white')} in smart-log!"
            print(message)
        elif VERBOSE:
            message = f"{fg('white')}Device {fg('yellow')}{device}'s{fg('white')} smart-log is {fg('green')}Ok"
            print(message)
        if not error_stats.get(device).get('healthy'):
            message = f"{fg('white')}Device {fg('yellow')}{device}{fg('white')} has {fg('red')}non-zero error counts{fg('white')} in error-log!"
            print(message)
        elif VERBOSE:
            message = f"{fg('white')}Device {fg('yellow')}{device}'s{fg('white')} error-log is {fg('green')}Ok"
            print(message)
        

@app.get("/devices")
def read_root():
    return {
        "devices": all_block_devices
    }


@app.get("/devices/{device}")
def read_root(device: str):
    return scan_dict(all_block_devices, 'name', device)


@app.get("/health/usage")
def read_root():
    return {
        "healthy": healthy,
        "details": {
            'usage': usage_data
        }
    }


@app.get("/health/usage/{device}")
def get_device_usage(device: str):
    """
    Get disk health
    """
    disk_usage_data = {device: {}}
    mountpoints = get_mountpoints(device=device)
    for partition, mountpoint in mountpoints.items():
        disk_usage = get_disk_usage(filepath=mountpoint)
        for stat in disk_usage:
            pct_value = int(stat['use%'][0:-1])
            stat['status'] = "Ok" if pct_value >= 0 and pct_value < STATUS_WARN else None
            stat['status'] = "Warn" if not stat['status'] and pct_value >= STATUS_WARN and pct_value < STATUS_CRITICAL else stat['status']
            stat['status'] = "Critical" if not stat['status'] else stat['status']
            disk_usage_data[device][partition] = stat
    if disk_usage_data:
        usage_health = all([disk_usage_data[device][partition]['status'] != "Critical" for partition in disk_usage_data[device].keys()])
        return {'usage_health': usage_health, 'details': disk_usage_data}
    return {}


@app.get("/health/usage/{device}/{partition}")
def get_device_usage(device: str, partition: str):
    """
    Get disk health
    """
    disk_usage_data = {device: {}}
    mountpoints = get_mountpoints(device=device)
    mountpoint = mountpoints.get(partition)
    disk_usage = get_disk_usage(filepath=mountpoint)
    for stat in disk_usage:
        pct_value = int(stat['use%'][0:-1])
        stat['status'] = "Ok" if pct_value >= 0 and pct_value < STATUS_WARN else None
        stat['status'] = "Warn" if not stat['status'] and pct_value >= STATUS_WARN and pct_value < STATUS_CRITICAL else stat['status']
        stat['status'] = "Critical" if not stat['status'] else stat['status']
        disk_usage_data[device][partition] = stat
    if disk_usage_data:
        usage_health = disk_usage_data[device][partition]['status'] != "Critical"
        return {'usage_health': usage_health, 'details': disk_usage_data}
    return {}


def get_usage() -> None:
    """
    Query for disk health

    :param diskname: Diskname to query; optional;
    default: None for all disks

    :return: Health data for disk(s)
    """
    usage_data = {}
    for device in all_block_devices:
        mountpoints = get_mountpoints(device.get('name'))
        usage_data.setdefault(device.get('name'), {})
        for partition, mountpoint in mountpoints.items():
            disk_stats = get_disk_usage(filepath=mountpoint)
            for stat in disk_stats:
                pct_value = int(stat['use%'][0:-1])
                stat['status'] = "Ok" if pct_value >= 0 and pct_value < STATUS_WARN else None
                stat['status'] = "Warn" if not stat['status'] and pct_value >= STATUS_WARN and pct_value < STATUS_CRITICAL else stat['status']
                stat['status'] = "Critical" if not stat['status'] else stat['status']
                usage_data[device.get('name')][partition] = stat
    return usage_data


def get_disk_names():
    """
    Get disk names
    """
    disk_url = BASE_URL + "diskio/disk_name"
    response = requests.get(disk_url)
    return response.json()


def get_disk_stats(disk_name: str = None):
    """
    Get disk stats for all or a specific disk
    
    :param disk_name: Name of disk
    """
    disk_url = BASE_URL + "/diskio"
    disk_url = disk_url + f"/disk_name/{disk_name}" if disk_name else ""
    response = requests.get(disk_url)
    response.raise_for_status()
    json_resp = response.json()
    return json_resp


def get_device_stats(device: str = None, report_type: str = 'smart-log'):
    """
    Get S.M.A.R.T stats of the given device if
    provided, otherwise get stats of all
    devices on the system
    """
    devices = [device] if device else [device.get('name') for device in all_block_devices]
    device_stats = {}
    for device in devices:
        command = f"nvme {report_type} -o json {device}"
        proc = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        output = proc.communicate()[0].decode('utf-8')
        json_output = json.loads(output)
        device_stats[device] = json_output
        if report_type == 'smart-log':
            device_healthy = True if device_stats[device]['critical_warning'] == 0 else False
        elif report_type == 'error-log':
            device_healthy = all([value.get('error_count') == 0 for value in device_stats[device]['errors']])
        device_stats[device].update({'healthy': device_healthy})
    return device_stats


def get_block_devices():
    """
    Get list of block devices
    """
    global all_block_devices
    df = subprocess.Popen(["lsblk-wrapper"], stdout=subprocess.PIPE)
    output = df.communicate()[0].decode('utf-8')
    all_block_devices = json.loads(output).get('blockdevices')
    return all_block_devices


def get_device_partitions(device: str = None):
    """
    Get devices and their partitions
    """
    devices_partitions = {}
    if device:
        return {
            device: [
                a_device['children'][i].get('name') for a_device in all_block_devices \
                    if a_device.get('name') == device for i in range(len(a_device.get('children')))
            ]
        }
    for device in all_block_devices:
        children = [child.get('name') for child in device.get('children', [])]
        devices_partitions[device] = children
    return devices_partitions


def get_mountpoints(device: str, partition: str = None):
    """
    Get mountpoint of a device
    """
    partitions = [partition] if partition else list(get_device_partitions(device).values())[0]
    mount_points = {part: scan_dict(all_block_devices, 'name', part).get('mountpoint') for part in partitions}
    return mount_points


def get_disk_usage(filepath: str = None):
    """
    Get filesystem disk usage

    :param filesystem: File system name
    """
    df = subprocess.Popen(["df", "-Tha", filepath], stdout=subprocess.PIPE)
    output = df.communicate()[0]
    output_lines = output.decode('utf-8').split("\n")
    #print(json.dumps(output_lines, indent=4))
    all_fields = output_lines[0].lower().split()
    del all_fields[-1]
    all_fields[-1] = 'mounted_on'
    stat_lines = output_lines[1:]
    disk_stats = []
    filepath = filepath or ""
    for line in stat_lines:
        if not line:
            continue
        values = line.split()
        if filepath in values[-1]:
            stat_dict = {all_fields[i]: values[i] for i in range(len(all_fields))}
            disk_stats.append(stat_dict)
    return disk_stats


if __name__ == '__main__':
    print(json.dumps(get_disk_usage('nvme0n1'), indent=4))
    print(json.dumps(get_block_devices(), indent=4))
    print(json.dumps(get_device_partitions('nvme0n1'), indent=4))
    print(json.dumps(get_mountpoints('nvme0n1'), indent=4))
    print(json.dumps(get_disk_usage('/srv/cache/ssd_cache/00'), indent=4))
    print(json.dumps(get_usage(), indent=4))
    print(json.dumps(get_device_stats(report_type='smart-log'), indent=4))
    print(json.dumps(get_device_stats(report_type='error-log'), indent=4))