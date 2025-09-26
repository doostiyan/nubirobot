from collections import defaultdict
from operator import itemgetter

from django.conf import settings


class SQLQuery:
    def __init__(self, query):
        if isinstance(query, str):
            query = {'sql': query, 'time': 0}
        self.time = int(float(query['time']) * 1000)
        self.sql = sql = query['sql']
        verb = sql[:sql.find(' ')]
        self.type = verb.upper()
        self.table = '?'
        self.sql_extra = ''

        if self.is_select:
            from_start = sql.find('FROM ') + 6
            from_to = sql.find('"', from_start)
            self.table = sql[from_start:from_to]
            self.sql_extra = sql[from_to + 2:]

    @property
    def is_select(self):
        return self.type == 'SELECT'

    def __str__(self):
        if self.is_select:
            return 'SELECT...FROM {} {}'.format(self.table, self.sql_extra)
        return self.sql


def analyze_queries(print_all=False):
    if not settings.DEBUG:
        return
    from django.db import connection
    queries = []
    for query in connection.queries:
        queries.append(SQLQuery(query))

    times = defaultdict(int)
    counts = defaultdict(int)
    tables_select = defaultdict(int)
    tables_select_time = defaultdict(int)

    for q in queries:
        counts[q.type] += 1
        times[q.type] += q.time
        if q.is_select:
            tables_select[q.table] += 1
            tables_select_time[q.table] += q.time

    duplicates = defaultdict(int)
    for q in queries:
        duplicates[q.sql] += 1
    duplicates = [(c, q) for q, c in duplicates.items() if c > 1]
    duplicates.sort(reverse=True)

    print('')
    print('=' * 120)
    print('Total Queries:\t{}'.format(len(queries)))
    print('Queries by type:', end='\t')
    for tp, count in counts.items():
        print('{}: {}, {}ms'.format(tp, count, times[tp]), end='\t')
    print('')
    print('Selects by table:')
    for table, count in tables_select.items():
        print('\t{}{}{}\t{}ms'.format(table, ' ' * (32 - len(table)), count, tables_select_time[table]))
    if duplicates:
        print('Duplicates:')
        for count, query in duplicates:
            print('\t{}x\t{}'.format(count, str(SQLQuery(query))[:100]))
    if print_all:
        print('Queries:')
        for query in queries:
            print('\t' + str(query))

    print('Total Queries:\t{}'.format(len(queries)))
    print('=' * 120)
    print('')
