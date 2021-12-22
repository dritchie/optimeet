from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import re

days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

'''
Returns:
 - URL of created when2meet
'''
def create_when2meet(name, timeZone, daysOfWeek, earliestTime, latestTime):
    possibleDates = "|".join([str(days.index(day)) for day in daysOfWeek])
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
 - Names of all people who have responded thus far
 - List of slots, where each slot has a day, a time, and a list of people who are available then
'''
def parse_when2meet(url):
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
    
    return list(id2personname.values()), slots

if __name__ == '__main__':
    # r = create_when2meet('Test', 'America/New_York', days, '9:00 AM', '5:00 PM')
    # r = parse_when2meet('https://when2meet.com/?13956703-y2gl6')
    names, slots = parse_when2meet('https://www.when2meet.com/?8079662-q5hqG')
    