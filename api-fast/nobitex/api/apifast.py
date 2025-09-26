import json
import os
import socket

import sentry_sdk
from flask import Flask
from sentry_sdk.integrations.flask import FlaskIntegration

from nobitex.api import cache
from nobitex.api.base import create_response
from nobitex.api.market import market_app
from nobitex.api.udf import udf_app

# Variables
SERVER_NAME = socket.gethostname()
ENV = os.environ.get('ENV') or 'debug'
DEBUG = ENV == 'debug'
IS_PROD = ENV == 'prod'
IS_TESTNET = ENV == 'testnet'
REDIS_DB = 1 if IS_PROD else 3 if IS_TESTNET else 5
REDIS_HOST = 'db.local:6379' if IS_PROD else 'localhost:6379'
ENABLE_SENTRY = not DEBUG

# Versioning
RELEASE_VERSION = 'v1.0.0'
CURRENT_COMMIT = 'ec9d5506'

if ENABLE_SENTRY:
    sentry_sdk.init(
        dsn="https://18bd94ea084be6947b3c327f86c01bc2@sentry.hamravesh.com/6838",
        integrations=[FlaskIntegration(transaction_style='url')],
        environment=ENV,
        enable_tracing=True,
        traces_sampler=lambda _: 1e-5,  # To ignore requests being traced in frontend -- i.e. have Sentry-Trace header
    )

# Flask App
app = Flask(__name__)
app.config['REDIS_URL'] = f'redis://{REDIS_HOST}/{REDIS_DB}'
app.register_blueprint(udf_app)
app.register_blueprint(market_app)
cache.init(app)


@app.route('/')
def home():
    return 'api-f'


@app.route('/users/preferences', methods=['POST'])
def user_preferences():
    options_v1 = cache.get('options_v1', {})
    options_v2 = cache.get('options_v2', {})
    return create_response(json.dumps({
        'status': 'ok',
        'options': options_v1,
        'optionsV2': options_v2,
        'preferences': {'muteNotifications': True},
    }), cors=True)


@app.route('/crm/news/list', methods=['POST'])
def news_list():
    news_list_response = cache.get('news_list', '{"status":"ok","news":[]}')
    return app.response_class(
        response=news_list_response,
        status=200,
        mimetype='application/json'
    )


@app.route('/notifications/list', methods=['POST'])
def notifications_list():
    user_id = None
    default_response = '{"status":"ok","notifications":[]}'
    if user_id:
        notifications_response = cache.get('user_{}_notifications'.format(user_id), default_response)
    else:
        notifications_response = default_response
    return app.response_class(
        response=notifications_response,
        status=200,
        mimetype='application/json'
    )


@app.route('/check/version', methods=['POST'])
def check_version():
    response = '{"status":"ok","version":{"api":"v3.6.0-4292eed","web":"v2.7-44099ca","android":9812141},"flags":[]}'
    return app.response_class(
        response=response,
        status=200,
        mimetype='application/json'
    )


@app.route('/check/debug', methods=['GET'])
def check_debug():
    return create_response(json.dumps({
        'status': 'ok',
        'version': '{}-{}'.format(RELEASE_VERSION, CURRENT_COMMIT),
        'server': SERVER_NAME,
    }))


@app.route('/users/wallets/list', methods=['POST'])
def user_wallets_list():
    return create_response('{"status":"failed"}', status=200)


@app.route('/market/orders/list', methods=['POST'])
def user_orders_list():
    return create_response('{"status":"failed"}', status=200)
