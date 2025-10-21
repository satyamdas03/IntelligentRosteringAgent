import json
import boto3
import mysql.connector
from math import radians, sin, cos, sqrt, atan2
import time

# --- This section is correct and remains unchanged ---
SECRET_NAME = "seld_mysql"
session = boto3.session.Session()
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

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    try:
        if any(v is None for v in [lat1, lon1, lat2, lon2]):
            return None
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c
    except (ValueError, TypeError):
        return None
# -----------------------------------------------------------------

def lambda_handler(event, context):
    start_time = time.time()
    print("Function execution started.")

    global db_config
    if not db_config:
        creds = get_db_credentials()
        db_config = {
            'user': creds['username'], 'password': creds['password'],
            'host': creds['host'], 'database': creds['dbname'],
            'connection_timeout': 28
        }

    service_requests = event.get('Services', [])
    available_mcas = event.get('MCAs', [])
    
    if not service_requests or not available_mcas:
        return {"roster": []}

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    try:
        # --- DATA ENRICHMENT ---
        member_ids = [s['member_account_id'] for s in service_requests if s.get('member_account_id')]
        mca_employee_ids = [m['employee_id'] for m in available_mcas if m.get('employee_id')]

        if member_ids:
            cursor.execute(f"SELECT id_c, latitude_c, longitude_c, member_id_c FROM contacts_cstm WHERE id_c IN ({','.join(['%s'] * len(member_ids))})", tuple(member_ids))
            member_details = {row['id_c']: row for row in cursor.fetchall()}
            
            member_internal_ids = [m['member_id_c'] for m in member_details.values() if m.get('member_id_c')]
            if member_internal_ids:
                 cursor.execute(f"SELECT member_id, prefered_language FROM nb_csv_member_details WHERE member_id IN ({','.join(['%s'] * len(member_internal_ids))})", tuple(member_internal_ids))
                 member_languages = {row['member_id']: row['prefered_language'] for row in cursor.fetchall()}
                 for details in member_details.values():
                     details['language'] = member_languages.get(details.get('member_id_c'))

            for req in service_requests:
                details = member_details.get(req['member_account_id'], {})
                req['location'] = {'lat': details.get('latitude_c'), 'lon': details.get('longitude_c')}
                req['language'] = details.get('language')
                req['member_id'] = details.get('member_id_c')

        if mca_employee_ids:
            cursor.execute(f"SELECT employee_id, language FROM nb_user_details WHERE employee_id IN ({','.join(['%s'] * len(mca_employee_ids))})", tuple(mca_employee_ids))
            mca_languages = {row['employee_id']: row.get('language') for row in cursor.fetchall()}
            for mca in available_mcas:
                mca['language'] = mca_languages.get(mca['employee_id'])

            cursor.execute(f"""
                SELECT t1.employee_id, t1.latitude, t1.longitude FROM emp_location_tracke t1
                INNER JOIN (
                    SELECT employee_id, MAX(CONCAT(date, ' ', time)) as max_datetime
                    FROM emp_location_tracke WHERE employee_id IN ({','.join(['%s'] * len(mca_employee_ids))})
                    GROUP BY employee_id
                ) t2 ON t1.employee_id = t2.employee_id AND CONCAT(t1.date, ' ', t1.time) = t2.max_datetime
            """, tuple(mca_employee_ids))
            mca_locations = {row['employee_id']: {'lat': row['latitude'], 'lon': row['longitude']} for row in cursor.fetchall()}
            for mca in available_mcas:
                mca['location'] = mca_locations.get(mca['employee_id'])

        if member_ids:
            cursor.execute(f"""
                SELECT member_id_c, employee_id, COUNT(*) as visit_count 
                FROM zcdutyslip 
                WHERE member_id_c IN ({','.join(['%s'] * len(member_ids))}) AND employee_id IS NOT NULL
                GROUP BY member_id_c, employee_id
            """, tuple(member_ids))
            service_history = {}
            for row in cursor.fetchall():
                if row['member_id_c'] not in service_history: service_history[row['member_id_c']] = {}
                service_history[row['member_id_c']][row['employee_id']] = row['visit_count']
            for req in service_requests:
                req['previous_mcas'] = service_history.get(req['member_account_id'], {})
            
    finally:
        if cursor: cursor.close()
        if conn.is_connected(): conn.close()

    final_roster = []
    assigned_mca_ids = set()
    
    WEIGHT_DISTANCE, WEIGHT_CONTINUITY, WEIGHT_LANGUAGE = 0.50, 0.30, 0.20

    for service in service_requests:
        best_match, lowest_score, best_justification, best_scores = None, float('inf'), "No suitable MCA found.", {}

        for mca in available_mcas:
            if mca['mca_id'] in assigned_mca_ids: continue
            
            scores, distance_km = {}, None
            if service.get('location') and mca.get('location'):
                distance_km = haversine_distance(service['location'].get('lat'), service['location'].get('lon'), mca['location'].get('lat'), mca['location'].get('lon'))
            scores['distance'] = distance_km if distance_km is not None else 100
            
            previous_visits = service.get('previous_mcas', {}).get(mca['employee_id'], 0)
            scores['continuity'] = 1 / (1 + previous_visits)
            
            language_score = 1
            if service.get('language') and mca.get('language') and service.get('language') in mca.get('language'): language_score = 0
            scores['language'] = language_score
            
            final_score = ( (scores['distance'] * WEIGHT_DISTANCE) + (scores['continuity'] * WEIGHT_CONTINUITY) + (scores['language'] * WEIGHT_LANGUAGE) )
            
            if final_score < lowest_score:
                lowest_score, best_match, best_scores = final_score, mca, scores

        if best_match:
            final_previous_visits = service.get('previous_mcas', {}).get(best_match['employee_id'], 0)
            final_distance_km = best_scores.get('distance') if best_scores.get('distance') != 100 else None
            
            reasons = []
            if final_previous_visits > 0:
                reasons.append({'p': best_scores['continuity'], 't': f"Strong continuity of care with {final_previous_visits} previous visits"})
            if final_distance_km is not None:
                if final_distance_km < 5: desc = "Close proximity"
                elif final_distance_km <= 15: desc = "Moderate distance"
                else: desc = "Far distance"
                reasons.append({'p': best_scores['distance'], 't': f"{desc} of {round(final_distance_km, 1)} km to member location"})
            if best_scores.get('language') == 0:
                reasons.append({'p': best_scores['language'] + 0.1, 't': f"Language preference matches ({service.get('language')})"})
            
            reasons.sort(key=lambda x: x['p'])
            
            if not reasons:
                final_justification = "Assigned as best available option."
            else:
                justification_lines = [f"{i+1}. {r['t']}" for i, r in enumerate(reasons)]
                final_justification = "\n".join(justification_lines)

            final_roster.append({
                'case_number': service['case_number'],
                'service_datetime': service.get('service_datetime'),
                'member_id': service.get('member_account_id'), # Using the reliable ID
                'assigned_mca_name': best_match['mca_name'],
                'assigned_mca_employee_id': best_match['employee_id'],
                'language_match_percentage': 100 if best_scores.get('language') == 0 else 0,
                'justification': final_justification
            })
            assigned_mca_ids.add(best_match['mca_id'])
            
    return {"roster": final_roster}
