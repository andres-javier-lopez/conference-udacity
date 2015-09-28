# coding: utf-8

from datetime import datetime

import endpoints
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import models
import utils


def copySessionToForm(sess):
    """Copy relevant fields from Session to SessionForm."""
    session = models.SessionForm()
    for field in session.all_fields():
        if hasattr(sess, field.name):
            # convert Date to date string; just copy others
            if field.name == 'date':
                setattr(session, field.name, str(getattr(sess, field.name)))
            else:
                setattr(session, field.name, getattr(sess, field.name))
            # get name of speaker based on its id
            if field.name == 'speakerId':
                s_id = getattr(sess, field.name)
                if s_id:
                    speaker = ndb.Key(urlsafe=s_id).get()
                    if speaker:
                        session.speaker = speaker.name
            session.websafeKey = sess.key.urlsafe()
    session.check_initialized()
    return session

def createSessionObject(request):
    """Create a new Session object. Returns SessionForm/request."""
    # preload necessary data items
    user = endpoints.get_current_user()
    if not user:
        raise endpoints.UnauthorizedException('Authorization required')
    user_id = utils.getUserId(user)

    # update existing conference
    conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
    # check that conference exists
    if not conf:
        raise endpoints.NotFoundException(
            'No conference found with key: %s' % request.websafeConferenceKey)

    # check that user is owner
    if user_id != conf.organizerUserId:
        raise endpoints.ForbiddenException(
            'Only the owner can create a session.')

    if not request.name:
        raise endpoints.BadRequestException("Session 'name' field required")

    # copy SessionForm/ProtoRPC Message into dict
    data = {}
    for field in request.all_fields():
        data[field.name] = getattr(request, field.name)
    del data['websafeConferenceKey']
    del data['websafeKey']

    # convert dates from strings to Date objects
    if data['date']:
        data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()

    # If the request contains a speaker name, first query the database to see if the speaker already exists
    # If not create a new entity
    # Clean up by deleting the speaker name from the data dictionary
    if data['speaker']:
        speaker = models.Speaker.query(
            models.Speaker.name == data['speaker']
        ).get()
        if not speaker:
            sp_id = models.Speaker.allocate_ids(size=1)[0]
            sp_key = ndb.Key(models.Speaker, sp_id)
            models.Speaker(name=data['speaker']).put()
            data['speakerId'] = sp_key.urlsafe()
        else:
            data['speakerId'] = speaker.key.urlsafe()
    del data['speaker']

    c_key = conf.key
    s_id = models.Session.allocate_ids(size=1, parent=c_key)[0]
    s_key = ndb.Key(models.Session, s_id, parent=c_key)
    data['key'] = s_key

    models.Session(**data).put()
    taskqueue.add(params={
            'conferenceKey': c_key.urlsafe(),
            'speakerKey': data['speakerId']
        },
        url='/tasks/set_featured_speaker'
    )
    return copySessionToForm(s_key.get())


def getQuery(request):
    """Return formatted query for sessions."""
    return utils.getQuery(request, models.Session)
