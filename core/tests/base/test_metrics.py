import pytest

from exchange.base.metrics import (
    _gauge_meter,
    _gauge_meter_incr,
    _log_time,
    _metric_incr,
    _metric_reset,
    extract_labels_from_metric,
    get_labels_from_metric,
    validate_metric,
)
from exchange.broker.broker.topics import Topics


# A fake metric producer that captures events.
class FakeMetricProducer:
    def __init__(self):
        self.events = []  # List of tuples: (topic, event, key)

    def write_event(self, topic, event, key, on_error=None):
        self.events.append((topic, event, key))


# A fake MetricSchema that simply stores its input and returns it on serialize.
class FakeMetricSchema:
    def __init__(self, **kwargs):
        self.data = kwargs

    def serialize(self):
        return self.data


@pytest.fixture
def fake_producer(monkeypatch):
    producer = FakeMetricProducer()
    # Patch the metric_producer in the 'metrics' module.
    monkeypatch.setattr('exchange.base.metrics.metric_producer', producer)
    return producer


@pytest.fixture(autouse=True)
def fake_metric_schema(monkeypatch):
    # Replace MetricSchema in the 'metrics' module with our fake version.
    monkeypatch.setattr('exchange.base.metrics.MetricSchema', FakeMetricSchema)


@pytest.fixture(autouse=True)
def setup_metric_label_mapping(monkeypatch):
    # Create a new mapping for each test to ensure parallel safety.
    new_mapping = {
        'test_metric': ['label1', 'label2'],
        'hist_metric': ['labelA', 'labelB'],
    }
    monkeypatch.setattr('exchange.base.metrics.METRIC_LABEL_MAPPING', new_mapping)


# ------------------ Tests for get_labels_from_metric ------------------
def test_get_labels_from_metric_valid():
    metric, labels = get_labels_from_metric('test__a_b_c')
    assert metric == 'test'
    assert labels == ['a', 'b', 'c']


def test_get_labels_from_metric_without_label():
    assert get_labels_from_metric('metric1') == ('metric1', None)


# ------------------ Tests for extract_labels_from_metric ------------------
def test_extract_labels_from_metric_valid():
    metric, label_dict = extract_labels_from_metric('test_metric__v1_v2')
    assert metric == 'test_metric'
    assert label_dict == {'label1': 'v1', 'label2': 'v2'}


def test_extract_labels_from_metric_invalid_label_count():
    with pytest.raises(ValueError, match='invalid labels for metric test_metric!'):
        extract_labels_from_metric('test_metric__v1')


def test_extract_labels_from_metric_unknown_metric():
    with pytest.raises(KeyError, match="Metric's labels should be defined in METRIC_LABEL_MAPPING"):
        extract_labels_from_metric('unknown__v1_v2')


# ------------------ Tests for validate_metric ------------------
def test_validate_metric_no_conflict():
    validate_metric('test_metric__v1_v2', {})


def test_validate_metric_no_conflict_explicit_label():
    validate_metric('test_metric', {'v1': '1', 'v2': '2'})


def test_validate_metric_conflict():
    with pytest.raises(ValueError, match='Labels should be set only in metric or labels args'):
        validate_metric('test_metric__v1_v2', {'extra': 'value'})


# ------------------ Tests for metric_incr ------------------
def test_metric_incr_with_explicit_labels(fake_producer):
    # Explicit labels provided; metric string does not include '__'
    _metric_incr('custom_metric', amount=5, external='value')
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'counter',
        'name': 'custom_metric',
        'labels': {'external': 'value'},
        'value': 5,
        'operation': 'inc',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'custom_metric'


def test_metric_incr_without_explicit_labels(fake_producer):
    # No explicit labels; labels are extracted from the metric string.
    _metric_incr('test_metric__v1_v2', amount=3)
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'counter',
        'name': 'test_metric',
        'labels': {'label1': 'v1', 'label2': 'v2'},
        'value': 3,
        'operation': 'inc',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'test_metric'


def test_metric_incr_conflicting_labels():
    # Providing both embedded labels and explicit labels should raise an error.
    with pytest.raises(ValueError, match='Labels should be set only in metric or labels args'):
        _metric_incr('test_metric__v1_v2', amount=5, extra='value')


# ------------------ Tests for metric_reset ------------------
def test_metric_reset_with_explicit_labels(fake_producer):
    # Explicit labels provided; metric string does not include '__'
    _metric_reset('custom_metric', external='value')
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'counter',
        'name': 'custom_metric',
        'labels': {'external': 'value'},
        'operation': 'reset',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'custom_metric'


def test_metric_reset_without_explicit_labels(fake_producer):
    # No explicit labels; labels are extracted from the metric string.
    _metric_reset('test_metric__v1_v2')
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'counter',
        'name': 'test_metric',
        'labels': {'label1': 'v1', 'label2': 'v2'},
        'operation': 'reset',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'test_metric'


def test_metric_reset_conflicting_labels():
    # Providing both embedded labels and explicit labels should raise an error.
    with pytest.raises(ValueError, match='Labels should be set only in metric or labels args'):
        _metric_reset('test_metric__v1_v2', amount=5, extra='value')


# ------------------ Tests for gauge_meter ------------------
def test_gauge_meter_with_explicit_labels(fake_producer):
    # Explicit labels provided; metric string does not include '__'
    _gauge_meter('custom_metric', amount=5, external='value')
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'gauge',
        'name': 'custom_metric',
        'labels': {'external': 'value'},
        'value': 5,
        'operation': 'set',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'custom_metric'


def test_gauge_meter_without_explicit_labels(fake_producer):
    # No explicit labels; labels are extracted from the metric string.
    _gauge_meter('test_metric__v1_v2', amount=-3)
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'gauge',
        'name': 'test_metric',
        'labels': {'label1': 'v1', 'label2': 'v2'},
        'value': -3,
        'operation': 'set',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'test_metric'


def test_gauge_meter_conflicting_labels():
    # Providing both embedded labels and explicit labels should raise an error.
    with pytest.raises(ValueError, match='Labels should be set only in metric or labels args'):
        _gauge_meter('test_metric__v1_v2', amount=5, extra='value')


def test_gauge_meter_incr_with_explicit_labels(fake_producer):
    # Explicit labels provided; metric string does not include '__'
    _gauge_meter_incr('custom_metric', amount=5, external='value')
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'gauge',
        'name': 'custom_metric',
        'labels': {'external': 'value'},
        'value': 5,
        'operation': 'inc',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'custom_metric'


def test_gauge_meter_incr_without_explicit_labels(fake_producer):
    # No explicit labels; labels are extracted from the metric string.
    _gauge_meter_incr('test_metric__v1_v2', amount=-3)
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'gauge',
        'name': 'test_metric',
        'labels': {'label1': 'v1', 'label2': 'v2'},
        'value': -3,
        'operation': 'inc',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'test_metric'
# ------------------ Tests for log_time ------------------
def test_log_time_with_explicit_labels_and_buckets(fake_producer):
    _log_time('custom_metric', value=100, buckets=[0.1, 1.0, 10.0], external='value')
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'histogram',
        'name': 'custom_metric',
        'labels': {'external': 'value'},
        'value': 100,
        'operation': 'set',
        'buckets': [0.1, 1.0, 10.0],
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'custom_metric'


def test_log_time_without_explicit_labels(fake_producer):
    _log_time('hist_metric__a_b', value=200)
    assert len(fake_producer.events) == 1
    topic, event, key = fake_producer.events[0]
    expected_event = {
        'type': 'histogram',
        'name': 'hist_metric',
        'labels': {'labelA': 'a', 'labelB': 'b'},
        'value': 200,
        'operation': 'set',
    }
    assert topic == Topics.METRIC
    assert event == expected_event
    assert key == 'hist_metric'


def test_log_time_conflicting_labels():
    with pytest.raises(ValueError, match='Labels should be set only in metric or labels args'):
        _log_time('hist_metric__a_b', value=100, extra='value')
