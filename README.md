App Engine application for the Udacity training course. This application has
extended functionality based on the project 4 requirements.

## Author
   Andrés Javier López <ajavier.lopez@gmail.com>

## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.

## Design Choices
   Process have been moved out from conference.py, leaving only the endpoints
   configuration. This is for a better organization of the code.

   Sessions have been implemented as Session and SessionForm classes in
   models.py. The speaker has been saved on its own entity Speaker, but as the
   moment the only known field for speaker is name. Speakers with the same name
   will be treated as the same, to allow different speakers with the same name
   a better key has to be established, like an speaker id or email. Right now
   speakers are created on session creation when no other speaker with the same
   name exists, and the websafe key is stored on the Session.

   The featured speaker is calculated as the speaker with the higher number of
   sessions. After a session is created a task is queued to verify who is the
   speaker with the highest number of sessions, and is stored on memcache as
   the featured speaker.

   Sessions can be filtered by typeOfSession, that currently is a simple String
   field, or by speaker. When you filter by Speaker a query is made to the
   Speaker kind to see if a speaker with the provided name exists. If the
   speaker exists, is filtered by its webafe key on the Session kind. If it
   doesn't exists an error is returned.

   The wishlist is represented as as multiple field in the Profile entity. The
   websafe keys of the selected sessions are stored on this field.

### Data Models
    Session:
    * name: String property because is of a fixed lenght and needs to be indexed.
    * highlights: String property. At the moment is implemented as different
    keywords separated by commas, but could also be implemented as a multiple
    field.
    * speakerId: String property. Stores the websafe key of the Speaker.
    * duration: Integer property. Stores the lenght of the session in number of
    minutes.
    * typeOfSession: String property. Is stored as a simple word.
    * date: Date property. The date is provided as a String by the frontend and
    then parsed as a datetime element.
    * startTime: Integer property. This is a number for 0 to 2359 that represents
    the time of the day. Hours are represented by the first two digits and
    minutes by the last two digits.

    Speaker:
    * name: String property. Same as the Session name.

## Queries

    Sessions have the following additional queries:

    * Query by date, that allows to filter all the sessions on a particular
    date.

    * Query by duration, allows to filter all the sessions that have a duration
    within the provided parameters.

    * A multipurpose query, similar to the one in conferences. This is specially
    useful to search by name, highlights and type of session.

    As for the proposed query, the reason it will fail is because it contains
    two inequality filters, one for sessions that are NOT workshops and the
    other one for sessions before a specified time.

    To avoid this problem, the query has been refactored as to show only the
    selected types of sessions within the specified hours. The fronted of the
    application should list all the available types of sessions, and the user
    will select only the ones he or she is interested in, avoiding the other
    ones like the workshop. If no types of sessions are selected, all the types
    of sessions will be shown.

    This query has been implemented as the filterQuery endpoint.


[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
