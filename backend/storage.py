import boto3
from botocore.client import Config
from config import settings
from typing import BinaryIO
import hashlib


class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        self.bucket = settings.s3_bucket

    def upload_file(self, file_obj: BinaryIO, key: str) -> str:
        self.s3_client.upload_fileobj(file_obj, self.bucket, key)
        return f"{settings.s3_endpoint}/{self.bucket}/{key}"

    def upload_bytes(self, data: bytes, key: str) -> str:
        self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return f"{settings.s3_endpoint}/{self.bucket}/{key}"

    def download_file(self, key: str, file_obj: BinaryIO) -> None:
        self.s3_client.download_fileobj(self.bucket, key, file_obj)

    def download_bytes(self, key: str) -> bytes:
        response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
        return response['Body'].read()

    def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        return self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=expiration
        )

    def file_exists(self, key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete_file(self, key: str) -> None:
        self.s3_client.delete_object(Bucket=self.bucket, Key=key)

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()


storage = StorageService()
