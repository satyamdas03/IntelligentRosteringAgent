import json
import boto3

stepfunctions_client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    try:
        execution_arn = event['pathParameters']['executionArn']
        response = stepfunctions_client.describe_execution(executionArn=execution_arn)
        status = response['status']

        if status == 'RUNNING':
            return {'statusCode': 202, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'status': 'RUNNING'})}
        elif status == 'SUCCEEDED':
            output = json.loads(response['output'])
            return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps(output)}
        else:
            error_output = {'status': status, 'error': response.get('cause', 'An unknown error occurred.')}
            return {'statusCode': 500, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps(error_output)}
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}