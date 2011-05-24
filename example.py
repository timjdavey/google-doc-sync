#!/usr/bin/python
import getopt
import sys
from test_data import test_data
from spreadsheet import GoogleSpreadsheet, MutipleEntriesExist

class BondSheet(GoogleSpreadsheet):
    primary_key = 'pk'
    
    def convert(self, payload):
        if not isinstance(payload, dict): # better checks against class
            raise TypeError
        # example just add new user
        payload['author'] = 'Ian Fleming'
        return payload


def main():
    import getopt
    from getpass import getpass
    sheet = BondSheet(
        raw_input('email:'),
        getpass(),
        raw_input('spreadsheet:'),
        raw_input('worksheet:'), # od6 for first
        cache_feed=True
    )
    
    c = 0
    while c < 1000:
        print 'count:', c
        for d in test_data:
            print ' '*4, 'syncing:', d['pk']
            
            try:
                row = sheet.get(d)
            except MutipleEntriesExist:
                print ' '*8, 'dedup'
                sheet.deduplicate()
            else:
                print ' '*8, 'save'
                row.save(refresh=True)
        
        c += 1


if __name__ == '__main__':
    main()
