##Description

A small helper tool to sync a list of objects backed in a typical database, json, csv format with a google spreadsheet. Currently it only supports push sync 
    
Two main common use cases are
* Augment existing data in a flexible way. Add and append extra data columns to the object being sent over.
* BI tool. Use Google's built in filter, graphs, charts & formula functions to cut up the data how the analysis likes.

There are however two prerequesist to using this tool
* The list of objects must be convertable into a dictionary which supports only key value string pairs (e.g. no sub lists unless using csv)
* Each object must have a unique primary key


##Example

###Setting up the spreadsheet
Setting up and extending the base ``GoogleSpreadsheet`` class
        
    class ExampleUserSheet(GoogleSpreadsheet):
        primary_key = 'pk'
        
        def __init__(self, cache_feed=False):
            # optionally can preprogram creditials into sheet
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
        
Where there are three important steps here.

**First.** you need to set the ``primary_key`` which identifies the spreadsheet entry to the payload object's database equivalent. This value much be unique. So for the example above the ``payload`` is a ``User`` object with its ``primary_key`` being the ``pk`` (django example).

**Second.** define a ``convert`` function. It takes a payload
object and returns a dictionary where the keys are the google column header's you define. *Watch out* The value will be cohereced to a string when sent to google, so be careful that the __str__ is exactly what you want to be sent. So with that Google has some general restrictions. For key names it removes all spaces and underscores - so make sure your dictionary has those removed. While for values it turns entries like '006' to just 6.

**Third.** setup the actual google spreadsheet and store the creditials. For this simply create a spreadsheet in some users name. Once created in the URL you'll see ``key=`` which is the spreadsheet key which needs setting above. Working out the worksheet id is a little trickier, but for now its always ``od6`` for the first sheet. Throw these creditials in like above. The optional ``source`` value is for audit purposes. When setting up the google doc, simply put in the column headers at the top line of the doc, with the primary_key set as the first column.

There is a final optional **fourth** parameter called ``cache_feed`` which if ``True`` will cache the feed brought back from google on a per sheet basis. We talk about that later.


###Interacting with the spreadsheet
When creating or updating a new user on the fly, you can insert it on an ad-hoc basis. Or of course delete it as well.
    
    # when updating a user, or can override the user save function
    user.save()
    urow = ExampleUserSheet().get(user)
    urow.save()
    
    # or similiarly if you delete
    user.delete()
    urow.delete()
    

Or when doing a bulk sync, you can do a bit more advanced logic.
        
    sheet = ExampleUserSheet()
    
    users = User.objects.all()
    for u in users:
        row = sheet.get(u)
        if u.is_active:
            row.save()
        else:
            if row.exists(): # if it exists remotely
                row.delete() # then must remove as only want active

However, the code is incredibly slow as on each ``get`` it gets the entire spreadsheet fresh & rebuilds the rows. This is good as changes may have been made which you don't want overridden. However, you can also cache the feed.
    
    sheet = ExampleUserSheet(cache_feed=True)
    users = User.objects.all()
    for u in users:
       row = sheet.get(u)
       row.save(refresh=True)

By setting ``refresh=True`` on the row save, despite the fact cache_feed is set before sending any changes to the spreadsheet it will forcely get the latest from the spreadsheet. There is a possibility that you miss updates that should happen, however your won't accidentaly overwrite good data and you'll  massively improve performance.

If there are corruptions in the sheet causing there to be multiple entries per pk (if say they were manually entered by a human).

    try:
        sheet.get(u)
    except MutipleEntriesExist:
        sheet.deduplicate()

Deduplicate will unintelligently remove all but the first entries it finds. This can be overridden by smarter functions which look at a last_updated column or the equivelent value stored on the google entry which is returned. The current function returns a list of pks which were removed.


###Experimental feeding back to database:

This is experimental. Obviously very dangerous & probably massively error prone. However, if you want to live dangerously, here's how...
    
    def convert_back(self):
        # payload is User with correct pk, could defined model & lookup?
        for k, v in self.incoming().items():
            # inreality will need some cohercing into correct keys & types
            setattr(self.payload, k, v)
        self.payload.save()
    
    # another example
    def convert_back(self):
        User.objects.filter(pk=self.pk).update(**self.incoming())

Define this on the row and simply call it after doing a 


##TODO
Need to add logging. However want to add in the new django logging but don't want to spoil it for the rest. Then also tossing up setting up leveling.

