import configparser
import locale
import logging
import os
import sys
import csv
import smtplib
from email.message import EmailMessage
import mimetypes

import requests


def handle_msg(confirm: bool):
    if not msg["id"] in already_read_messages:
        print(f'UNREAD{" TO CONFIRM" if confirm else ""}  {msg["id"]} - {msg["subject"]}')

        message_response = requests.get(
            f'{config[section]["server"]}/WebUntis/api/rest/view/v1/messages/{msg["id"]}',
            cookies=cookies,
            headers=headers)
        msg_details = message_response.json()
        msg_attachments = dict()
        if "storageAttachments" in msg_details and msg_details["storageAttachments"]:
            for att in msg_details["storageAttachments"]:
                storageurl_response = requests.get(
                    f'{config[section]["server"]}/WebUntis/api/rest/view/v1/messages/{att["id"]}/attachmentstorageurl',
                    cookies=cookies,
                    headers=headers)
                storage_json = storageurl_response.json()
                download_url = storage_json["downloadUrl"]
                amazon_headers = dict()
                for header_entry in storage_json["additionalHeaders"]:
                    amazon_headers[header_entry["key"]] = header_entry["value"]
                download_response = requests.get(download_url,
                                                 cookies=cookies,
                                                 headers=amazon_headers)
                msg_attachments[att["name"]] = download_response.content

        confirm_timestamp = None
        if confirm:
            try:
                confirm_response = requests.post(
                    f'{config[section]["server"]}/WebUntis/api/rest/view/v1/messages/{msg["id"]}/read-confirmation',
                    cookies=cookies,
                    headers=headers)
                confirm_details = confirm_response.json()
                confirm_timestamp = confirm_details["confirmationDate"]
            except:
                print(f'COULD NOT CONFIRM  {msg["id"]} - {msg["subject"]}')

        mail = EmailMessage()
        content = msg_details["content"] if "content" in msg_details and msg_details["content"] is not None else ""
        if confirm_timestamp:
            content += f"\n\nMessage was confirmed at {confirm_timestamp}"
        mail.set_content(content)
        for att in msg_attachments:
            mimetype = mimetypes.guess_type(url=att)
            if "/" in mimetype[0]:
                splitted = mimetype[0].split("/")
                mime1 = splitted[0]
                mime2 = splitted[1]
            else:
                mime1 = mimetype[0]
                mime2 = mimetype[1]
            mail.add_attachment(msg_attachments[att], maintype=mime1, subtype=mime2,
                                filename=att)
        mail['Subject'] = f'[{msg["sender"]["displayName"]}] {msg["subject"]}'
        mail['From'] = config[section]["mail_from"]
        mail['To'] = config[section]["mail_to"]

        s = smtplib.SMTP(config[section]["mail_host"])
        s.send_message(mail)
        s.quit()

        already_read_messages.append(msg["id"])


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        stream=sys.stdout)
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    else:
        configfile = f"{os.path.realpath(os.path.dirname(__file__))}/config.ini"
    logging.debug(f'starting messages run - using configuration from {configfile}')

    if not os.path.isfile(configfile):
        logging.log(logging.ERROR, f"{configfile} not found")
        exit(1)
    config = configparser.ConfigParser()
    config.read(configfile)

    for section in config:
        if section != 'DEFAULT':
            if "message_id_file" not in config[section]:
                logging.log(logging.ERROR, f"message_id_file not configured for {section}")
                exit(2)
            already_read_messages = list()
            if os.path.isfile(config[section]["message_id_file"]):
                with open(config[section]["message_id_file"], newline='') as message_id_file:
                    message_id_reader = csv.reader(message_id_file, delimiter=',')
                    for row in message_id_reader:
                        already_read_messages.append(int(row[0]))

            try:
                response_initial = requests.get(
                    f'{config[section]["server"]}/WebUntis/?school={config[section]["school"]}')
                cookies = response_initial.cookies
                requests.post(f'{config[section]["server"]}/WebUntis/j_spring_security_check', cookies=cookies,
                              params={"school": config[section]["school"],
                                      "j_username": config[section]["username"],
                                      "j_password": config[section]["password"],
                                      "token": ""})
                token_new_response = requests.get(
                    f'{config[section]["server"]}/WebUntis/api/token/new',
                    cookies=cookies)
                headers = {"Authorization": f"Bearer {token_new_response.text}"}
                messages_response = requests.get(f'{config[section]["server"]}/WebUntis/api/rest/view/v1/messages',
                                                 cookies=cookies,
                                                 headers=headers)
                messages = messages_response.json()

                if "readConfirmationMessages" in messages:
                    for msg in messages["readConfirmationMessages"]:
                        handle_msg(True)
                if "incomingMessages" in messages:
                    for msg in messages["incomingMessages"]:
                        handle_msg(False)

                with open(config[section]["message_id_file"], 'w', newline='') as message_id_file:
                    message_id_writer = csv.writer(message_id_file, delimiter=',', quoting=csv.QUOTE_MINIMAL)
                    for already_read_message_id in already_read_messages:
                        message_id_writer.writerow([already_read_message_id])

            except requests.RequestException as re:
                pass
