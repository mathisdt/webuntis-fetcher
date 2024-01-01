import configparser
import datetime
import locale
import logging
import os
import sys

import requests


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


def write(target, line):
    target.write(line + "\n")


def get_next_key(base, this_key):
    last_key = None
    for key in base.keys():
        if last_key == this_key:
            return key
        last_key = key
    return None


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
        periods_by_time[start_time][date] = dict()
        if period["cellState"] == "EXAM":
            periods_by_time[start_time][date]["cell_class"] = "exam"
        elif period["cellState"] == "STANDARD":
            periods_by_time[start_time][date]["cell_class"] = "normal"
        else:
            periods_by_time[start_time][date]["cell_class"] = "warn"
        for group_id in group_ids:
            if "group" in periods_by_time[start_time][date]:
                periods_by_time[start_time][date]["group"] = (periods_by_time[start_time][date]["group"] + ", "
                                                              + get_element_name(elements, 1, group_id))
            else:
                periods_by_time[start_time][date]["group"] = get_element_name(elements, 1, group_id)
        for teacher_id in teacher_ids:
            if "teacher" in periods_by_time[start_time][date]:
                periods_by_time[start_time][date]["teacher"] = (periods_by_time[start_time][date]["teacher"] + ", "
                                                                + get_element_name(elements, 2, teacher_id))
            else:
                periods_by_time[start_time][date]["teacher"] = get_element_name(elements, 2, teacher_id)
        for subject_id in subject_ids:
            if "subject" in periods_by_time[start_time][date]:
                periods_by_time[start_time][date]["subject"] = (periods_by_time[start_time][date]["subject"] + ", "
                                                                + get_element_name(elements, 3, subject_id))
            else:
                periods_by_time[start_time][date]["subject"] = get_element_name(elements, 3, subject_id)
        for room_id in room_ids:
            if "room" in periods_by_time[start_time][date]:
                periods_by_time[start_time][date]["room"] = (periods_by_time[start_time][date]["room"] + ", "
                                                             + get_element_name(elements, 4, room_id))
            else:
                periods_by_time[start_time][date]["room"] = get_element_name(elements, 4, room_id)

    group_string = f' ({section_config["class"]})' if "class" in section_config else ''
    write(target, f'''<h2>{section_config["firstname"]}{group_string}</h2>
                       <table>
                       <tr>
                       <td class="width1"></td>''')
    for date in days:
        write(target,
              f'<td class="width2 centered">{date.strftime("<b>%a</b> <span class=""bleak"">%d.%m.</span>")}</td>')
    write(target, "</tr>")

    block_start = True
    for start_time in dict(sorted(periods_by_time.items())):
        row = dict(sorted(periods_by_time[start_time].items()))
        write(target, f'''<tr>
                           <td class="height2 text_top">{start_time.strftime("%H:%M")} Uhr</td>''')
        for date in days:
            if date in row and row[date]:
                period = row[date]
                if period == "ROWSPAN_APPLIED":
                    continue
                row_span = ''
                if block_start:
                    next_start_time = get_next_key(periods_by_time, start_time)
                    if (next_start_time and next_start_time in periods_by_time and periods_by_time[next_start_time]
                            and date in periods_by_time[next_start_time] and periods_by_time[next_start_time][date]
                            and periods_by_time[next_start_time][date] == period):
                        row_span = ' rowspan="2"'
                        periods_by_time[next_start_time][date] = "ROWSPAN_APPLIED"
                if "class" in section_config:
                    group_string = ""
                    teacher_string = f' ({period["teacher"]})'
                else:
                    group_string = f'{period["group"]} '
                    teacher_string = ""
                write(target,
                      f'<td class="centered {period["cell_class"]}"{row_span}>{group_string}{period["subject"]}{teacher_string}<br/><small>@ {period["room"]}</small></td>')
            else:
                write(target, "<td></td>")
        write(target, "</tr>")
        block_start = not block_start
    write(target, "</table>")


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
                                .normal { background-color: rgba(244, 159, 37, 0.7) }
                                .exam { background-color: rgba(255, 237, 0, 0.7) }
                                .warn { background-color: rgba(255, 50, 50, 0.7) }
                                </style>
                                </head>
                                <body>''')
        for section in config:
            if section != 'DEFAULT':
                # get_data(config[section])

                # today = datetime.date.today()
                # TODO temporary beause of christmas vacation:
                today = datetime.date(2024, 1, 10)
                monday = today - datetime.timedelta(days=today.weekday())
                get_data_direct(config[section], monday, target_file)

        write(target_file, '''</body>
                                </html>''')
