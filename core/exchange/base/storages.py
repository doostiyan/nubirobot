from dataclasses import dataclass
from posixpath import join
from typing import Optional
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.storage import DefaultStorage
from storages.backends.s3boto3 import S3Boto3Storage


class PublicS3MediaStorage(S3Boto3Storage):
    location = 'media'
    default_acl = 'public-read'
    file_overwrite = False

    def url(self, name, parameters=None, expire=None, http_method=None):
        return urljoin(
            settings.AWS_S3_ENDPOINT_URL,
            join(settings.AWS_STORAGE_BUCKET_NAME, self.location, name),
        )


class PrivateS3MediaStorage(S3Boto3Storage):
    location = 'private'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = False


def get_public_s3_storage():
    if settings.USE_S3:
        return PublicS3MediaStorage()

    return DefaultStorage()


def get_private_s3_storage():
    if settings.USE_S3:
        return PrivateS3MediaStorage()

    return DefaultStorage()


@dataclass
class SftpProperties:
    host: str
    port: int
    username: str
    password: str
    file_path: str


@dataclass
class S3Properties:
    bucket: str
    file_path: str


def read_file_from_sftp(sftp_props: SftpProperties):
    from paramiko.sftp_client import SFTPClient
    from paramiko.sftp_file import SFTPFile

    ftp_connection: Optional[SFTPClient] = None
    ftp_file: Optional[SFTPFile] = None
    try:
        ftp_connection = open_ftp_connection(sftp_props)
        ftp_file = ftp_connection.open(sftp_props.file_path, 'r')
        return ftp_file.read()
    finally:
        _clean_up(ftp_file, ftp_connection)


def transfer_file_from_sftp_to_s3(
    sftp_props: SftpProperties, s3_props: S3Properties, chunk_size: int = None, exists_check: bool = True
):
    import boto3
    from paramiko.sftp_client import SFTPClient
    from paramiko.sftp_file import SFTPFile

    ftp_connection: Optional[SFTPClient] = None
    ftp_file: Optional[SFTPFile] = None
    try:
        ftp_connection = open_ftp_connection(sftp_props)
        ftp_file = ftp_connection.open(sftp_props.file_path, 'rb')
        ftp_file_size = ftp_file._get_size()
        s3_connection = boto3.client('s3')
        if exists_check:
            s3_file_size = file_exists_on_s3(s3_connection, s3_props.bucket, s3_props.file_path)
            if s3_file_size == ftp_file_size:
                return

        _transfer_file(ftp_file, s3_connection, s3_props, chunk_size)
    finally:
        _clean_up(ftp_file, ftp_connection)


def open_ftp_connection(sftp_props: SftpProperties) -> 'SFTPClient':
    import paramiko

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    transport = paramiko.Transport(sftp_props.host, sftp_props.port)
    transport.connect(username=sftp_props.username, password=sftp_props.password)
    ftp_connection = paramiko.SFTPClient.from_transport(transport)
    return ftp_connection


def file_exists_on_s3(s3_connection, bucket_name, s3_file_path):
    try:
        s3_file = s3_connection.head_object(Bucket=bucket_name, Key=s3_file_path)
        return s3_file['ContentLength']
    except Exception as e:
        return None


def _transfer_file(ftp_file, s3_connection, s3_props, chunk_size=None):
    from boto3.s3.transfer import TransferConfig

    transfer_config = TransferConfig()
    if chunk_size is not None:
        transfer_config.multipart_threshold = chunk_size
        transfer_config.multipart_chunksize = chunk_size

    s3_connection.upload_fileobj(ftp_file, s3_props.bucket, s3_props.file_path, Config=transfer_config)


def _clean_up(ftp_file, ftp_connection):
    if ftp_file:
        ftp_file.close()
    if ftp_connection:
        ftp_connection.close()
