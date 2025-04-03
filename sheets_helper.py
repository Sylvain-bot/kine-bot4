import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_json = json.loads(os.environ.get("GOOGLE_CREDS"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Patients").sheet1
    data = sheet.get_all_records()
    return data

def find_patient(patient_input):
    data = get_sheet_data()
    for row in data:
        if (
            str(row.get("patient_id", "")).lower() == str(patient_input).lower()
            or row.get("prenom", "").lower() == patient_input.lower()
        ):
            return row
    return None