import json
import os
import sqlite3
import time
from argparse import _ArgumentGroup, Namespace
from pathlib import Path
from tabulate import _table_formats, tabulate
from binascii import hexlify
from enum import Enum

from knowsmore.cmdbase import CmdBase
from knowsmore.password import Password
from knowsmore.util.color import Color
from knowsmore.util.database import Database
from knowsmore.util.knowsmoredb import KnowsMoreDB
from knowsmore.util.logger import Logger


class Stats(CmdBase):
    db = None
    out_file = None

    def __init__(self):
        super().__init__('stats', 'Generate password and hashes statistics')

    def add_flags(self, flags: _ArgumentGroup):
        flags.add_argument('--save-to',
                           action='store',
                           default='',
                           dest=f'out_file',
                           help=Color.s(
                               'Output file to save JSON data'))

    def add_commands(self, cmds: _ArgumentGroup):
        pass

    def load_from_arguments(self, args: Namespace) -> bool:

        if args.out_file is not None and args.out_file.strip() != '':
            self.out_file = Path(args.out_file).absolute()

        if self.out_file is not None:
            if os.path.exists(self.out_file):
                Logger.pl('{!} {R}error: out file ({O}%s{R}) already exists {W}\r\n' % (
                    self.out_file))
                exit(1)

        self.db = self.open_db(args)

        return True

    def run(self):

        data = []

        # General Top 10
        rows_general = self.db.select_raw(
            sql='select row_number() OVER (ORDER BY count(distinct c.credential_id) DESC) AS top, p.password, count(distinct c.credential_id) as qty '
                'from credentials as c '
                'inner join passwords as p '
                'on c.password_id = p.password_id '
                'where p.password <> "" '
                'group by p.password '
                'order by qty desc '
                'LIMIT 10',
            args=[]
        )

        if len(rows_general) > 0:
            data.append({
                'type': 'top10',
                'domain': 'all',
                'description': 'General Top 10 passwords',
                'rows': rows_general
            })

        domains = self.db.select('domains')
        for r in domains:

            # Domain Top 10
            rows = self.db.select_raw(
                sql='select row_number() OVER (ORDER BY count(distinct c.credential_id) DESC) AS top, p.password, count(distinct c.credential_id) as qty '
                    'from credentials as c '
                    'inner join passwords as p '
                    'on c.password_id = p.password_id '
                    'where p.password <> "" and c.domain_id = ?'
                    'group by p.password '
                    'order by qty desc '
                    'LIMIT 10',
                args=[r['domain_id']]
            )

            if len(rows) > 0:
                data.append({
                    'type': 'top10',
                    'domain': r['name'],
                    'description': 'Top 10 passwords for %s' % r['name'],
                    'rows': rows
                })

        if self.out_file is None:

            for d in data:
                Color.pl('{?} {W}{D}%s{W}' % d['description'])
                headers = d['rows'][0].keys()
                data = [item.values() for item in d['rows']]
                print(tabulate(data, headers, tablefmt='psql'))
                print(' ')

        else:
            with open(self.out_file, "a", encoding="UTF-8") as text_file:
                text_file.write(json.dumps(
                    {
                        'data': data,
                        'meta': {
                            'type': 'stats',
                            'count': len(data),
                            'version': 1
                        }
                    }
                ))





