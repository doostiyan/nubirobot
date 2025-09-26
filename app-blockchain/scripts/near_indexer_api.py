import logging
import atexit
import os
from decimal import Decimal, localcontext
from typing import Union

import psycopg2
from flask import Flask, jsonify, request

"""
    This module provides REST API over NEAR-Indexer (https://github.com/near/near-indexer-for-explorer), 
    a public Read-only PostgreSQL connection to DB that records almost all network events.  
"""

app = Flask(__name__)


APP_NAME = 'Near_indexer_API'
DB_HOST = 'mainnet.db.explorer.indexer.near.dev'
DB_NAME = 'mainnet_explorer'
DB_USER = 'public_readonly'
DB_PASS = 'nearprotocol'
VALID_TX_TYPE = 'TRANSFER'
LOG_LEVEL = logging.DEBUG
GET_TXS_LIMIT = 3
tries = 20  # in case of DB connection error
ENV = os.environ.get('ENV') or 'debug'
IS_DEBUG = ENV == 'debug'

HOSTNAME = os.environ.get('HOSTNAME') or ('127.0.0.1' if IS_DEBUG else 'nearapi61')

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')


@app.route('/nearindexer_getlatestblock', methods=['GET'])
def get_latest_block():
    global db_connection
    logging.debug(f'get_latest_block started, request arg: {request.args}')
    min_height = request.args.get('min_height')
    max_height = request.args.get('max_height')
    get_addresses_query = f"""
        select t2.*, status, gas_burnt from (
            select t.*, action_kind, args from (
                select transaction_hash, block_hash, gas_price, blocks.block_timestamp, signer_account_id, receiver_account_id, converted_into_receipt_id 
                  from transactions join blocks on included_in_block_hash=block_hash 
                  where included_in_block_hash in (select block_hash from blocks where block_height between {min_height} and {max_height})) as t 
                left outer join transaction_actions on t.transaction_hash=transaction_actions.transaction_hash 
                where action_kind='TRANSFER') as t2 
              left outer join execution_outcomes on converted_into_receipt_id=receipt_id 
              where execution_outcomes.status != 'FAILURE'

                """
    results = execute_query(get_addresses_query)
    logging.debug(f'get_latest_block finished, result: {results}')
    response = serialize_addresses_in_block_range(results)
    return jsonify(response)


@app.route('/nearindexer_gettxs', methods=['GET'])
def get_txs():
    global db_connection
    logging.debug(f'get_txs started, request arg: {request.args}')
    account_address = request.args.get('account_address')
    direction = request.args.get('direction', default='receiver')
    account_id_column_name = 'signer_account_id' if direction == 'sender' else 'receiver_account_id'
    get_txs_query = f"""
        select 
            txs.transaction_hash,
            txs.block_timestamp,
            txs.signer_account_id,
            txs.receiver_account_id,
            transaction_actions.action_kind,
            transaction_actions.args,
            blocks.block_height,
            execution_outcomes.status
        from(
        
                SELECT 
                    transactions.transaction_hash,
                    transactions.included_in_block_hash, 
                    transactions.block_timestamp,
                    transactions.signer_account_id,
                    transactions.receiver_account_id,
                    transactions.converted_into_receipt_id
                FROM transactions
                where {account_id_column_name}='{account_address}'
                ORDER BY transactions.block_timestamp DESC
                  LIMIT {GET_TXS_LIMIT}
            ) as txs 
        left join execution_outcomes on txs.converted_into_receipt_id = execution_outcomes.receipt_id
        left join blocks on txs.included_in_block_hash = blocks.block_hash
        LEFT JOIN transaction_actions on txs.transaction_hash = transaction_actions.transaction_hash
  """
    results = execute_query(get_txs_query)
    logging.debug(f'get_txs finished, result: {results}')
    response = serialize_address_txs(results)
    return jsonify(response)


@app.route('/nearindexer_gettxdetail', methods=['GET'])
def get_tx_details():
    global db_connection
    logging.debug(f'get_tx_details started, request arg: {request.args}')
    tx_hash = request.args.get('tx_hash')
    get_tx_detail_query = f"""
        select 
            transactions.transaction_hash as tx_hash, 
            transactions.converted_into_receipt_id as receipt_id,
            transactions.signer_account_id,
            transactions.receiver_account_id,
            transactions.block_timestamp,
            execution_outcomes.status,
            execution_outcomes.gas_burnt,
            transaction_actions.action_kind,
transaction_actions.args
        from transactions 
        left join transaction_actions on transactions.transaction_hash = transaction_actions.transaction_hash
        left join execution_outcomes on transactions.converted_into_receipt_id=execution_outcomes.receipt_id
        where transactions.transaction_hash='{tx_hash}'
  """
    results = execute_query(get_tx_detail_query)
    logging.debug(f'get_tx_details finished, result: {results}')
    response = serialize_tx_detail(results)
    return jsonify(response)


def serialize_tx_detail(results):
    if len(results) == 1:
        row = results[0]
        details = {
            'hash': row[0],
            'from': row[2],
            'to': row[3],
            'date': row[4],
            'success': row[5],
            'fees': from_unit(int(Decimal(row[6]))),
            'type': row[7],
            'value': from_unit(int(Decimal(row[8].get('deposit', 0))))
        }
    else:  # invalidate multi transfer txs if exist
        details = {
            'success': 'multi_transfer',
        }
    return {'details': details}


def execute_query(get_addresses_query):
    global db_connection
    for i in range(tries):
        try:
            with db_connection.cursor() as cursor:
                cursor.execute(get_addresses_query)
                results = cursor.fetchall()
                break
        except psycopg2.Error as e:
            logging.error(e)
            logging.warning(f'retry : {i}')
            if i < tries - 1:  # i is zero indexed
                db_connection = reconnect()
                continue
            else:
                disconnect()
                logging.critical('all attempts failed!')
                raise
    return results


def serialize_addresses_in_block_range(results):
    addresses = []
    for row in results:
        addresses.append({
            'tx_hash': row[0],
            'from_address': row[4],
            'to_address': row[5],
            'value': from_unit(int(Decimal(row[8].get('deposit', 0))))
        })
    return addresses


def serialize_address_txs(results):
    txs = []
    for row in results:
        action_kind = row[4]
        if action_kind == VALID_TX_TYPE:
            txs.append({
                'tx_hash': row[0],
                'value': from_unit(int(Decimal(row[5].get('deposit', 0)))),
                'sender': row[2],
                'receiver': row[3],
                'block_height': int(row[6]),
                'block_time': (row[1]),
                'status': row[7]
            })
    return {'txs': txs}

@app.route('/nearindexer_getblockhead', methods=['GET'])
def get_block_head():
    logging.debug(f'get_block_head started')
    get_block_head_query = '''select * from blocks order by block_height desc limit 1'''
    results = execute_query(get_block_head_query)
    response = serialize_block_head(results)
    logging.debug(f'get_block_head finished, result: {response}')
    return jsonify(response)


def serialize_block_head(results):
    return {'block_height': int(results[0][0])}


def from_unit(number: int, precision=24, negative_value=False) -> Union[int, Decimal]:
    """
    imported from blockchain.utils.py
    """
    min_unit = 1
    max_unit = 2 ** 256 - 1
    if number == 0:
        return Decimal('0.0')
    min_value = -max_unit if negative_value else min_unit
    if number < min_value or number > max_unit:
        raise ValueError('value must be between 1 and 2**256 - 1')
    unit_value = Decimal('1e{}'.format(precision))
    with localcontext() as ctx:
        ctx.prec = 999
        d_number = Decimal(value=number, context=ctx)
        result_value = d_number / unit_value
    return result_value


@atexit.register
def disconnect():
    if 'db_connection' in locals():
        db_connection.close()


def reconnect():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS,
                            connect_timeout=10, options='-c statement_timeout=10000')


db_connection = reconnect()
if __name__ == '__main__':
    host = HOSTNAME
    port = 5000
    app.run(host=host, port=port, debug=IS_DEBUG)
