"""Native PostgreSQL client; standard library only, no Python packages required."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def command():
    executable = os.environ.get('PSQL') or shutil.which('psql')
    if not executable:
        executable = r'C:\Program Files\PostgreSQL\17\bin\psql.exe'
    return [executable, '-X', '-w', '-q', '-At', '-v', 'ON_ERROR_STOP=1',
            '-h', os.environ.get('PGHOST') or '127.0.0.1',
            '-p', os.environ.get('PGPORT') or '5432',
            '-U', os.environ.get('PGUSER') or 'postgres',
            '-d', os.environ.get('PGDATABASE') or 'docbench']


def sql(statement):
    env = dict(os.environ, PGCLIENTENCODING='UTF8', PGCONNECT_TIMEOUT='10')
    # Consistent object resolution even if a role has a custom search_path.
    return subprocess.check_output(command(), input='SET search_path TO public;\n' + statement, text=True,
                                   encoding='utf-8', env=env).strip()
