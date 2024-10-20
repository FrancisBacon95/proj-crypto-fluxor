from datetime import datetime
import pytz
import pandas as pd
import gspread
from src.connection.gcp_auth import GCPAuth

class GSheetsConn(GCPAuth):
    def __init__(self, url) -> None:
        self.gs_url = url
        self.scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]
        super().__init__(scope=self.scope)
        
        # gspread를 사용하여 Google Sheets API 인증
        self.client = gspread.authorize(self.credential)
        self.spreadsheet = self.client.open_by_url(self.gs_url)

    def get_worksheet(self, sheet) -> gspread.worksheet:
        return self.spreadsheet.worksheet(sheet)

    def get_df_from_google_sheets(self, sheet) -> pd.DataFrame:
        #개인에 따라 수정 필요 - 스프레드시트 url 가져오기
        worksheet = self.get_worksheet(sheet)
        df = pd.DataFrame(worksheet.get_all_values())
        return df.rename(columns=df.iloc[0]).drop(df.index[0])
    
    def write_worksheet(self, df: pd.DataFrame, worksheet_name: str) -> None:
        tmp = df.copy()
        tmp['update_dt'] = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
        real_worksheet_list = list(map(lambda x: x.title, self.spreadsheet.worksheets()))
        if worksheet_name not in real_worksheet_list:
            self.spreadsheet.add_worksheet(title=worksheet_name, rows=tmp.shape[0]+10, cols=tmp.shape[1]+5)
        worksheet = self.spreadsheet.worksheet(worksheet_name)
        worksheet.update([tmp.columns.values.tolist()] + tmp.values.tolist())

    def update_google_sheet_column(self, df:pd.DataFrame, col_nm: str, sheet: get_worksheet) -> None:
        col_idx = chr(65+df.columns.to_list().index(col_nm))
        row_min, row_max = df.index.min()+1, df.index.max()+1
        update_cells = f'{col_idx}{row_min}:{col_idx}{row_max}'
        update_values = [[x] for x in df[col_nm].to_list()]
        sheet.update(update_cells, update_values)