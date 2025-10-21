import json
import boto3
import mysql.connector
from datetime import date
import time # Import time for logging

# --- Database credentials logic remains the same ---
SECRET_NAME = "seld_mysql"
session = boto3.session.Session()
#secrets_client = session.client(service_name='secretsmanager')

# Find this in your VPC Endpoint's "Details" tab after it's created
VPCE_URL = "https://vpce-07f6f918ac43279ea-chsz7oon.secretsmanager.us-west-2.vpce.amazonaws.com" 

secrets_client = session.client(
    service_name='secretsmanager',
    endpoint_url=VPCE_URL
)
db_config = None

def get_db_credentials():
    try:
        get_secret_value_response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        secret = get_secret_value_response['SecretString']
        return json.loads(secret)
    except Exception as e:
        print(f"FATAL: Could not retrieve secret: {e}")
        raise e

def lambda_handler(event, context):
    start_time = time.time()
    print("Function execution started.")

    global db_config
    if not db_config:
        print("Attempting to get DB credentials from Secrets Manager...")
        creds_start = time.time()
        creds = get_db_credentials()
        print(f"Successfully retrieved credentials in {time.time() - creds_start:.2f} seconds.")
        
        db_config = {
            'user': creds['username'], 'password': creds['password'],
            'host': creds['host'], 'database': creds['dbname'],
            'connection_timeout': 28
        }

    pending_services = []
    try:
        target_date_str = event.get('service_date', date.today().isoformat())
        print(f"Fetching services from zcdutyslip for date: {target_date_str}")
        
        print("Attempting to connect to the database...")
        conn_start = time.time()
        conn = mysql.connector.connect(**db_config)
        print(f"Database connection successful in {time.time() - conn_start:.2f} seconds.")
        
        cursor = conn.cursor(dictionary=True)
        
        sql_query = """
            SELECT 
                case_number, member_id_c, member_name, service_date, 
                start_time, description
            FROM 
                zcdutyslip
            WHERE 
                service_date = %s;
        """
        
        print("Executing SQL query...")
        query_start = time.time()
        cursor.execute(sql_query, (target_date_str,))
        results = cursor.fetchall()
        print(f"Query executed in {time.time() - query_start:.2f} seconds.")
        
        for row in results:
            service_datetime = f"{row['service_date'].isoformat()}T{row['start_time']}" if row.get('service_date') and row.get('start_time') else None
            pending_services.append({
                "case_number": row['case_number'],
                "member_account_id": row['member_id_c'],
                "member_name": row['member_name'],
                "service_datetime": service_datetime,
                "service_description": row['description']
            })
            
        print(f"Found {len(pending_services)} services.")

    except mysql.connector.Error as err:
        print(f"DATABASE ERROR: {err}")
        raise err
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn.is_connected(): 
            conn.close()
            print("Database connection closed.")

    print(f"Function finished in {time.time() - start_time:.2f} seconds.")
    return pending_services