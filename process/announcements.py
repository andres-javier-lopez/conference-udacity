# coding: utf-8

import endpoints
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import models
import process.profiles
import utils


MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')


def cacheAnnouncement():
    """Create Announcement & assign to memcache; used by
    memcache cron job & putAnnouncement().
    """
    confs = models.Conference.query(ndb.AND(
        models.Conference.seatsAvailable <= 5,
        models.Conference.seatsAvailable > 0)
    ).fetch(projection=[models.Conference.name])

    if confs:
        # If there are almost sold out conferences,
        # format announcement and set it in memcache
        announcement = ANNOUNCEMENT_TPL % (
            ', '.join(conf.name for conf in confs))
        memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
    else:
        # If there are no sold out conferences,
        # delete the memcache announcements entry
        announcement = ""
        memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

    return announcement
