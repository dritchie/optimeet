from datetime import datetime, timedelta
from functools import reduce
import json
import os
import re
import smtplib
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

'''
Returns:
 - URL of created when2meet
'''
def createWhen2Meet(name, timeZone, daysOfWeek, earliestTime, latestTime):
    possibleDates = "|".join([str(DAYS.index(day)) for day in daysOfWeek])
    earliestTime = datetime.strptime(earliestTime, "%I:%M %p").hour
    latestTime = datetime.strptime(latestTime, "%I:%M %p").hour
    url = 'https://when2meet.com/SaveNewEvent.php'
    post_fields = {
        'NewEventName': name,
        'DateTypes': 'DaysOfTheWeek',
        'PossibleDates': possibleDates,
        'NoEarlierThan': earliestTime,
        'NoLaterThan': latestTime,
        'TimeZone': timeZone
    }
    r = Request(url + '?' + urlencode(post_fields))
    html = urlopen(r).read().decode()
    match = re.search(r"window.location='/(\?[a-zA-Z0-9-]+)'", html)
    when2meet_id = match.group(1)
    return 'https://when2meet.com/' + when2meet_id

'''
Returns:
 - Dictionary of Sa|M|T|W|Th|F|Su, each day maps to a list of half-hour slots, each slot has a time
   and a list of people who are available then
'''
def parseWhen2Meet(url):
    r = Request(url)
    html = urlopen(r).read().decode()

    slot_info = re.findall(r'ShowSlot\(([0-9]+),"([a-zA-Z]+) (\d\d:\d\d):\d\d (AM|PM)"\);', html)
    id2slot = {s[0] : {'day' : s[1], 'time': s[2]+' '+s[3], 'available': []} for s in slot_info}
    slot_index_info = re.findall(r'TimeOfSlot\[(\d+)\]=(\d+);', html)
    slots = [None] * len(slot_index_info)
    for idx,Id in slot_index_info:
        slots[int(idx)] = id2slot[Id]

    people_name_info = re.findall(r"PeopleNames\[(\d+)\] = '([\w\s]+)';", html)
    if len(people_name_info) > 0:
        people_id_info = re.findall(r"PeopleIDs\[(\d+)\] = (\d+);", html)
        idx2name = {p[0] : p[1] for p in people_name_info}
        idx2id = {p[0] : p[1] for p in people_id_info}
        id2personname = {idx2id[idx] : name for idx,name in idx2name.items()}
        
        availability_info = re.findall(r"AvailableAtSlot\[(\d+)\].push\((\d+)\);", html)
        for slotidx,personid in availability_info:
            slots[int(slotidx)]['available'].append(id2personname[personid])

    # Restructure by day
    ret = {day : [] for day in DAYS}
    for slot in slots:
        ret[slot['day']].append({
            'time': datetime.strptime(slot['time'], "%I:%M %p"),
            'available': slot['available']
        })
    # Sort and merge 15 min slots into half hour ones
    for day in ret.keys():
        slots = sorted(ret[day], key=lambda slot: slot['time'])
        mergedSlots = []
        for i in range(0, len(slots), 2):
            mergedSlots.append({
                'time': datetime.strftime(slots[i]['time'], "%I:%M %p"),
                'available': list(set(slots[i]['available']).intersection(set(slots[i+1]['available'])))
            })
        ret[day] = mergedSlots
    
    return ret

def respondents(when2meet):
    res = set([])
    for slots in when2meet.values():
        for slot in slots:
            for person in slot['available']:
                res.add(person)
    return res
 
def viableSlots(when2meet):
    everyone = respondents(when2meet)
    viable = {day: [] for day in DAYS}
    for day,slots in when2meet.items():
        for slot in slots:
            if everyone == set(slot['available']):
                viable[day].append(slot)
    return viable

def numViableMeetingTimes(when2meet, meetingLength):
    when2meet = viableSlots(when2meet)
    if meetingLength == 30:
        return reduce(lambda a,b: a+b, [len(slots) for slots in when2meet.values()])
    # Count number of back-to-back half hour slots we have
    num = 0
    thirtymins = timedelta(minutes=30)
    for slots in when2meet.values():
        for i in range(0,len(slots)-1):
            time1 = datetime.strptime(slots[i]['time'], "%I:%M %p")
            time2 = datetime.strptime(slots[i+1]['time'], "%I:%M %p")
            if time2 - time1 == thirtymins:
                num += 1
    return num

def loadConfig():
    filename = os.path.dirname(os.path.abspath(__file__)) + '/config.json'
    with open(filename) as f:
        j = json.load(f)
    assert 'name' in j, 'config.json missing "name"'
    assert 'emailAddress' in j, 'config.json missing "emailAddress"'
    defaults = {
        'timeZone' : 'America/New_York',
        'deadlineInDaysFromNow': 7,
        'reminderFrequencyInHours' : 24
    }
    return {**defaults, **j}

def loadPeople():
    filename = os.path.dirname(os.path.abspath(__file__)) + '/people.json'
    with open(filename) as f:
        j = json.load(f)
    return j

def loadInputFile(filename):
    with open(filename) as f:
        j = json.load(f)
    
    assert 'myAvailability' in  j, 'Input file did not provide "myAvailability"'
    defaultAvailability = {day : [] for day in
        ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']}
    j['myAvailability'] = {**defaultAvailability, **j['myAvailability']}

    myPhysicalLocation = j['myLocations']['physical'] if ('myLocations' in j) and ('physical' in j['myLocations']) else None
    myRemoteLocation = j['myLocations']['remote'] if ('myLocations' in j) and ('remote' in j['myLocations']) else None

    assert 'meetingsToSchedule' in  j, 'Input file did not provide any "meetingsToSchedule"'
    meetings = j['meetingsToSchedule']
    meetingDefaults = {
        'length': 60,
        'type': 'hybrid'
    }
    if myPhysicalLocation is not None:
        meetingDefaults['physicalLocation'] = myPhysicalLocation
    if myRemoteLocation is not None:
        meetingDefaults['remoteLocation'] = myRemoteLocation
    for i in range(len(meetings)):
        meetings[i] = {**meetingDefaults, **meetings[i]}
        assert 'name' in meetings[i], f'Meeting {i} has no "name"'
        name = meetings[i]['name']
        assert 'participants' in meetings[i], f'Meeting "{name}" has no "participants"'
        mtype = meetings[i]['type']
        if mtype == 'hybrid' or mtype == 'in-person':
            assert 'physicalLocation' in meetings[i], 'Meeting "{name}" has no "physicalLocation"'
        if mtype == 'hybrid' or mtype == 'remote':
            assert 'remoteLocation' in meetings[i], 'Meeting "{name}" has no "remoteLocation"'
        if mtype == 'in-person':
            meetings[i].pop('remoteLocation', None)
        if mtype == 'remote':
            meetings[i].pop('physicalLocation', None)
    
    return j

def sendInitialEmails(inputjson):
    j = inputjson
    people = loadPeople()
    config = loadConfig()
    meetings = j['meetingsToSchedule']

    availableDays = [day for day in DAYS if len(j['myAvailability'][day]) > 0]
    allTimes = [datetime.strptime(time, "%I:%M %p") for timepairs in j['myAvailability'].values() for timepair in timepairs for time in timepair]
    earliestTime = datetime.strftime(min(allTimes), "%I:%M %p")
    latestTime = datetime.strftime(max(allTimes), "%I:%M %p")

    person2meetings = {}

    for meeting in meetings:
        # meeting['when2meet'] = createWhen2Meet(meeting['name'], config['timeZone'], availableDays, earliestTime, latestTime)
        meeting['when2meet'] = 'https://www.when2meet.com/?13981717-exqIc'
        for person in meeting['participants']:
            if not (person in person2meetings):
                person2meetings[person] = []
            person2meetings[person].append(meeting)

    remindFreq = config['reminderFrequencyInHours']
    deadline = datetime.now().date() + timedelta(days=config['deadlineInDaysFromNow'])
    deadline = datetime.strftime(deadline, "%A, %B %d")

    port = 465  # For SSL
    password = input("Type your email password and press enter: ")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
        server.login(config['emailAddress'], password)
        for person,meetings in person2meetings.items():
            assert person in people, f'Person "{person}" not found in people.json'
            personInfo = people[person]
            assert 'name' in personInfo,  f'Person "{person}" missing "name" field' 
            assert 'email' in personInfo,  f'Person "{person}" missing "email" field' 
            name = personInfo['name']
            firstname = name.split()[0]
            email = personInfo['email']

            linklist = ""
            for meeting in meetings:
                linklist += f"* {meeting['name']}: {meeting['when2meet']}\n"

            message =  f"""\
Subject: Please provide your meeeting availability

Hi {firstname},

{config['name']} requests that you fill out the when2meets for the following meetings:
{linklist}
Please use the name '{name}' when filling them out.

Please provide your availibility by {deadline}. You will receive a reminder message from this email address every {remindFreq} hours.
"""
            server.sendmail(config['emailAddress'], email, message)

def createProgressFile(filename, inputjson):
    j = inputjson
    # for each meeting: name, when2meet link, who has filled it out, who hasn't filled it out, num slots that work for everyone so far
    progressData = []
    for meeting in j['meetingsToSchedule']:
        progressData.append({
            'name': meeting['name'],
            'when2meet': meeting['when2meet'],
            'hasResponded': [],
            'hasNotResponded': meeting['participants'],
            'numViableSlotsSoFar': 0
        })
    with open(filename, 'w') as f:
        json.dump(progressData, f, sort_keys=True, indent=3)

def initScheduling(inputFilename):
    j = loadInputFile(inputFilename)
    sendInitialEmails(j)
    progFileName = os.path.splitext(inputFilename)[0] + '.progress.json'
    createProgressFile(progFileName, j)
    # TODO: Set up loop that periodically checks things

def checkProgress(inputFilename):
    pass

if __name__ == '__main__':
    # r = createWhen2Meet('Test', 'America/New_York', DAYS, '9:00 AM', '5:00 PM')
    r = parseWhen2Meet('https://www.when2meet.com/?8079662-q5hqG')
    # print(json.dumps(r, sort_keys=True, indent=3))
    # print(json.dumps(viableSlots(r), sort_keys=True, indent=3))
    print(numViableMeetingTimes(r, 60))
    # j = loadConfig()
    # print(j)
    # j = loadPeople()
    # print(j)
    # j = loadInputFile('test.json')
    # print(json.dumps(j, sort_keys=True, indent=3))
    # sendInitialEmails(loadInputFile('test.json'))
    # initScheduling('test.json')
    