"""`main` is the top level module for your Flask application."""

# Import the Flask Framework
from flask import Flask
from flask import render_template, redirect, url_for, request, abort, flash
app = Flask(__name__)
app.secret_key = 'squirrel'
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

class SantaPairing(ndb.Model):
    """ Represents a pair of partipciants in a Secret Santa run. """    
    source = ndb.StringProperty()
    target = ndb.StringProperty()
    verifyTime = ndb.DateTimeProperty()
    secret = ndb.StringProperty()

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
    if not record and users.get_current_user():
        user = users.get_current_user()
        record = SantaPerson(user=user, email=user.email(), name=user.nickname())
        record.put()

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

    flash("OH NO")

    
    return render_template('index.html', users=users, userRecord=getCurrentUserRecord())


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
    userObj = getCurrentUserRecord()

    # if userObj is None:        
    #     return redirect(users.create_login_url(url_for('view_group', groupName=groupName)))

    grpObj = SantaGroup.query(SantaGroup.name==groupName).get()
    if grpObj:

        target = None
        others = []
        joined = False

        for reg in SantaRegistration.query(SantaRegistration.group == grpObj.key):
            person = reg.person.get()
            logging.info("Checking on %s", reg)
            if person is not getCurrentUserRecord():
                others.append(person)
            else:
                joined = True
                logging.info("Found myself %s", person)

        return render_template('groupView.html', users=users, userRecord=getCurrentUserRecord(), group=grpObj, joined=joined, target=target, others=others)
    abort(404)

@app.route('/group/<groupName>/join')
def join_group(groupName):
    grpObj = SantaGroup.query(SantaGroup.name==groupName).get()
    userObj = getCurrentUserRecord()

    if userObj is None:        
        return redirect(users.create_login_url(url_for('view_group', groupName=groupName)))

    # Dedupe
    if SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key).get():
        return redirect(url_for('view_group', groupName=groupName))        

    reg = SantaRegistration(group = grpObj.key, person = userObj.key)    
    reg.put()

    return redirect(url_for('view_group', groupName=groupName))

@app.route('/group/<groupName>/ready', methods=['POST'])
def ready_group(groupName):
    grpObj = SantaGroup.query(SantaGroup.name==groupName).get()
    userObj = getCurrentUserRecord()

    logging.info("oh %s", request.form)
    logging.info("MSG %s", request.form['message'])

    if "unchecked0" in request.form:
        logging.info("CHK0 %s", request.form['unchecked0'])
    if "unchecked1" in request.form:
        logging.info("CHK1 %s", request.form['unchecked1'])

    reg = SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key).get()
    reg.shoppingAdvice = str(request.form['message'])
    reg.completionDate = datetime.datetime.now()
    del reg.prohibitedPeople[:]
    if "unchecked0" in request.form:
        reg.prohibitedPeople.append(ndb.Key(urlsafe=request.form['unchecked0']))
    if "unchecked1" in request.form:
        reg.prohibitedPeople.append(ndb.Key(urlsafe=request.form['unchecked1']))
    reg.put()

    return "OK"


@app.route("/email/acknowledge/<key>")
def email_acknowledge(key):
    found = None
    successful = False

    pair = SantaPairing.query(SantaPairing.secret == key).get()
    pair.verify()
    pair.put()

    logging.info("Found: {} {}".format(pair, key))
    
    if successful:
        flash("Thanks for verifying!")
    else:
        flash("Yup, you already confirmed.")

    return render_template('index.html', users=users, userRecord=getCurrentUserRecord())

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

@app.route('/admin/group/<groupName>/run')
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

        santa_pair = SantaPairing(parent=runObj.key, source=sources[i].email, target=targets[i].email, secret=keyString)
        santa_pair.put()

    return redirect(url_for('admin_list_run_details', runId=runObj.key.urlsafe()))

@app.route('/admin/listRunDetails/<runId>', methods=['POST'])
def admin_list_email_run_messages(runId):
    runObj = ndb.Key(urlsafe=runId).get()
    logging.info("Run ID: {} run {}".format(runId, runObj))

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

@app.route('/admin/group/<groupName>/list')
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
