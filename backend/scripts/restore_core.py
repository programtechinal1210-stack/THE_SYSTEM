"""Restore to a new isolated path; never overwrite a live database."""
from backup_core import backup
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(backup(args.backup, args.destination))
