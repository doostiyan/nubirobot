import hashlib
import io
import unittest
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from exchange.base.storages import S3Properties, SftpProperties, transfer_file_from_sftp_to_s3


@pytest.mark.skip
class TestTransferFile(unittest.TestCase):
    @mock_aws
    @patch('botocore.utils.calculate_md5')
    @patch('exchange.base.storages.open_ftp_connection')
    def test_transfer_file_from_ftp_to_s3(self, mock_connection, mock_md5):
        file_bytes = b'Test data'
        file_size = len(file_bytes)
        def file_tell():
            if file_tell.call_count == 0:
                file_tell.call_count += 1
                return 0
            elif file_tell.call_count == 1:
                file_tell.call_count += 1
                return file_size
            elif file_tell.call_count in [2, 3]:
                file_tell.call_count += 1
                return 0

        file_tell.call_count = 0
        mock_ftp_file = MagicMock()
        mock_ftp_file._get_size.return_value = file_size
        mock_ftp_file.read.return_value = file_bytes
        mock_ftp_file.tell.side_effect = file_tell
        mock_connection.return_value.open.return_value = mock_ftp_file

        mock_md5.return_value = hashlib.md5(file_bytes).hexdigest()

        sftp_props = SftpProperties(
            host='ftp.nobitex.ir',
            port=22,
            username='siavash',
            password='XXXX',
            file_path='/remote/directory/file_to_transfer.txt',
        )
        s3_props = S3Properties(bucket='example-bucket', file_path='file_in_s3.txt')

        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=s3_props.bucket)

        transfer_file_from_sftp_to_s3(sftp_props, s3_props)

        mock_connection.return_value.open.assert_called_once_with(sftp_props.file_path, 'rb')
        mock_ftp_file.read.assert_called_once()

        response = s3.get_object(Bucket=s3_props.bucket, Key=s3_props.file_path)
        assert response['Body'].read() == b'Test data'

    @mock_aws
    @patch('exchange.base.storages.open_ftp_connection')
    def test_transfer_file_from_ftp_to_s3_file_exists_exists_check_true_do_nothing(self, mock_connection):
        file_bytes = b'Test data'
        mock_ftp_file = MagicMock()
        mock_ftp_file._get_size.return_value = len(file_bytes)
        mock_ftp_file.read.return_value = file_bytes
        mock_connection.return_value.open.return_value = mock_ftp_file

        sftp_props = SftpProperties(
            host='ftp.nobitex.ir',
            port=22,
            username='siavash',
            password='XXXX',
            file_path='/remote/directory/file_to_transfer.txt',
        )
        s3_props = S3Properties(bucket='example-bucket', file_path='file_in_s3.txt')

        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=s3_props.bucket)
        s3.upload_fileobj(io.BytesIO(b'Test data'), s3_props.bucket, s3_props.file_path)

        transfer_file_from_sftp_to_s3(sftp_props, s3_props)

        mock_connection.return_value.open.assert_called_once_with(sftp_props.file_path, 'rb')
        mock_ftp_file.read.assert_not_called()

        response = s3.get_object(Bucket=s3_props.bucket, Key=s3_props.file_path)
        assert response['Body'].read() == b'Test data'

    @mock_aws
    @patch('botocore.utils.calculate_md5')
    @patch('exchange.base.storages.open_ftp_connection')
    def test_transfer_file_from_ftp_to_s3_file_exists_exists_check_false_replace(self, mock_connection, mock_md5):
        file_bytes = b'Test repl'
        file_size = len(file_bytes)

        def file_tell():
            if file_tell.call_count == 0:
                file_tell.call_count += 1
                return 0
            elif file_tell.call_count == 1:
                file_tell.call_count += 1
                return file_size
            elif file_tell.call_count in [2, 3]:
                file_tell.call_count += 1
                return 0

        file_tell.call_count = 0
        mock_ftp_file = MagicMock()
        mock_ftp_file._get_size.return_value = file_size
        mock_ftp_file.read.return_value = file_bytes
        mock_ftp_file.tell.side_effect = file_tell
        mock_connection.return_value.open.return_value = mock_ftp_file

        mock_md5.return_value = hashlib.md5(file_bytes).hexdigest()

        sftp_props = SftpProperties(
            host='ftp.nobitex.ir',
            port=22,
            username='siavash',
            password='XXXX',
            file_path='/remote/directory/file_to_transfer.txt',
        )
        s3_props = S3Properties(bucket='example-bucket', file_path='file_in_s3.txt')

        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=s3_props.bucket)
        s3.upload_fileobj(io.BytesIO(b'Test data'), s3_props.bucket, s3_props.file_path)

        transfer_file_from_sftp_to_s3(sftp_props, s3_props, exists_check=False)

        mock_connection.return_value.open.assert_called_once_with(sftp_props.file_path, 'rb')
        mock_ftp_file.read.assert_called_once()

        response = s3.get_object(Bucket=s3_props.bucket, Key=s3_props.file_path)
        assert response['Body'].read() == b'Test repl'

    @mock_aws
    @patch('botocore.utils.calculate_md5')
    @patch('exchange.base.storages.open_ftp_connection')
    def test_transfer_file_from_ftp_to_s3_large_file_multipart_upload(self, mock_connection, mock_md5):
        simulated_large_chunk_file = ''.join([f'test {i}' for i in range(500000)]).encode('utf-8')
        file_bytes_0 = b'part 1 ' + simulated_large_chunk_file
        file_bytes_1 = b'part 2 ' + simulated_large_chunk_file
        file_bytes_2 = b'part 3 ' + simulated_large_chunk_file

        file_size = len(file_bytes_0) + len(file_bytes_1) + len(file_bytes_2)

        def file_read(chunk_size):
            if file_read.call_count == 0:
                file_read.call_count += 1
                return file_bytes_0
            elif file_read.call_count == 1:
                file_read.call_count += 1
                return file_bytes_1
            else:
                file_read.call_count += 1
                return file_bytes_2

        def file_tell():
            if file_tell.call_count == 0:
                file_tell.call_count += 1
                return 0
            elif file_tell.call_count == 1:
                file_tell.call_count += 1
                return file_size
            elif file_tell.call_count in [2, 3]:
                file_tell.call_count += 1
                return 0

        file_read.call_count = 0
        file_tell.call_count = 0
        mock_ftp_file = MagicMock()
        mock_ftp_file._get_size.return_value = file_size
        mock_ftp_file.read.side_effect = file_read
        mock_ftp_file.tell.side_effect = file_tell
        mock_connection.return_value.open.return_value = mock_ftp_file

        mock_md5.return_value = hashlib.md5(file_bytes_0).hexdigest()

        sftp_props = SftpProperties(
            host='ftp.nobitex.ir',
            port=22,
            username='siavash',
            password='XXXX',
            file_path='/remote/directory/file_to_transfer.txt',
        )
        s3_props = S3Properties(bucket='example-bucket', file_path='file_in_s3.txt')

        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket=s3_props.bucket)

        transfer_file_from_sftp_to_s3(sftp_props, s3_props, chunk_size=file_size // 3)

        mock_connection.return_value.open.assert_called_once_with(sftp_props.file_path, 'rb')
        mock_ftp_file.read.assert_called()

        response = s3.get_object(Bucket=s3_props.bucket, Key=s3_props.file_path)
        content = response['Body'].read()
        assert content == (
            b'part 1 '
            + simulated_large_chunk_file
            + b'part 2 '
            + simulated_large_chunk_file
            + b'part 3 '
            + simulated_large_chunk_file
        )
