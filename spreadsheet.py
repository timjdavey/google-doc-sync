import gdata.spreadsheet
import gdata.spreadsheet.service
import gdata.service


class EntryDoesNotExist(Exception):
    pass

class EntryAlreadyExists(Exception):
    pass

class MutipleEntriesExist(Exception):
    pass

class GoogleRow(object):
    """Helper object to pass info. Please see docs for usage."""
    def __init__(self, payload, data, entry, sheet):
        self.payload = payload
        self.converted = self.clean(data)
        self._entry = entry # underscored for proper error handling
        self.sheet = sheet
    
    @property
    def entry(self):
        """ Gets the google entry with proper exceptions """
        if self._entry is None:
            raise EntryDoesNotExist
        else:
            return self._entry
    
    def exists(self):
        """ Checks to see if entry exists on google """
        try:
            self.entry
        except EntryDoesNotExist:
            return False
        else:
            return True
    
    def clean(self, data):
        """ Cleans the data ready for Googles consumption """
        d = {}
        for k, v in data.items():
            if v is not None: # leave in None (blank cells)
                v = str(v) # otherwise make string
            d[str(k)] = v
        return d
    
    def outgoing(self):
        """ Data to be sent to Google. Cleaned & updated with incoming. """
        try:
            out = self.incoming()
        except EntryDoesNotExist:
            out = self.converted
        else:
            out.update(self.converted)
        return out
    
    def incoming(self):
        """ Data returned from Google row. Contains extra cols. """
        data = dict([(k, v.text) for k,v in self.entry.custom.items()])
        return self.clean(data)
    
    def out_of_sync(self):
        """ Returns bool on if incoming & outgoing are out of sync"""
        try:
            self.entry
        except EntryDoesNotExist:
            return True
        else:
            incoming = self.incoming()
            outgoing = self.outgoing()
            for k, v in incoming.items():
                if k in outgoing and not v == outgoing[k]:
                    return True
            return False
    
    def save(self, refresh=False):
        if self.out_of_sync() and refresh:
            self.sheet.feed(refresh=True)
        return self.sheet.save(self)
    
    def delete(self, silent=False):
        try:
            self.sheet.delete(self)
        except EntryDoesNotExist:
            return None # None not False
        else:
            return True


class GoogleSpreadsheet(object):
    """ Base Spreadsheet example. Please see documents on how to extend. """
    primary_key = 'pk'
    
    def __init__(self, email, password,
                    spreadsheet, worksheet, cache_feed=False, source=None):
        self.email = email
        self.password = password
        self.spreadsheet = spreadsheet
        self.worksheet = worksheet
        self.source = email if source is None else source
        self.cache_feed = cache_feed
    
    def convert(self, payload):
        """ Please specify how the payload (e.g. User) converts to dict """
        raise NotImplementedError
    
    def convert_back(self, row, payload):
        """ Please specify how the row should convert back to a payload """
        raise NotImplementedError
    
    @property
    def client(self):
        """ Logs you into the spreadsheet lazily with creditials """
        try:
            self._client
        except AttributeError:
            client = gdata.spreadsheet.service.SpreadsheetsService()
            client.email = self.email
            client.password = self.password
            client.source = self.source
            client.ProgrammaticLogin()
            self._client = client
        return self._client
    
    def feed(self, refresh=False):
        """ Managed feed from Google, list dict by primary key """
        if not self.cache_feed or refresh \
            or not hasattr(self, '_cached_entries'):
            ents = {}
            feed = self.client.GetListFeed(self.spreadsheet, self.worksheet)
            for entry in feed.entry:
                t = str(entry.title.text)
                if t in ents:
                    ents[t].append(entry)
                else:
                    ents[t] = [entry]
            self._cached_entries = ents
        return self._cached_entries
    
    def entry(self, pk):
        """ Returns the single entry with proper Exception handling """
        feed = self.feed()
        try:
            lst = feed[str(pk)]
        except KeyError:
            raise EntryDoesNotExist
        else:
            if len(lst) > 1:
                raise MutipleEntriesExist
            else:
                return lst[0]
    
    def get(self, payload):
        """ Returns a GoogleRow given a payload object """
        data = self.convert(payload)
        pk = data[self.primary_key]
        try:
            entry = self.entry(pk)
        except EntryDoesNotExist:
            entry = None
        return GoogleRow(payload, data, entry, self)
    
    def create(self, row):
        """ Creates a row in Google, making sure it doesn't already exist """
        try:
            # checks the make sure the code isn't doing something stupid
            row.entry
        except EntryDoesNotExist:
            self.client.InsertRow(
                row.outgoing(), self.spreadsheet, self.worksheet)
        else:
            raise EntryAlreadyExists
        return row
    
    def update(self, row):
        """ Updates a given row, with built in exception handling """
        self.client.UpdateRow(row.entry, row.outgoing())
        return row
    
    def save(self, row):
        """ Create or Update appropriately """
        try:
            self.create(row)
        except EntryAlreadyExists:
            if row.out_of_sync():
                self.update(row)
        return row
    
    def delete(self, entry):
        """ Simply deletes a row """
        if isinstance(entry, GoogleRow):
            entry = row.entry
        self.client.DeleteRow(entry)
    
    def deduplicate(self):
        """ Removes duplicate rows """
        feed = self.feed()
        c = []
        for k, v in feed.items():
            if len(v) > 1:
                # could do something more fancy here like check last updated
                for entry in v[1:]:
                    self.delete(entry)
                    c.append(k)
        return c




