# Optimeet: Schedule ALL the meetings

https://user-images.githubusercontent.com/2229830/148315574-35f21e41-75ea-4ddc-a97b-3b3b6d699896.mov

Optimeet is a tool for coordinated scheduling of multiple meetings. Existing meeting scheduling tools (e.g. Doodle, when2meet, Calendly) poll participants for availability and help everyone find a time that works, but they only do this for a **single** meeting. In contrast, Optimeet gathers availability for **multiple** meetings (which may have overlapping sets of participants) and visualizes this information in a convenient interface that allows rapid exploration of different viable ways to schedule all meetings. Optimeet is built on existing standard tools: it uses automatically-generated when2meets to gather participant availability, and it can export the final meeting schedule to Google Calendar.

**NOTE: At present, the Google Calendar export feature is limited to a known set of test users that I control.** This is because Optimeet has not yet been verified by Google. Getting verified is a bit of a hassle; if enough people express interest in Optimeet, I'll jump through the requisite hoops. For now, if you'd like to use the GCal export functionality, [send me email](mailto:daniel_ritchie@brown.edu) so I can add you to the test users list.

## Requirements & Installation
Optimeet requires Python 3 and an ES5-compatible web browser.

Optimeet is easy to install; just run

```pip install -r requirements.txt```

from the repository root directory. In fact, Optimeet only has one external dependency (the Python [schedule](https://schedule.readthedocs.io/en/stable/) package).

## Overview & Input Files
Using Optimeet proceeds in two phases: first, use `optimeet.py` to gather availabilities from meeting participants; second, use a web interface to visualize availabilities and find a viable meeting schedule.

Optimeet's behavior is defined by a few files:

### config.json
This file specifies general configuration options that tend to be constant for a given user (i.e. you!) It has the following options:
* `"timeZone"`: Time zone in which the user is located (defaults to `"America/New_York"`),
* `"deadlineInDaysFromNow"`: Deadline by which participants should provide their availability, expressed as a number of days after Optimeet starts (defaults to `7`)
* `"reminderFrequencyInHours"`: How often to send reminder emails to participants who have not yet provided their availability (defaults to `24`)
* `"progressCheckFrequencyInHours"`: How often to check for updates to participant availability (defaults to `1`)
* `"name"`: The user's name, which will be included in emails sent to participants
* `"emailAddress"`: The email address from which Optimeet will send emails to participants
* `"emailServer"`: The SMTP server from which Optimeet will send emails (for GMail, this should be `"smtp.gmail.com"`)
* `"gCalEventColorId"`: A number from 1 to 11 specifying the color to be used for created Google Calendar events. [This image](https://i.stack.imgur.com/YSMrI.png) shows the colors to which each number corresponds. This field is optional; if omitted, the default calendar event color will be used.
* `"useBestSlotsIfNoneViable"`: A boolean value indicating what to do if there end up being no times that work for all participants of a meeting. If true, the times for which the most people are available will be treated as the set of viable meeting times. If false, the meeting will register as having no valid meeting times.

IMPORTANT NOTE: Due to Google's new security policies (as of May 2022), if you use GMail to send Optimeet emails, you will need to set up an "App Password" and use that password to log in to your email account when prompted by Optimeet. [This page](https://support.google.com/accounts/answer/185833#zippy=) provides information on how to set up an App Password (note that you will also need to have 2-factor authentication enabled).

### people.json
This file specifies information about people that participate in the user's meetings. It contains a dictionary mapping from unique person IDs to `{name:, email:}` dictionaries. Enter info for all the people you meet with here, and then simply refer to them by ID when creating a scheduling input file.

### Scheduling Input Files
Each one of these files specifies a set of meetings to be scheduled; an example can be found in `exampleInput/input.json`. They contain the following fields:
* `"meetingsToSchedule"`: A list of meetings to schedule. Each meeting contains the following fields:
  * `"name"`: A name for the meeting
  * `"length"`: The meeting length in minutes, which must be a multiple of 30 (defaults to `60`)
  * `"type"`: One of `"in-person"`, `"remote"`,  or `"hybrid"` (defaults to `"hybrid"`)
  * `"participants"`: A list of person IDs for each person who should participate in the meeting
  * `"physicalLocation"`: Physical location where the meeting will be held. This is required for `"in-person"` and `"hybrid"` meetings.
  * `"remoteLocation"`: Video conference link. This is required for `"remote"` and `"hybrid"` meetings.
* `"myLocations"`: Contains two fields, `"physical"` and `"remote"`, specifying the user's typicial physical location and typical video conference link (e.g. a personal Zoom room). These are used to fill in the `"physicalLocation"` and `"remoteLocation"` fields for any meetings with do not provide them. 
* `"myAvailability"`: A map from days of the week to a list of time ranges when the user is available for meetings
* `"myCommitments"`: A map from days of the week to a list of pre-existing commitments the user has. This is optional and only affects the web interface visualization. If these commitments overlap with any of the time ranges specified in `"myAvailability"`, those ranges will be adjusted accordingly. Each commitment contains the following fields:
  * `"name"`: A name for the commitment
  * `"time"`: When the commitment starts
  * `"length"`: How long the commitment is in minutes, which must be a multiple of 30 

## Gathering Participant Availabilities
To gather participant availabilities, run `python optimeet.py start <inputFilename>`. This automatically creates when2meets, sends an email to each participant with links to all the when2meets they should fill out, and starts a loop which periodically checks for when2meet updates and sends reminder emails to participants who have not yet filled them out.

Every time Optimeet checks for when2meet updates, it stores the results in `<inputBasename>.progress.json`, where `<inputBasename>` is the name of the input file minus the `.json` file extension. For convenience, this data is also written to a simple web page at `<inputBasename>.progress.html`. This webpage includes clickable links to all when2meets, shows who has and has not yet filled out each when2meet, and even shows how many viable meeting times exist for all participants who have filled it out thus far.

When all participants have filled out all when2meets, Optimeet saves information about valid meeting times for all meetings to `<inputBasename>.avail.json`. It also creates a scheduling web interface at `<inputBasename>.interface.html`.

If you need to restart the progress check/reminder email loop (e.g. because Optimeet crashed, or you restarted your machine), run `python optimeet.py resume <inputFilename>`. You can also manually check for progress using `python optimeet.py check <inputFilename>`, send reminder emails using `python optimeet.py remind <inputFilename>`, or regenerate the scheduling web interface using `python optimeet.py finalize <inputFilename>`.

### What if there's no meeting time that works for all participants?
If at any point the Optimeet progress report shows that there are zero valid times that work for all participants of a meeting, you have a couple of options: remove one or more participants from the meeting's participants list, or split the meeting into multiple meetings (each with a subset of the original participants). Both options will require manual editing of `<inputBasename>.json` and `<inputBasename>.progress.json`.

## Scheduling Interface
Once you've finished gathering participant availability, you can use the scheduling interface provided in the file `<inputBasename>.interface.html`. To do this, run

```
python -m http.server 8000
```

from the repository root directory and then point your browser to `http://localhost:8000/<testInterface>.interface.html`. **NOTE: You MUST use port 8000**, otherwise exporting to Google Calendar will not work (the Google Cloud project for Optimeet is configured to allow access to the Calendar API only from the exact URL `http://localhost:8000`).

You'll see something like this (also shown at the top of this README): 

https://user-images.githubusercontent.com/2229830/148315574-35f21e41-75ea-4ddc-a97b-3b3b6d699896.mov

Each cell of the calendar shows the number of meetings which can currently be scheduled at that slot (as it is often helpful to schedule meetings into less-contentious slots). Hovering over a cell highlights those meetings in the right-hand panel.

The meeting list in the right hand panel shows the name of the meeting, allows you to change the meeting length via a dropdown (e.g. if you need to make a meeting shorter to create a viable schedule), and shows the number of viable times for each meeting (so you can prioritize scheduling the more constrained meetings first). If you hover over a meeting, the meeting list also shows the number of participants that other meetings have in common with that one (to help you schedule meetings with many common participants back-to-back).

Clicking on a meeting selects it; while in select mode, clicking on a valid time slot for that meeting schedules it into that slot. To de-schedule a meeting, click on the slot in which it is currently schduled while in select mode. You can also click the "Clear Schedule" button below the calendar to de-schedule all meetings.

Once all meetings have been scheduled, the "Export to Google Calendar" button becomes enabled. Clicking this takes you through a confirmation dialog, then asks you to select a start date for the meetings. You'll then be asked to log into your Google Account (if you aren't already) and to authorize Optimeet to view and make changes to your calendar events. Here's what it looks like, if you've already logged in and authorized:

https://user-images.githubusercontent.com/2229830/148320152-2e320808-a07a-41ba-ac3d-6f0613c643c5.mov

## Privacy Policy
To export schedules to Google Calendar, Optimeet requires read/write access to your Google Calendar Events data. Since **you** run the Optimeet web interface locally on your machine, this data is never accessed or stored anywhere except by your local machine.

## Contact
Optimeet was created by me, [Daniel Ritchie](https://dritchie.github.io), professor of Computer Science at Brown University, for scheduling weekly meetings with members of my research group every semester. If you find Optimeet useful, please do send me [email](mailto:daniel_ritchie@brown.edu)! I'm especially interested in hearing about use cases outside of academia. If you find a bug or make a modificaton to Optimeet that you think might be useful to others, I'm happy to review pull requests. I am open to hearing feature requests, but I can't promise I'll have time to work on new features any time soon.
