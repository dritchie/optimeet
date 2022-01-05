from datetime import date, datetime, timedelta
from functools import reduce
import json
import os
import re
import schedule
import smtplib
import ssl
import time
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

    # Build reverse index of people names to people ids/keys
    people = loadPeople()
    name2pid = {p['name'] : pid for pid,p in people.items()}

    people_name_info = re.findall(r"PeopleNames\[(\d+)\] = '([\w\s]+)';", html)
    if len(people_name_info) > 0:
        people_id_info = re.findall(r"PeopleIDs\[(\d+)\] = (\d+);", html)
        idx2name = {p[0] : p[1] for p in people_name_info}
        idx2id = {p[0] : p[1] for p in people_id_info}
        id2personname = {idx2id[idx] : name for idx,name in idx2name.items()}
        
        availability_info = re.findall(r"AvailableAtSlot\[(\d+)\].push\((\d+)\);", html)
        for slotidx,personid in availability_info:
            personName = id2personname[personid]
            pid = getPersonFromName(personName)
            slots[int(slotidx)]['available'].append(pid)

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
    return list(res)
 
def viableSlots(when2meet, everyone=None):
    if everyone is None:
        everyone = respondents(when2meet)
    everyone = set(everyone)
    viable = {day: [] for day in DAYS}
    if len(everyone) == 0:
        return viable
    for day,slots in when2meet.items():
        for slot in slots:
            if everyone == set(slot['available']):
                viable[day].append(slot)
    return viable

def numViableMeetingTimes(when2meet, meetingLength, everyone=None):
    when2meet = viableSlots(when2meet, everyone)
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

__config = None
def loadConfig():
    global __config
    if __config is None:
        dirPath = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(dirPath, 'config.json')
        with open(filename) as f:
            j = json.load(f)
        assert 'name' in j, 'config.json missing "name"'
        assert 'emailAddress' in j, 'config.json missing "emailAddress"'
        assert 'emailServer' in j, 'config.json missing "emailServer"'
        defaults = {
            'timeZone' : 'America/New_York',
            'deadlineInDaysFromNow': 7,
            'reminderFrequencyInHours' : 24,
            'progressCheckFrequencyInHours' : 1
        }
        __config = {**defaults, **j}
    return __config

__people = None
def loadPeople():
    global __people
    if __people is None:
        dirPath = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(dirPath, 'people.json')
        with open(filename) as f:
            j = json.load(f)
        __people = j
    return __people

'''
Tries exact name match, then just first name (case insensitive)
If both fail, returns UnknownPerson<Name>
'''
def getPersonFromName(name):
    people = loadPeople()
    origName = name
    name = name.lower()
    exactMatch = next((pid for pid,p in people.items() if p['name'].lower() == name), None)
    if not (exactMatch is None):
        return exactMatch
    firstname = name.split(' ')[0]
    firstMatch = next((pid for pid,p in people.items() if p['name'].split(' ')[0].lower() == firstname), None)
    if not (firstMatch is None):
        return firstMatch
    return f'UnknownPerson<{origName}>'

__inputFiles = {}
def loadInputFile(filename):
    global __inputFiles
    if not filename in __inputFiles:
        with open(filename) as f:
            j = json.load(f)
        
        assert 'myAvailability' in  j, 'Input file did not provide "myAvailability"'
        defaultAvailability = {day : [] for day in
            ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']}
        j['myAvailability'] = {**defaultAvailability, **j['myAvailability']}
        j['myAvailability'] = {day: ranges2slots(ranges) for day,ranges in j['myAvailability'].items()}

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
        
        __inputFiles[filename] = j
    
    return __inputFiles[filename]

'''
Convert ranges of availabilities into a list of slsots
'''
def ranges2slots(ranges):
    slots = []
    for r in  ranges:
        rmin = datetime.strptime(r[0], "%I:%M %p")
        rmax = datetime.strptime(r[1], "%I:%M %p")
        t = rmin
        while t <= rmax:
            slots.append(datetime.strftime(t, "%I:%M %p"))
            t += timedelta(minutes=30)
    return  slots

def makeWhen2Meets(inputjson):
    j = inputjson
    config = loadConfig()
    meetings = j['meetingsToSchedule']

    availableDays = [day for day in DAYS if len(j['myAvailability'][day]) > 0]
    allTimes = [datetime.strptime(time, "%I:%M %p") for timepairs in j['myAvailability'].values() for timepair in timepairs for time in timepair]
    earliestTime = datetime.strftime(min(allTimes), "%I:%M %p")
    latestTime = datetime.strftime(max(allTimes), "%I:%M %p")

    for meeting in meetings:
        meeting['when2meet'] = createWhen2Meet(meeting['name'], config['timeZone'], availableDays, earliestTime, latestTime)
        # meeting['when2meet'] = 'https://www.when2meet.com/?13981717-exqIc'

__emailPassword = None
def getEmailPassword():
    global __emailPassword
    if __emailPassword is None:
        __emailPassword = input("Type your email password and press enter: ")
    return __emailPassword

def sendInitialEmails(inputjson):
    j = inputjson
    people = loadPeople()
    config = loadConfig()
    meetings = j['meetingsToSchedule']

    person2meetings = {}
    for meeting in meetings:
        for person in meeting['participants']:
            if not (person in person2meetings):
                person2meetings[person] = []
            person2meetings[person].append(meeting)

    remindFreq = config['reminderFrequencyInHours']
    deadline = datetime.now().date() + timedelta(days=config['deadlineInDaysFromNow'])
    deadline = datetime.strftime(deadline, "%A, %B %d")

    port = 465  # For SSL
    password = getEmailPassword()
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['emailServer'], port, context=context) as server:
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

def initScheduling(inputFilename):
    inp = loadInputFile(inputFilename)
    makeWhen2Meets(inp)
    sendInitialEmails(inp)
    prog = createProgressFile(inputFilename, inp)
    saveProgressReportHTML(inputFilename, inp, prog)

def progressFilename(inputFilename):
    return os.path.splitext(inputFilename)[0] + '.progress.json'

def createProgressFile(inputFilename, inputjson):
    j = inputjson
    config = loadConfig()
    deadline = datetime.now().date() + timedelta(days=config['deadlineInDaysFromNow'])
    deadline = datetime.strftime(deadline, "%x")
    progressData = []
    for meeting in j['meetingsToSchedule']:
        progressData.append({
            'name': meeting['name'],
            'when2meet': meeting['when2meet'],
            'hasResponded': [],
            'hasNotResponded': meeting['participants'],
            'numViableMeetingTimesSoFar': 0,
            'deadline': deadline
        })
    with open(progressFilename(inputFilename), 'w') as f:
        json.dump(progressData, f, sort_keys=True, indent=3)
    return progressData

def saveProgressReportHTML(inputFilename, inp, prog):
    dirPath = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(dirPath, 'progress_template.html')
    with open(filename) as f:
        html = f.read()
    html = html.replace('[[INPUTFILE]]', os.path.abspath(inputFilename))
    html = html.replace('[[LASTCHECKED]]', datetime.strftime(datetime.now(), '%A %B %m, %I:%M %p'))
    tableRows = '';
    people = loadPeople()
    for meeting in prog:
        inpMeeting = next(m for m in inp['meetingsToSchedule'] if m['name'] == meeting['name'])
        hasResponded = sorted([people[p]["name"] for p in meeting["hasResponded"]])
        hasNotResponded = sorted([people[p]["name"] for p in meeting["hasNotResponded"]])
        tableRows += f'''\
        <tr>
            <td>{meeting["name"]}</td>
            <td>{inpMeeting["length"]}</td>
            <td><a target="_blank" href="{meeting["when2meet"]}">{meeting["when2meet"]}</a></td>
            <td>{"<br/>".join(hasResponded)}</td>
            <td>{"<br/>".join(hasNotResponded)}</td>
            <td>{meeting["numViableMeetingTimesSoFar"]}</td>
        </tr>
        '''
    html = html.replace('[[TABLEROWS]]', tableRows)
    filename = os.path.splitext(progressFilename(inputFilename))[0] + '.html'
    with open(filename, 'w') as f:
        f.write(html)

def loadProgressFile(inputFilename):
    with open(progressFilename(inputFilename)) as f:
        j = json.load(f)
    return j

def saveProgressFile(inputFilename, prog):
    with open(progressFilename(inputFilename), 'w') as f:
        json.dump(prog, f, sort_keys=True, indent=3)

def checkProgress(inputFilename):
    inp = loadInputFile(inputFilename)
    prog = loadProgressFile(inputFilename)
    for meeting in prog:
        inpMeeting = next(m for m in inp['meetingsToSchedule'] if m['name'] == meeting['name'])
        when2meet = parseWhen2Meet(meeting['when2meet'])
        ppl = respondents(when2meet)
        ppl = list(set(ppl).intersection(set(inpMeeting['participants'])))
        meeting['hasResponded'] = ppl
        meeting['hasNotResponded'] = list(set(inpMeeting['participants']).difference(set(ppl)))
        meetingLength = inpMeeting['length']
        meeting['numViableMeetingTimesSoFar'] = numViableMeetingTimes(when2meet, meetingLength, ppl)
    saveProgressFile(inputFilename, prog)
    saveProgressReportHTML(inputFilename, inp, prog)
    return prog

'''
Returns list of people to whom reminder emails were sent
'''
def sendReminderEmails(inputFilename):
    config = loadConfig()
    people = loadPeople()
    progressData = loadProgressFile(inputFilename)

    people2meetings = {}
    for meeting in progressData:
        for person in meeting['hasNotResponded']:
            if not (person in people2meetings):
                people2meetings[person] = []
            people2meetings[person].append(meeting)
    
    remindFreq = config['reminderFrequencyInHours']

    port = 465  # For SSL
    password = getEmailPassword()
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
        server.login(config['emailAddress'], password)
        for person,meetings in people2meetings.items():
            personInfo = people[person]
            name = personInfo['name']
            firstname = name.split()[0]
            email = personInfo['email']
            deadline = datetime.strptime(meeting['deadline'], '%x')
            overdue = datetime.now() > deadline
            deadline = datetime.strftime(deadline, "%A, %B %d")
            deadlineStatement  = f'Your availability is now overdue (the deadline was {deadline})' if overdue else f'Please provide your availibility by {deadline}'
            linklist = ""
            for meeting in meetings:
                linklist += f"* {meeting['name']}: {meeting['when2meet']}\n"
            msg = f'''\
Subject: [{"OVERDUE" if overdue else "Reminder"}] Please provide your meeeting availability

Hi {firstname},

This is a reminder that {config['name']} requests that you fill out the when2meets for the following meetings:
{linklist}
Please use the name '{name}' when filling them out.

{deadlineStatement}. You will continue to receive a reminder message from this email address every {remindFreq} hours.
'''
            server.sendmail(config['emailAddress'], email, msg)
    
    return list(people2meetings.keys())

def availabilityFilename(inputFilename):
    return os.path.splitext(inputFilename)[0] + '.avail.json'

def saveFinalAvailability(inputFilename):
    prog  = loadProgressFile(inputFilename)
    availabilities = {}
    for meeting in prog:
        when2meet = parseWhen2Meet(meeting['when2meet'])
        when2meet = viableSlots(when2meet, meeting['hasResponded'])
        # Turn when2meet into a map from days to lists of times
        availabilities[meeting['name']] = {day: [slot['time'] for slot in slots] for day,slots in when2meet.items()}
    filename = availabilityFilename(inputFilename)
    with open(filename, 'w') as f:
        json.dump(availabilities, f, sort_keys=True, indent=3)
    return availabilities

def loadAvailabilityFile(inputFilename):
    with open(availabilityFilename(inputFilename)) as f:
        j = json.load(f)
    return j

def timeRange(avail):
    def add(a,b):
        return a + b
    times = reduce(add, [reduce(add, day2times.values(), []) for day2times in avail.values()], [])
    times = list(map(lambda t: datetime.strptime(t, "%I:%M %p"), times))
    return min(times), max(times)

def doPeriodicChecksAndReminders(inputFilename, verbose=True):

    # Ensure that we have the user's email password before we start the schedule loop
    getEmailPassword()

    def log(msg):
        if verbose:
            now = datetime.now()
            msg = f'[{datetime.strftime(now, "%c")}] ' + msg
            print(msg)

    config = loadConfig()
    progCheckFreq = config['progressCheckFrequencyInHours']
    remindFreq = config['reminderFrequencyInHours'] 

    def progCheckJob():
        meetings = checkProgress(inputFilename)
        if all([len(m['hasNotResponded']) == 0 for m in meetings]):
            schedule.clear()
        log('Checked when2meets')

    def reminderJob():
        remindees = sendReminderEmails(inputFilename)
        log(f'Sent reminder emails to {remindees}')

    schedule.every(progCheckFreq).hours.do(progCheckJob)
    schedule.every(remindFreq).hours.do(reminderJob)
    # schedule.every(20).seconds.do(progCheckJob)
    # schedule.every(40).seconds.do(reminderJob)

    log(f'Checking when2meets every {progCheckFreq} hours and sending reminder emails every {remindFreq} hours...')
    while len(schedule.get_jobs()) > 0:
        schedule.run_pending()
        time.sleep(1)
    log('DONE (All when2meets have been filled out by all participants)')
    saveFinalAvailability(inputFilename)
    log(f'Final availabilities saved to {availabilityFilename(inputFilename)}')

def interfaceFilename(inputFilename):
    return os.path.splitext(inputFilename)[0] + '.interface.html'

def createInterfaceHTML(inputFilename):
    config = loadConfig()
    people = loadPeople()
    inp = loadInputFile(inputFilename)
    avail = loadAvailabilityFile(inputFilename)
    dirPath = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(dirPath, 'interface_template.html')
    with open(filename) as f:
        html = f.read()

    # Inject config
    html = html.replace('let config = undefined;', f'let config = {json.dumps(config)}');
    # Inject all the people who participate in these meetings
    participants = set(reduce(lambda a,b: a+b, [m['participants'] for m in inp['meetingsToSchedule']]))
    relevantPeople = {k:v for k,v in people.items() if k in participants}
    html = html.replace('let people = undefined;', f'let people = {json.dumps(relevantPeople)};')
    html = html.replace('let meetings = undefined;', f'let meetings = {json.dumps(inp["meetingsToSchedule"])};')
    # Inject user availability and participant availability
    html = html.replace('let myAvailability = undefined;', f'let myAvailability = {json.dumps(inp["myAvailability"])};')
    html = html.replace('let meeting2validslots = undefined;', f'let meeting2validslots = {json.dumps(avail)};')

    # Create DOM elements for rows of calendar (according to availability)
    calendarRows = ''
    times = []
    minTime, maxTime = timeRange(avail)
    currTime = minTime
    while currTime <= maxTime:
        timestr = datetime.strftime(currTime, "%I:%M %p")
        calendarRows += f'''
        <tr>
            <th scope="row">{timestr}</th>
            {''.join([f'<td day="{DAYS[i]}" time="{timestr}"></td>' for i in range(7)])}
        </tr>
        '''
        times.append(timestr)
        currTime += timedelta(minutes=30)
    html = html.replace('[[CALENDARROWS]]', calendarRows)
    html = html.replace('const TIMES = undefined;', f'const TIMES = {json.dumps(times)};')

    with open(interfaceFilename(inputFilename), 'w') as f:
        f.write(html)

if __name__ == '__main__':
    # r = createWhen2Meet('Test', 'America/New_York', DAYS, '9:00 AM', '5:00 PM')
    # r = parseWhen2Meet('https://www.when2meet.com/?8079662-q5hqG')
    # print(json.dumps(r, sort_keys=True, indent=3))
    # print(json.dumps(viableSlots(r), sort_keys=True, indent=3))
    # print(numViableMeetingTimes(r, 60))
    # j = loadConfig()
    # print(j)
    # j = loadPeople()
    # print(j)
    # j = loadInputFile('test.json')
    # print(json.dumps(j, sort_keys=True, indent=3))
    # sendInitialEmails(loadInputFile('test.json'))
    # initScheduling('test.json')
    # checkProgress('test.json')
    # sendReminderEmails('test.json')
    # doPeriodicChecksAndReminders('test.json')
    # saveFinalAvailability('test.json')
    # print(ranges2slots([
    #     ["9:00 AM", "5:00 PM"]
    # ]))
    # print(json.dumps(loadInputFile('test.json'), sort_keys=True, indent=3))
    createInterfaceHTML('test.json')
    