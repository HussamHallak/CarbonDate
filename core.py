__author__ = "Neo"
__copyright__ = "Copyleft 2016, United States"

import os
import sys
import datetime
import json
import urllib.parse
import logging
from threading import Thread
from requests.utils import requote_uri
from modules.cdGetLowest import getLowestSources
from collections import OrderedDict


class ModuleManager():
    """docstring for ModuleManager"""

    def __init__(self,):
        self.available = []
        self.modules = []
        self.entryPoints = {}
        for root, dirs, files in os.walk("modules"):
            for f in files:
                # get python codes
                if f.endswith(".py"):
                    # ignore __init__.py and remove extention
                    if f != "__init__.py":
                        modName = os.path.splitext(f)[0]
                        self.modules.append(modName)
            # just look for files, do not dig into sub folders
            break

    def loadModule(self, sysconfig, args, **kwargs):
        utilityLst = sysconfig['SystemUtility']
        fromlist = []
        excludeList = getattr(args, 'e', None)
        includeList = getattr(args, 'm', None)
        op_all = getattr(args, 'all', True)

        for m in self.modules:
            # skip utility script (module will import them automatically)
            if m not in utilityLst:

                if (excludeList is not None and m not in excludeList) or \
                    (includeList is not None and m in includeList) or \
                    op_all or \
                        ((excludeList is None) and (includeList is None)):
                    fromlist.append(m)

        api = __import__('modules', fromlist=fromlist)

        # load selected modules
        for mod in fromlist:
            # remove 'cdGet' prefix
            funcName = "get" + mod[5:]
            modName = mod
            self.entryPoints[modName] = {}
            currentMod = getattr(api, mod)
            try:
                if hasattr(currentMod, "entry"):
                    funcName = getattr(currentMod, 'entry')
                self.entryPoints[modName]["getFunc"] = getattr(
                    currentMod, funcName)
            except Exception as e:
                kwargs['logger'].error("ModuleManager: ", e)
                sys.exit(1)
            if hasattr(currentMod, "moduleTag"):
                self.entryPoints[modName]["displayName"] = getattr(
                    currentMod, 'moduleTag')
            else:
                self.entryPoints[modName]["displayName"] = mod[5:]

    def getAvailableModules(self):
        return self.modules

    def call(self, moduleName, **kwargs):
        if moduleName in self.entryPoints:
            url = kwargs['url']
            outputArray = kwargs['outputArray']
            indexOfOutputArray = kwargs['indexOfOutputArray']
            self.entryPoints[moduleName]['getFunc'](
                url, outputArray,
                indexOfOutputArray,
                kwargs['verbose'],
                displayArray=kwargs['displayArray'])
        else:
            kwargs['logger'].error(
                'ModuleManager: Error : No such module: %s' % moduleName)

    def run(self, args, **kwargs):
        url = args.url
        # handle character accents
        url = requote_uri(url)

        timeout = args.timeout
        threads = []
        resultDict = kwargs['resultDict']
        outputArray = [''] * len(self.entryPoints)
        displayArray = [''] * len(self.entryPoints)
        now0 = datetime.datetime.now()

        parsedUrl = urllib.parse.urlparse(url)
        if(len(parsedUrl.scheme) < 1):
            url = 'http://' + url

        index = 0
        modNames = []
        for mod in self.entryPoints:
            modNames.append(self.entryPoints[mod]["displayName"])
            # note that the comma next to mod cannot be left out
            newThread = Thread(target=self.call, args=(mod,),
                               kwargs={'url': url,
                                       'outputArray': outputArray,
                                       'indexOfOutputArray': index,
                                       'verbose': args.verbose,
                                       'displayArray': displayArray})
            threads.append(newThread)
            index += 1

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout)

        # json dictionary to print
        resultDict["uri"] = url
        resultDict["estimated-creation-date"] = ""
        resultDict["earliest-sources"] = []
        resultDict["sources"] = {}

        for i in range(len(modNames)):
            '''
            if a module returns a dictionary with sources update the main
            dictionary with the sources passed, otherwise assume the module
            returns a single string for the earliest date
            '''
            if type(displayArray[i]) is dict:
                resultDict["sources"].update(displayArray[i])
            else:
                resultDict["sources"][modNames[i]] = {
                    "earliest": displayArray[i]}

        earliest_date, earliest_sources = getLowestSources(
            resultDict["sources"])
        resultDict["earliest-sources"] = earliest_sources
        resultDict["estimated-creation-date"] = earliest_date
        values = OrderedDict(resultDict)
        r = json.dumps(values, sort_keys=False,
                       indent=2, separators=(',', ': '))

        now1 = datetime.datetime.now() - now0

        logging.debug("Runtime in seconds: " + str(now1.seconds))
        # end result
        kwargs['logger'].log(35, r)

        return resultDict


if __name__ == '__main__':
    import argparse

    # init argparse
    parser = argparse.ArgumentParser(
        description='Core module to load services and perform queries')
    modOpGroup = parser.add_mutually_exclusive_group()
    modOpGroup.add_argument('-a', '--all', action="store_true",
                            help='Load all modules (default)', dest='all')
    modOpGroup.add_argument(
        '-m', help='Specify mode, only load given modules ', nargs='+')
    modOpGroup.add_argument(
        '-e', help="Exclusive mode, load all modules except the given modules",
        nargs='+')

    parser.add_argument('-t', '--timeout', type=int,
                        help='Set timeout for all modules', default=300)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')

    parser.add_argument('url', help='The url to look up')

    args = parser.parse_args()

    # read system config
    fileConfig = open("config", "r")
    config = fileConfig.read()
    fileConfig.close()
    cfg = json.loads(config)

    resultDict = {}
    mod = ModuleManager()
    mod.loadModule(cfg, args)
    mod.run(args=args, resultDict=resultDict)
    os._exit(0)
