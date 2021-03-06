import pymongo
import os

class MongoDatabase():
    def __init__(self, name, court_type):
        self.client = pymongo.MongoClient(os.environ['MONGO_DB'])[name]
        self.court_type = court_type
    
    def add_court(self, name, fips, location):
        self.client[self.court_type + '_courts'].insert_one({
            'name': name,
            'fips_code': fips,
            'location': {'type': 'Point', 'coordinates': [
                location.longitude, location.latitude
            ]}
        })
    
    def add_court_location_index(self):
        self.client[self.court_type + '_courts'].create_index( \
            [('location', pymongo.GEOSPHERE)], background=True)
    
    def drop_courts(self):
        self.client[self.court_type + '_courts'].drop()
        
    def get_courts(self):
        return self.client[self.court_type + '_courts'].find(None, {'_id':0})

    def add_date_tasks(self, tasks):
        self.client[self.court_type + '_court_date_tasks'].insert_many(tasks)

    def get_cases_by_hearing_date(self, start, end):
        return self.client[self.court_type + '_court_detailed_cases'].find({
            'details_fetched_for_hearing_date': {'$gte': start, '$lt': end}
        })
