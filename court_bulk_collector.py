from courtreader import readers
from courtutils.logger import get_logger
from datetime import datetime, timedelta
from time import sleep
import pymongo
import os
import sys
import time
import traceback

# configure logging
log = get_logger()
log.info('Worker running')

court_type = sys.argv[1]
if court_type != 'circuit' and court_type != 'district':
    raise ValueError('Unknown court type')
court_type += '_court_'

def get_db_connection():
    return pymongo.MongoClient(os.environ['MONGO_DB'])['va_court_search']

def get_cases_on_date(db, reader, court_fips, case_type, date, dateStr):
    log.info('Getting cases on ' + dateStr)
    cases = reader.get_cases_by_date(court_fips, case_type, dateStr)
    for case in cases:
        case['details_fetched_for_hearing_date'] = date
        case['court_fips'] = court_fips
        case_details = db[court_type + 'detailed_cases'].find_one({
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
                            case['case_number'],
                            case['details_url'] if 'details_url' in case else None)
        case['details_fetched'] = datetime.utcnow()
        if 'error' in case['details']:
            log.warn('Could not collect case details for ' + \
                case['case_number'] + ' in ' + case['court_fips'])
        else:
            print case
            log.info(case['case_number'] + ' ' + \
                        case['defendant'])
            keys = case['details'].keys()
            for key in keys:
                if not case['details'][key]:
                    del case['details'][key]
        db[court_type + 'detailed_cases'].find_one_and_replace({
            'court_fips': case['court_fips'],
            'case_number': case['case_number']
        }, case, upsert=True)

def run_collector():
    court_reader = None
    current_court_fips = None
    db = get_db_connection()

    reader = readers.CircuitCourtReader() if 'circuit' in court_type else \
             readers.DistrictCourtReader()
    reader.connect()

    task = db[court_type + 'date_tasks'].find_one_and_delete({})
    if task is None:
        reader.log_off()
        log.info('Nothing to do. Sleeping for 30 seconds.')
        sleep(30)
        return

    try:
        court_fips = task['court_fips']
        start_date = task['start_date']
        end_date = task['end_date']
        case_type = 'criminal'

        log.info('Start ' + court_fips + ' ' + \
                    start_date.strftime('%m/%d/%Y') + '-' + \
                    end_date.strftime('%m/%d/%Y'))
        date = start_date

        while date >= end_date:
            date_search = {
                'court_fips': court_fips,
                'case_type': case_type,
                'date': date
            }
            dateStr = date.strftime('%m/%d/%Y')
            if db[court_type + 'dates_searched'].find_one(date_search) != None:
                log.info(dateStr + ' already searched')
            else:
                get_cases_on_date(db, reader, court_fips, case_type, date, dateStr)
                db[court_type + 'dates_searched'].insert_one(date_search)
            date += timedelta(days=-1)

        reader.log_off()
    except Exception, err:
        log.error(traceback.format_exc())
        log.warn('Putting task back')
        db[court_type + 'date_tasks'].insert_one(task)
        reader.log_off()
        raise
    except KeyboardInterrupt:
        log.warn('Putting task back')
        db[court_type + 'date_tasks'].insert_one(task)
        reader.log_off()
        raise

while(True):
    try:
        run_collector()
    except Exception, err:
        log.error(traceback.format_exc())
        log.info('Unexpect error. Sleeping for 5 minutes.')
        sleep(300)
    log.info('Sleeping for 10 seconds')
    sleep(10)
