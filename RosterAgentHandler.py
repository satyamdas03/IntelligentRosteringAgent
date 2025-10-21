import json
import boto3
from datetime import date

step_functions_client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    state_machine_arn = 'arn:aws:states:us-west-2:565741009456:stateMachine:RosteringOrchestrator'
    service_date = date.today().isoformat()
    is_bedrock_agent_call = 'agent' in event and 'id' in event['agent']

    if is_bedrock_agent_call:
        print("Invocation source detected: Amazon Bedrock Agent")
        try:
            if 'requestBody' in event:
                body = event['requestBody']
                if 'application/json' in body.get('content', {}):
                    params = body['content']['application/json'].get('properties', [])
                    for param in params:
                        if param.get('name') == 'service_date':
                            service_date = param.get('value')
                            break
        except Exception as e:
            print(f"Could not parse date from Bedrock agent event, defaulting to today. Error: {e}")
    else:
        print("Invocation source detected: API Gateway")
        try:
            if event.get('body'):
                body = json.loads(event['body'])
                if 'service_date' in body:
                    service_date = body['service_date']
        except Exception as e:
            print(f"Could not parse date from API Gateway body, defaulting to today. Error: {e}")

    print(f"Starting rostering workflow for date: {service_date}")
    step_function_input = {"service_date": service_date}
    
    try:
        response = step_functions_client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(step_function_input)
        )
        if is_bedrock_agent_call:
            success_message = f"The rostering process has been successfully started for {service_date}."
            return {'messageVersion': '1.0', 'response': {'actionGroup': event['actionGroup'], 'apiPath': event['apiPath'], 'httpMethod': event['httpMethod'], 'httpStatusCode': 200, 'responseBody': {'application/json': {'body': json.dumps({'message': success_message})}}}}
        else:
            return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'executionArn': response['executionArn']})}
    except Exception as e:
        print(f"Error starting Step Function: {e}")
        if is_bedrock_agent_call:
            error_message = "I'm sorry, I failed to start the rostering workflow. Please check the logs."
            return {'messageVersion': '1.0', 'response': {'actionGroup': event['actionGroup'], 'apiPath': event['apiPath'], 'httpMethod': event['httpMethod'], 'httpStatusCode': 500, 'responseBody': {'application/json': {'body': json.dumps({'error': error_message})}}}}
        else:
            return {'statusCode': 500, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'message': 'Failed to start the rostering workflow.'})}