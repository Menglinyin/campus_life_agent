"""Run the isolated project suite from any working directory."""
import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=('all', 'unit', 'integration'), default='all')
    parser.add_argument('--chroma', action='store_true', help='Include optional real local Chroma test')
    parser.add_argument('--without-mcp', action='store_true', help='Deselect loopback MCP tests')
    args = parser.parse_args(argv)
    tests = Path(__file__).resolve().parent
    target = tests if args.scope == 'all' else tests / args.scope
    report = tests / 'reports' / ('pytest-' + args.scope + '.xml')
    report.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'pytest', '-c', str(tests / 'pytest.ini'), str(target),
               '-q', '--junitxml=' + str(report)]
    if args.chroma:
        command.append('--run-chroma')
    if args.without_mcp:
        command.extend(['-m', 'not local_mcp'])
    return subprocess.run(command, cwd=tests.parent, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
