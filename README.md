# Optimeet: Schedule ALL the meetings

Optimeet is a tool for coordinated scheduling of multiple meetings. Existing meeting scheduling tools (e.g. Doodle, when2meet, Calendly) poll participants for availability and help everyone find a time that works, but they only do this for a **single** meeting. In contrast, Optimeet gathers availability for **multiple** meetings (which may have overlapping sets of participants) and visualizes this information in a convenient interface that allows rapid exploration of different viable ways to schedule all meetings. Optimeet is built on existing standard tools: it uses automatically-generated when2meets to gather participant availability, and it can export the final meeting schedule to Google Calendar.

## Table of Contents

## Installation
Optimeet is easy to install; just run

```pip install -r requirements.txt```

from the repository root directory. In fact, Optimeet only has one external dependency (the Python [schedule](https://schedule.readthedocs.io/en/stable/) package).

## Overview & Input Files
Using Optimeet proceeds in two phases: first, use `optimeet.py` to gather availabilities from meeting participants; second, use a web interface to visualize availabilities and find a viable meeting schedule.

Optimeet's behavior is defined by a few files:

### config.json
This file specifies general configuration options that tend to be constant for a given user (i.e. you!) It has the following options:
* `"timeZone"`: Time zone in which the user is location (defaults to `"America/New_York"`),
* `"deadlineInDaysFromNow"`: Deadline by which participants should provide their availabiliity, expressed in a number of days after Optimeet starts (defaults to `7`)
* `"reminderFrequencyInHours"`: How often to send reminder emails to participants who have not yet provided their availability (defaults to `24`)
* `"progressCheckFrequencyInHours"`: How often to check for updates to participant availability (defaults to `1`)
* `"name"`: The user's name, which will be included in emails sent to participants
* `"emailAddress"`: The email address from which Optimeet will send emails to participants
* `"emailServer"`: The SMTP server from which Optimeet will send emails (for GMail, this should be `"smtp.gmail.com"`)
* `"gCalEventColorId"`: A number from 1 to 11 specifying the color to be used for created Google Calendar events. [This image](https://i.stack.imgur.com/YSMrI.png) shows the colors to which each number corresponds.

### people.json

## Gathering Participant Availabilities

## Scheduling Interface

## Contact
Optimeet was created by me, [Daniel Ritchie](https://dritchie.github.io), professor of Computer Science at Brown University, for scheduling weekly meetings with members of my research group every semester. If you find Optimeet useful, please do send me [email](mailto:daniel_ritchie@brown.edu)! I'm especially interested in hearing about use cases outside of academia. If you find a bug or make a modificaton to Optimeet that you think might be useful to others, I'm happy to review pull requests. I am open to hearing feature requests, but I can't promise I'll have time to work on new features any time soon.
