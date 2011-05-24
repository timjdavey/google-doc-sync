"""
Description:

    A small helper tool to sync a list of objects backed in a typical
    database, json, csv format with a google spreadsheet. Currently it only
    supports push sync 
    
    Two main common use cases are
        # Augment existing data in a flexible way. Add and append extra 
        data columns to the object being sent over.
        # BI tool. Use Google's built in filter, graphs, charts & formula
        functions to cut up the data how the analysis likes.
    
    There are only two prerequesist to using this tool. The list of objects
    must be convertable into a dictionary which supports only key value string
    pairs. Therefore its difficult to store sub-lists against the items unless
    csv is good enough.


Example Definition:
    First you need to extend the ``GoogleSpreadsheet`` with two parts.::
        
        class ExampleUserSheet(GoogleSpreadsheet):
            primary_key = 'pk'
            
            def __init__(self, cache_feed=False):
                # optionally can preprogram creditials how you like
                self.email = settings.GOOGLE_SPREADSHEET_EMAIL
                self.password = settings.GOOGLE_SPREADSHEET_PASSWORD
                self.spreadsheet = 'h8fw4kbaeflnafaf'
                self.worksheet = 'od6'
                self.source = 'server'
                self.cache_feed = cache_feed
            
            def convert(self, payload):
                converted = {
                    'pk': payload.pk,
                    'username': payload.username,
                    'email: payload.email,
                }
                return converted
            
    Where there are two important parts here. Firstly you need to set
    the primary_key which identifies the spreadsheet entry to the payload
    objects database equivalent. This value much be unique.
    
    The second is to define a ``convert`` function, which takes a payload
    object (or any definition of your choosing) and returns a dictionary.
    Keyed to the google column header you define. The value will be cohereced
    to a string when sent to google, so be careful that the __str__ is how
    you expect.
    
    Google has some restrictions on key names. It seems to remove all spaces
    and underscores. While for values turns values like '006' to just 6.
    
    There is a final parameter called ``cache_feed`` which if ``True`` will
    cache the feed brought back from google. If you are writing back, it is
    highly recommened that this is set to ``False`` otherwise you are
    increasing the risk that changes made to the spread sheet will be
    overridden (even those which are not payload fields). If you are simply
    reading from 


Example Usage:
    When creating or updating a new user insert indiviually::
    
        # when updating a user, or can override the user save function
        user.save()
        urow = ExampleUserSheet().get(user)
        urow.save()
        
        # or similiarly if you delete
        user.delete()
        urow.delete()
    
    When updating a sheet can reuse the sheet::
        
        sheet = ExampleUserSheet()
        
        users = User.objects.all()
        for u in users:
            row = sheet.get(u)
            if u.is_active:
                # will only update if they are out of date
                # it will also not create two entries if pk's are correct
                row.save()
            else:
                if row.exists(): # if it exists remotely
                    row.delete() # then must remove as only want active
    
    
    When updating in bulk, can use cache lazily::
    
        sheet = ExampleUserSheet(cache_feed=True)
        
        users = User.objects.all()
        for u in users:
            row = sheet.get(u)
            row.save(refresh=True)
    
    By setting ``refresh=True`` on save, if the row is out_of_sync, it will
    force the sheet to update with the latest feed (entries). This ensures
    that any writes check for the latest first. There is a possibility that
    you miss updates that should happen, however you also don't need to hit
    google to check each time - massively improving performance.
    
    If there are corruptions in the sheet (multiple entries per pk). A
    ``MutipleEntriesExist`` exception will be thrown. These can be tieded
    up using ``sheet.deduplicate()``, which is unintelligently remove all but
    the first entries it finds. This can be overridden by smarter functions
    which look at a last_updated column or the equivelent value stored on the
    google entry which is returned. The current function returns a list of
    pks which were removed.


Experimental feed back to database:

    This is experimental. Obviously very dangerous & probably massively
    error prone. However, if you want to live dangerously, here's how::
    
        def convert_back(self, row, payload):
            # payload is User with correct pk, could defined model & lookup?
            for k, v in row.incoming().items():
                # inreality will need some cohercing into correct keys & types
                setattr(payload, k, v)
            payload.save()
            
            # or another example
            User.objects.filter(pk=row.pk).update(**row.incoming)

TODO:

    * add logging


THIS IS NEW! I did this not so long ago and it was fine


"""
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
    def __init__(self, data, entry, sheet):
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
        return GoogleRow(data, entry, self)
    
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




