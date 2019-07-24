#TODO: check on https://www.artificialworlds.net/blog/2017/06/12/making-100-million-requests-with-python-aiohttp/
from aiohttp import web, ClientSession
import json
import pywaves as pw
import sys
from pathlib import Path
import os
from datetime import datetime
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import webbrowser
import asyncio
import string
#from random import *
import random
from multidict import MultiDict
import uuid
from itertools import permutations
import pickle
#TODO: replace the get method (used only for registering the IP at the gateway) with aio
from requests import get
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

allchar = string.ascii_letters + string.digits

CMD = ""
CFG_FILE = os.path.join(os.path.dirname(__file__), 'config.cfg')

COLOR_RESET = "\033[0;0m"
COLOR_GREEN = "\033[0;32m"
COLOR_RED = "\033[1;31m"
COLOR_BLUE = "\033[1;34m"
COLOR_WHITE = "\033[1;37m"

try:
    testResults = pickle.load(open("testResults.pickle", "rb"))
except (OSError, IOError) as e:
    testResults = {}
    pickle.dump(testResults, open("testResults.pickle", "wb"))

rfbNodes = {}

def log(msg):
    timestamp = datetime.utcnow().strftime("%b %d %Y %H:%M:%S UTC")
    s = "[%s] %s:%s %s" % (timestamp, COLOR_WHITE, COLOR_RESET, msg)
    print(s)
    try:
        f = open(LOGFILE, "a")
        f.write(s + "\n")
        f.close()
    except:
        pass

if len(sys.argv) >= 2:
    CFG_FILE = sys.argv[1]

if len(sys.argv) == 3:
    CMD = sys.argv[2].upper()

if not os.path.isfile(CFG_FILE):
    log("Missing config file")
    log("Exiting.")
    exit(1)

# parse config file
try:
    log("%sReading config file '%s'" % (COLOR_RESET, CFG_FILE))
    config = configparser.RawConfigParser()
    config.read(CFG_FILE)
    
    DATA_API_URL = config.get('main', 'api_url')
    NODE = config.get('main', 'node')
    NETWORK = config.get('main', 'network')
    RFBT_ADDRESS = config.get('main', 'rfbt_address')
    
    pw.setNode(node=NODE, chain=NETWORK)
    
    LOGFILE = config.get('logging', 'logfile')

    RFBGATEWAY = config.get('rfbnetwork', 'rfb_gateway')
    RFBGATEWAYPORT = config.getint('rfbnetwork', 'rfb_gateway_port')

    log("-" * 80)
    log("  RFBGATEWAY: %s" % RFBGATEWAY)
    log("  RFBGATEWAYPORT : %s" % RFBGATEWAYPORT)
    log("-" * 80)
    log("")
except:
    log("Error reading config file")
    log("Exiting.")
    exit(1)

#create missing results directory if any
if not os.path.exists("results"):
    os.makedirs("results")
    print ("create missing results directory")

async def saveTestsToPickle():
    CURRENT_HEIGHT = int(pw.height())
    for testId in list(testResults):
        if int(testId) <= CURRENT_HEIGHT-20:
            pickle.dump(testResults[testId], open("results/"+testId+".pickle", "wb"))            
            del testResults[testId]
            pickle.dump(testResults, open("testResults.pickle", "wb"))

#old self testing module, not in use anymore but has nice stuff in for future references
async def runTests():
    perm = permutations(rfbNodes.keys(), 2)
    list_of_tests = []
    for i in list(perm):
        list_of_tests.append(i)
    random.shuffle(list_of_tests)
    test_results_timestamp = str(datetime.utcnow())
    for i in list_of_tests:
        testId=test_results_timestamp+'_'+str(i[0])+'_'+str(i[1])
        
        testStart=datetime.utcnow()
        testNodeA=i[0]
        testNodeAwallet=str(rfbNodes[i[0]]['nodeWallet'])
        testNodeB=i[1]
        testNodeBwallet=str(rfbNodes[i[1]]['nodeWallet'])
        #testResults.setdefault(test_results_timestamp[:10], {}).setdefault(test_results_timestamp, {}).setdefault(testId, {}).setdefault(testType, {})[data["indicator"]["name"]] = data["values"][0].get("value", data["values"][0].get("status", "NaN"))        
        async with ClientSession() as session:
            usedHandler='downloadFileFromRemoteNode'
            nodeUrl = 'http://'+testNodeA+'/downloadFileFromRemoteNode'
            parameters = {'testId': testId,
                          'destinationFileName': '10k.txt',
                          'sourceHost': testNodeB,
                          'sourceFileName': '10k.txt'}        
            try:
                async with session.post(nodeUrl, data=parameters) as response:
                    httpStatus = response.status
                    responseData = await response.json()
                    responseStatus = responseData['status']
                    responseMessage = responseData['message']
                    responsetaskDuration = responseData['taskDuration']
                    testResults.setdefault(testId, {}).setdefault(testNodeB, {}).setdefault(testNodeA, {})[usedHandler] = responseData
                    pickle.dump(testResults, open("testResults.pickle", "wb"))
                    #print(responseStatus)
                    #print(responseMessage)
            except Exception as e:
                print(str(e))

            usedHandler='uploadFileToRemoteNode'
            nodeUrl = 'http://'+testNodeA+'/uploadFileToRemoteNode'
            parameters = {'testId': testId,
                          'destinationFileName': '10k.txt',
                          'fileName': '10k.txt',
                          'destinationHost': testNodeB}        
            try:
                async with session.post(nodeUrl, data=parameters) as response:
                    httpStatus = response.status
                    responseData = await response.json()
                    responseStatus = responseData['status']
                    responseMessage = responseData['message']
                    testResults.setdefault(testId, {}).setdefault(testNodeB, {}).setdefault(testNodeA, {})[usedHandler] = responseData
                    pickle.dump(testResults, open("testResults.pickle", "wb"))
            except Exception as e:
                print(str(e))

async def IndexHandler(request):
    response_obj = { 'status' : 'success', 'IP' : get('https://api.ipify.org').text }
    return web.Response(text=json.dumps(response_obj))

async def CheckAPIHandler(request):
    """
    POST handler ...
    """
    try:
        data = await request.post()
        peername = request.transport.get_extra_info('peername')
        if peername is not None:
            host, port = peername
        else:
            host = 'noHost'
        nodeAddress = data['nodeAddress']
        nodePort = data['nodePort']
        nodeWallet = data['nodeWallet']
        nodeToken = data['nodeToken']
        if host == nodeAddress and rfbNodes.get(nodeAddress+':'+nodePort)['nodeWallet'] == nodeWallet and rfbNodes.get(nodeAddress+':'+nodePort)['nodeToken'] == nodeToken:
            status = 'success'
            message = nodeAddress+':'+nodePort+' is registered with address '+nodeWallet
            response_obj = { 'status': status, 'message': message, 'rfbNodes': list(rfbNodes.keys()) }
        else:
            status = 'need register'
            message = nodeAddress+':'+nodePort+' is not registered with address '+nodeWallet
            response_obj = { 'status': status, 'message': message }
        return web.json_response(response_obj)
    except Exception as e:
        response_obj = { 'status' : 'failed', 'message': str(e) }
        return web.json_response(response_obj)

async def ShareResultsAPIHandler(request):
    """
    POST handler ...
    """
    try:
        data = await request.post()
        peername = request.transport.get_extra_info('peername')
        if peername is not None:
            host, port = peername
        testNode = data['nodeAddress']
        nodePort = data['nodePort']
        nodeToken = data['nodeToken']
        testConfirmationsNew = json.loads(data['testConfirmations'])
        testResultsNew = json.loads(data['testResults'])
        CURRENT_HEIGHT = int(pw.height())
        print(host)
        print(testNode)
        print(nodeToken)
        print(rfbNodes.get(testNode+':'+nodePort)['nodeToken'])
        print(testConfirmationsNew)
        print(testResultsNew)
        print('---')
        if host == testNode and nodeToken == rfbNodes.get(testNode+':'+nodePort)['nodeToken']:
            for test in testResultsNew:
                if int(test) >= CURRENT_HEIGHT-10:
                    #print(test)
                    for node in testResultsNew[test]:
                        #print(node)
                        for nodeA in testResultsNew[test][node]:
                            #print(nodeA)
                            for usedHandler in testResultsNew[test][node][nodeA]:
                                if nodeA == testNode+':'+nodePort:
                                    #print('setting test results')
                                    testResults.setdefault(test, {}).setdefault(node, {}).setdefault(nodeA, {})[usedHandler] = testResultsNew[test][node][nodeA][usedHandler]
                                    pickle.dump(testResults, open("testResults.pickle", "wb"))
                                    #print(testResults)
                                else:
                                    print('He shall not try to load some of these tests results: '+testResultsNew[test])

            for test in testConfirmationsNew:
                if int(test) >= CURRENT_HEIGHT-10:
                    #print(test)
                    for node in testConfirmationsNew[test]:
                        #print(node)
                        for nodeA in testConfirmationsNew[test][node]:
                            #print(nodeA)
                            for usedHandler in testConfirmationsNew[test][node][nodeA]:
                                if node == testNode+':'+nodePort:
                                    testResults.setdefault(test, {}).setdefault(node, {}).setdefault(nodeA, {})[usedHandler] = testConfirmationsNew[test][node][nodeA][usedHandler]
                                    pickle.dump(testResults, open("testResults.pickle", "wb"))
                                    #print(testResults)
                                else:
                                    print('He shall not try to confirm some of these tests results: '+testConfirmationsNew[test])
            #print(testResults)

            print('---')
        response_obj = { 'status': 'success', 'message': 'Thanks for sharing' }
        return web.json_response(response_obj)
    except Exception as e:
        response_obj = { 'status' : 'failed', 'message': str(e) }
        return web.json_response(response_obj)

async def RegisterAPIHandler(request):
    """
    POST handler ...
    """
    try:
        data = await request.post()
        peername = request.transport.get_extra_info('peername')
        if peername is not None:
            host, port = peername
        else:
            host = 'noHost'
        nodeAddress = data['nodeAddress']
        nodePort = data['nodePort']
        nodeWallet = data['nodeWallet']
        nodeToken = data['nodeToken']
        nodeUrl = 'http://'+nodeAddress+':'+nodePort+'/account'
        async with ClientSession() as session:
            async with session.get(nodeUrl) as response:
                responseData = await response.json()
                responseStatus = responseData['status']
                responseWallet = responseData['wallet']
                if host == nodeAddress and nodeWallet == responseWallet:
                    rfbNodes.setdefault(nodeAddress+':'+nodePort, {})["nodeWallet"] = nodeWallet
                    rfbNodes.setdefault(nodeAddress+':'+nodePort, {})["nodeToken"] = nodeToken
                    log("  Registered node : %s" % nodeAddress+':'+nodePort)
                    log("  with BC address : %s" % nodeWallet)
                    status = 'success'
                    message = nodeAddress+':'+nodePort+' registered with address '+nodeWallet
                    response_obj = { 'status': status, 'message': message, 'rfbNodes': list(rfbNodes.keys()) }
                    return web.json_response(response_obj)
                elif nodeWallet != responseWallet:
                    status = 'failed'
                    message = nodeAddress+':'+nodePort+' is trying to register with address '+nodeWallet+' but its address is '+responseWallet
                    response_obj = { 'status': status, 'message': message }
                    return web.json_response(response_obj)
    except Exception as e:
        response_obj = { 'status' : 'failed', 'message': str(e) }
        return web.json_response(response_obj)

app = web.Application()
app.router.add_get('/', IndexHandler)
app.router.add_post('/checkAPI', CheckAPIHandler)
app.router.add_post('/registerAPI', RegisterAPIHandler)
app.router.add_post('/shareResults', ShareResultsAPIHandler)

scheduler = AsyncIOScheduler()
scheduler.add_job(saveTestsToPickle, 'interval', seconds=300)
scheduler.start()

# Execution will block here until Ctrl+C (Ctrl+Break on Windows) is pressed.
print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
try:
    web.run_app(app, port=RFBGATEWAYPORT)
except (KeyboardInterrupt, SystemExit):
    pass
