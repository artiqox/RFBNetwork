#TODO:
#- oauth2 or some token passed to the gateway so not everyone can upload/download files
#- lean toward OOP
#- handlers to download/upload files from/to HDD
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
from random import *
from multidict import MultiDict
from datetime import timedelta
#Maybe uuid not needed? to be analysed
import uuid
#TODO: replace the get method (used only for registering the IP at the gateway) with aio
from requests import get
#workaround for pyinstaller
from apscheduler.triggers.cron import CronTrigger
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

allchar = string.ascii_letters + string.digits
nodeToken = "".join(choice(allchar) for x in range(randint(5, 5)))

rfbAllowedAccounts = []

rfbGateways = []

NODE_ADDRESS = ['localhost']

CMD = ""
CFG_FILE = os.path.join(os.path.dirname(__file__), 'config.cfg')

COLOR_RESET = "\033[0;0m"
COLOR_GREEN = "\033[0;32m"
COLOR_RED = "\033[1;31m"
COLOR_BLUE = "\033[1;34m"
COLOR_WHITE = "\033[1;37m"

#We create set of files if they dont exist, then we load those to download_files dictionary, later http server uses that dictionary to serve files (from memory instead of HDD)
def createDummyFile(fname, size):
    #1. get the directory name
    dname = os.path.dirname(fname)
    
    #2. create missing directories if any
    if  dname != "" and not os.path.exists(dname):
        os.makedirs(dname)
        print ("create missing directory(ies) ", dname)
    
    #3. create missing files if any
    if os.path.exists(fname) == False:
        f = open(fname,'wb')
        f.seek(size-1)
        f.write(b"\0")
        f.close()
        print ("create missing file ", fname, "with size: ", os.stat(fname).st_size)

createDummyFile('data/1k.txt', 1024)
createDummyFile('data/10k.txt', 10240)
createDummyFile('data/100k.txt', 102400)
createDummyFile('data/1000k.txt', 1024000)
createDummyFile('data/10000k.txt', 10240000)
createDummyFile('data/100000k.txt', 102400000)
createDummyFile('data/1000000k.txt', 1024000000)

download_files = {'1k.txt': open('data/1k.txt', 'rb').read(),'10k.txt': open('data/10k.txt', 'rb').read(),'100k.txt': open('data/100k.txt', 'rb').read(),'1000k.txt': open('data/1000k.txt', 'rb').read(),'10000k.txt': open('data/10000k.txt', 'rb').read(),'100000k.txt': open('data/100000k.txt', 'rb').read(),'1000000k.txt': open('data/1000000k.txt', 'rb').read()}

#this is list of all RFBNodes, this list is provided by RFBGateways
rfbNodes = []
#this is dictionary where node stores speed test results that he performs to/from other nodes
testResults = {}
#this is dictionary where node stores http requests he receives from other nodes, it is then used to validate test results on RFBGateway level
testConfirmations = {}

async def start_browser():
    """
    Function to start web browser and display localhost:port page, it is executed with appscheduler 5 seconds after RFBNode starts and then the job is removed
    """
    webbrowser.open('http://localhost:'+str(HOST_PORT), new=2)
    job.remove()

async def cleanTestResults(CURRENT_HEIGHT):
    """
    Function to remove test results and confirmations older than 10 blocks
    """
    LAST_GOOD_HEIGHT = int(CURRENT_HEIGHT) - 10
    
    for testId in list(testResults):
        if int(testId) <= LAST_GOOD_HEIGHT:
            del testResults[testId]

    for testId in list(testConfirmations):
        if int(testId) <= LAST_GOOD_HEIGHT:
            del testConfirmations[testId]

async def register_ip():
    """
    This function:
    - checks which RFBGateways to connect to: 1) checks list of burn transactions. 2) checks currennt balance for accounts that did those burns. 3) checks (for acounts with minimum balance) for data transactions with key:value where key: RFBGateway_address and value: hostname:port. 4) creates rfbGateways python list
    - connects to each gateway and fetches the list of RFBNodes
    - runs tests to all RFBNodes (one by one)
    - shares test results with gateways from rfbGateways list
    """
    async with ClientSession() as session:

        checkBurnUrl = DATA_API_URL+'transactions/burn?sort=desc&limit=100&assetId='+RFBT_ADDRESS
        try:
            async with session.get(checkBurnUrl) as response:
                httpStatus = response.status
                checkBurnResponseData = await response.json()
                burnTransactions = []
                burnSenders = []
                rfbGateways.clear()
                for i in range(0, len(checkBurnResponseData['data'])):
                    burnTransactions.append({'sender':checkBurnResponseData['data'][i]['data']['sender'],'amount':checkBurnResponseData['data'][i]['data']['amount'],'id':checkBurnResponseData['data'][i]['data']['id']})
                    burnSenders.append(checkBurnResponseData['data'][i]['data']['sender'])
                for sender in set(burnSenders):
                    myAddress = pw.Address(sender)
                    if myAddress.balance(RFBT_ADDRESS) > 100000000:
                        checkDataUrl = DATA_API_URL+'transactions/data?sender='+sender+'&key=RFBGateway_address&sort=desc&limit=100'
                        try:
                            async with session.get(checkDataUrl) as response:
                                httpStatus = response.status
                                checkDataResponseData = await response.json()
                                rfbGateways.append(checkDataResponseData['data'][0]['data']['data'][0]['value'])
                        except Exception as e:
                            print(e)
        except Exception as e:
            print(e)
        rfbNodes_temp2 = []
        rfbNodes_temp = []
        for gateway in set(rfbGateways):
            gatewayUrl = 'https://'+str(gateway)+'/checkAPI'
            parameters = {'nodeAddress': NODE_ADDRESS[0],
                          'nodePort': str(HOST_PORT),
                          'nodeToken': nodeToken,
                          'nodeWallet': ACCOUNT_ADDRESS}
            try:
                async with session.post(gatewayUrl, data=parameters) as response:
                    httpStatus = response.status
                    responseData = await response.json()
                    responseStatus = responseData['status']
                    responseMessage = responseData['message']
                    if responseStatus == "success":
                        rfbNodes_temp.append(responseData['rfbNodes'])
                    NEW_NODE_ADDRESS = get('https://api.ipify.org').text
                    if NEW_NODE_ADDRESS != NODE_ADDRESS[0] or responseStatus != "success":
                        NODE_ADDRESS[0] = NEW_NODE_ADDRESS
                        gatewayUrl = 'https://'+str(gateway)+'/registerAPI'
                        parameters = {'nodeAddress': NODE_ADDRESS[0],
                                      'nodePort': str(HOST_PORT),
                                      'nodeToken': nodeToken,
                                      'nodeWallet': ACCOUNT_ADDRESS}
                        async with session.post(gatewayUrl, data=parameters) as response:
                            httpStatus = response.status
                            responseData = await response.json()
                            responseStatus = responseData['status']
                            responseMessage = responseData['message']
                            rfbNodes_temp.append(responseData['rfbNodes'])
                            print(responseMessage)
            except Exception as e:
                print(e)

        if rfbNodes_temp:
            for node in rfbNodes_temp[0]:
                rfbNodes_temp2.append(node)
            rfbNodes = set(rfbNodes_temp2)

            if len(rfbNodes) >= 2:

                rfbNodes.remove(NODE_ADDRESS[0]+':'+str(HOST_PORT))

                fileName = "100k.txt"

                for rfbNode in rfbNodes:

                    CURRENT_HEIGHT = str(pw.height())
                    testId = CURRENT_HEIGHT
                    asyncio.ensure_future(cleanTestResults(testId))
                    fileUrl = 'http://'+rfbNode+'/downloadFile/'+fileName+'/'+testId+'/'+str(HOST_PORT)
            
                    async with ClientSession() as session:
                        try:
                            fileSize = 0
                            timestampStart = datetime.utcnow()
                            async with session.get(fileUrl) as response:
                                async for data in response.content.iter_chunked(1024):
                                    fileSize += len(data)
                            timestampEnd = datetime.utcnow()
                            taskDuration = timestampEnd - timestampStart
                            if fileSize > 0:
                                testResults.setdefault(testId, {}).setdefault(rfbNode, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {})['downloadFile'] = { 'status': 'success', 'message': 'File downloaded', 'testId': testId, 'usedHandler': 'downloadFile', 'taskDuration': str(taskDuration), 'fileName': fileName, 'sourceFileName': fileName, 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd), 'speed': str(fileSize/taskDuration.total_seconds()) }
                            else:
                                testResults.setdefault(testId, {}).setdefault(rfbNode, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {})['downloadFile'] = { 'status': 'failed', 'message': 'Empty file downloaded', 'testId': testId, 'usedHandler': 'downloadFile', 'taskDuration': str(taskDuration), 'fileName': fileName, 'sourceFileName': fileName, 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd), 'speed': '0' }
                        except Exception as e:
                            timestampEnd = datetime.utcnow()
                            taskDuration = timestampEnd - timestampStart
                            testResults.setdefault(testId, {}).setdefault(rfbNode, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {})['downloadFile'] = { 'status': 'failed', 'message': str(e), 'testId': testId, 'usedHandler': 'downloadFile', 'taskDuration': str(taskDuration), 'fileName': fileName, 'sourceFileName': fileName, 'fileSize': 0, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd), 'speed': '0' }
                            #print(str(e))
            
                    fileUrl = 'http://'+rfbNode+'/uploadFile/'+fileName+'/'+testId+'/'+str(HOST_PORT)
            
                    async with ClientSession() as session:
                        try:
                            timestampStart = datetime.utcnow()
                            async with ClientSession() as session:
                                async with session.post(fileUrl, data ={
                                    'testId': testId,
                                    'fileName': fileName, 
                                    'file': download_files[fileName]
                                }) as response:
                                    data = await response.json()
                                    fileSize = len(download_files[fileName])
                                    timestampEnd = datetime.utcnow()
                                    taskDuration = timestampEnd - timestampStart
                                    if data:
                                        testResults.setdefault(testId, {}).setdefault(rfbNode, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {})['uploadFile'] = { 'status': 'success', 'message': 'File uploaded', 'testId': testId, 'usedHandler': 'uploadFile', 'taskDuration': str(taskDuration), 'fileName': fileName, 'sourceFileName': fileName, 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd), 'speed': str(fileSize/taskDuration.total_seconds()) }
                        except Exception as e:
                            timestampEnd = datetime.utcnow()
                            taskDuration = timestampEnd - timestampStart
                            testResults.setdefault(testId, {}).setdefault(rfbNode, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {})['uploadFile'] = { 'status': 'failed', 'message': str(e), 'testId': testId, 'usedHandler': 'uploadFile', 'taskDuration': str(taskDuration), 'fileName': fileName, 'sourceFileName': fileName, 'fileSize': 0, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd), 'speed': '0' }
                            #print(str(e))
                async with ClientSession() as session:
                    for gateway in set(rfbGateways):
                        gatewayUrl = 'https://'+str(gateway)+'/shareResults'
                        parameters = {'nodeAddress': NODE_ADDRESS[0],
                                      'nodePort': str(HOST_PORT),
                                      'nodeToken': nodeToken,
                                      'testResults': json.dumps(testResults),
                                      'testConfirmations': json.dumps(testConfirmations)}
                        try:
                            async with session.post(gatewayUrl, data=parameters) as response:
                                httpStatus = response.status
                                responseData = await response.json()
                                responseStatus = responseData['status']
                                responseMessage = responseData['message']
                        except Exception as e:
                            print(str(e))

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

#WAVES stuff to generate wallet
def get_seed_phrase(prompt):
    while True:
        value = input(prompt)
        if not re.match( r'^([\w]+)$', value, re.M|re.I):
            print("Sorry, please provide a single word.")
            continue
        else:
            break
    return value

def get_account_address(prompt):
    while True:
        value = input(prompt)
        pw.setNode(node=NODE, chain=NETWORK)
        if not pw.validateAddress(value):
            print("Sorry, please provide correct address.")
            continue
        else:
            break
    return value

def configureAccountAddress(NODE, NETWORK):
    while True:
        print("(1) - create new RFB address")
        print("(2) - use existing RFB address")
        data = input("Enter number :")
        if data not in ('1', '2'):
            print("Not an appropriate choice.")
            continue
        elif data == "1":
            seed_list = []
            for i in range(1, 13):
                seed = get_seed_phrase("Please enter seed "+str(i)+": ")
                seed_list.append(seed)
            pw.setNode(node=NODE, chain=NETWORK)
            new_account_data = pw.Address(seed=' '.join(seed_list))
            print("Save the below data, it is not saved and cant be restored if you loose it!!!")
            lines = str(new_account_data).split('\n')
            print(lines[0])
            print(lines[1])
            print(lines[2])
            matchObj = re.match( r'^address \= ([a-zA-Z0-9]{35}).*', str(new_account_data), re.M|re.I)
            if matchObj:
                ACCOUNT_ADDRESS = matchObj.group(1)
                f= open("wallet.dat","w+")
                f.write(ACCOUNT_ADDRESS)
                f.close()
            else:
                ACCOUNT_ADDRESS = "THISISWRONGACCOUNT"
            break
        elif data == "2":
            ACCOUNT_ADDRESS = get_account_address("Please enter your account address: ")
            break
    return ACCOUNT_ADDRESS

#stuff to read command line pars, need to be reviewed as was used long time back
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
    DATA_API_URL = config.get('rfbnetwork', 'rfb_gateway_minimum_balance')
    DATA_API_URL = config.get('main', 'api_url')
    NODE = config.get('main', 'node')
    NETWORK = config.get('main', 'network')
    HOST_PORT = config.getint('rfbnetwork', 'rfb_node_port')
    ACCOUNT_ADDRESS = config.get('account', 'account_address')
    RFBT_ADDRESS = config.get('main', 'rfbt_address')
    LOGFILE = config.get('logging', 'logfile')
    pw.setNode(node=NODE, chain=NETWORK)
    wallet_file = Path("wallet.dat")
    if wallet_file.is_file():
        f=open("wallet.dat", "r")
        if f.mode == 'r':
            contents = f.read()
            if pw.validateAddress(contents):
                ACCOUNT_ADDRESS = contents

    if ACCOUNT_ADDRESS == "XXX":
        print("Please configure your account address")
        ACCOUNT_ADDRESS = configureAccountAddress(NODE, NETWORK)

    log("-" * 80)
    log("  Network : %s" % NETWORK)
    log("  HostPort : %s" % HOST_PORT)
    log("  AccountAddress : %s" % ACCOUNT_ADDRESS)
    log("-" * 80)
    log("")
except Exception as e:
    print(e)
    log("Error reading config file")
    log("Exiting.")
    exit(1)

async def IndexHandler(request):
    response_obj = { 'status' : 'success', 'IP' : get('https://api.ipify.org').text, 'wallet' : ACCOUNT_ADDRESS }
    return web.Response(text=json.dumps(response_obj))

async def AccountHandler(request):
    response_obj = { 'status' : 'success', 'IP' : get('https://api.ipify.org').text, 'wallet' : ACCOUNT_ADDRESS }
    return web.json_response(response_obj)

async def UploadHandlerMem(request):
    """
    POST handler that accepts uploads of files.
    It does not store the content of the file, just creates entry in the dictionary to keep track of upload activity.
    """
    # You cannot rely on Content-Length if transfer is chunked.
    try:
        fileSize = 0
        timestampStart = datetime.utcnow()
        usedHandler = 'UploadHandlerMem'
        try:
            testId = request.match_info['testId']
        except Exception as e:
            testId = "noId"
        try:
            sourceHostPort = request.match_info['sourceHostPort']
        except Exception as e:
            sourceHostPort = "noPort"
        try:
            fileName = request.match_info['fileName']
        except Exception as e:
            fileName = "noFileName"
        while True:
            chunk, is_end_of_http_chunk = await request.content.readchunk()
            if not chunk:
                break
            fileSize += len(chunk)
        peername = request.transport.get_extra_info('peername')
        if peername is not None:
            host, port = peername
        else:
            host = 'nohost'
        timestampEnd = datetime.utcnow()
        taskDuration = str(timestampEnd - timestampStart)
        if testId != "noId" and sourceHostPort != "noPort" and fileName != "noFileName":
            testConfirmations.setdefault(testId, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {}).setdefault(host+':'+sourceHostPort, {})['UploadHandlerMem'] = { 'status': 'success', 'message': 'File uploaded', 'testId': testId, 'usedHandler': 'UploadHandlerMem', 'taskDuration': taskDuration, 'fileName': fileName, 'sourceFileName': '10k.txt', 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd) }
        response_obj = { 'status': 'success', 'message': 'File uploaded to memory', 'testId': testId, 'usedHandler': usedHandler, 'taskDuration': taskDuration, 'fileName': fileName, 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd) }
        return web.json_response(response_obj)
    except Exception as e:
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        print(str(e))
        return web.json_response(response_obj)

async def DownloadHandlerMem(request):
    try:
        fileSize = 0
        timestampStart = datetime.utcnow()
        usedHandler = 'DownloadHandlerMem'
        try:
            testId = request.match_info['testId']
        except Exception as e:
            testId = "noId"
        try:
            sourceHostPort = request.match_info['sourceHostPort']
        except Exception as e:
            sourceHostPort = "noPort"
        try:
            fileName = request.match_info['fileName']
        except Exception as e:
            fileName = "noFileName"
        fileSize = len(download_files[fileName])
        peername = request.transport.get_extra_info('peername')
        if peername is not None:
            host, port = peername
        else:
            host = 'noHost'
        if testId != "noId" and sourceHostPort != "noPort" and host != "noHost":
            testConfirmations.setdefault(testId, {}).setdefault(NODE_ADDRESS[0]+':'+str(HOST_PORT), {}).setdefault(host+':'+sourceHostPort, {})[usedHandler] = { 'status': 'success', 'message': 'File downloaded', 'testId': testId, 'usedHandler': usedHandler, 'fileName': fileName, 'sourceFileName': '10k.txt', 'fileSize': fileSize, 'timestampStart': str(timestampStart) }
        return web.Response(
            headers=MultiDict({'Content-Disposition': 'Attachment'}),
            body=download_files[fileName]
        )
    except Exception as e:
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        print(str(e))
        return web.Response(text=json.dumps(response_obj), status=500)

#below two functions are not anymore needed since new way for runnig the tests but I keep it to maybe reuse later on for other stuff
async def UploadToRemoteNodeHandler(request):
    """
    POST handler that uploads file to remote host.
    """
    fileSize = 0
    timestampStart = datetime.utcnow()
    usedHandler = 'uploadFileToRemoteNode'
    try:
        data = await request.post()
        try:
            testId = data['testId']
        except Exception as e:
            testId = str(uuid.uuid4())
        try:
            fileName = data['fileName']
        except Exception as e:
            fileName = '1k.txt'
        try:
            destinationFileName = data['destinationFileName']
        except Exception as e:
            destinationFileName = fileName
        try:
            destinationHost = data['destinationHost']
        except Exception as e:
            print('no destinationHost')

        fileUrl = 'http://'+destinationHost+'/uploadFile/'+testId
        #print(fileUrl)
        async with ClientSession() as session:
            try:
                async with ClientSession() as session:
                    async with session.post(fileUrl, data ={
                           'testId': testId,
                           'fileName': destinationFileName, 
                           'file': download_files[fileName]
                    }) as response:
                           data = await response.json()
                fileSize = len(download_files[fileName])
                timestampEnd = datetime.utcnow()
                taskDuration = str(timestampEnd - timestampStart)
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["fileName"] = fileName
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["destinationFileName"] = destinationFileName
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["fileSize"] = fileSize
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["timestampStart"] = str(timestampStart)
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["timestampEnd"] = str(timestampEnd)
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["taskDuration"] = taskDuration
                response_obj = { 'status': 'success', 'message': 'File uploaded', 'testId': testId, 'usedHandler': usedHandler, 'taskDuration': taskDuration, 'fileName': fileName, 'destinationFileName': destinationFileName, 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd) }
                return web.json_response(response_obj)
            except Exception as e:
                response_obj = { 'status' : 'failed', 'message': str(e) }
                return web.json_response(response_obj)
    except Exception as e:
        response_obj = { 'status' : 'failed', 'message': str(e) }
        return web.json_response(response_obj)

async def DownloadFromRemoteNodeHandler(request):
    """
    POST handler that downloads file from remote host.
    """
    fileSize = 0
    timestampStart = datetime.utcnow()
    usedHandler = 'downloadFileFromRemoteNode'
    try:
        data = await request.post()
        try:
            testId = data['testId']
        except Exception as e:
            print('no testId, generating own')
            testId = str(uuid.uuid4())
        try:
            fileName = data['destinationFileName']
        except Exception as e:
            print('no fileName, generating own')
            fileName = "".join(choice(allchar) for x in range(randint(5, 5)))
        try:
            sourceHost = data['sourceHost']
            sourceFileName = data['sourceFileName']
        except Exception as e:
            print('no sourceHost and sourceFileName')

        fileUrl = 'http://'+sourceHost+'/downloadFile/'+sourceFileName+'/'+testId

        async with ClientSession() as session:
            try:
                async with session.get(fileUrl) as response:
                    async for data in response.content.iter_chunked(1024):
                            fileSize += len(data)
                timestampEnd = datetime.utcnow()
                taskDuration = str(timestampEnd - timestampStart)
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["fileName"] = fileName
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["sourceFileName"] = sourceFileName
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["fileSize"] = fileSize
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["timestampStart"] = str(timestampStart)
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["timestampEnd"] = str(timestampEnd)
                testResults.setdefault(testId, {}).setdefault(usedHandler, {})["taskDuration"] = taskDuration
                response_obj = { 'status': 'success', 'message': 'File downloaded', 'testId': testId, 'usedHandler': usedHandler, 'taskDuration': taskDuration, 'fileName': fileName, 'sourceFileName': sourceFileName, 'fileSize': fileSize, 'timestampStart': str(timestampStart), 'timestampEnd': str(timestampEnd) }
                return web.json_response(response_obj)
            except Exception as e:
                response_obj = { 'status' : 'failed', 'message': str(e) }
                return web.json_response(response_obj)
    except Exception as e:
        response_obj = { 'status' : 'failed', 'message': str(e) }
        return web.json_response(response_obj)

app = web.Application()
app.router.add_get('/', IndexHandler)
app.router.add_get('/account', AccountHandler)
app.router.add_post('/uploadFile', UploadHandlerMem)
app.router.add_post('/uploadFile/{fileName}/{testId}/{sourceHostPort}', UploadHandlerMem)
app.router.add_get('/downloadFile/{fileName}', DownloadHandlerMem)
app.router.add_get('/downloadFile/{fileName}/{testId}/{sourceHostPort}', DownloadHandlerMem)
app.router.add_post('/uploadFileToRemoteNode', UploadToRemoteNodeHandler)
app.router.add_post('/downloadFileFromRemoteNode', DownloadFromRemoteNodeHandler)

scheduler = AsyncIOScheduler()

#below does not work with pyinstaller
#scheduler.add_job(register_ip, 'date', run_date=datetime.now() + timedelta(seconds=5))
#scheduler.add_job(register_ip, 'interval', seconds=60)
#global job
#job = scheduler.add_job(start_browser, 'interval', seconds=5)

#below works with pytinstaller
trigger = CronTrigger(minute='*/5')
trigger2 = CronTrigger(second='*/5')
scheduler.add_job(register_ip, trigger)
global job
job = scheduler.add_job(start_browser, trigger2)

scheduler.start()

# Execution will block here until Ctrl+C (Ctrl+Break on Windows) is pressed.
print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
try:
    web.run_app(app, port=HOST_PORT)
except (KeyboardInterrupt, SystemExit):
    pass
