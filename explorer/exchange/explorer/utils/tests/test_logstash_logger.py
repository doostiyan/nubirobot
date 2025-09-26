import json

from exchange.settings import SafeLogstashRecordFormatter, logging


def test__safe_logstash_record_formatter_message_field__successful():
    formatter = SafeLogstashRecordFormatter()

    logger = logging.getLogger('test_logger')
    log_record = logger.makeRecord(
        name='test_logger',
        level=logging.INFO,
        fn='test_fn',
        lno=10,
        msg='This is a test message',
        args=(),
        exc_info=None
    )

    formatted = formatter.format(log_record)
    record_dict = json.loads(formatted)

    expected = {
        'args': [],
        'created': log_record.created,
        'extra': {'index_name': 'log'},
        'levelno': 20,
        'message': 'This is a test message',
        'msg': 'This is a test message',
        'relativeCreated': log_record.relativeCreated
    }

    for k, v in expected.items():
        assert record_dict.get(k) == v
