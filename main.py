"""
    SantaBot, because Cyber Santas are the Best Santas
    Copyright (C) 2014 James 'J.C.' Jones

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Import the Flask Framework
from flask import Flask
from flask import render_template, redirect, url_for, request, abort, flash
app = Flask(__name__)
app.secret_key = 'squirrel'

import logging
import random
import string
import datetime

# Google APIs
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import mail

# Constants
SANTABOT_SEND_FROM = "The Santabot Elfbots <elfbots@santabot.co>"

#
# Data models
#
class SantaPerson(ndb.Model):
    """ Describes a partipciant in the Secret Santa """
    email = ndb.StringProperty()
    name = ndb.StringProperty()
    createDate = ndb.DateTimeProperty(auto_now_add=True)
    userId = ndb.StringProperty()

class SantaPairing(ndb.Model):
    """ Represents a pair of partipciants in a Secret Santa run. """    
    source = ndb.KeyProperty(kind="SantaRegistration")
    target = ndb.KeyProperty(kind="SantaRegistration")

class SantaGroup(ndb.Model):
    """ Models a group of secret santa participants """
    name = ndb.StringProperty()
    ownerId = ndb.StringProperty()
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
    viewedDate = ndb.DateTimeProperty()
    prohibitedPeople = ndb.KeyProperty(kind=SantaPerson, repeated=True)
    shoppingAdvice = ndb.BlobProperty()

#
# Top level (ancestor) keys for the datastore
#
peopleKey = ndb.Key("People", "people")
groupsKey = ndb.Key("Groups", "groups")
registrationKey = ndb.Key("Registrations", "registrations")

#
# Convenience Methods
#
def getSantaPersonForEmail(email=None):
    return SantaPerson.query(SantaPerson.email == email, ancestor=peopleKey).get()

class Unregistered(Exception):
    pass

def getCurrentUserRecord():
    record = None
    user = users.get_current_user()

    # Return the record, or none. In which case the caller should catch it.
    if user and user.user_id():
        record = SantaPerson.query(SantaPerson.userId == user.user_id(), ancestor=peopleKey).get()
        if not record:
            raise Unregistered()

    return record

def createUserProfile(destination):
    user = users.get_current_user()
    if user is None:
        raise Exception("Assertion failure; user is not logged in.")

    record = SantaPerson(parent=peopleKey, userId=user.user_id(), email=user.email(), name=user.email())
    record.put()
    # TODO: Redirect them to the profile page somehow
    return redirect(url_for('configure_profile', destination=destination))


#
# WebApp Endpoints
#

@app.route('/')
def mainPage():
    """Return a friendly HTTP greeting."""
    try:
        userObj = getCurrentUserRecord()

        memberGroups = []
        if userObj:
            # Get all santa groups the current user is in
            for reg in SantaRegistration.query(SantaRegistration.person == userObj.key, ancestor=registrationKey):
                group = reg.group.get()
                memberGroups.append({"group":group, "pair":None})
                logging.warn("Group: %s %s", str(group), reg )

        return render_template('index.html', users=users, userRecord=userObj, memberGroups=memberGroups)
    except(Unregistered):
        return createUserProfile(url_for('mainPage'))

@app.route('/profile')
def configure_profile():
    try:
        userObj = getCurrentUserRecord()
        logging.info("UserOBJ is {}".format(userObj))
        destination = request.args.get('destination', '')
        return render_template('profile.html', users=users, userRecord=userObj, destination=destination)
    except(Unregistered):
        return createUserProfile(url_for('configure_profile'))


@app.route('/profile/update', methods=['POST'])
def save_profile():
    try:
        record = getCurrentUserRecord()
        record.name = request.form['userName']
        record.put()

        if request.form['destination']:
            return redirect(request.form['destination'])

        return redirect(url_for('mainPage'))

    except(Unregistered):
        return createUserProfile(url_for('mainPage'))

@app.route('/test')
def usefulTestMethod():

    flash("OH NO", "error")

    
    return render_template('index.html', users=users, userRecord=getCurrentUserRecord())


    # santa_pair.put()


@app.route('/group/<groupId>')
def view_group(groupId):
    try:
        userObj = getCurrentUserRecord()
        
        grpObj = ndb.Key(urlsafe=groupId).get()
        if grpObj is None:
            abort(404)

        target = None
        others = []
        myReg = None

        if userObj:
            for reg in SantaRegistration.query(SantaRegistration.group == grpObj.key, ancestor=registrationKey):
                person = reg.person.get()
                logging.info("Checking on %s", reg)
                if person != userObj:
                    others.append(person)
                else:
                    myReg = reg
                    logging.info("Found myself %s", person)

            for pairKey in grpObj.pairs:
                pair = pairKey.get()
                logging.info("Checking pair %s", pair)
                if pair.source.get().person == userObj.key:
                    logging.info("Checking against %s", userObj)
                    target = pair.target.get()

        return render_template('groupView.html', users=users, userRecord=getCurrentUserRecord(), group=grpObj, myReg=myReg, target=target, others=others)
    except(Unregistered):
        return createUserProfile(url_for('view_group', groupId=groupId))

@app.route('/group/<groupId>/join')
def join_group(groupId):
    try:
        grpObj = ndb.Key(urlsafe=groupId).get()
        if grpObj is None:
            abort(404)

        userObj = getCurrentUserRecord()
        if userObj is None:
            return redirect(users.create_login_url(url_for('join_group', groupId=groupId)))

        # Dedupe
        if SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key, ancestor=registrationKey).get():
            return redirect(url_for('view_group', groupId=grpObj.key.urlsafe()))

        reg = SantaRegistration(parent=registrationKey, group=grpObj.key, person=userObj.key)

        # Send email
        message = mail.EmailMessage(sender=SANTABOT_SEND_FROM)
        message.subject = "Welcome to the Secret Santa group {groupName}".format(name=userObj.name, groupName=grpObj.name)
        message.to = "{name} <{email}>".format(name=userObj.name, email=userObj.email)
        message.body = render_template('email-welcome.txt', name=userObj.name, groupName=grpObj.name, groupPage=url_for('view_group', groupId=groupId, _external=True))
        message.html = render_template('email-welcome.html', name=userObj.name, groupName=grpObj.name, groupPage=url_for('view_group', groupId=groupId, _external=True))
        message.send()
        logging.info("MESSAGE BODY: " + message.body)

        reg.put()

        # Tell the user
        flash("Joined group " + grpObj.name, "success")

        return redirect(url_for('view_group', groupId=groupId))
    except(Unregistered):
        return createUserProfile(url_for('join_group', groupId=groupId))

@app.route('/group/<groupId>/ready', methods=['POST'])
def ready_group(groupId):
    grpObj = ndb.Key(urlsafe=groupId).get()
    if grpObj is None:
        abort(404)
    userObj = getCurrentUserRecord()
    if not userObj:
        raise(401)

    shoppingAdvice = str(request.form['message'])
    if shoppingAdvice is None or len(shoppingAdvice) < 20:
        flash("You need to provide some more detailed shopping advice." ,"error")
        return redirect(url_for('view_group', groupId=groupId))

    logging.info("oh %s", request.form)
    logging.info("MSG %s", request.form['message'])

    if "unchecked0" in request.form:
        logging.info("CHK0 %s", request.form['unchecked0'])
    if "unchecked1" in request.form:
        logging.info("CHK1 %s", request.form['unchecked1'])

    reg = SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key, ancestor=registrationKey).get()
    reg.shoppingAdvice = shoppingAdvice
    reg.completionDate = datetime.datetime.now()
    del reg.prohibitedPeople[:]
    if "unchecked0" in request.form:
        reg.prohibitedPeople.append(ndb.Key(urlsafe=request.form['unchecked0']))
    if "unchecked1" in request.form:
        reg.prohibitedPeople.append(ndb.Key(urlsafe=request.form['unchecked1']))
    reg.put()

    return "OK"

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

    return render_template('listGroups.html', users=users, userRecord=getCurrentUserRecord(), listObj=structure)

@app.route('/admin/group/new', methods=['POST'])
def admin_new_group():
    userObj = getCurrentUserRecord()
    if not userObj:
        return redirect(url_for('mainPage'))

    if "groupName" in request.form:
        groupName = request.form['groupName']
        logging.info("CHK0 %s", groupName)

        group = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
        if group is None:
            group = SantaGroup(parent=groupsKey, name=groupName, ownerId=userObj.userId, registering=True)
            group.put()

            logging.info("Created group " + groupName)
            flash("Created group " + groupName, "success")

        return redirect(url_for('view_group', groupId=group.key.urlsafe()))

    return redirect(url_for('admin_list'))

@app.route('/admin/group/<groupId>/close')
def admin_close_registration(groupId):
    group = ndb.Key(urlsafe=groupId).get()

    # Error check
    if group is None:
        abort(404)

    if SantaRegistration.query(SantaRegistration.group == group.key, ancestor=registrationKey).count() < 2:
        flash("You need at least two people to close the group.", "error")
        return redirect(url_for('admin_list'))

    group.registering = False
    group.put()

    for reg in SantaRegistration.query(SantaRegistration.group == group.key, ancestor=registrationKey):
        userObj = reg.person.get()
        # Send email
        message = mail.EmailMessage(sender=SANTABOT_SEND_FROM)
        message.subject = "Complete Registration for Secret Santa group {groupName}".format(name=userObj.name, groupName=group.name)
        message.to = "{name} <{email}>".format(name=userObj.name, email=userObj.email)
        message.body = render_template('email-complete.txt', name=userObj.name, groupName=group.name, groupPage=url_for('view_group', groupId=group.key.urlsafe(), _external=True))
        message.html = render_template('email-complete.html', name=userObj.name, groupName=group.name, groupPage=url_for('view_group', groupId=group.key.urlsafe(), _external=True))
        message.send()

    flash("Registration is now complete for {}".format(group.name), "info")

    return redirect(url_for('admin_list'))

@app.route('/admin/group/<groupId>/run')
def admin_run(groupId):
    group = ndb.Key(urlsafe=groupId).get()

    # Error check
    if group is None:
        abort(404)


    # Don't run if we've already run.
    if group.runDate:
        logging.info("This has already run.")
        flash("{} has already run.".format(group.name), "info")
        return redirect(url_for('admin_list'))


    sources = []
    targets = None

    for reg in SantaRegistration.query(SantaRegistration.group == group.key, ancestor=registrationKey):
        sources.append(reg)
        if reg.completionDate is None:
            # Don't run if anyone hasn't completed their registration.
            flash("{} has not completed their registration.".format(reg.person.get().name), "error")
            return redirect(url_for('admin_list'))

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

        santa_pair = SantaPairing(parent=group.key, source=sources[i].key, target=targets[i].key)
        santa_pair.put()
        group.pairs.append(santa_pair.key)

    group.runDate = datetime.datetime.now()
    group.put()

    for pairKey in group.pairs:
        pair = pairKey.get()

        logging.info("PAIR: " + str(pair))
        sourceReg = pair.source.get()
        sourceUser = sourceReg.person.get()
        targetReg = pair.target.get()
        targetUser = targetReg.person.get()



        message = mail.EmailMessage(sender=SANTABOT_SEND_FROM)
        message.subject = "Secret Santa Result for {sourceName}".format(sourceName=sourceUser.name)
        message.to = "{sourceName} <{sourceEmail}>".format(sourceName=sourceUser.name, sourceEmail=sourceUser.email)
        message.body = render_template('email-result.txt', targetName=targetUser.name, sourceName=sourceUser.name, shoppingAdvice=targetReg.shoppingAdvice, ackPage=url_for('view_group', groupId=group.key.urlsafe(), _external=True))
        message.html = render_template('email-result.html', targetName=targetUser.name, sourceName=sourceUser.name, shoppingAdvice=targetReg.shoppingAdvice, ackPage=url_for('view_group', groupId=group.key.urlsafe(), _external=True))
        message.send()

    flash("Done! Sent %i emails." % len(group.pairs), "success")
    return redirect(url_for('admin_list'))


@app.route('/admin/group/<groupId>')
def admin_list_runs(groupId):
    groupObj = ndb.Key(urlsafe=groupId).get()
    if groupObj is None:
        abort(404)

    pairs = SantaPairing.query(ancestor=groupObj.key)

    logging.info("groupObj Obj: %s", groupObj)

    return render_template('santaRunList.html', users=users, userRecord=getCurrentUserRecord(), group=groupObj, pairsList=pairs)


@app.errorhandler(404)
def error_404(e):
    userObj = None

    try:
        userObj = getCurrentUserRecord();
    except(Unregistered):
        # Ignore exceptions for the 404.
        pass

    """Return a custom 404 error."""
    return render_template('404.html', users=users, userRecord=userObj)
