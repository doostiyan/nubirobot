import hashlib
import os
import subprocess
import uuid

from django.conf import settings
from django.test import TestCase

from exchange.accounts.models import UploadedFile, User


def calculate_file_checksum(file_disk_path, file_content) -> str:
    try:
        return subprocess.run(['sha1sum', file_disk_path], stdout=subprocess.PIPE, text=True).stdout.split()[0]
    except FileNotFoundError:  # command not found in os
        return hashlib.sha1(file_content).digest().hex()


class TestUploadedFileModel(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.disk_file_upload_folder_path = os.path.join(settings.MEDIA_ROOT, 'uploads/files')

    def tearDown(self) -> None:
        for file in UploadedFile.objects.all():
            try:
                os.remove(file.disk_path)
            except FileNotFoundError:  # for empty_uploaded_file scenario
                pass

    def test_create_uploaded_file(self):
        filename_uuid = uuid.uuid4()
        test_file_path = os.path.join(self.disk_file_upload_folder_path, filename_uuid.hex)
        file_content = b'This is a test file.'

        with open(test_file_path, 'wb') as f:
            f.write(file_content)

        uploaded_file = UploadedFile(filename=filename_uuid, user=self.user)
        uploaded_file.save()

        expected_size = len(file_content)
        expected_sha1 = calculate_file_checksum(uploaded_file.disk_path, file_content)

        assert uploaded_file.size == expected_size
        assert uploaded_file.checksum.hex() == expected_sha1

    def test_create_empty_uploaded_file(self):
        uploaded_file = UploadedFile(user=self.user)
        uploaded_file.save()
        assert uploaded_file.size == 0
        assert uploaded_file.checksum == b''

    def test_update_uploaded_file(self):
        uploaded_file = UploadedFile(user=self.user)
        uploaded_file.save()

        filename_uuid = uuid.uuid4()
        test_file_path = os.path.join(self.disk_file_upload_folder_path, filename_uuid.hex)
        file_content = b'This is a another test file.'

        with open(test_file_path, 'wb') as f:
            f.write(file_content)

        uploaded_file.filename = filename_uuid
        uploaded_file.save()

        expected_size = len(file_content)
        expected_sha1 = calculate_file_checksum(uploaded_file.disk_path, file_content)

        assert uploaded_file.size == expected_size
        assert uploaded_file.checksum.hex() == expected_sha1
