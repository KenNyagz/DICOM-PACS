# This script anonymizes studies by removing sensitive metadata from patient studies
# It removes tags such as patient ID, referring physician, etc and only retains the study date and time
# It also retrieves the respective report for the study, saves it as pdf and attaches to the anonymized study
# We are relying on orthanc and orthanc's rest endpoints to achieve all the above

import requests
import pymysql
import json
import datetime
import base64
from fpdf import FPDF


ORTHANC_URL = "http://localhost:8042"
AUTH = ("orthanc", "orthanc")

MYSQL_CFG = {
    "host": "",
    "user": "",
    "password": "",
    "database": "",
    "port": 3306,
}


def fetch_ids():
    """
    Fetch the latest report text for the given patient identifier (pat_num).
    Adjust SQL if your DB uses a different patient key.
    """
    conn = pymysql.connect(**MYSQL_CFG, charset="utf8mb4", cursorclass=pymysql.cursors.Cursor)
    results = []
    try:
        with conn.cursor() as cur:
            query = """
                SELECT p.pat_num
                FROM patient p
                JOIN request r ON r.patient_id = p.patient_id
                JOIN request_detail rd ON rd.request_id = r.request_id
				JOIN exam e ON e.exam_id = rd.exam_id
                WHERE e.type = 23
                ORDER BY r.created_at DESC;
            """
            cur.execute(query)
            rows = cur.fetchall()
            for item in rows:
                results.append(item[0])
            return results
    finally:
        conn.close()


def studyID_lookup(patient_id):
    orthanc_endpoint = f"{ORTHANC_URL}/tools/find"
    request_body = {"Level":"Study","Expand":True,"Limit":101,"Query":{"StudyDate":"","PatientID": patient_id},"Full":True}
    response = requests.post(orthanc_endpoint, json=request_body)
    #print(response.json())
    response_json = json.loads(response.text)
    #print(response_json)
    return response_json[0] #if len(response_json) < 1  else []
	
def anonymize_study(study):
    #print(study_id, '----')
    study_id = study['ID']
    endpoint = f"{ORTHANC_URL}/studies/{study_id}/anonymize"
    body = { "Keep" : [ "SeriesDescription", "StudyDescription","StudyDate","StudyTime" ] }
    response = requests.post(endpoint,json=body)
    #print(endpoint)
    response_json = json.loads(response.text)
    #print(response_json)
    return response_json['ID']

# Logic to query and extract report from DB
def fetch_report_from_db(patient_num) -> str:
    conn = pymysql.connect(
        host="192.168.5.57",
        user="jris",
        password="Agsrvc2ls",
        database="c_ris",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor
    )
    try:
        with conn.cursor() as cur:
            query = """
                SELECT r.text
                FROM report r
                JOIN patient p ON r.patient_id = p.patient_id
                WHERE p.pat_num = %s
                ORDER BY r.created_at DESC
                LIMIT 1;
            """
            cur.execute(query, (patient_num,))
            row = cur.fetchone()
            if not row:
                return ''

            raw_text = row[0]

            try:
                data = json.loads(raw_text)   # parse JSON
                # Pick first available key
                if "report" in data:
                    content = data["report"]
                elif "findings" in data:
                    content = data["findings"]
                else:
                    # If unknown format, just return whole thing
                    content = str(data)
            except json.JSONDecodeError:
                # Not JSON ? return as-is
                content = raw_text

            # Strip HTML tags
            return (
                content.replace('<p>', '')
                       .replace('</p>', '\n')
                       .replace('<strong>', '')
                       .replace('</strong>', '')
                       .replace('<br />', '\n')
                       .strip()
            )
    finally:
        conn.close()

	
def generate_pdf_from_report(report,patient_num):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.multi_cell(0, 10, report)  # auto-handles multiple lines
    pdf.output(f"{patient_num}.pdf")
	
    with open(f"{patient_num}.pdf",'rb') as handle: pdf_bytes = handle.read()
	
    return base64.b64encode(pdf_bytes).decode('utf-8') #dicom requires PDFs to be encoded in base64
	

def upload_pdf_to_othanc(study_id,base64_pdf):
    endpoint = f"{ORTHANC_URL}/tools/create-dicom"
    today = datetime.date.today().strftime("%Y%m%d")
    body = {"Parent":study_id,"Tags":{"Modality":"DOC","SeriesDate":today,"SeriesDescription":"Report","AcquisitionDate":today,"ContentDate":today},"Content":f"data:application/pdf;base64,{base64_pdf}"}
    response = requests.post(endpoint,json=body)
	
    print(response.text)

#orthanc generates a UID for every patient, you need to match/map those with the actual patient IDs in the DB
def build_patient_map():
    r = requests.get(f"{ORTHANC_URL}/patients", auth=AUTH)
    r.raise_for_status()
    patient_ids = r.json()

    mapping = {}

    for pid in patient_ids:
        details = requests.get(f"{ORTHANC_URL}/patients/{pid}", auth=AUTH).json()
        dicom_pid = details["MainDicomTags"].get("PatientID", None)
        mapping[dicom_pid] = pid   # RIS PatientID ? Orthanc UUID
		
    pat_ids = []
    for key in mapping.keys():
        pat_ids.append(key)
		
    return pat_ids

#patient_ids = fetch_ids()
#print(build_patient_map())

def pipe():
    pat_ids = build_patient_map()
    print(pat_ids)
    for ID in pat_ids:
        print(ID)
        study_id = studyID_lookup(ID)
        anon_study = anonymize_study(study_id)
        report = fetch_report_from_db(ID)
        report_pdf = generate_pdf_from_report(report, ID)
        upload_pdf_to_othanc(anon_study, report_pdf)
        

pipe()

#for patient_id in patient_ids:
 #   study_id = studyID_lookup(patient_id)
	#
    #if len(study_id) < 1: continue
	
    #study_id = study_id['ID']
	
    #anonymized_study_id = anonymize_study(study_id)
	
    #patient_report = fetch_report_from_db(patient_id)
	
    #if patient_report == '': continue
	
    #base64_encoded_pdf = generate_pdf_from_report(patient_report,patient_id)
	
    #upload_pdf_to_othanc(anonymized_study_id,base64_encoded_pdf)
	
	
