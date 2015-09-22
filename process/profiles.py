# coding: utf-8

import endpoints
from google.appengine.ext import ndb

import models
import utils


def copyProfileToForm(prof):
    """Copy relevant fields from Profile to ProfileForm."""
    # copy relevant fields from Profile to ProfileForm
    pf = models.ProfileForm()
    for field in pf.all_fields():
        if hasattr(prof, field.name):
            # convert t-shirt string to Enum; just copy others
            if field.name == 'teeShirtSize':
                setattr(pf, field.name,
                        getattr(models.TeeShirtSize,
                                getattr(prof, field.name)))
            else:
                setattr(pf, field.name, getattr(prof, field.name))
    pf.check_initialized()
    return pf


def getProfileFromUser():
    """Return user Profile from datastore, creating new one if non-existent."""
    # make sure user is authed
    user = endpoints.get_current_user()
    if not user:
        raise endpoints.UnauthorizedException('Authorization required')

    # get Profile from datastore
    user_id = utils.getUserId(user)
    p_key = ndb.Key(models.Profile, user_id)
    profile = p_key.get()
    # create new Profile if not there
    if not profile:
        profile = models.Profile(
            key=p_key,
            displayName=user.nickname(),
            mainEmail=user.email(),
            teeShirtSize=str(models.TeeShirtSize.NOT_SPECIFIED)
        )
        profile.put()

    return profile      # return Profile


def doProfile(save_request=None):
    """Get user Profile and return to user, possibly updating it first."""
    # get user Profile
    prof = getProfileFromUser()

    # if saveProfile(), process user-modifyable fields
    if save_request:
        for field in ('displayName', 'teeShirtSize'):
            if hasattr(save_request, field):
                val = getattr(save_request, field)
                if val:
                    setattr(prof, field, str(val))
                    #if field == 'teeShirtSize':
                    #    setattr(prof, field, str(val).upper())
                    #else:
                    #    setattr(prof, field, val)
                    prof.put()

    # return ProfileForm
    return copyProfileToForm(prof)
