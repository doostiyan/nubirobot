import glob
from pathlib import Path

from django.conf import settings
from django.test import TestCase, TransactionTestCase


def wrap_test(test):
    def wrapper(self):
        self.run_test(test)
    return wrapper


class FileBasedTestCaseMeta(type):
    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        if hasattr(self, 'root') and self.root:
            files_path = Path(settings.BASE_DIR) / Path(self.root) / '**' / 'test-*'
            for test_file_path in glob.glob(str(files_path), recursive=True):
                with open(test_file_path) as file:
                    name = Path(test_file_path).stem.replace('-', '_')
                    test = file.read()
                setattr(self, name, wrap_test(test))
        return self


class FileBasedTestCase(TestCase, metaclass=FileBasedTestCaseMeta):
    root = None

    @staticmethod
    def run_test(test_input):
        pass


class MultipleFileBasedTestCaseMeta(type):
    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls, *args, **kwargs)
        if hasattr(self, 'root') and self.root:
            files_path = Path(settings.BASE_DIR) / Path(self.root) / '**' / 'test-*'
            tests = []
            for test_file_path in glob.glob(str(files_path), recursive=True):
                with open(test_file_path) as file:
                    name = Path(test_file_path).stem.replace('-', '_')
                    tests.append(file.read())
            setattr(self, name, wrap_test(tests))
        return self


class MultipleFileBasedTestCase(TransactionTestCase, metaclass=MultipleFileBasedTestCaseMeta):
    root = None

    @staticmethod
    def run_test(test_input):
        pass
