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

    roster_date_str = event.get('roster_date', date.today().isoformat())
    fully_available_mcas = []
    
    try:
        print("Attempting to connect to the database...")
        conn_start = time.time()
        conn = mysql.connector.connect(**db_config)
        print(f"Database connection successful in {time.time() - conn_start:.2f} seconds.")
        
        cursor = conn.cursor(dictionary=True)
        
        sql_query = """
            SELECT 
                u.user_id AS mca_id,
                u.name AS mca_name,
                u.employee_id AS employee_id
            FROM 
                nb_user_details u
            LEFT JOIN 
                nb_leave_apply_transaction l ON u.employee_id = l.employee_id
                AND l.status = 'Approved'
                AND DATE(%s) BETWEEN l.start_date AND l.end_date
            WHERE 
                u.status = 'A' -- This assumes 'A' means Active. Change if your status column uses a different value.
                AND l.employee_id IS NULL;
        """
        
        print("Executing SQL query...")
        query_start = time.time()
        cursor.execute(sql_query, (roster_date_str,))
        fully_available_mcas = cursor.fetchall()
        print(f"Query executed in {time.time() - query_start:.2f} seconds. Found {len(fully_available_mcas)} MCAs.")

    except mysql.connector.Error as err:
        print(f"DATABASE ERROR: {err}")
        raise err
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn.is_connected(): 
            conn.close()
            print("Database connection closed.")
    
    print(f"Function finished in {time.time() - start_time:.2f} seconds.")
    return fully_available_mcas