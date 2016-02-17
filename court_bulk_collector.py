from courtreader import readers
from courtutils.logger import get_logger
from datetime import datetime, timedelta
import pymongo
import os
import sys
import time

# configure logging
log = get_logger()
log.info('Worker running')

def get_db_connection():
    return pymongo.MongoClient(os.environ['MONGO_DB'])['va_court_search']

# Fill in cases
court_reader = None
current_court_fips = None
db = get_db_connection()

court_fips = sys.argv[1]
year = int(sys.argv[2])
case_type = 'criminal'

reader = readers.CircuitCourtReader()
reader.connect()

def get_cases_on_date(date, dateStr):
    log.info('Getting cases on ' + dateStr)
    cases = reader.get_cases_by_date(court_fips, case_type, dateStr)
    for case in cases:
        case['details_fetched_for_hearing_date'] = date
        case['court_fips'] = court_fips
        case_details = db.circuit_court_detailed_cases.find_one({
            'court_fips': case['court_fips'],
            'case_number': case['case_number'],
            'details_fetched_for_hearing_date': {'$gte': date}
        })
        if case_details != None:
            last_date = case_details['details_fetched_for_hearing_date'].strftime('%m/%d/%Y')
            log.info(case['case_number'] + ' details collected for hearing on ' + last_date)
            continue
        case['details'] = reader.get_case_details_by_number( \
                            court_fips, \
                            case_type, \
                            case['case_number'])
        case['details_fetched'] = datetime.utcnow()
        log.info(case['case_number'] + ' ' + \
                    case['defendant'] + ' ' + \
                    case['details']['Filed'])
        db.circuit_court_detailed_cases.find_one_and_replace({
            'court_fips': case['court_fips'],
            'case_number': case['case_number']
        }, case, upsert=True)

date = datetime(year, 12, 31)
while date.year == year:
    date_search = {
        'court_fips': court_fips,
        'case_type': case_type,
        'date': date
    }
    dateStr = date.strftime('%m/%d/%Y')
    if db.circuit_court_dates_searched.find_one(date_search) != None:
        log.info(dateStr + ' already searched')
    else:
        get_cases_on_date(date, dateStr)
        db.circuit_court_dates_searched.insert_one(date_search)
    date += timedelta(days=-1)

reader.log_off()
