import os
import pytz
import time
from datetime import timedelta, datetime, date
import numpy  as np
import pandas as pd
import pandas_gbq

from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from src.connection.gcp_auth import GCPAuth
from src.config.helper import log_method_call
class BigQueryConn(GCPAuth):
    def __init__(self, scope=None):
        super().__init__(scope=scope)
        self.client = bigquery.Client(credentials=self.credential)

    def extract_schema_from_df(self, df: pd.DataFrame):
        type_df = df.dtypes
        result = []
        for col in type_df.index:
            dtype = type_df.at[col]
            if pd.api.types.is_datetime64_any_dtype(dtype):
                result += [bigquery.SchemaField(col, 'DATETIME')]
            elif pd.api.types.is_bool_dtype(dtype):
                result += [bigquery.SchemaField(col, 'BOOL')]
            elif pd.api.types.is_float_dtype(dtype):
                result += [bigquery.SchemaField(col, 'FLOAT64')]
            elif pd.api.types.is_integer_dtype(dtype):
                result += [bigquery.SchemaField(col, 'INT64')]
            else:
                result += [bigquery.SchemaField(col, 'STRING')]
        return result

    @log_method_call
    def preprocess_for_insert(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        seoul_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(seoul_tz)
        result['update_dt'] = pd.Timestamp(now)
        return result
    
    @log_method_call
    def insert(self, df: pd.DataFrame, table_id: str, data_set:str, if_exists: str='append'):
        df = self.preprocess_for_insert(df)
        pandas_gbq.to_gbq(dataframe=df, destination_table=f"{data_set}.{table_id}", project_id=self.project_id, if_exists=if_exists, credentials=self.credential)

    @log_method_call
    def upsert(self, df: pd.DataFrame, table_id: str, data_set:str, target_dict: dict):
        df = self.preprocess_for_insert(df)
        
        if len(target_dict) == 0:
            raise Exception('UPSERT를 위한 save_idx가 없습니다.(to_gbq를 insert로 사용하는 걸 더 권장함.)')
        # 1. 테이블 존재 여부 확인: 테이블이 없다면, 새로 만들어서 넣기
        try:
            table_info = self.client.get_table(f"{self.project_id}.{data_set}.{table_id}")
            table_schema = [x.name for x in table_info.schema]
            df = df[table_schema]
        except NotFound as e:
            print('Target table does not exist, So create table.')
            schema = self.extract_schema_from_df(df)
            table = bigquery.Table(f'{self.project_id}.{data_set}.{table_id}', schema=schema)
            self.client.create_table(table)  # Make an API request.

        # DELETE
        del_query = f'''
        DELETE FROM `{self.project_id}.{data_set}.{table_id}` 
        WHERE 1=1
        '''
        for _k, _v in target_dict.items():
            if isinstance(_v, str) or isinstance(_v, date) or isinstance(_v, datetime):
                del_query += f" AND {_k} = '{_v}'\n" 
            else:
                del_query += f" AND {_k} = {_v}\n"

        del_query_job = self.client.query(del_query)

        # INSERT
        if del_query_job.result() is not None:
            pandas_gbq.to_gbq(dataframe=df, destination_table=f"{data_set}.{table_id}", project_id=self.project_id, if_exists='append', credentials=self.credential)
    
    @log_method_call
    def query_from_sql_file(self, file_path, file_name, **kwargs) -> pd.DataFrame:
        sql_file_path = os.path.join(file_path, file_name)
        sql = open(sql_file_path, 'r').read()

        for key, value in kwargs.items():
            sql = sql.replace('<' + key + '>', str(value))
        strt_time = time.time()
        response = self.client.query(sql)
        elapsed_time = round(time.time() - strt_time, 2)
        print(f'[BigQuery] job ID(elapsed_time: {str(elapsed_time)} sec.): {response.job_id}')
        return response.to_dataframe()

    def query(self, sql, **kwargs) -> pd.DataFrame:
        strt_time = time.time()
        response = self.client.query(sql, **kwargs)
        result = response.to_dataframe()
        elapsed_time = round(time.time() - strt_time, 2)
        print(f'[BigQuery] job ID(elapsed_time: {str(elapsed_time)} sec.): {response.job_id}')
        return result