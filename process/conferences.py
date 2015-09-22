# coding: utf-8

from datetime import datetime

import endpoints
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import models
import process.profiles
import utils


DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"]
}


def copyConferenceToForm(conf, displayName):
    """Copy relevant fields from Conference to ConferenceForm."""
    cf = models.ConferenceForm()
    for field in cf.all_fields():
        if hasattr(conf, field.name):
            # convert Date to date string; just copy others
            if field.name.endswith('Date'):
                setattr(cf, field.name, str(getattr(conf, field.name)))
            else:
                setattr(cf, field.name, getattr(conf, field.name))
        elif field.name == "websafeKey":
            setattr(cf, field.name, conf.key.urlsafe())
    if displayName:
        setattr(cf, 'organizerDisplayName', displayName)
    cf.check_initialized()
    return cf


def createConferenceObject(request):
    """Create or update Conference object, returning ConferenceForm/request."""
    # preload necessary data items
    user = endpoints.get_current_user()
    if not user:
        raise endpoints.UnauthorizedException('Authorization required')
    user_id = utils.getUserId(user)

    if not request.name:
        raise endpoints.BadRequestException("Conference 'name' field required")

    # copy ConferenceForm/ProtoRPC Message into dict
    data = {}
    for field in request.all_fields():
        data[field.name] = getattr(request, field.name)
    del data['websafeKey']
    del data['organizerDisplayName']

    # add default values for those missing (both data model & outbound Message)
    for df in DEFAULTS:
        if data[df] in (None, []):
            data[df] = DEFAULTS[df]
            setattr(request, df, DEFAULTS[df])

    # convert dates from strings to Date objects; set month based on start_date
    if data['startDate']:
        data['startDate'] = datetime.strptime(
            data['startDate'][:10], "%Y-%m-%d"
        ).date()
        data['month'] = data['startDate'].month
    else:
        data['month'] = 0
    if data['endDate']:
        data['endDate'] = datetime.strptime(
            data['endDate'][:10], "%Y-%m-%d"
        ).date()

    # set seatsAvailable to be same as maxAttendees on creation
    if data["maxAttendees"] > 0:
        data["seatsAvailable"] = data["maxAttendees"]
    # generate Profile Key based on user ID and Conference
    # ID based on Profile key get Conference key from ID
    p_key = ndb.Key(models.Profile, user_id)
    c_id = models.Conference.allocate_ids(size=1, parent=p_key)[0]
    c_key = ndb.Key(models.Conference, c_id, parent=p_key)
    data['key'] = c_key
    data['organizerUserId'] = request.organizerUserId = user_id

    # create Conference, send email to organizer confirming
    # creation of Conference & return (modified) ConferenceForm
    models.Conference(**data).put()
    taskqueue.add(params={'email': user.email(),
        'conferenceInfo': repr(request)},
        url='/tasks/send_confirmation_email'
    )
    return request


@ndb.transactional()
def updateConferenceObject(request):
    user = endpoints.get_current_user()
    if not user:
        raise endpoints.UnauthorizedException('Authorization required')
    user_id = utils.getUserId(user)

    # copy ConferenceForm/ProtoRPC Message into dict
    data = {}
    for field in request.all_fields():
        data[field.name] = getattr(request, field.name)

    # update existing conference
    conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
    # check that conference exists
    if not conf:
        raise endpoints.NotFoundException(
            'No conference found with key: %s' % request.websafeConferenceKey)

    # check that user is owner
    if user_id != conf.organizerUserId:
        raise endpoints.ForbiddenException(
            'Only the owner can update the conference.')

    # Not getting all the fields, so don't create a new object; just
    # copy relevant fields from ConferenceForm to Conference object
    for field in request.all_fields():
        data = getattr(request, field.name)
        # only copy fields where we get data
        if data not in (None, []):
            # special handling for dates (convert string to Date)
            if field.name in ('startDate', 'endDate'):
                data = datetime.strptime(data, "%Y-%m-%d").date()
                if field.name == 'startDate':
                    conf.month = data.month
            # write to Conference object
            setattr(conf, field.name, data)
    conf.put()
    prof = ndb.Key(models.Profile, user_id).get()
    return copyConferenceToForm(conf, getattr(prof, 'displayName'))


def getQuery(request):
    """Return formatted query for conferences."""
    return utils.getQuery(request, models.Conference)


@ndb.transactional(xg=True)
def conferenceRegistration(request, reg=True):
    """Register or unregister user for selected conference."""
    retval = None
    prof = process.profiles.getProfileFromUser() # get user Profile

    # check if conf exists given websafeConfKey
    # get conference; check that it exists
    wsck = request.websafeConferenceKey
    conf = ndb.Key(urlsafe=wsck).get()
    if not conf:
        raise endpoints.NotFoundException(
            'No conference found with key: %s' % wsck)

    # register
    if reg:
        # check if user already registered otherwise add
        if wsck in prof.conferenceKeysToAttend:
            raise models.ConflictException(
                "You have already registered for this conference")

        # check if seats avail
        if conf.seatsAvailable <= 0:
            raise models.ConflictException(
                "There are no seats available.")

        # register user, take away one seat
        prof.conferenceKeysToAttend.append(wsck)
        conf.seatsAvailable -= 1
        retval = True

    # unregister
    else:
        # check if user already registered
        if wsck in prof.conferenceKeysToAttend:

            # unregister user, add back one seat
            prof.conferenceKeysToAttend.remove(wsck)
            conf.seatsAvailable += 1
            retval = True
        else:
            retval = False

    # write things back to the datastore & return
    prof.put()
    conf.put()
    return models.BooleanMessage(data=retval)
