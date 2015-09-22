# coding: utf-8

import endpoints
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import models
import utils


def cacheSpeaker():
    speakers = models.Speaker.query()
    featured_speaker = ''
    max_sessions = 0
    for speaker in speakers:
        total_sessions = models.Session.query(
            models.Session.speakerId == speaker.key.urlsafe()
        ).count()
        if total_sessions > max_sessions:
            max_sessions = total_sessions
            featured_speaker = speaker.name

    feature = 'Featured Speaker: %s' % featured_speaker
    memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, feature)

    return feature
