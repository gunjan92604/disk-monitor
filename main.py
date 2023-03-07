from typing import Union

from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
import os
import random
import requests
import subprocess


BASE_URL = "http://localhost:61208/api/3"
MAX_USAGE_PCT = 100


app = FastAPI()

healthy = True
health_data = []

@app.get("/health")
def read_root():

    #return {'healthy': health}
    return {
        "healthy": healthy,
        "details": health_data
    }


@app.get("/health/{diskname}")
def get_disk_health(diskname: str):
    """
    Get disk health
    """
    health_data = get_health(diskname)
    if health_data:
        disk_health = health_data[0].get('healthy')
        return {'healthy': disk_health, 'details': health_data[0]}
    return {}


@app.on_event("startup")
@repeat_every(seconds=5)  # 1 hour
def refresh_health_status() -> None:
    """
    Query for disk health
    """
    global healthy
    global health_data

    health_data = get_health()
    health_values = [health_data[i]['healthy'] for i in range(len(health_data))]
    healthy = all(health_values)
    message = "All disks are healthy!" if healthy else "Some disks are not healthy!"
    print(message)


def get_health(diskname: str = None) -> None:
    """
    Query for disk health

    :param diskname: Diskname to query; optional;
    default: None for all disks

    :return: Health data for disk(s)
    """
    health_data = []
    disk_stats = get_disk_usage(filesystem=diskname)
    for stat in disk_stats:
        pct_value = int(stat['use%'][0:-1])
        health_value = pct_value <= MAX_USAGE_PCT
        stat['healthy'] = health_value
        health_data.append(stat)

    return health_data


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


def get_disk_usage(filesystem: str = None):
    """
    Get filesystem disk usage

    :param filesystem: File system name
    """
    df = subprocess.Popen(["df", "-T"], stdout=subprocess.PIPE)
    output = df.communicate()[0]
    output_lines = output.decode('utf-8').split("\n")
    all_fields = output_lines[0].lower().split()
    del all_fields[-1]
    all_fields[-1] = 'mounted_on'
    stat_lines = output_lines[1:]
    disk_stats = []
    filesystem = filesystem or ""
    for line in stat_lines:
        if not line:
            continue
        #print(line)
        values = line.split()
        if filesystem in values[0]:
            stat_dict = {all_fields[i]: values[i] for i in range(len(all_fields))}
            disk_stats.append(stat_dict)
    return disk_stats


if __name__ == '__main__':
    print(get_disk_usage('sdf'))