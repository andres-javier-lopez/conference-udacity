# coding: utf-8

from google.appengine.api import memcache
from google.appengine.ext import ndb

import models


MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED_SPEAKER"


def cacheSpeaker(request):
    """Save featured Speaker in memcache. Used on a task queue."""
    # get the conference and speaker keys for the recently added session
    c_key = request.get('conferenceKey')
    sp_key = request.get('speakerKey')

    conference = ndb.Key(urlsafe=c_key).get()
    speaker = ndb.Key(urlsafe=sp_key).get()

    # get all the sessions for the conference
    sessions = Session.query(ancestor=conference.key)

    # get the total number of sessions of the current speaker in the conference
    total_sessions = 0
    sessions_names = []
    for session in sessions:
        if session.speakerId == sp_key:
            total_sessions += 1
            session_names.append(session.name)

    # if the total number of sessions is greater than 1, the speaker is
    # selected as the featured speaker
    if total_sessions > 1:
        feature = 'Featured Speaker on %s conference: %s on sessions %s' % (
            conference.name, speaker.name, ''.join(session_names, ', ')
        )
        memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, feature)
    else:
        feature = ''

    return feature
