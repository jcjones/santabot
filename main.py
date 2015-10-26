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
import urllib, hashlib

# Google APIs
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import mail

# Santa help
from people_matcher import PeopleMatcher

# Constants
SANTABOT_SEND_FROM = "The Santabot Elfbots <elfbots@secretsantabotwin.appspotmail.com>"

#
# Data models
#
class SantaPerson(ndb.Model):
    """ Describes a partipciant in the Secret Santa """
    email = ndb.StringProperty()
    name = ndb.StringProperty()
    createDate = ndb.DateTimeProperty(auto_now_add=True)
    userId = ndb.StringProperty()

    def getAvatarUrl(this, size=80):
        email = this.email.lower()
        return "http://www.gravatar.com/avatar/" + hashlib.md5(email).hexdigest() + "?s=" + str(size) + "&d=retro"


class SantaPairing(ndb.Model):
    """ Represents a pair of partipciants in a Secret Santa run. """    
    source = ndb.KeyProperty(kind="SantaRegistration")
    target = ndb.KeyProperty(kind="SantaRegistration")

class SantaGroup(ndb.Model):
    """ Models a group of secret santa participants """
    name = ndb.StringProperty()
    ownerId = ndb.StringProperty()
    owner = ndb.KeyProperty(kind=SantaPerson)
    registering = ndb.BooleanProperty()
    createDate = ndb.DateTimeProperty(auto_now_add=True)
    runDate = ndb.DateTimeProperty()
    pairs = ndb.KeyProperty(kind=SantaPairing, repeated=True)
    advice = ndb.StringProperty()

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

def getUserRecord(userid):
    return SantaPerson.query(SantaPerson.userId == userid, ancestor=peopleKey).get()

def createUserProfile(destination):
    user = users.get_current_user()
    if user is None:
        raise Exception("Assertion failure; user is not logged in.")

    name = user.email()
    if user.nickname():
        name = user.nickname()

    record = SantaPerson(parent=peopleKey, userId=user.user_id(), email=user.email(), name=name)
    record.put()
    # TODO: Redirect them to the profile page somehow
    return redirect(url_for('configure_profile', destination=destination))


def send_mail_close_registration(userObj=None, groupObj=None):
    message = mail.EmailMessage(sender=SANTABOT_SEND_FROM)
    message.subject = "Complete Santa Registration for {groupName}".format(name=userObj.name, groupName=groupObj.name)
    message.to = "{name} <{email}>".format(name=userObj.name, email=userObj.email)
    message.body = render_template('email-complete.txt', name=userObj.name, groupName=groupObj.name, groupPage=url_for('view_group', groupId=groupObj.key.urlsafe(), _external=True))
    message.html = render_template('email-complete.html', name=userObj.name, groupName=groupObj.name, groupPage=url_for('view_group', groupId=groupObj.key.urlsafe(), _external=True))
    message.send()

def send_mail_result(sourceUser=None, targetUser=None, groupObj=None, targetReg=None):
    message = mail.EmailMessage(sender=SANTABOT_SEND_FROM)
    message.subject = "Secret Santa Result for {sourceName}".format(sourceName=sourceUser.name)
    message.to = "{sourceName} <{sourceEmail}>".format(sourceName=sourceUser.name, sourceEmail=sourceUser.email)
    message.body = render_template('email-result.txt', targetName=targetUser.name, sourceName=sourceUser.name, shoppingAdvice=targetReg.shoppingAdvice, groupName=groupObj.name, groupPage=url_for('view_group', groupId=groupObj.key.urlsafe(), _external=True))
    message.html = render_template('email-result.html', targetName=targetUser.name, sourceName=sourceUser.name, shoppingAdvice=targetReg.shoppingAdvice, groupName=groupObj.name, groupPage=url_for('view_group', groupId=groupObj.key.urlsafe(), _external=True))
    message.send()


#
# WebApp Endpoints
#

@app.route('/')
def mainPage():
    """Return a friendly HTTP greeting."""

    oldAgeCutoff = datetime.datetime.today() - datetime.timedelta(days=180)

    try:
        userObj = getCurrentUserRecord()

        recentGroups = []
        oldGroups = []

        if userObj:
            # Get all santa groups the current user is in
            for reg in SantaRegistration.query(SantaRegistration.person == userObj.key, ancestor=registrationKey):
                group = reg.group.get()
                groupObj = {"group":group, "pair":None}

                if group.createDate < oldAgeCutoff:
                    oldGroups.append(groupObj)
                else:
                    recentGroups.append(groupObj)

                logging.debug("Group: %s %s", str(group), reg )

        # memberGroups = sorted(memberGroups, reverse=True, key=lambda x: x['group'].createDate)

        return render_template('index.html', users=users, userRecord=userObj,
            recentGroups=recentGroups, oldGroups=oldGroups)
    except(Unregistered):
        return createUserProfile(url_for('mainPage'))

@app.route('/profile')
def configure_profile():
    try:
        userObj = getCurrentUserRecord()
        # logging.info("UserOBJ is {}".format(userObj))
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

@app.route('/group/<groupId>')
def view_group(groupId):
    try:
        userObj = getCurrentUserRecord()
        
        grpObj = ndb.Key(urlsafe=groupId).get()
        if grpObj is None:
            abort(404)

        target = None
        others = []
        members = []
        registrants = []
        myReg = None

        if userObj:
            for reg in SantaRegistration.query(SantaRegistration.group == grpObj.key, ancestor=registrationKey):
                person = reg.person.get()
                members.append(person)
                registrants.append(reg)
                if person != userObj:
                    others.append(person)
                else:
                    myReg = reg

            for pairKey in grpObj.pairs:
                pair = pairKey.get()
                # logging.info("Checking pair %s", pair)
                if pair.source.get().person == userObj.key:
                    # logging.info("Checking against %s", userObj)
                    target = pair.target.get()

        if grpObj.registering:
            # Registration is open
            template = "group-registering.html"
        elif target:
            # The run completed, and they are santa for someone
            template = "group-result.html"
        else:
            # Registration is closed, they need to enter wishlist
            template = "group-complete.html"

        return render_template(template, users=users, userRecord=getCurrentUserRecord(),
            ownerRecord=getUserRecord(grpObj.ownerId), group=grpObj, myReg=myReg, target=target, others=others, members=members,
            registrants=registrants)
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
        logging.debug("MESSAGE BODY: " + message.body)

        logging.info("User {} joined {}".format(userObj.name, grpObj.name))


        reg.put()

        # Tell the user
        flash("Joined group " + grpObj.name, "success")

        return redirect(url_for('view_group', groupId=groupId))
    except(Unregistered):
        return createUserProfile(url_for('join_group', groupId=groupId))

@app.route('/group/<groupId>/advice', methods=['POST'])
def advice_for_group(groupId):
    logging.info("oh %s", request.form)
    groupObj = ndb.Key(urlsafe=groupId).get()
    if groupObj is None:
        abort(404)
    userObj = getCurrentUserRecord()
    if not userObj:
        abort(401)
    if groupObj.ownerId != userObj.userId:
        abort(401)

    groupObj.advice = request.form['value']
    groupObj.put()
    return "Updated"

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

    # logging.info("oh %s", request.form)
    # logging.info("MSG %s", request.form['message'])

    # if "unchecked0" in request.form:
    #     logging.info("CHK0 %s", request.form['unchecked0'])
    # if "unchecked1" in request.form:
    #     logging.info("CHK1 %s", request.form['unchecked1'])

    reg = SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.person == userObj.key, ancestor=registrationKey).get()
    reg.shoppingAdvice = shoppingAdvice
    reg.completionDate = datetime.datetime.now()
    del reg.prohibitedPeople[:]
    if "unchecked0" in request.form:
        reg.prohibitedPeople.append(ndb.Key(urlsafe=request.form['unchecked0']))
    if "unchecked1" in request.form:
        reg.prohibitedPeople.append(ndb.Key(urlsafe=request.form['unchecked1']))
    reg.put()

    # If this was the last registration, the run is ready
    qry = SantaRegistration.query(SantaRegistration.group == grpObj.key, SantaRegistration.completionDate == None , ancestor=registrationKey)

    logging.info("User {} is ready for {} with advice {}".format(userObj.name, grpObj.name, shoppingAdvice))
    
    if not qry.iter().has_next():
        logging.info("It looks like all registrations are done.")

        group_run(grpObj.key.urlsafe())

    return "OK"

@app.route('/group/new', methods=['POST'])
def new_group():
    userObj = getCurrentUserRecord()
    if not userObj:
        return redirect(url_for('mainPage'))

    if "groupName" not in request.form:
        return redirect(url_for('mainPage'))

    groupName = request.form['groupName']
    groupName = groupName.strip(string.whitespace)
    # logging.info("CHK0 %s", groupName)

    if len(groupName) < 5:
        flash("The group name is too short.","error")
        return redirect(url_for('mainPage'))

    group = SantaGroup.query(SantaGroup.name==groupName, ancestor=groupsKey).get()
    if group is None:
        group = SantaGroup(parent=groupsKey, name=groupName, owner=userObj.key, ownerId=userObj.userId, registering=True)
        group.put()

        logging.info("Created group " + groupName)
        flash("Created group " + groupName, "success")

    return join_group(group.key.urlsafe())

    # return redirect(url_for('view_group', groupId=group.key.urlsafe()))

@app.route('/group/<groupId>/close')
def close_registration(groupId):
    userObj = getCurrentUserRecord()
    if not userObj:
        return redirect(url_for('mainPage'))

    groupObj = ndb.Key(urlsafe=groupId).get()

    if groupObj.ownerId != userObj.userId:
        abort(401)    

    # Error check
    if groupObj is None:
        abort(404)

    if SantaRegistration.query(SantaRegistration.group == groupObj.key, ancestor=registrationKey).count() < 3:
        flash("You need at least three people to close the group.", "error")
        return redirect(url_for('view_group', groupId=groupId))


    groupObj.registering = False
    groupObj.put()

    for reg in SantaRegistration.query(SantaRegistration.group == groupObj.key, ancestor=registrationKey):
        userObj = reg.person.get()
        # Send email
        send_mail_close_registration(userObj=userObj, groupObj=groupObj)

    flash("Registration is now complete for {}".format(groupObj.name), "info")
    logging.info("User {} closed registration for {}".format(userObj.name, groupObj.name))


    return redirect(url_for('view_group', groupId=groupId))

@app.route('/group/<groupId>/run')
def group_run_owner(groupId):
    userObj = getCurrentUserRecord()
    if not userObj:
        return redirect(url_for('mainPage'))

    groupObj = ndb.Key(urlsafe=groupId).get()

    if groupObj.ownerId != userObj.userId:
        abort(401)
    group_run(groupId)
    return redirect(url_for('view_group', groupId=groupId))

def group_run(groupId):
    group = ndb.Key(urlsafe=groupId).get()
    # Error check
    if group is None:
        abort(404)

    # Don't run if we've already run.
    if group.runDate:
        logging.info("This has already run. {}".format(group.runDate))
        flash("{} has already run.".format(group.name), "info")
        return redirect(url_for('view_group', groupId=groupId))    


    pm = PeopleMatcher()

    for reg in SantaRegistration.query(SantaRegistration.group == group.key, ancestor=registrationKey):
        pm.addPerson(reg.person, prohibited=reg.prohibitedPeople)
        # Don't run if anyone hasn't registered.
        if not reg.completionDate:
            flash("Not everyone has completed signup.", "warning")
            return redirect(url_for('view_group', groupId=groupId))    


    graphSegments = None

    for i in range(2,-1,-1):
        # logging.info("============= %d" % i)
        pm.setHonoredProhibited(i)
        # logging.info(pm)

        graphSegments = pm.execute()
        if graphSegments:
            break

    # At this point we should have the graph
    if graphSegments is None:
        raise Exception("Could not solve", pm)

    # Clear out pairs
    del group.pairs[:]

    for segment in graphSegments:
        sourceReg = SantaRegistration.query(SantaRegistration.person == segment["source"], SantaRegistration.group == group.key, ancestor=registrationKey).get()
        targetReg = SantaRegistration.query(SantaRegistration.person == segment["target"], SantaRegistration.group == group.key, ancestor=registrationKey).get()

        logging.debug("{} ==> {}".format(segment["source"].get().email, segment["target"].get().email))

        santa_pair = SantaPairing(parent=group.key, source=sourceReg.key, target=targetReg.key)
        santa_pair.put()
        group.pairs.append(santa_pair.key)

    group.runDate = datetime.datetime.now()
    group.put()

    for pairKey in group.pairs:
        pair = pairKey.get()

        logging.debug("PAIR: " + str(pair))
        sourceReg = pair.source.get()
        sourceUser = sourceReg.person.get()
        targetReg = pair.target.get()
        targetUser = targetReg.person.get()

        send_mail_result(sourceUser=sourceUser, targetUser=targetUser, groupObj=group, targetReg=targetReg)

    flash("Done! Sent %i emails." % len(group.pairs), "success")    


@app.route('/admin')
def admin_list():
    structure=[]

    groups = SantaGroup.query(ancestor=groupsKey)

    return render_template('admin-list.html', users=users, userGet=getUserRecord, userRecord=getCurrentUserRecord(), groups=groups)

@app.route('/admin/group/<groupId>')
def admin_list_runs(groupId):
    groupObj = ndb.Key(urlsafe=groupId).get()
    if groupObj is None:
        abort(404)

    pairs = SantaPairing.query(ancestor=groupObj.key)
    regs = SantaRegistration.query(SantaRegistration.group == groupObj.key, ancestor=registrationKey)


    # logging.info("groupObj Obj: %s", groupObj)

    return render_template('admin-run-details.html', users=users, userRecord=getCurrentUserRecord(), group=groupObj, pairsList=pairs, regsList=regs)

@app.route('/admin/cron/daily')
def admin_cron_daily():
    countReg = 0
    for group in SantaGroup.query(SantaGroup.registering == False, SantaGroup.runDate == None, ancestor=groupsKey):
        for reg in SantaRegistration.query(SantaRegistration.group == group.key, SantaRegistration.completionDate == None, ancestor=registrationKey):
            logging.info("DAILY: reg {} for {} is not completed".format(group.name, reg.person.get().name))
            userObj = reg.person.get()
            groupObj = reg.group.get()            
            send_mail_close_registration(groupObj=groupObj, userObj=userObj)

            countReg = countReg + 1

    return "OK {}".format(countReg)

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
