#!/usr/bin/env python3

import requests
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from botocore.config import Config


def save_image(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)


# def delete_temp_file_util(file_path):
#     asyncio.run(asyncio.sleep(5))  # Delay for 5 seconds
#     os.remove(file_path)
#     print(f"{file_path} deleted")


# async def delete_temp_file(file_path):
#     # Use ThreadPoolExecutor to run the delete function in a separate thread
#     with ThreadPoolExecutor() as executor:
#         loop = asyncio.get_running_loop()
#         await loop.run_in_executor(executor, delete_temp_file_util, file_path)


class SunoAPI:
    base_url = "http://suno-api:3000"

    @classmethod
    def generate_audio_by_prompt(cls, payload):
        url = f"{cls.base_url}/api/generate"
        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )
        data = response.json()
        print("suno data:", data)
        if "error" in data:
            raise Exception(data["error"])
        ids = f"{data[0]['id']},{data[1]['id']}"

        print(f"ids: {ids}")
        for _ in range(60):
            data = SunoAPI.get_audio_information(ids)
            if data[0]["status"] == "streaming":
                print(f"{data[0]['id']} ==> {data[0]['audio_url']}")
                print(f"{data[1]['id']} ==> {data[1]['audio_url']}")
                break
            # sleep 5s
            time.sleep(5)
        # return the audio urls
        urls = [data[0]["audio_url"], data[1]["audio_url"]]
        return urls
        # return response.json()

    @classmethod
    def get_audio_information(cls, audio_ids):
        url = f"{cls.base_url}/api/get?ids={audio_ids}"
        response = requests.get(url)
        return response.json()

    @classmethod
    def get_limits(cls):
        url = f"{cls.base_url}/api/get_limit"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return None


class AwsEc2Api:
    my_config = Config(
        region_name="eu-west-2",
        signature_version="v4",
        retries={"max_attempts": 10, "mode": "standard"},
    )

    @classmethod
    def change_instance_state(cls, action, instance_id):
        ec2 = boto3.client("ec2", config=cls.my_config)

        ret_txt = "aye, looks like that worked"
        if action == "ON":
            try:
                response = ec2.start_instances(InstanceIds=[instance_id], DryRun=False)
                print(response)
            except ClientError as e:
                print(e)
                ret_txt = str(e)
        elif action == "OFF":
            try:
                response = ec2.stop_instances(InstanceIds=[instance_id], DryRun=False)
                print(response)
            except ClientError as e:
                print(e)
                ret_txt = str(e)
        elif action == "REBOOT":
            try:
                response = ec2.reboot_instances(InstanceIds=[instance_id], DryRun=False)
                print(response)
            except ClientError as e:
                print(e)
                ret_txt = str(e)

        return ret_txt

    @classmethod
    def get_instance_cost(cls, tag_key, tag_value, days):
        # Create a Cost Explorer client
        ce = boto3.client("ce", config=clsmy_config)

        # Calculate the start and end dates for the past N days
        end = datetime.utcnow().date()
        start = end - timedelta(days=days)

        # Format the dates
        start = start.strftime("%Y-%m-%d")
        end = end.strftime("%Y-%m-%d")

        # Filter by tag key-value pair
        tag_filter = {"Tags": {"Key": tag_key, "Values": [tag_value]}}

        # Try to retrieve the cost information, using tags for the given instance
        try:
            data = ce.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "TAG", "Key": tag_key}],
                Filter=tag_filter,
            )

            # Calculate the total cost
            total_cost = sum(
                float(group["Metrics"]["UnblendedCost"]["Amount"])
                for time_frame in data["ResultsByTime"]
                for group in time_frame["Groups"]
                if group["Keys"] == [f"{tag_key}${tag_value}"]
            )

            ret_txt = f"Total spend for instance with tag {tag_key}: {tag_value} in the past {days} days: ${total_cost:.2f}"

            return ret_txt

        except ClientError as e:
            print(e)
            return None
