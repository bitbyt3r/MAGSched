import boto3
import time
import json

client = boto3.client('s3')
resources = {}
resources_timestamp = 0

def lambda_handler(event, context):
    global resources
    global resources_timestamp
    if not resources or time.time() - resources_timestamp > 60:
        data = client.get_object(Bucket="magsched-cache", Key="cache.json")['Body'].read()
        resources = json.loads(data)
        resources_timestamp = time.time()
    return {
        'statusCode': 200,
        'body': json.dumps(resources)
    }