#!/usr/bin/env python3

# Configuration
import secrets


# Standard Library
from operator import *
from datetime import datetime
from collections import Counter
import smtplib
from email.headerregistry import Address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import argparse

# Issue Tracking API
from jira import JIRA

# Templating
from jinja2 import Environment, FileSystemLoader



def generateHTML(issue_dict):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('email.html.j2')
    return template.render(issue_dict=issue_dict)


# User info object from jira instead of username and the other garbage
def sendEmail(user, html_message, text_message):
    to_username, to_domain = user.emailAddress.split("@")

    # Create the base text message.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Daily Todo Test"
    msg['From'] = str(Address(secrets.smtp['from_display'], secrets.smtp['from_username'], secrets.smtp['from_domain']))
    msg['To'] = str(Address(user.displayName, to_username, to_domain))

    msg.attach(MIMEText(text_message, 'plain'))
    msg.attach(MIMEText(html_message, 'html'))

    # Send the message via the SMTP server
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(secrets.smtp['user'], secrets.smtp['auth'])
        server.send_message(msg)
        server.close()
        print('successfully sent the mail')



def main(send_email):
    jira = JIRA(\
        secrets.jira[0]["url"], \
        auth=(secrets.jira[0]["user"], secrets.jira[0]["auth"]))

    issues = jira.search_issues("assignee=weston and status not in ('Done')")

    # Data cleanup
    for issue in issues:
        # @TODO
        # If "assignedDueDate" is set then convert to datetime and store in normal duedate
        # ELSE do the next block
        if issue.fields.duedate != None:
            issue.fields.duedate = datetime.fromisoformat(issue.fields.duedate)
            if issue.fields.duedate.time() == datetime.min.time():
                issue.fields.duedate = issue.fields.duedate.replace(hour=23, minute=59, second=59, microsecond=999999)
            # @TODO
            # If it's due at 00:00:00 then make it due at 23:59:59 of the same day
        else:
            issue.fields.duedate = datetime.fromtimestamp(0)

    # Since Python's sorting is stable we are sorting from least significant
    # to most significant sorting keys to get the order we want
    issues.sort(key=attrgetter('fields.summary'))
    issues.sort(key=attrgetter('fields.status.id'))
    issues.sort(key=attrgetter('fields.priority.id'))
    issues.sort(key=attrgetter('fields.duedate'))

    # Remove placehodler values for duedate
    for issue in issues:
        if issue.fields.duedate == datetime.fromtimestamp(0):
            issue.fields.duedate = None
    

    # Sort the things :)
    assignee = None
    if len(issues) > 0:
        assignee = issues[0].fields.assignee

    issue_dict = {
        "Past Due": [],
        "Today": [],
        "This Week": [],
        "This Month": [],
        "Future": [],
        "No Due Date": [],
        "In Review": [],
    }

    for n in range(len(issues)-1, -1, -1):
        if issues[n].fields.status.name == "In Review":
            issue_dict["In Review"].insert(0, issues.pop(n))
        elif issues[n].fields.duedate is None:
            issue_dict["No Due Date"].insert(0, issues.pop(n))
        elif issues[n].fields.duedate < datetime.now():
            issue_dict["Past Due"].insert(0, issues.pop(n))
        elif issues[n].fields.duedate.date() == datetime.today().date():
            issue_dict["Today"].insert(0, issues.pop(n))
        elif issues[n].fields.duedate.isocalendar()[0] == datetime.today().isocalendar()[0] and issues[n].fields.duedate.isocalendar()[1] == datetime.today().isocalendar()[1]:
            issue_dict["This Week"].insert(0, issues.pop(n))
        elif issues[n].fields.duedate.month == datetime.today().month and issues[n].fields.duedate.year == datetime.today().year:
            issue_dict["This Month"].insert(0, issues.pop(n))
        elif issues[n].fields.duedate > datetime.now():
            issue_dict["Future"].insert(0, issues.pop(n))

    if len(issues) > 0:
        raise Exception("Some issues were not sorted.")

    # Do things with the results

    if assignee is not None and send_email:
        sendEmail(assignee, generateHTML(issue_dict), "")

    with open('out.html', 'w+') as f:
        f.write(generateHTML(issue_dict))
    
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--email", help="Send an email with the contents", action="store_true")

    args = parser.parse_args()
    main(args.email)
