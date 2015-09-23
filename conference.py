#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.ext import ndb

from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForms
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionQueryForm
from models import Speaker

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

import process.conferences
import process.sessions
import process.profiles

from process.speakers import MEMCACHE_FEATURED_SPEAKER_KEY
from process.announcements import MEMCACHE_ANNOUNCEMENTS_KEY


EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1)
)

SESSION_QUERY_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2)
)

SESSION_SPEAKER_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1)
)

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

SESSION_DATE_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    date=messages.StringField(1)
)

SESSION_DURATION_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    start_duration=messages.IntegerField(1),
    end_duration=messages.IntegerField(2)
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID,
                        ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return process.conferences.createConferenceObject(request)

    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return process.conferences.updateConferenceObject(request)

    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException((
                'No conference found with key: %s'
            )% request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return process.conferences.copyConferenceToForm(
            conf, getattr(prof, 'displayName')
        )

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[
                process.conferences.copyConferenceToForm(
                    conf, getattr(prof, 'displayName')
                ) for conf in confs
            ]
        )

    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = process.conferences.getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organizers = [
            (ndb.Key(Profile, conf.organizerUserId)) for conf in conferences
        ]
        profiles = ndb.get_multi(organizers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[
                process.conferences.copyConferenceToForm(
                    conf, names[conf.organizerUserId]
                ) for conf in conferences
            ]
        )

# - - - Session objects - - - - - - - - - - - - - - - - - - -

    @endpoints.method(SESSION_POST_REQUEST, SessionForm,
                      path='conference/{websafeConferenceKey}/createSession',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """Create a new session in selected conference."""
        return process.sessions.createSessionObject(request)

    @endpoints.method(CONF_GET_REQUEST, SessionForms,
                      path='conference/{websafeConferenceKey}/sessions',
                      http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """List all the sessions on the selected conference."""
        c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        if not c_key.get():
            raise endpoints.NotFoundException(
                (
                    'No conference found with key: %s'
                ) % request.websafeConferenceKey
            )
        sessions = Session.query(ancestor=c_key)
        sessions = sessions.order(Session.startTime)
        return SessionForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

    @endpoints.method(
        SESSION_QUERY_REQUEST, SessionForms,
        path='conference/{websafeConferenceKey}/sessions/{typeOfSession}',
        http_method='GET', name='getConferenceSessionsByType'
    )
    def getConferenceSessionsByType(self, request):
        """List all the sessions of the selected Type."""
        c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        if not c_key.get():
            raise endpoints.NotFoundException(
                (
                    'No conference found with key: %s'
                ) % request.websafeConferenceKey
            )
        sessions = Session.query(ancestor=c_key)
        sessions = sessions.filter(
            Session.typeOfSession == request.typeOfSession
        )
        sessions = sessions.order(Session.startTime)
        return SessionForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

    @endpoints.method(SESSION_SPEAKER_REQUEST, SessionForms,
                      path='conference/speaker/{speaker}',
                      http_method='GET', name='getConferenceBySpeaker')
    def getSessionsBySpeaker(self, request):
        """List of the sessions by the selected Speaker."""
        speaker = Speaker.query(Speaker.name == request.speaker).get()
        if not speaker:
            raise endpoints.NotFoundException(
                'Speaker %s is not registered' % request.speaker
            )

        sessions = Session.query(Session.speakerId == speaker.key.urlsafe())
        sessions = sessions.order(Session.startTime)
        return SessionForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

    @endpoints.method(SESSION_DATE_REQUEST, SessionForms,
                      path='conference/sessions/date',
                      http_method='GET', name='getSessionsByDate')
    def getSessionsByDate(self, request):
        """List of sessions on the selected date."""
        sessions = Session.query()
        sessions = sessions.filter(
            Session.date == datetime.strptime(
                request.date[:10], "%Y-%m-%d"
            ).date()
        )
        sessions.order(Session.startTime)
        return SessionsForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

    @endpoints.method(SESSION_DURATION_REQUET, SessionForms,
                      path='conference/sessions/duration',
                      http_method='GET', name='getSessionsByDuration')
    def getSessionsByDuration(self, request):
        """List of sessions within the specified duration."""
        sessions = Session.query()
        sessions = sessions.filter(
            Session.duration >= request.start_duration
        )
        sessions = sessions.filter(
            Session.duration <= request.end_duration
        )
        sessions = sessions.order(Session.duration)
        sessions = sessions.order(Session.startTime)
        return SessionForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

    @endpoints.method(SessionQueryForm, SessionForms,
                      path='conference/sessions/query',
                      http_method='GET', name='querySessions')
    def querySessions(self, request):
        """Query sessions with user provided filters"""
        sessions = process.sessions.getQuery(request)
        return SessionForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

# - - - Featured Speaker - - - - - - - - - - - - - - - - - - -

    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/featured_speaker/get',
            http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return Featured Speaker from memcache."""
        return StringMessage(
            data=memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY) or ""
        )

# - - - Wishlist - - - - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(SESSION_GET_REQUEST, BooleanMessage,
                      path='addSessionToWishlist/{websafeSessionKey}',
                      http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        prof = process.profiles.getProfileFromUser()

        session = ndb.Key(urlsafe=request.websafeSessionKey).get()
        if not session:
            raise endpoints.NotFoundException(
                'Session Not Found'
            )

        prof.sessionsWishlist.append(request.websafeSessionKey)
        prof.put()
        return BooleanMessage(data=True)

    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path='wishlist', http_method='GET',
                      name='getSessionsWishlist')
    def getSessionsInWishlist(self, request):
        prof = process.profiles.getProfileFromUser()
        sess_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.sessionsWishlist]
        sessions = ndb.get_multi(sess_keys)
        return SessionForms(
            items=[
                process.sessions.copySessionToForm(sess) for sess in sessions
            ]
        )

# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return process.profiles.doProfile()

    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return process.profiles.doProfile(request)

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(
            data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or ""
        )

# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = process.profiles.getProfileFromUser() # get user Profile
        conf_keys = [
            ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend
        ]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [
            ndb.Key(Profile, conf.organizerUserId) for conf in conferences
        ]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[process.conferences.copyConferenceToForm(
                conf, names[conf.organizerUserId]
            ) for conf in conferences]
        )

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return process.conferences.conferenceRegistration(request)

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return process.conferences.conferenceRegistration(request, reg=False)

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='filterPlayground',
            http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
        """Filter Playground"""
        q = Conference.query()
        # field = "city"
        # operator = "="
        # value = "London"
        # f = ndb.query.FilterNode(field, operator, value)
        # q = q.filter(f)
        q = q.filter(Conference.city == "London")
        q = q.filter(Conference.topics == "Medical Innovations")
        q = q.filter(Conference.month == 6)

        return ConferenceForms(
            items=[
                process.conferences.copyConferenceToForm(conf,
                                                         "") for conf in q
            ]
        )


api = endpoints.api_server([ConferenceApi]) # register API
