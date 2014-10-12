"""`main` is the top level module for your Flask application."""

# Import the Flask Framework
from flask import Flask
from flask import render_template, redirect, url_for, request, abort
app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

import logging
import random
import string
import datetime

# Google APIs
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import mail

class SantaPerson(ndb.Model):
    """ Describes a partipciant in the Secret Santa """
    email = ndb.StringProperty()
    name = ndb.StringProperty()
    createDate = ndb.DateTimeProperty(auto_now_add=True)
    user = ndb.UserProperty()
    prohibitedEmails = ndb.TextProperty()

class SantaPairing(ndb.Model):
    """ Represents a pair of partipciants in a Secret Santa run. """    
    source = ndb.StringProperty()
    target = ndb.StringProperty()
    verifyTime = ndb.DateTimeProperty()
    key = ndb.StringProperty()

    def isVerified(self):
        return self.verifyTime is not None

    def verify(self):
        self.verifyTime = datetime.datetime.now()

class SantaGroup(ndb.Model):
    """ Models a group of secret santa participants """
    name = ndb.StringProperty()
    registering = ndb.BooleanProperty()
    createDate = ndb.DateTimeProperty(auto_now_add=True)
    runDate = ndb.DateTimeProperty()
    pairs = ndb.KeyProperty(kind=SantaPairing, repeated=True)

class SantaRegistration(ndb.Model):
    """ Mapping, registering a Person for a Group """
    person = ndb.KeyProperty(kind=SantaPerson)
    group = ndb.KeyProperty(kind=SantaGroup)
    createDate = ndb.DateTimeProperty(auto_now_add=True)
    completionDate = ndb.DateTimeProperty()
    prohibitedPeople = ndb.KeyProperty(kind=SantaPerson, repeated=True)
    shoppingAdvice = ndb.BlobProperty()

# Top level keys for the datastore
peopleKey = ndb.Key("People", "people")
groupsKey = ndb.Key("Groups", "groups")

def getSantaPersonForEmail(email=None):
    return SantaPerson.query(SantaPerson.email == email).get()

def getCurrentUserRecord():
    if users.get_current_user() and users.get_current_user().email():
        return getSantaPersonForEmail(email=users.get_current_user().email())
    return None

@app.route('/')
def mainPage():
    """Return a friendly HTTP greeting."""

    record = getCurrentUserRecord()

    memberGroups = []
    logging.warn("record: %s", str(record) )
    if record:
        # Get all santa groups the current user is in
        for reg in SantaRegistration.query(SantaRegistration.person == record.key):
            group = reg.group.get()
            memberGroups.append({"group":group, "pair":None})
            logging.warn("Group: %s %s", str(group), reg )

    return render_template('index.html', users=users, userRecord=record, memberGroups=memberGroups)

@app.route('/test')
def usefulTestMethod():


    
    return render_template('index.html', users=users, userRecord=getCurrentUserRecord(), alertMessage="n")


    # santa_pair.put()

def email_send(sourceUser=None, targetUser=None, pairSecret=None):
    message = mail.EmailMessage(sender="The Santabot of Win <santa@secretsantabotwin.appspot.com>")
    message.subject = "{sourceName}'s Secret Santa Result".format(sourceName=sourceUser.name)
    message.to = "{sourceName} <{sourceEmail}>".format(sourceName=sourceUser.name, sourceEmail=sourceUser.email)
    message.body = """
    Dear {sourceName}:

    You are the Secret Santa for {targetName}. You aren't done yet! You must acknowledge by clicking this link:
    {mainPage} .

    Please DO NOT LOSE THIS EMAIL. There is NO EASILY ACCESSIBLE RECORD of whom you picked... so, don't forget! 
    J.C. doesn't want to have to potentially blow the surprise to himself by having look this up! While the rest 
    of you revel in determining the whole web this wacky algorithm determines, he dwells in the land of magic 
    where ANYTHING CAN HAPPEN. LA LA LA LA (FA LA LA)

    The SantaBot
    """.format(targetName=targetUser.name, sourceName=sourceUser.name, mainPage=url_for('email_acknowledge', key=pairSecret, _external=True))

    message.send()

    logging.info(message.body)

@app.route('/group/<groupName>')
def view_group(groupName):
    grpObj = SantaGroup.query(SantaGroup.name==groupName).get()
    if grpObj:

        target = None
        others = []
        joined = True

        return render_template('groupView.html', users=users, userRecord=getCurrentUserRecord(), group=grpObj, joined=joined, target=target, others=others)
    abort(404)

@app.route('/group/<groupName>', methods='POST')
def register_group(groupName):
    pass

@app.route("/email/acknowledge/<key>")
def email_acknowledge(key):
    found = None
    successful = False

    for run in SantaRun.query():
        logging.info("Run is {}".format(run))
        for pair in run.pairs:
            logging.info("   Pair is {}".format(pair))
            if key == pair.key:
                found = pair
                break

        if found:
            if not found.isVerified():
                successful = True
                found.verify()
                run.put()
            break

    logging.info("Found: {} {}".format(found, key))
    
    if successful:
        return render_template('index.html', users=users, userRecord=getCurrentUserRecord(), alertMessage="Thanks for verifying!")
    else:
        return render_template('index.html', users=users, userRecord=getCurrentUserRecord(), alertMessage="Yup, you already confirmed.")

@app.route('/admin/listGroups')
def admin_list():
    structure=[]

    for sg in SantaGroup.query():
        group = {}

        group["name"] = sg.name
        group["people"] = []

        for email in sg.emails:
            person = SantaPerson.query(SantaPerson.email == email).get()

            group["people"].append(person)

        structure.append(group)

    logging.info("Structure: {}".format(structure))
    return render_template('listGroups.html', users=users, listObj=structure)

@app.route('/admin/group/new/<groupName>')
def admin_new_group(groupName):
    grpObj = SantaGroup(name=groupName, registering=True)
    grpObj.put()
    return redirect(url_for('view_group', groupName=groupName))

@app.route('/admin/initialize')
def admin_initialize():
    logging.info("Initializing database...")    
    # jcj = SantaPerson(parent=peopleKey, email="james.jc.jones@gmail.com", name="J.C. Jones", prohibitedEmails="kpiburnjones@gmail.com")
    # kpj = SantaPerson(parent=peopleKey, email="kpiburnjones@gmail.com", name="Katie Jones", prohibitedEmails="james.jc.jones@gmail.com")
    # ccj = SantaPerson(parent=peopleKey, email="wakosama@gmail.com", name="Chris Jones", prohibitedEmails="amyalexanderjones@gmail.com")
    # aaj = SantaPerson(parent=peopleKey, email="amyalexanderjones@gmail.com", name="Amy Jones", prohibitedEmails="wakosama@gmail.com")

    jcj = SantaPerson(parent=peopleKey, email="pug+jcj@pugsplace.net", name="J.C. Jones", prohibitedEmails="pug+kpj@pugsplace.net;pug+ccj@pugsplace.net")
    kpj = SantaPerson(parent=peopleKey, email="pug+kpj@pugsplace.net", name="Katie Jones", prohibitedEmails="pug+jcj@pugsplace.net")
    ccj = SantaPerson(parent=peopleKey, email="pug+ccj@pugsplace.net", name="Chris Jones", prohibitedEmails="pug+aaj@pugsplace.net")
    aaj = SantaPerson(parent=peopleKey, email="pug+aaj@pugsplace.net", name="Amy Jones", prohibitedEmails="pug+ccj@pugsplace.net")


    jcj.put()
    kpj.put()
    ccj.put()
    aaj.put()

    csc = SantaGroup(parent=groupsKey, name="CSC Secret Santa", emails=[jcj.email, kpj.email])
    csc.put()

    jones = SantaGroup(parent=groupsKey, name="Jones Family Secret Santa", emails=[jcj.email, kpj.email, ccj.email, aaj.email])
    jones.put()

    return render_template('index.html', users=users, alertMessage="Initialized Database")

@app.route('/admin/run/<groupName>')
def admin_run(groupName):
    group = SantaGroup.query(SantaGroup.name==groupName).get()

    logging.info("Group is {}".format(group))

    sources = []
    targets = None

    for email in group.emails:
        person = SantaPerson.query(SantaPerson.email == email).get()
        sources.append(person)

    logging.info("Got people: {}".format(sources))

    stillTrying = True
    tryNumber = 0

    while stillTrying and tryNumber < 99:
        tryNumber = tryNumber+1
        targets = list(sources)
        random.shuffle(targets)

        # Assume we're done
        stillTrying = False

        for i in range(len(sources)):
            logging.info("{} == {}".format(sources[i].email, targets[i].email))

            # Don't assign to self
            if sources[i].email == targets[i].email:
                logging.info("Failed self")
                stillTrying = True
                break
            # Don't assign to prohibited person
            if targets[i].email in sources[i].prohibitedEmails.split(';'):
                logging.info("Failed right prohibs left")
                stillTrying = True
                break

    runObj = SantaRun(parent=runsKey, group=group.key)
    runObj.put()

    keyField = string.lowercase+string.digits
    
    for i in range(len(sources)):
        logging.info("{} ==> {}".format(sources[i].email, targets[i].email))

        keyString = ''.join(random.sample(keyField, 32))        

        santa_pair = SantaPairing(parent=runObj.key, source=sources[i].email, target=targets[i].email, key=keyString)
        santa_pair.put()

    return redirect(url_for('admin_list_run_details', runId=runObj.key.urlsafe()))

@app.route('/admin/listRunDetails/<runId>', methods=['POST'])
def admin_list_email_run_messages(runId):
    runObj = ndb.Key(urlsafe=runId).get()
    logging.info("Run ID: {} run {}".format(runId, runObj))
    alertMessage = None

    for pair in SantaPairing.query(ancestor=runObj.key):

        logging.info("PAIR: " + str(pair))
        source = getSantaPersonForEmail(pair.source)
        target = getSantaPersonForEmail(pair.target)

        email_send(sourceUser=source, targetUser=target, pairSecret=pair.key)
    return ""

@app.route('/admin/listRunDetails/<runId>')
def admin_list_run_details(runId):
    runObj = ndb.Key(urlsafe=runId).get()
    
    groupObj = runObj.group.get()
    pairs = SantaPairing.query(ancestor=runObj.key)

    return render_template('santaRunDetails.html', users=users, runObj=runObj, pairsList=pairs, groupObj=groupObj)

@app.route('/admin/listRuns/<groupName>')
def admin_list_runs(groupName):
    groupObj = SantaGroup.query(SantaGroup.name==groupName).get()

    logging.info("groupObj Obj: %s", groupObj)

    runList = SantaRun.query(SantaRun.group==groupObj.key).order(-SantaRun.date)

    logging.info("runList Obj: %s", runList)

    return render_template('santaRunList.html', users=users, group=groupObj, runs=runList)


@app.errorhandler(404)
def error_404(e):
    """Return a custom 404 error."""
    return render_template('404.html', users=users)
