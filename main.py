"""`main` is the top level module for your Flask application."""

# Import the Flask Framework
from flask import Flask
from flask import render_template
app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

import logging

# Google APIs
from google.appengine.api import users
from google.appengine.ext import ndb

class SantaPerson(ndb.Model):
    """ Describes a partipciant in the Secret Santa """
    email = ndb.StringProperty()
    name = ndb.StringProperty()
    user = ndb.UserProperty()
    prohibitedEmails = ndb.TextProperty()


class SantaGroup(ndb.Model):
    """ Models a group of secret santa participants """
    name = ndb.StringProperty()
    emails = ndb.StringProperty(repeated=True)

peopleKey = ndb.Key("People", "people")
groupsKey = ndb.Key("Groups", "groups")

currentUser = users.get_current_user()

@app.route('/')
def hello():
    """Return a friendly HTTP greeting."""

    return render_template('index.html', users=users)

@app.route('/admin/list')
def list():
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
    return render_template('list.html', users=users, listObj=structure)

@app.route('/admin/initialize')
def initialize():
    logging.info("Initializing database...")    
    jcj = SantaPerson(parent=peopleKey,  email="james.jc.jones@gmail.com", name="J.C. Jones", prohibitedEmails="kpiburnjones@gmail.com")
    kpj = SantaPerson(parent=peopleKey,  email="kpiburnjones@gmail.com", name="Katie Jones", prohibitedEmails="james.jc.jones@gmail.com")

    jcj.put()
    kpj.put()

    csc = SantaGroup(parent=groupsKey, name="CSC Secret Santa", emails=[jcj.email, kpj.email])
    csc.put()

    return render_template('index.html', users=users)

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404
