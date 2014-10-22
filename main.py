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
    source = ndb.KeyProperty(kind=SantaPerson)
    target = ndb.KeyProperty(kind=SantaPerson)
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
registrationKey = ndb.Key("Registrations", "registrations")

def getSantaPersonForEmail(email=None):
    return SantaPerson.query(SantaPerson.email == email, ancestor=peopleKey).get()

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
        record = SantaPerson(parent=peopleKey, user=user, email=user.email(), name=user.nickname())
        record.put()

    memberGroups = []
    logging.warn("record: %s", str(record) )
    if record:
        # Get all santa groups the current user is in
        for reg in SantaRegistration.query(SantaRegistration.person == record.key, ancestor=registrationKey):
            group = reg.group.get()
            memberGroups.append({"group":group, "pair":None})
            logging.warn("Group: %s %s", str(group), reg )

    return render_template('index.html', users=users, userRecord=record, memberGroups=memberGroups)

@app.route('/test')
def usefulTestMethod():

    flash("OH NO", "error")

    
    return render_template('index.html', users=users, userRecord=getCurrentUserRecord())


    # santa_pair.put()


@app.route('/group/<groupName>')
def view_group(groupName):
    userObj = getCurrentUserRecord()

    # if userObj is None:        
    #     return redirect(users.create_login_url(url_for('view_group', groupName=groupName)))

    grpObj = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
    if grpObj:

        target = None
        others = []
        joined = False

        for reg in SantaRegistration.query(SantaRegistration.group == grpObj.key, ancestor=registrationKey):
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
    grpObj = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
    userObj = getCurrentUserRecord()

    if userObj is None:        
        return redirect(users.create_login_url(url_for('view_group', groupName=groupName)))

    # Dedupe
    if SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key, ancestor=registrationKey).get():
        return redirect(url_for('view_group', groupName=groupName))        

    reg = SantaRegistration(parent=registrationKey, group=grpObj.key, person=userObj.key)
    reg.put()

    return redirect(url_for('view_group', groupName=groupName))

@app.route('/group/<groupName>/ready', methods=['POST'])
def ready_group(groupName):
    grpObj = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
    userObj = getCurrentUserRecord()

    logging.info("oh %s", request.form)
    logging.info("MSG %s", request.form['message'])

    if "unchecked0" in request.form:
        logging.info("CHK0 %s", request.form['unchecked0'])
    if "unchecked1" in request.form:
        logging.info("CHK1 %s", request.form['unchecked1'])

    reg = SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key, ancestor=registrationKey).get()
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

    pair = SantaPairing.query(SantaPairing.secret == key).get()
    if pair:
        if not pair.isVerified():
            pair.verify()
            pair.put()

            logging.info("Found: {} {}".format(pair, key))
    
            flash("Thanks for verifying!", "success")
        else:
            flash("Yup, you already confirmed.", "info")

    else:
        flash("Unknown authentication ID. Please check your link.", "warning")

    return redirect(url_for('mainPage'))

@app.route('/admin')
def admin_list():
    structure=[]

    for sg in SantaGroup.query(ancestor=groupsKey):
        group = {}

        group["group"] = sg
        group["people"] = []

        # for pairKey in sg.pairs:
        #     pair = pairKey.get()

        for reg in SantaRegistration.query(SantaRegistration.group == sg.key, ancestor=registrationKey):
            person = reg.person.get()

            group["people"].append(reg)

        structure.append(group)

    logging.info("Structure: {}".format(structure))
    return render_template('listGroups.html', users=users, listObj=structure)

@app.route('/admin/group/new', methods=['POST'])
def admin_new_group():
    if "groupName" in request.form:
        groupName = request.form['groupName']
        logging.info("CHK0 %s", groupName)

        group = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
        if group is None:
            grpObj = SantaGroup(parent=groupsKey, name=groupName, registering=True)
            grpObj.put()

            logging.info("Created group " + groupName)
            flash("Created group " + groupName, "success")

        return redirect(url_for('view_group', groupName=groupName))

    return redirect(url_for('admin_list'))

@app.route('/admin/group/<groupName>/close')
def admin_close_registration(groupName):
    group = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()

    # Error check
    if group is None:
        abort(404)

    group.registering = False
    group.put()

    flash("Registration is now closed.", "info")

    return redirect(url_for('admin_list'))

@app.route('/admin/group/<groupName>/run')
def admin_run(groupName):
    group = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()

    # Error check
    if group is None:
        abort(404)


    # Don't run if we've already run.
    if group.runDate:
        logging.info("This has already run.")
        flash("This has already run.", "info")
        return redirect(url_for('admin_list'))


    sources = []
    targets = None

    for reg in SantaRegistration.query(SantaRegistration.group == group.key, ancestor=registrationKey):
        sources.append(reg)

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
            logging.info("{} == {}".format(sources[i].person.get().email, targets[i].person.get().email))

            # Don't assign to self
            if sources[i].person.get().email == targets[i].person.get().email:
                logging.info("Failed self")
                stillTrying = True
                break
            # Don't assign to prohibited person
            if targets[i].person in sources[i].prohibitedPeople:
                logging.info("Failed right prohibs left")
                stillTrying = True
                break

   
    # Create our URL-safe key spcace
    keyField = string.lowercase+string.digits
     # Clear out pairs
    del group.pairs[:]

    for i in range(len(sources)):
        logging.info("{} ==> {}".format(sources[i].person.get().email, targets[i].person.get().email))

        keyString = ''.join(random.sample(keyField, 12))        

        santa_pair = SantaPairing(parent=group.key, source=sources[i].person, target=targets[i].person, secret=keyString)
        santa_pair.put()
        group.pairs.append(santa_pair.key)

    group.runDate = datetime.datetime.now()
    group.put()

    for pairKey in group.pairs:
        pair = pairKey.get()

        logging.info("PAIR: " + str(pair))
        sourceUser = pair.source.get()
        targetUser = pair.target.get()

        message = mail.EmailMessage(sender="The Santabot of Win <santa@secretsantabotwin.appspot.com>")
        message.subject = "{sourceName}'s Secret Santa Result".format(sourceName=sourceUser.name)
        message.to = "{sourceName} <{sourceEmail}>".format(sourceName=sourceUser.name, sourceEmail=sourceUser.email)
        message.body = render_template('email-result.txt', targetName=targetUser.name, sourceName=sourceUser.name, ackPage=url_for('email_acknowledge', key=pair.secret, _external=True))
        message.html = render_template('email-result.html', targetName=targetUser.name, sourceName=sourceUser.name, ackPage=url_for('email_acknowledge', key=pair.secret, _external=True))
        message.send()
        logging.info(message.body)

    flash("Done! Sent %i emails." % len(group.pairs), "success")
    return redirect(url_for('admin_list'))


@app.route('/admin/group/<groupName>')
def admin_list_runs(groupName):
    groupObj = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
    if groupObj is None:
        abort(404)

    pairs = SantaPairing.query(ancestor=groupObj.key)

    logging.info("groupObj Obj: %s", groupObj)

    return render_template('santaRunList.html', users=users, group=groupObj, pairsList=pairs)


@app.errorhandler(404)
def error_404(e):
    """Return a custom 404 error."""
    return render_template('404.html', users=users)
