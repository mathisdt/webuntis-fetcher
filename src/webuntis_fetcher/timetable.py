#!/usr/bin/env python3
import datetime
import logging
import sys
from io import TextIOWrapper
from typing import TextIO

import requests
from bs4 import BeautifulSoup

from webuntis_fetcher.statistics import Statistics


def kks_kannover_teachers() -> dict:
    html = requests.get("https://www.kks-hannover.de/ueber-uns/personen/kollegium/").text

    soup = BeautifulSoup(html, features="html.parser")
    table = soup.find("table")

    headings = [th.get_text() for th in table.find("tr").find_all("th")]
    index_of_lastname = headings.index("Nachname")
    index_of_abbreviation = headings.index("Kürzel")

    # some teachers are not on the web site:
    abbrev_to_name = {"HAT": "Hatala", "PAP": "Pape", "VER": "Verwolt", "JK": "Junitz-Kofeld", "PFL": "Pflanz",
                      "BEJ": "Berger"}
    for row in table.find_all("tr")[1:]:
        row_data = [td.get_text() for td in row.find_all("td")]
        abbrev_to_name[row_data[index_of_abbreviation]] = row_data[index_of_lastname]
    return abbrev_to_name


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


def get_element_id_list(elements: dict, element_type: int, attribute: str = "id"):
    element_ids = list()
    for element in elements:
        if element["type"] == element_type:
            element_ids.append(element[attribute])
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
    if not element or element == "---":
        return
    if category not in data_dict:
        data_dict[category] = dict()
    if kind in data_dict[category]:
        data_dict[category][kind] = data_dict[category][kind] + ", " + element
    else:
        data_dict[category][kind] = element


def get_data_direct(section_config, week_start_date, target):
    statistics = None
    if "statistics_file" in section_config:
        statistics = Statistics(section_config["statistics_file"],
                                f'{section_config["firstname"]} {section_config["lastname"]} - {section_config["class"]}')
        statistics.open()
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

    if "data" not in week_data or "result" not in week_data["data"]:
        return

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

    infotexts_to_ignore = [t.strip() for t in section_config["ignore_infotext"].split(sep="|")] \
        if "ignore_infotext" in section_config else ()

    teacher_fullnames = eval(section_config["teacher_fullname_function"] + "()") \
        if "teacher_fullname_function" in section_config else None

    for period in periods:
        day = str(period["date"])
        date = datetime.date(year=int(day[:4]), month=int(day[4:6]), day=int(day[6:]))
        time = str(period["startTime"])
        if time == '0':
            start_time = datetime.time(hour=0, minute=0)
        else:
            start_time = datetime.time(hour=int(time[:-2]), minute=int(time[-2:]))
        if start_time not in periods_by_time:
            periods_by_time[start_time] = dict()
        group_ids = get_element_id_list(period["elements"], 1)
        teacher_ids = get_element_id_list(period["elements"], 2)
        original_teacher_ids = get_element_id_list(period["elements"], 2, "orgId")
        subject_ids = get_element_id_list(period["elements"], 3)
        original_subject_ids = get_element_id_list(period["elements"], 3, "orgId")
        room_ids = get_element_id_list(period["elements"], 4)
        original_room_ids = get_element_id_list(period["elements"], 4, "orgId")
        if date not in periods_by_time[start_time]:
            periods_by_time[start_time][date] = dict()
        kind = "yes"
        if period["cellState"] == "EXAM":
            periods_by_time[start_time][date]["cell_class"] = "exam"
        elif period["cellState"] in ("SHIFT", "SUBSTITUTION", "ROOMSUBSTITUTION", "ADDITIONAL", "SUBST_TEXT"):
            periods_by_time[start_time][date]["cell_class"] = "change"
        elif period["cellState"] in ("CANCEL", "FREE"):
            kind = "no"
            if ("cell_class" not in periods_by_time[start_time][date]
                    or not periods_by_time[start_time][date]["cell_class"] == "change"):
                # we don't already have a "change" entry, so we may put "cancel" as cell class:
                periods_by_time[start_time][date]["cell_class"] = "cancel"
        elif period["cellState"] == "STANDARD":
            # only if we don't have a cell class already (parallel entries: non-standard takes precendence)
            if "cell_class" not in periods_by_time[start_time][date]:
                periods_by_time[start_time][date]["cell_class"] = "normal"
        else:
            periods_by_time[start_time][date]["cell_class"] = "warn"

        if "teacher_as_cancelled" in section_config:
            for teacher_id in teacher_ids:
                if section_config["teacher_as_cancelled"] == get_element_name(elements, 2, teacher_id):
                    periods_by_time[start_time][date]["cell_class"] = "cancel"
        if "room_as_cancelled" in section_config:
            for room_id in room_ids:
                if section_config["room_as_cancelled"] == get_element_name(elements, 4, room_id):
                    periods_by_time[start_time][date]["cell_class"] = "cancel"

        for group_id in group_ids:
            add_entry(periods_by_time[start_time][date], "group", kind, get_element_name(elements, 1, group_id))
        for teacher_id in teacher_ids:
            teacher = get_element_name(elements, 2, teacher_id)
            if teacher_fullnames is not None and teacher in teacher_fullnames and teacher_fullnames[teacher]:
                teacher = teacher_fullnames[teacher]
            add_entry(periods_by_time[start_time][date], "teacher", kind, teacher)
        for teacher_id in original_teacher_ids:
            teacher = get_element_name(elements, 2, teacher_id)
            if teacher_fullnames is not None and teacher in teacher_fullnames and teacher_fullnames[teacher]:
                teacher = teacher_fullnames[teacher]
            add_entry(periods_by_time[start_time][date], "teacher", "no", teacher)
        for subject_id in subject_ids:
            add_entry(periods_by_time[start_time][date], "subject", kind, get_element_name(elements, 3, subject_id))
        for subject_id in original_subject_ids:
            add_entry(periods_by_time[start_time][date], "subject", "no", get_element_name(elements, 3, subject_id))
        for room_id in room_ids:
            add_entry(periods_by_time[start_time][date], "room", kind, get_element_name(elements, 4, room_id))
        for room_id in original_room_ids:
            add_entry(periods_by_time[start_time][date], "room", "no", get_element_name(elements, 4, room_id))
        end_time_str = str(period["endTime"])
        end_time = datetime.time(hour=int(end_time_str[:-2]), minute=int(end_time_str[-2:]))
        periods_by_time[start_time][date]["date"] = date
        periods_by_time[start_time][date]["start_time"] = start_time
        if ("end_time" not in periods_by_time[start_time][date]
                or end_time > periods_by_time[start_time][date]["end_time"]):
            periods_by_time[start_time][date]["end_time"] = end_time

        if "infotext" not in periods_by_time[start_time][date]:
            periods_by_time[start_time][date]["infotext"] = ""
        if ("lessonText" in period and period["lessonText"] and
                period["lessonText"] not in periods_by_time[start_time][date]["infotext"] and
                period["lessonText"] not in infotexts_to_ignore):
            if periods_by_time[start_time][date]["infotext"].strip() in period["lessonText"]:
                periods_by_time[start_time][date]["infotext"] = f'{period["lessonText"]} '
            else:
                periods_by_time[start_time][date]["infotext"] += f'{period["lessonText"]} '
        if ("periodText" in period and period["periodText"] and
                period["periodText"] not in periods_by_time[start_time][date]["infotext"] and
                period["periodText"] not in infotexts_to_ignore):
            if periods_by_time[start_time][date]["infotext"].strip() in period["periodText"]:
                periods_by_time[start_time][date]["infotext"] = f'{period["periodText"]} '
            else:
                periods_by_time[start_time][date]["infotext"] += f'{period["periodText"]} '
        if ("periodInfo" in period and period["periodInfo"] and
                period["periodInfo"] not in periods_by_time[start_time][date]["infotext"] and
                period["periodInfo"] not in infotexts_to_ignore):
            if periods_by_time[start_time][date]["infotext"].strip() in period["periodInfo"]:
                periods_by_time[start_time][date]["infotext"] = f'{period["periodInfo"]} '
            else:
                periods_by_time[start_time][date]["infotext"] += f'{period["periodInfo"]} '
        if ("substText" in period and period["substText"] and
                period["substText"] not in periods_by_time[start_time][date]["infotext"] and
                period["substText"] not in infotexts_to_ignore):
            if periods_by_time[start_time][date]["infotext"].strip() in period["substText"]:
                periods_by_time[start_time][date]["infotext"] = f'{period["substText"]} '
            else:
                periods_by_time[start_time][date]["infotext"] += f'{period["substText"]} '
        if ("staffText" in period and period["staffText"] and
                period["staffText"] not in periods_by_time[start_time][date]["infotext"] and
                period["staffText"] not in infotexts_to_ignore):
            if periods_by_time[start_time][date]["infotext"].strip() in period["staffText"]:
                periods_by_time[start_time][date]["infotext"] = f'{period["staffText"]} '
            else:
                periods_by_time[start_time][date]["infotext"] += f'{period["staffText"]} '
        if periods_by_time[start_time][date]["infotext"]:
            # delete duplicate words from infotext:
            periods_by_time[start_time][date]["infotext"] \
                = ' '.join(dict.fromkeys(periods_by_time[start_time][date]["infotext"].split()))

    group_string = f' ({section_config["class"]})' if "class" in section_config else ''
    write(target, f'''<h2>{section_config["firstname"]}{group_string}</h2>
                       <table>
                       <tr>
                       <td class="width1"></td>''')
    for date in days:
        write(target,
              f'<td class="width2 centered">{date.strftime("<b>%a</b> <span class=""smallbleak"">%d.%m.</span>")}</td>')
    write(target, "</tr>")

    for start_time in dict(sorted(periods_by_time.items())):
        row = dict(sorted(periods_by_time[start_time].items()))
        write(target, f'''<tr>
                           <td class="height2 text_top">{start_time.strftime("%H:%M")} Uhr</td>''')
        for date in days:
            if date in row and row[date]:
                period = row[date]
                if "rowspan_applied" not in period or not period["rowspan_applied"]:
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
                            periods_by_time[next_start_time][date]["rowspan_applied"] = True
                            # copy the values from the "rowspan master":
                            copy_values_for(period, periods_by_time[next_start_time][date],
                                            "teacher", "subject", "room", "group", "cell_class", "infotext")
                        start_time_to_check = next_start_time
                    if row_span > 1:
                        row_span_str = f' rowspan="{row_span}"'
                    else:
                        row_span_str = ''
                    if "class" in section_config:
                        group_string = ""
                        teacher_string = f'<span class="spaceleft">{period["teacher"]["yes"] if "yes" in period["teacher"] else ""}</span>' \
                                         f'<span class="no{" spaceleft" if "yes" in period["teacher"] and "no" in period["teacher"] else ""}">{period["teacher"]["no"] if "no" in period["teacher"] else ""}</span>'
                    else:
                        group_string = f'<span class="spaceright">{period["group"]["yes"] if "yes" in period["group"] else ""}</span>' \
                                       f'<span class="no{" spaceleft" if "yes" in period["group"] and "no" in period["group"] else ""}">{period["group"]["no"] if "no" in period["group"] else ""}</span>'
                        teacher_string = ""
                    write(target,
                          f'<td class="centered {period["cell_class"]}"{row_span_str}>{group_string}'
                          f'{period["subject"]["yes"] if "subject" in period and "yes" in period["subject"] else ""}'
                          f'<span class="no{" spaceleft" if "subject" in period and "yes" in period["subject"] and "no" in period["subject"] else ""}">{period["subject"]["no"] if "subject" in period and "no" in period["subject"] else ""}</span>'
                          f'{teacher_string}<br/>'
                          f'<small>@ {period["room"]["yes"] if "room" in period and "yes" in period["room"] else ""}'
                          f'<span class="no{" spaceleft" if "room" in period and "yes" in period["room"] and "no" in period["room"] else ""}">{period["room"]["no"] if "room" in period and "no" in period["room"] else ""}</span></small>'
                          f'{"<br/>" + period["infotext"].strip() if "infotext" in period and len(period["infotext"]) else ""}</td>')
                if statistics:
                    planned_teacher = None
                    actual_teacher = None
                    planned_subject = None
                    actual_subject = None
                    if "teacher" in periods_by_time[start_time][date]:
                        if "no" in periods_by_time[start_time][date]["teacher"]:
                            planned_teacher = periods_by_time[start_time][date]["teacher"]["no"]
                        else:
                            planned_teacher = periods_by_time[start_time][date]["teacher"]["yes"]
                        if "yes" in periods_by_time[start_time][date]["teacher"]:
                            actual_teacher = periods_by_time[start_time][date]["teacher"]["yes"]
                    if "subject" in periods_by_time[start_time][date]:
                        if "no" in periods_by_time[start_time][date]["subject"]:
                            planned_subject = periods_by_time[start_time][date]["subject"]["no"]
                        else:
                            planned_subject = periods_by_time[start_time][date]["subject"]["yes"]
                        if "yes" in periods_by_time[start_time][date]["subject"]:
                            actual_subject = periods_by_time[start_time][date]["subject"]["yes"]
                    if "cell_class" in periods_by_time[start_time][date]:
                        is_cancelled = periods_by_time[start_time][date]["cell_class"] == "cancel"
                    else:
                        is_cancelled = False
                    if "infotext" in periods_by_time[start_time][date]:
                        comment = periods_by_time[start_time][date]["infotext"]
                    else:
                        comment = None
                    statistics.put(datetime.datetime.combine(date, start_time),
                                   planned_teacher,
                                   planned_subject,
                                   actual_teacher=actual_teacher,
                                   actual_subject=actual_subject,
                                   is_cancelled=is_cancelled,
                                   comment=comment)
            else:
                write(target, "<td></td>")
        write(target, "</tr>")
    write(target, "</table>")
    if statistics:
        statistics.save()
        write(target, f'<span class="bleak">seit {statistics.earliest_date().strftime("%d.%m.%Y")}:'
                      f' Entfall = {round(100 * statistics.percentage_cancelled(), 1)} % /'
                      f' Fach&auml;nderung = {round(100 * statistics.percentage_changed_subject(), 1)} % /'
                      f' personelle &Auml;nderung = {round(100 * statistics.percentage_changed_teacher(), 1)} %</span>')


def copy_values_for(source_dict: dict, target_dict: dict, *keys: str):
    for key in keys:
        if key in source_dict:
            target_dict[key] = source_dict[key]


def same_content(one: dict, two: dict):
    return (one.get("cell_class") == two.get("cell_class")
            and one.get("teacher") == two.get("teacher")
            and one.get("group") == two.get("group")
            and one.get("subject") == two.get("subject")
            and one.get("room") == two.get("room"))


def open_if_necessary(name, mode=None):
    if isinstance(name, TextIO) or isinstance(name, TextIOWrapper):
        return name
    else:
        return open(name, mode=mode)


def run(config):
    if "OUTPUT" in config and "timetable_file" in config["OUTPUT"]:
        outfile = config["OUTPUT"]["timetable_file"]
    else:
        outfile = sys.stdout
    logging.debug(f'starting run - output to {outfile}')

    with open_if_necessary(outfile, "w") as target_file:
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
                           .smallbleak { color: #999999; font-size: small }
                           .bleak { color: #999999 }
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
            if section not in ('DEFAULT', 'OUTPUT'):
                today = datetime.date.today()
                target = today + datetime.timedelta(days=2)
                monday = target - datetime.timedelta(days=target.weekday())
                try:
                    get_data_direct(config[section], monday, target_file)
                except requests.RequestException as re:
                    # silently ignore connection problems
                    exit(1)

        write(target_file, '''</body>
                                </html>''')
