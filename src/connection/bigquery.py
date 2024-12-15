import os
import pytz
import time
from datetime import timedelta, datetime, date
import numpy  as np
import pandas as pd
import pandas_gbq
from typing import Tuple, Sequence
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from google.cloud.bigquery.table import Table
from src.connection.gcp_auth import GCPAuth
from src.config.helper import log_method_call

class BigQueryConn(GCPAuth):
    def __init__(self, scope=None):
        super().__init__(scope=scope)
        self.client = bigquery.Client(credentials=self.credential)
        self.project_id = 'proj-asset-allocation'
    
    @log_method_call
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
            elif df[col].apply(lambda x: isinstance(x, dict)).any():
                result += [bigquery.SchemaField(col, 'JSON')]
            else:
                result += [bigquery.SchemaField(col, 'STRING')]
        return result

    def wait_for_table_creation(self, table_full_id, timeout=60, interval=5) -> bool:
        """
        BigQuery 테이블 생성 후 생성 완료를 기다리는 함수.
        
        Parameters:
        - client: BigQuery Client 객체
        - project_id: GCP 프로젝트 ID
        - data_set: 데이터셋 ID
        - table_id: 테이블 ID
        - timeout: 대기 시간 (초)
        - interval: 확인 간격 (초)
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 테이블 정보 가져오기
                self.client.get_table(table_full_id)
                print(f"Table {table_full_id} created successfully.")
                return True
            except NotFound:
                print(f"Table {table_full_id} not yet available. Retrying in {interval} seconds...")
                time.sleep(interval)
        return False

    @log_method_call
    def preprocess_for_insert(self, df: pd.DataFrame, proj_id: str, data_set: str, table_id: str) -> Tuple[pd.DataFrame, Table]:
        result = df.copy()
        table_full_id = f'{proj_id}.{data_set}.{table_id}'
        seoul_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(seoul_tz)
        result['update_dt'] = pd.Timestamp(now)

        # 1. 테이블 존재 여부 확인: 테이블이 없다면, 새로 만들어서 넣기
        try:
            table_info = self.client.get_table(table_full_id)
            table_schema = [x.name for x in table_info.schema]
            result = result[table_schema]
        except NotFound as err:
            print(err)
            print('Target table does not exist, So create table.')
            schema = self.extract_schema_from_df(result)
            table_info = bigquery.Table(table_full_id, schema=schema)
            table_info = self.client.create_table(table_info)  # Make an API request.
            self.wait_for_table_creation(table_full_id)

        return (result, table_info)
    
    @log_method_call
    def insert(self, df: pd.DataFrame, table_id: str, data_set:str, if_exists: str='append'):
        df, table_info = self.preprocess_for_insert(df, proj_id=self.project_id, data_set=data_set, table_id=table_id)
        pandas_gbq.to_gbq(dataframe=df, destination_table=f"{data_set}.{table_id}", project_id=self.project_id, if_exists=if_exists, credentials=self.credential)

    @log_method_call
    def upsert(self, df: pd.DataFrame, table_id: str, data_set:str, target_dict: dict):
        df, table_info = self.preprocess_for_insert(df, proj_id=self.project_id, data_set=data_set, table_id=table_id)
        
        if len(target_dict) == 0:
            raise Exception('UPSERT를 위한 save_idx가 없습니다.(to_gbq를 insert로 사용하는 걸 더 권장함.)')

        # DELETE
        print('DELETE FOR UPSERT')
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
        print('INSERT FOR UPSERT')
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
    
    @log_method_call
    def insert_using_stream(self, df: pd.DataFrame, table_id: str, data_set:str) -> Sequence[Sequence[dict]]:
        '''
        이 함수는 내부적으로 stream API를 활용한다.
        장점: JSON schemaField를 다룰 수 있다.
        단점: stream API 작업이 걸려있는 테이블은 일정 기간(몇 분에서 몇 시간 정도) 동안은 DELETE/UPDATE 접근이 불가하다.
        '''
        df, table_info = self.preprocess_for_insert(df=df, proj_id=self.project_id, data_set=data_set, table_id=table_id)
        
        interval, timeout = 5, 60*3
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 테이블 정보 가져오기
                # tmp_client = bigquery.Client(project=self.project, credentials=self.credentials)
                # tmp_client.insert_rows_from_dataframe(dataframe=df,table=table_info)
                self.client.insert_rows_from_dataframe(dataframe=df,table=table_info)
                print(f"streamAPI을 활용한 INSERT 완료")
                return True
            except NotFound:
                print(f"streamAPI에서 사용할 테이블을 못 찾고 있습니다.")
                time.sleep(interval)
        return False
