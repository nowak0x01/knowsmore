import errno
import os
import re
import sqlite3
import time
from argparse import _ArgumentGroup, Namespace
from enum import Enum
from clint.textui import progress

from knowsmore.cmdbase import CmdBase
from knowsmore.password import Password
from knowsmore.util.color import Color
from knowsmore.util.database import Database
from knowsmore.util.logger import Logger
from knowsmore.util.tools import Tools


class NTLMHash(CmdBase):

    class ImportMode(Enum):
        Undefined = 0, "Undefined"
        NTDS = 1, "NTDS File"
        Cracked = 2, "Cracked File"

    filename = ''
    db = None
    mode = ImportMode.Undefined

    def __init__(self):
        super().__init__('ntlm-hash', 'Import NTLM hashes ans users')

    def add_flags(self, flags: _ArgumentGroup):
        flags.add_argument('-format',
                           action='store',
                           default='secretsdump',
                           dest=f'file_format',
                           help=Color.s('Specify NTLM hashes format (default: {G}secretsdump{W}). Available methods: {G}secretsdump{W}'))

    def add_commands(self, cmds: _ArgumentGroup):
        cmds.add_argument('--import-ntds',
                          action='store',
                          metavar='[hashes file]',
                          type=str,
                          dest=f'ntlmfile',
                          help=Color.s('NTLM hashes filename.'))

        cmds.add_argument('--import-cracked',
                          action='store',
                          metavar='[cracked file]',
                          type=str,
                          dest=f'crackedfile',
                          help=Color.s('Hashcat cracked hashes filename. (format: {G}hash{R}:{G}password{W})'))

    def load_from_arguments(self, args: Namespace) -> bool:
        if (args.ntlmfile is None or args.ntlmfile.strip() == '') and \
                (args.crackedfile is None or args.crackedfile.strip() == ''):
            Tools.mandatory()

        if args.ntlmfile is not None and args.ntlmfile.strip() != '':
            if not os.path.isfile(args.ntlmfile):
                Logger.pl('{!} {R}error: NTLM filename is invalid {O}%s{R} {W}\r\n' % (
                    args.ntlmfile))
                Tools.exit_gracefully(1)

            try:
                with open(args.ntlmfile, 'r') as f:
                    # file opened for writing. write to it here
                    pass
            except IOError as x:
                if x.errno == errno.EACCES:
                    Logger.pl('{!} {R}error: could not open NTLM hashes file {O}permission denied{R}{W}\r\n')
                    Tools.exit_gracefully(1)
                elif x.errno == errno.EISDIR:
                    Logger.pl('{!} {R}error: could not open NTLM hashes file {O}it is an directory{R}{W}\r\n')
                    Tools.exit_gracefully(1)
                else:
                    Logger.pl('{!} {R}error: could not open NTLM hashes file {W}\r\n')
                    Tools.exit_gracefully(1)

            self.mode = NTLMHash.ImportMode.NTDS
            self.filename = args.ntlmfile

        elif args.crackedfile is not None or args.crackedfile.strip() != '':
            if not os.path.isfile(args.crackedfile):
                Logger.pl('{!} {R}error: NTLM filename is invalid {O}%s{R} {W}\r\n' % (
                    args.ntlmfile))
                Tools.exit_gracefully(1)

            try:
                with open(args.crackedfile, 'r') as f:
                    # file opened for writing. write to it here
                    pass
            except IOError as x:
                if x.errno == errno.EACCES:
                    Logger.pl('{!} {R}error: could not open NTLM hashes file {O}permission denied{R}{W}\r\n')
                    Tools.exit_gracefully(1)
                elif x.errno == errno.EISDIR:
                    Logger.pl('{!} {R}error: could not open NTLM hashes file {O}it is an directory{R}{W}\r\n')
                    Tools.exit_gracefully(1)
                else:
                    Logger.pl('{!} {R}error: could not open NTLM hashes file {W}\r\n')
                    Tools.exit_gracefully(1)

            self.mode = NTLMHash.ImportMode.Cracked
            self.filename = args.crackedfile

        if self.mode == NTLMHash.ImportMode.Undefined:
            Logger.pl('{!} {R}error: Nor {O}--import-ntds{R} or {O}--import-cracked{R} was provided{W}\r\n' % (
                args.ntlmfile))
            Tools.exit_gracefully(1)

        self.db = self.open_db(args)

        return True

    def run(self):
        if self.mode == NTLMHash.ImportMode.NTDS:
            (user_index, ntlm_hash_index) = self.get_ntds_columns()
            min_col = -1
            if user_index > min_col:
                min_col = user_index + 1
            if ntlm_hash_index > min_col:
                min_col = ntlm_hash_index + 1

            count = 0
            ignored = 0

            total = Tools.count_file_lines(self.filename)

            with progress.Bar(label="Processing ", expected_size=total) as bar:
                try:
                    with open(self.filename, 'r', encoding="UTF-8", errors="surrogateescape") as f:
                        line = f.readline()
                        while line:
                            count += 1
                            bar.show(count)

                            line = line.lower()
                            if line.endswith('\n'):
                                line = line[:-1]
                            if line.endswith('\r'):
                                line = line[:-1]

                            c1 = line.split(':')
                            if len(c1) < min_col:
                                ignored += 1
                                continue

                            f1 = c1[user_index]
                            hash = c1[ntlm_hash_index]

                            if '\\' in f1:
                                f1s = f1.strip().split('\\')
                                domain = f1s[0].strip()
                                usr = f1s[1].strip()
                            else:
                                domain = 'default'
                                usr = f1.strip()

                            type = 'U'

                            if usr.endswith('$'):
                                usr = usr[:-1]
                                type = 'M'

                            if domain == '' or usr == '' or hash == '':
                                self.print_verbose(f'Line ignored: {line}')

                            didx = self.db.insert_or_get_domain(domain)
                            if didx == -1:
                                Tools.clear_line()
                                Logger.pl('{!} {R}error: Was not possible to import the domain {O}%s{R}\r\n' % domain)
                                Tools.exit_gracefully(1)

                            self.db.insert_or_update_credential(
                                domain=didx,
                                username=usr,
                                ntlm_hash=hash,
                                type=type,
                            )

                            try:
                                line = f.readline()
                            except:
                                pass

                except KeyboardInterrupt as e:
                    raise e
                finally:
                    bar.hide = True
                    Tools.clear_line()
                    Logger.pl('{+} {C}Loaded {O}%s{W} lines' % count)

        elif self.mode == NTLMHash.ImportMode.Cracked:
            count = 0
            ignored = 0

            total = Tools.count_file_lines(self.filename)
            with progress.Bar(label="Processing ", expected_size=total) as bar:
                try:
                    with open(self.filename, 'r', encoding="UTF-8", errors="surrogateescape") as f:
                        line = f.readline()
                        while line:
                            count += 1
                            bar.show(count)

                            if line.endswith('\n'):
                                line = line[:-1]
                            if line.endswith('\r'):
                                line = line[:-1]

                            c1 = line.split(':', maxsplit=1)
                            if len(c1) != 2:
                                ignored += 1
                                continue

                            password = Password(
                                ntlm_hash=c1[0].lower(),
                                clear_text=c1[1]
                            )

                            self.db.update_password(password)

                            try:
                                line = f.readline()
                            except:
                                pass

                except KeyboardInterrupt as e:
                    raise e
                finally:
                    bar.hide = True
                    Tools.clear_line()
                    Logger.pl('{+} {C}Loaded {O}%s{W} lines' % count)

    def get_ntds_columns(self):
        self.print_verbose('Getting file column design')
        limit = 50
        count = 0
        user_index = ntlm_hash_index = -1

        with open(self.filename, 'r', encoding="UTF-8", errors="surrogateescape") as f:
            line = f.readline()
            while line:
                count += 1
                if count >= limit:
                    break

                line = line.lower()
                if line.endswith('\n'):
                    line = line[:-1]
                if line.endswith('\r'):
                    line = line[:-1]

                c1 = line.split(':')
                if len(c1) < 3:
                    continue

                for idx, x in enumerate(c1):
                    if user_index == -1:
                        if '$' in x or '\\' in x:
                            user_index = idx

                    if ntlm_hash_index == -1:
                        hash = re.sub("[^a-f0-9]", '', x.lower())
                        if len(hash) == 32 and hash != "aad3b435b51404eeaad3b435b51404ee":
                            ntlm_hash_index = idx

                if user_index != -1 and ntlm_hash_index != -1:
                    break

                if user_index == -1 or ntlm_hash_index == -1:
                    user_index = ntlm_hash_index = -1

                try:
                    line = f.readline()
                except:
                    pass

        if user_index < 0 or ntlm_hash_index < 0:
            Logger.pl('{!} {R}error: import file format not recognized {W}\r\n')
            Tools.exit_gracefully(1)

        return user_index, ntlm_hash_index
