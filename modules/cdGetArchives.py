import time
import urllib.request
import urllib.error
import urllib.parse
import sys
import calendar
import requests
import json
import logging
from .cdGetPubdate import findPubdate
from .cdGetLowest import getLowest, validateDate, getLowestSources

moduleTag = "archives"

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) \
    Gecko/20100101 Firefox/48.0'}


def getMementos(uri):

    uri = uri.replace(' ', '')

    # baseURI = 'http://timetravel.mementoweb.org/timemap/link/'
    # baseURI = 'http://mementoweb.org/timemap/link/'
    # baseURI = 'http://mementoproxy.cs.odu.edu/aggr/timemap/link/1/'
    # OR
    baseURI = 'http://memgator.cs.odu.edu/timemap/json/'
    memento_list = []

    try:
        search_results = urllib.request.urlopen(baseURI + uri)
        the_page = search_results.read().decode('ascii', 'ignore')

        data = json.loads(the_page)

        mementoNames = []
        for item in data["mementos"]["list"]:
            memento = {}

            timestamp = item["datetime"]
            mementoURL = item["uri"]

            epoch = int(calendar.timegm(
                time.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')))
            day_string = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(epoch))

            memento["time"] = day_string

            name = urllib.parse.urlparse(mementoURL.strip())

            memento["name"] = name.netloc
            memento["link"] = mementoURL

            # assumption that first memento is youngest - ON - start
            if(name.netloc not in mementoNames):
                memento_list.append(memento)
                mementoNames.append(name.netloc)

    except urllib.error.URLError:
        pass

    return memento_list


def getRealDate(url, memDate):
    '''Expects epoch date as parameter'''
    try:
        response = requests.get(url, headers=headers)
        page = response.headers
        date = ""

        if "X-Archive-Orig-last-modified" in page:
            date = page["X-Archive-Orig-last-modified"]

        if(date == ""):
            date = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(memDate))
        else:
            epoch = int(calendar.timegm(time.strptime(
                date, '%a, %d %b %Y %H:%M:%S %Z')))
            date = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(epoch))

        return date
    except Exception:
        date = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(memDate))
        return date


def getArchives(url, outputArray, outputArrayIndex, verbose=False, **kwargs):
    '''
    Return dictionary with earliest date, unique archives, or an empty
    dictionary if no mementos
    '''
    try:
        mementos = getMementos(url)

        if(len(mementos) == 0):
            earliest = ""
            outputArray[outputArrayIndex] = earliest
            kwargs['displayArray'][outputArrayIndex] = {}
            logging.debug("Done Archives 0")
            return earliest

        archives = {}
        limitEpoch = int(calendar.timegm(time.strptime(
            "1995-01-01T12:00:00", '%Y-%m-%dT%H:%M:%S')))

        for memento in mementos:

            epoch = int(calendar.timegm(time.strptime(
                memento["time"], '%Y-%m-%dT%H:%M:%S')))

            uri = memento["link"]
            mementoDatetime = getRealDate(uri, epoch)
            mementoDatetimeEpoch = int(calendar.timegm(
                time.strptime(mementoDatetime, '%Y-%m-%dT%H:%M:%S')))

            if(mementoDatetimeEpoch < limitEpoch):
                mementoDatetime = ""

            # find pubdate and make sure it isn't midnight
            mementoPubdate = validateDate(findPubdate(uri))
            # find earliest date between memento datetime and pubdate
            earliest = getLowest(dates=[mementoDatetime, mementoPubdate])

            archives[memento["name"]] = {
                "uri-m": memento["link"],
                "memento-datetime": mementoDatetime,
                "memento-pubdate": mementoPubdate,
                "earliest": earliest}

        earliest = getLowestSources(archives)[0]

        outputArray[outputArrayIndex] = earliest
        kwargs['displayArray'][outputArrayIndex] = archives
        logging.debug("Done Archives 1")
        return archives

    except:
        logging.exception(sys.exc_info())
        earliest = ""
        outputArray[outputArrayIndex] = earliest
        kwargs['displayArray'][outputArrayIndex] = {}
        logging.debug("Done Archives 2")
        return earliest
