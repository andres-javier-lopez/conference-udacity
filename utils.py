import json
import os
import time
import uuid

import endpoints
from google.appengine.api import urlfetch
from models import Profile


OPERATORS = {
    'EQ': '=',
    'GT': '>',
    'GTEQ': '>=',
    'LT': '<',
    'LTEQ': '<=',
    'NE': '!='
}

FIELDS = {
    'CITY': 'city',
    'TOPIC': 'topics',
    'MONTH': 'month',
    'MAX_ATTENDEES': 'maxAttendees',
}


def getUserId(user, id_type="email"):
    if id_type == "email":
        return user.email()

    if id_type == "oauth":
        """A workaround implementation for getting userid."""
        auth = os.getenv('HTTP_AUTHORIZATION')
        bearer, token = auth.split()
        token_type = 'id_token'
        if 'OAUTH_USER_ID' in os.environ:
            token_type = 'access_token'
        url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
               % (token_type, token))
        user = {}
        wait = 1
        for i in range(3):
            resp = urlfetch.fetch(url)
            if resp.status_code == 200:
                user = json.loads(resp.content)
                break
            elif resp.status_code == 400 and 'invalid_token' in resp.content:
                url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
                       % ('access_token', token))
            else:
                time.sleep(wait)
                wait = wait + i
        return user.get('user_id', '')

    if id_type == "custom":
        # implement your own user_id creation and getting algorythm
        # this is just a sample that queries datastore for an existing profile
        # and generates an id if profile does not exist for an email
        profile = Conference.query(Conference.mainEmail == user.email())
        if profile:
            return profile.id()
        else:
            return str(uuid.uuid1().get_hex())


def formatFilters(filters):
    """Parse, check validity and format user supplied filters."""
    formatted_filters = []
    inequality_field = None

    for f in filters:
        filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

        try:
            filtr["field"] = FIELDS[filtr["field"]]
            filtr["operator"] = OPERATORS[filtr["operator"]]
        except KeyError:
            raise endpoints.BadRequestException(
                "Filter contains invalid field or operator."
            )

        # Every operation except "=" is an inequality
        if filtr["operator"] != "=":
            # check if inequality operation has been used in previous filters
            # disallow the filter if inequality was performed on a different
            # field before
            # track the field on which the inequality operation is performed
            if inequality_field and inequality_field != filtr["field"]:
                raise endpoints.BadRequestException(
                    "Inequality filter is allowed on only one field."
                )
            else:
                inequality_field = filtr["field"]

        formatted_filters.append(filtr)
    return (inequality_field, formatted_filters)
