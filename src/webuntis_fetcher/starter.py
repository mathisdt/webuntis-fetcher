import configparser
import logging
import os
import sys

from webuntis_fetcher import timetable, messages


def run():
    if len(sys.argv) < 2 or sys.argv[1] not in ("timetable", "messages"):
        logging.log(logging.ERROR, "wrong arguments, here's some guidance:\n"
                                   "  1. mode (required) - either 'timetable' or 'messages'\n"
                                   "  2. config file (optional) - not not provided, 'config.ini' is used")
        exit(1)
    mode = sys.argv[1]

    if len(sys.argv) >= 3:
        config_file = sys.argv[2]
    else:
        config_file = "config.ini"

    if not os.path.isfile(config_file):
        logging.log(logging.ERROR, f"{config_file} not found")
        exit(1)
    config = configparser.ConfigParser()
    config.read(config_file)

    if mode == "timetable":
        timetable.run(config)
    elif mode == "messages":
        messages.run(config)
