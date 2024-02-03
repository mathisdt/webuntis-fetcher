#!/usr/bin/env python3
import configparser
import datetime
import locale
import logging
import os
import sys
from typing import TextIO

import requests
from requests import RequestException

ROWSPAN_APPLIED = "ROWSPAN_APPLIED"


def get_element_name(elements: dict, element_type: int, element_id: int):
    """
    type: 1=class/group, 2=teacher, 3=subject, 4=room, 5=student
    """
    for element in elements:
        if element["type"] == element_type and element["id"] == element_id:
            if element_type == 1:
                return element["displayname"]
            elif element_type == 2:
                return element["name"]
            elif element_type == 3:
                return element["displayname"]
            elif element_type == 4:
                return element["displayname"]
            elif element_type == 5:
                return element["displayname"]
    return None


def get_element_id_list(elements: dict, element_type: int):
    element_ids = list()
    for element in elements:
        if element["type"] == element_type:
            element_ids.append(element["id"])
    return sorted(element_ids)


def write(target: TextIO, line: str):
    target.write(line + "\n")


def get_next_key(base: dict, this_key: datetime.time):
    last_key = None
    for key in sorted(base.keys()):
        if last_key == this_key:
            return key
        last_key = key
    return None


def add_entry(data_dict: dict, category: str, kind: str, element: str):
    if category not in data_dict:
        data_dict[category] = dict()
    if kind in data_dict[category]:
        data_dict[category][kind] = data_dict[category][kind] + ", " + element
    else:
        data_dict[category][kind] = element


def get_data_direct(section_config, week_start_date, target):
    response_initial = requests.get(f'{section_config["server"]}/WebUntis/?school={section_config["school"]}')
    cookies = response_initial.cookies
    requests.post(f'{section_config["server"]}/WebUntis/j_spring_security_check', cookies=cookies,
                  params={"school": section_config["school"],
                          "j_username": section_config["username"],
                          "j_password": section_config["password"],
                          "token": ""})
    if "class" in section_config:
        response_pageconfig = requests.get(
            f'{section_config["server"]}/WebUntis/api/public/timetable/weekly/pageconfig'
            f'?type=5&date={week_start_date}&isMyTimetableSelected=false', cookies=cookies)
    else:
        response_pageconfig = requests.get(
            f'{section_config["server"]}/WebUntis/api/public/timetable/weekly/pageconfig'
            f'?type=2&date={week_start_date}&isMyTimetableSelected=true', cookies=cookies)
    pageconfig = response_pageconfig.json()
    person_id = None
    for person in pageconfig["data"]["elements"]:
        if person["forename"] == section_config["firstname"] and person["longName"] == section_config["lastname"]:
            person_id = person["id"]
            break
    if "class" in section_config:
        response_week_data = requests.get(f'{section_config["server"]}/WebUntis/api/public/timetable/weekly/data'
                                          f'?elementType=5&elementId={person_id}&date={week_start_date}&formatId=1',
                                          cookies=cookies)
    else:
        response_week_data = requests.get(f'{section_config["server"]}/WebUntis/api/public/timetable/weekly/data'
                                          f'?elementType=2&elementId={person_id}&date={week_start_date}&formatId=9',
                                          cookies=cookies)
    week_data = response_week_data.json()

    days = [week_start_date + datetime.timedelta(days=x) for x in range(5)]
    periods_by_time = dict()

    if "class" in section_config:
        response_timegrid = requests.get(
            f'{section_config["server"]}/WebUntis/api/public/timegrid', cookies=cookies)
        timegrid = response_timegrid.json()

        for row in timegrid["data"]["rows"]:
            start_time = datetime.time(hour=int(str(row["startTime"])[:-2]), minute=int(str(row["startTime"])[-2:]))
            end_time = datetime.time(hour=int(str(row["endTime"])[:-2]), minute=int(str(row["endTime"])[-2:]))
            if (datetime.datetime.combine(datetime.date.today(), end_time)
                    - datetime.datetime.combine(datetime.date.today(), start_time) >= datetime.timedelta(minutes=45)
                    and len(periods_by_time) < 6):
                for day in days:
                    if start_time not in periods_by_time:
                        periods_by_time[start_time] = dict()
                    periods_by_time[start_time][day] = dict()

    periods = week_data["data"]["result"]["data"]["elementPeriods"][str(person_id)]
    elements = week_data["data"]["result"]["data"]["elements"]

    for period in periods:
        day = str(period["date"])
        date = datetime.date(year=int(day[:4]), month=int(day[4:6]), day=int(day[6:]))
        time = str(period["startTime"])
        start_time = datetime.time(hour=int(time[:-2]), minute=int(time[-2:]))
        if start_time not in periods_by_time:
            periods_by_time[start_time] = dict()
        group_ids = get_element_id_list(period["elements"], 1)
        teacher_ids = get_element_id_list(period["elements"], 2)
        subject_ids = get_element_id_list(period["elements"], 3)
        room_ids = get_element_id_list(period["elements"], 4)
        if date not in periods_by_time[start_time]:
            periods_by_time[start_time][date] = dict()
        kind = "yes"
        if period["cellState"] == "EXAM":
            periods_by_time[start_time][date]["cell_class"] = "exam"
        elif period["cellState"] == "STANDARD":
            periods_by_time[start_time][date]["cell_class"] = "normal"
        elif period["cellState"] in ("SHIFT", "SUBSTITUTION", "ROOMSUBSTITUTION", "ADDITIONAL", "SUBST_TEXT"):
            periods_by_time[start_time][date]["cell_class"] = "change"
        elif period["cellState"] in ("CANCEL", "FREE"):
            kind = "no"
            if ("cell_class" not in periods_by_time[start_time][date]
                    or not periods_by_time[start_time][date]["cell_class"] == "change"):
                # we don't already have a "change" entry, so we may put "cancel" as cell class:
                periods_by_time[start_time][date]["cell_class"] = "cancel"
        else:
            periods_by_time[start_time][date]["cell_class"] = "warn"

        if "teacher_as_cancelled" in section_config:
            for teacher_id in teacher_ids:
                if section_config["teacher_as_cancelled"] == get_element_name(elements, 2, teacher_id):
                    periods_by_time[start_time][date]["cell_class"] = "cancel"

        for group_id in group_ids:
            add_entry(periods_by_time[start_time][date], "group", kind, get_element_name(elements, 1, group_id))
        for teacher_id in teacher_ids:
            add_entry(periods_by_time[start_time][date], "teacher", kind, get_element_name(elements, 2, teacher_id))
        for subject_id in subject_ids:
            add_entry(periods_by_time[start_time][date], "subject", kind, get_element_name(elements, 3, subject_id))
        for room_id in room_ids:
            add_entry(periods_by_time[start_time][date], "room", kind, get_element_name(elements, 4, room_id))
        end_time_str = str(period["endTime"])
        end_time = datetime.time(hour=int(end_time_str[:-2]), minute=int(end_time_str[-2:]))
        periods_by_time[start_time][date]["date"] = date
        periods_by_time[start_time][date]["start_time"] = start_time
        if ("end_time" not in periods_by_time[start_time][date]
                or end_time > periods_by_time[start_time][date]["end_time"]):
            periods_by_time[start_time][date]["end_time"] = end_time

    group_string = f' ({section_config["class"]})' if "class" in section_config else ''
    write(target, f'''<h2>{section_config["firstname"]}{group_string}</h2>
                       <table>
                       <tr>
                       <td class="width1"></td>''')
    for date in days:
        write(target,
              f'<td class="width2 centered">{date.strftime("<b>%a</b> <span class=""bleak"">%d.%m.</span>")}</td>')
    write(target, "</tr>")

    for start_time in dict(sorted(periods_by_time.items())):
        row = dict(sorted(periods_by_time[start_time].items()))
        write(target, f'''<tr>
                           <td class="height2 text_top">{start_time.strftime("%H:%M")} Uhr</td>''')
        for date in days:
            if date in row and row[date]:
                period = row[date]
                if period == ROWSPAN_APPLIED:
                    continue
                row_span = 1
                start_time_to_check = start_time
                while get_next_key(periods_by_time, start_time_to_check):
                    next_start_time = get_next_key(periods_by_time, start_time_to_check)
                    if (next_start_time and next_start_time in periods_by_time and periods_by_time[next_start_time]
                            and date in periods_by_time[next_start_time] and periods_by_time[next_start_time][date]
                            and same_content(period, periods_by_time[next_start_time][date])
                            or "end_time" in period and date in periods_by_time[next_start_time]
                            and "start_time" in periods_by_time[next_start_time][date]
                            and period["end_time"] > periods_by_time[next_start_time][date]["start_time"]):
                        row_span = row_span + 1
                        periods_by_time[next_start_time][date] = ROWSPAN_APPLIED
                    start_time_to_check = next_start_time
                if row_span > 1:
                    row_span_str = f' rowspan="{row_span}"'
                else:
                    row_span_str = ''
                if "class" in section_config:
                    group_string = ""
                    teacher_string = f'<span class="spaceleft">{period["teacher"]["yes"] if "yes" in period["teacher"] else ""}</span>' \
                                     f'<span class="no{" spaceleft" if period["cell_class"] == "change" and "no" in period["teacher"] else ""}">{period["teacher"]["no"] if "no" in period["teacher"] else ""}</span>'
                else:
                    group_string = f'<span class="spaceright">{period["group"]["yes"] if "yes" in period["group"] else ""}</span>' \
                                   f'<span class="no{" spaceleft" if period["cell_class"] == "change" and "no" in period["group"] else ""}">{period["group"]["no"] if "no" in period["group"] else ""}</span>'
                    teacher_string = ""
                write(target,
                      f'<td class="centered {period["cell_class"]}"{row_span_str}>{group_string}'
                      f'{period["subject"]["yes"] if "yes" in period["subject"] else ""}'
                      f'<span class="no{" spaceleft" if period["cell_class"] == "change" and "no" in period["subject"] else ""}">{period["subject"]["no"] if "no" in period["subject"] else ""}</span>'
                      f'{teacher_string}<br/>'
                      f'<small>@ {period["room"]["yes"] if "room" in period and "yes" in period["room"] else ""}'
                      f'<span class="no{" spaceleft" if period["cell_class"] == "change" and "room" in period and "no" in period["room"] else ""}">{period["room"]["no"] if "room" in period and "no" in period["room"] else ""}</span></small></td>')
            else:
                write(target, "<td></td>")
        write(target, "</tr>")
    write(target, "</table>")


def same_content(one: dict, two: dict):
    return (one.get("cell_class") == two.get("cell_class")
            and one.get("teacher") == two.get("teacher")
            and one.get("group") == two.get("group")
            and one.get("subject") == two.get("subject")
            and one.get("room") == two.get("room"))


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        stream=sys.stdout)
    outfile = f"{os.path.realpath(os.path.dirname(__file__))}/output.html"
    if len(sys.argv) > 1:
        outfile = sys.argv[1]
    logging.debug(f'starting run - output to {outfile}')

    configfile = f"{os.path.realpath(os.path.dirname(__file__))}/config.ini"
    if not os.path.isfile(configfile):
        logging.log(logging.ERROR, f"{configfile} not found")
        exit(1)
    config = configparser.ConfigParser()
    config.read(configfile)

    with open(outfile, "w") as target_file:
        write(target_file, '''<html>
                           <head>
                           <title>Stundenplan</title>
                           <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                           <style>
                           .width1 { width: 120px }
                           .width2 { width: 150px }
                           .height2 { height: 47px }
                           .text_top { vertical-align: top }
                           .centered { text-align: center; vertical-align: middle }
                           .bleak { color: #999999; font-size: small }
                           .smallbold { font-size: small; font-weight: bold }
                           .no { text-decoration: line-through }
                           .spaceleft { padding-left: 0.5em }
                           .spaceright { padding-right: 0.5em }
                           .normal { background-color: rgba(245, 160, 35, 0.7) }
                           .exam { background-color: rgba(255, 235, 0, 0.7) }
                           .change { background-color: rgba(200, 160, 210) }
                           .cancel { background-color: rgba(195, 195, 195) }
                           .warn { background-color: rgba(255, 50, 50) }
                           </style>
                           </head>
                           <body>'''
                           f'<span class="smallbold">Stand: {datetime.datetime.now().strftime("%H:%M Uhr, %d.%m.%Y")}</span><br/>')
        for section in config:
            if section != 'DEFAULT':
                today = datetime.date.today()
                target = today + datetime.timedelta(days=2)
                monday = target - datetime.timedelta(days=target.weekday())
                try:
                    get_data_direct(config[section], monday, target_file)
                except RequestException as re:
                    # silently ignore connection problems
                    exit(1)

        write(target_file, '''</body>
                                </html>''')
