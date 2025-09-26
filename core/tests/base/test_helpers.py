import sys
import time
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

from django.db import models

from exchange.base.helpers import (
    batcher,
    context_flag,
    get_max_db_value,
    is_url_allowed,
    sleep_remaining,
    stage_changes,
)


class CacheDecoratorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        class SampleModel(models.Model):
            char_field = models.CharField(max_length=20)
            int_field = models.IntegerField()

            class Meta:
                app_label = 'test1'

        cls.model = SampleModel

    def setUp(self):
        self.model.save = Mock()
        self.sample_instance = self.model(char_field='test value', int_field=3)

    def test_save_changed_staged_field(self):
        with stage_changes(self.sample_instance, update_fields=['char_field']):
            self.sample_instance.char_field = 'new value'
        self.sample_instance.save.assert_called_with(update_fields=['char_field'], using='default')

    def test_ignore_unchanged_staged_field(self):
        with stage_changes(self.sample_instance, update_fields=['char_field']):
            self.sample_instance.char_field = 'test value'
        self.sample_instance.save.assert_called_with(update_fields=[], using='default')

    def test_ignore_changed_not_staged_field(self):
        with stage_changes(self.sample_instance, update_fields=['char_field']):
            self.sample_instance.int_field = 5
        self.sample_instance.save.assert_called_with(update_fields=[], using='default')

    def test_ignore_partial_unchanged_staged_field(self):
        with stage_changes(self.sample_instance, update_fields=['char_field', 'int_field']):
            self.sample_instance.int_field = 5
        self.sample_instance.save.assert_called_with(update_fields=['int_field'], using='default')

    def test_ignore_changed_staged_field_on_error(self):
        with self.assertRaises(Exception):
            with stage_changes(self.sample_instance, update_fields=['char_field', 'int_field']):
                self.sample_instance.int_field = 5
                raise Exception('test error')
        self.sample_instance.save.assert_not_called()


def test_max_db_value():
    class SampleModel(models.Model):
        decimal_field_1 = models.DecimalField(max_digits=10, decimal_places=4)
        decimal_field_2 = models.DecimalField(max_digits=10, decimal_places=0)
        decimal_field_3 = models.DecimalField(max_digits=10, decimal_places=10)

        class Meta:
            app_label = 'test2'

    assert get_max_db_value(SampleModel.decimal_field_1) == Decimal('999999.9999')
    assert get_max_db_value(SampleModel.decimal_field_2) == Decimal('9999999999')
    assert get_max_db_value(SampleModel.decimal_field_3) == Decimal('0.9999999999')


class FlagContextTest(TestCase):
    @staticmethod
    def assert_flag(value):
        assert context_flag.get('FLAG1', False) is value

    def setUp(self):
        self.assert_flag(value=False)

    def tearDown(self):
        self.assert_flag(value=False)

    def test_set_context_as_function_decorator(self):
        @context_flag(FLAG1=True)
        def f1():
            self.assert_flag(value=True)

        f1()

    def test_set_context_for_two_nested_function_decorator(self):
        @context_flag(FLAG1=True)
        def f1():
            self.assert_flag(value=True)

        @context_flag(FLAG1=False)
        def f2():
            self.assert_flag(value=False)
            f1()
            self.assert_flag(value=False)

        f2()

    def test_set_context_as_context_processor(self):
        with context_flag(FLAG1=True):
            self.assert_flag(True)

    def test_set_context_for_two_nested_context_processor(self):
        with context_flag(FLAG1=True):
            with context_flag(FLAG1=False):
                self.assert_flag(False)
            self.assert_flag(True)

    def test_set_context_as_class_decorator(self):
        """Using decorator on class can lead to many breaks"""
        assert_flag = self.assert_flag

        @context_flag(FLAG1=True)
        class C1:
            def __init__(self):
                self.a1 = 0
                assert_flag(value=True)  # Benefits class decorator

            @staticmethod
            def m1():
                assert_flag(value=False)  # Does not benefit class decorator (python3.10)

            @classmethod
            def m2(cls):
                cls.m1()
                assert_flag(value=False)  # Broken

            def m3(self):
                self.a1 += 1
                assert_flag(value=False)  # Does not benefit class decorator

        if sys.version_info < (3, 10, 0):
            with self.assertRaises(TypeError, msg="'staticmethod' object is not callable"):
                C1.m1()
        else:
            C1.m1()

        with self.assertRaises(TypeError, msg="'classmethod' object is not callable"):
            C1.m2()

        c1 = C1()
        c1.m3()

    def test_set_context_as_class_method_decorator(self):
        """Using decorator on class can lead to many breaks"""
        assert_flag = self.assert_flag

        class C1:
            def __init__(self):
                self.a1 = 0
                assert_flag(value=False)

            @staticmethod
            @context_flag(FLAG1=True)
            def m1():
                assert_flag(value=True)

            @classmethod
            @context_flag(FLAG1=True)
            def m2(cls):
                cls.m1()
                assert_flag(value=True)

            @context_flag(FLAG1=True)
            def m3(self):
                self.a1 += 1
                assert_flag(value=True)

        C1.m1()
        C1.m2()
        c1 = C1()
        c1.m3()


def test_sleep_remaining():
    t1 = time.time()

    with sleep_remaining(seconds=0.2):
        time.sleep(0.1)  # body less than seconds
    t2 = time.time()
    assert round(t2 - t1, 1) == 0.2

    with sleep_remaining(seconds=0.1):
        time.sleep(0.2)  # body more than seconds
    t3 = time.time()
    assert round(t3 - t2, 1) == 0.2


def test_batcher():
    # Test Sequence input type
    a = list(range(20))

    batched_a = batcher(a, batch_size=7)
    batches = list(batched_a)
    assert len(batches) == 3
    assert batches[0] == [0, 1, 2, 3, 4, 5, 6]
    assert batches[2] == [14, 15, 16, 17, 18, 19]

    batched_a = batcher(a, batch_size=15)
    batches = list(batched_a)
    assert len(batches) == 2
    assert batches[1] == [15, 16, 17, 18, 19]

    batched_a = batcher(a, batch_size=3)
    batches = list(batched_a)
    assert len(batches) == 7
    assert batches[0] == [0, 1, 2]
    assert batches[6] == [18, 19]

    # Idempotent = True
    a = list(range(20))
    batches = []
    for batch in batcher(a, batch_size=7, idempotent=True):
        for i in batch:
            a.remove(i)
        batches.append(batch)

    assert len(batches) == 3
    assert batches[2] == [14, 15, 16, 17, 18, 19]


class AllowedUrlTest(TestCase):
    @staticmethod
    def test_is_url_allowed():
        allowed_domains = {'nobitex.ir', 'nobitex.net', 'nobitex.co.ir'}
        url = 'https://nobitex.ir/app/wallet/?amount=1000'
        assert is_url_allowed(url, allowed_domains)

        url = 'https://nobitex.net/app/wallet/?amount=1000'
        assert is_url_allowed(url, allowed_domains)

        url = 'https://nobitex.co.ir/app/wallet/?amount=1000'
        assert is_url_allowed(url, allowed_domains)

        url = 'nobitex://open?amount=1000'
        assert is_url_allowed(url, allowed_domains)

        url = 'https://sub.nobitex.ir/app/wallet/?amount=1000'
        assert is_url_allowed(url, allowed_domains)

        url = 'https://sub.nobitex.co.ir/app/wallet/?amount=1000'
        assert is_url_allowed(url, allowed_domains)

        url = 'https://nobitex1.ir/app/wallet/?amount=1000'
        assert not is_url_allowed(url, allowed_domains)

        url = 'http://nobitex.ir/app/wallet/?amount=1000'
        assert not is_url_allowed(url, allowed_domains)

        url = 'https://sub.nobitex1.ir/app/wallet/?amount=1000'
        assert not is_url_allowed(url, allowed_domains)

        url = 'https://sub.nobitex.co.uk/app/wallet/?amount=1000'
        assert not is_url_allowed(url, allowed_domains)
