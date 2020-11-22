import argparse
import os
import sys

from modifier import Modifier


def main():
    parser = argparse.ArgumentParser(description='IpaModifier')
    parser.add_argument('ipa', type=str, help='IPA File (*.ipa)')
    parser.add_argument('config', type=str, help='Config file (*.json)')

    # Parse arguments.
    args = parser.parse_args()

    if not args.ipa or not args.config:
        parser.print_help()
        return False

    if not os.path.exists(args.ipa):
        print('IPA file was not found.')
        return False

    if not os.path.exists(args.config):
        print('Config file was not found.')
        return False

    with Modifier(args.ipa, args.config) as modifier:
        return modifier.modify()


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
