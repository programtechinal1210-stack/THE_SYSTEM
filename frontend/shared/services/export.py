# shared/services/export.py
import pandas as pd
from io import BytesIO
from django.http import HttpResponse
import json

class ExportService:
    @staticmethod
    def to_excel(data, filename="export.xlsx"):
        df = pd.DataFrame(data); output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0); response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'; return response
    
    @staticmethod
    def to_csv(data, filename="export.csv"):
        df = pd.DataFrame(data); output = BytesIO(); df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0); response = HttpResponse(output, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename={filename}'; return response
    
    @staticmethod
    def to_json(data, filename="export.json"):
        json_data = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        response = HttpResponse(json_data, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename={filename}'; return response
