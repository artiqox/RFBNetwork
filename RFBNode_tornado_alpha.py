import tornado.httpserver, tornado.ioloop, tornado.options, tornado.web, os.path, random, string
from tornado.options import define, options
import pywaves as pw
from requests import get, post
import urllib.request
import json
import time
import concurrent.futures
import tornado.concurrent
import tornado.gen
import re
from datetime import datetime
from apscheduler.schedulers.tornado import TornadoScheduler
import webbrowser
import sys
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
#import random
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

#define("port", default=8888, help="run on the given port", type=int)

NODE_ADDRESS = ['localhost']

CMD = ""
CFG_FILE = os.path.join(os.path.dirname(__file__), 'config.cfg')
print(CFG_FILE)
COLOR_RESET = "\033[0;0m"
COLOR_GREEN = "\033[0;32m"
COLOR_RED = "\033[1;31m"
COLOR_BLUE = "\033[1;34m"
COLOR_WHITE = "\033[1;37m"

download_files = {'10k.txt': open('data/10k.txt', 'rb'),'100k.txt': open('data/100k.txt', 'rb'),'1000k.txt': open('data/1000k.txt', 'rb'),'10000k.txt': open('data/10000k.txt', 'rb')}
print(type(download_files["10k.txt"]))
print(type(open('data/10k.txt', 'rb')))
uploaded_files = {}

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

    NODE = config.get('main', 'node')
    NETWORK = config.get('main', 'network')
    RFBGATEWAY = config.get('rfbnetwork', 'rfb_gateway')
    RFBGATEWAYPORT = config.getint('rfbnetwork', 'rfb_gateway_port')
    HOST_PORT = config.getint('rfbnetwork', 'rfb_node_port')
    ACCOUNT_ADDRESS = config.get('account', 'account_address')
    amountAssetID = config.get('market', 'amount_asset')
    priceAssetID = config.get('market', 'price_asset')
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
#    log("  Node : %s" % NODE)
    log("  Network : %s" % NETWORK)
    log("  RFBGateway : %s" % RFBGATEWAY)
    log("  RFBGatewayPort : %s" % RFBGATEWAYPORT)
    log("  HostPort : %s" % HOST_PORT)
    log("  AccountAddress : %s" % ACCOUNT_ADDRESS)
#    log("  Amount Asset ID : %s" % amountAssetID)
#    log("  Price Asset ID : %s" % priceAssetID)
    log("-" * 80)
    log("")
except Exception as e:
    print(e)
    log("Error reading config file")
    log("Exiting.")
    exit(1)

def register_ip():
    #print("Your global IP is %s" % (get('https://api.ipify.org').text))
    #print("Gateway IP is %s" % (RFBGATEWAY))
    gateway_url = RFBGATEWAY+':'+str(RFBGATEWAYPORT)+'/checkAPI/'+NODE_ADDRESS[0]+';'+str(HOST_PORT)+';'+ACCOUNT_ADDRESS
    try:
        e = urllib.request.urlopen(gateway_url).read().decode('utf8')
        status = json.loads(e)['status']
        NEW_NODE_ADDRESS = get('https://api.ipify.org').text
        if NEW_NODE_ADDRESS != NODE_ADDRESS[0] or status != "OK":
            NODE_ADDRESS[0] = NEW_NODE_ADDRESS
            gateway_url = RFBGATEWAY+':'+str(RFBGATEWAYPORT)+'/registerAPI/'+NODE_ADDRESS[0]+';'+str(HOST_PORT)+';'+ACCOUNT_ADDRESS
            #print(gateway_url)
            try:
                contents = urllib.request.urlopen(gateway_url).read().decode('utf8')
                print(contents)
            except Exception as e:
                print("Issue with RFBGateway: %s" % e)
    except Exception as e:
        print("Issue with RFBGateway: %s" % e)
    #print(e)


class DownloadAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def download_file(self, host, port, source_file, dest_file):
        file_url = 'http://'+host+':'+port+'/data/'+source_file
        try:
            e = urllib.request.urlretrieve(file_url, 'data/downloads/'+dest_file) 
            e_status = "OK"
            return e, e_status
        except Exception as e:
            e_status = "NOK"
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'^(.*);(.*);(.*);(.*)$', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.download_file(matchObj.group(1), matchObj.group(2), matchObj.group(3), matchObj.group(4))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \"status\": "'+letssee_status+'"}'
            #print(json_out)
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params", "status": "NOK"})
        

class UploadAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def upload_file(self, host, port, source_file, dest_file):
        url = 'http://'+host+':'+port+'/upload'
        try:
            files = {'file1': open('data/'+source_file, 'rb')}
            values = {'dest_file': dest_file}
            e = post(url, files=files, data=values)
            e_status = "OK"
            return e, e_status
        except Exception as e:
            e_status = "NOK"
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'(.*);(.*);(.*);(.*)', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.upload_file(matchObj.group(1), matchObj.group(2), matchObj.group(3), matchObj.group(4))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \"status\": "'+letssee_status+'"}'
            #print(json_out)
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params", "status": "NOK"})

class UploadMemAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def upload_file(self, host, port, source_file, dest_file):
        url = 'http://'+host+':'+port+'/uploadMem'
        try:
            files = {'file1': download_files[source_file]}
            values = {'dest_file': dest_file}
            e = post(url, files=files, data=values)
            e_status = "OK"
            return e, e_status
        except Exception as e:
            e_status = "NOK"
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'(.*);(.*);(.*);(.*)', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.upload_file(matchObj.group(1), matchObj.group(2), matchObj.group(3), matchObj.group(4))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \"status\": "'+letssee_status+'"}'
            #print(json_out)
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params", "status": "NOK"})

class DeleteAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def delete_file(self, dir, file):
        try:
            e = os.remove('data/'+dir+'/'+file)
            e_status = "OK"
            return e, e_status
        except Exception as e:
            e_status = "NOK"
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'^(uploads|downloads);(\d+_\d+_\d+_(u|d))$', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.delete_file(matchObj.group(1), matchObj.group(2))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \"status\": "'+letssee_status+'"}'
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params", "status": "NOK"})

class DeleteMemAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def delete_file(self, file):
        try:
            del uploaded_files[file]
            e = "file deleted"
            e_status = "OK"
            return e, e_status
        except Exception as e:
            e_status = "NOK"
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'^(\d+_\d+_\d+_(u|d))$', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.delete_file(matchObj.group(1))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \"status\": "'+letssee_status+'"}'
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params", "status": "NOK"})

class Application(tornado.web.Application):
    def __init__(self):
        script_path = os.path.join(os.path.dirname(__file__), 'data')
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        handlers = [
            (r"/", IndexHandler),
            (r"/account", accountAPI),
            (r'/uploadAPI/(.+)', UploadAPI, dict(executor=executor)),
            (r'/uploadMemAPI/(.+)', UploadMemAPI, dict(executor=executor)),
            (r'/downloadAPI/(.+)', DownloadAPI, dict(executor=executor)),
            (r'/deleteAPI/(.+)', DeleteAPI, dict(executor=executor)),
            (r'/deleteMemAPI/(.+)', DeleteMemAPI, dict(executor=executor)),
            (r"/data/(.*)", tornado.web.StaticFileHandler, {"path": script_path}),
            (r"/uploadForm", UploadFormHandler),
            (r"/uploadFormMem2Mem", UploadFormMem2MemHandler),
            (r"/uploadFormMem", UploadFormMemHandler),
            (r"/upload", UploadHandler),
            (r"/uploadMem2Mem", UploadHandlerMem2Mem),
            (r"/uploadMem", UploadHandlerMem)
        ]
        tornado.web.Application.__init__(self, handlers, debug=True)

class accountAPI(tornado.web.RequestHandler):
    def get(self):
        # get an existing address from seed
        #myAddress = pw.Address(seed='seven wrist bargain hope pattern banner plastic maple student chaos grit next space visa answer')
        #self.write(str(myAddress))
        #ip = get('https://api.ipify.org').text
        self.write({'account_address': ACCOUNT_ADDRESS})

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        items = ["Your IP is: "+get('https://api.ipify.org').text, "Your Account Address is: "+ACCOUNT_ADDRESS, "visit www.artiqox.com"]
        self.render("main.html", title="My title", items=items)

class UploadFormHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("upload_form.html")

class UploadFormMemHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("upload_form_mem.html")

class UploadFormMem2MemHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("upload_form_mem2mem.html")

MAX_STREAMED_SIZE = 1024 * 1024 * 1024

@tornado.web.stream_request_body
class UploadHandlerMem2Mem(tornado.web.RequestHandler):
    def initialize(self):
        self.bytes_read = 0
        self.data = b''


    def prepare(self):
        self.request.connection.set_max_body_size(MAX_STREAMED_SIZE)

    def data_received(self, chunck):
        self.bytes_read += len(chunck)
        self.data += chunck

    def post(self):
        this_request = self.request
        
        value = self.data
        #print(type(value))

        self.finish("file size " + str(len(value)) + " uploaded")
        #with open('file', 'wb') as f:
        #    f.write(value)

class UploadHandler(tornado.web.RequestHandler):
    def post(self):

        file1 = self.request.files['file1'][0]
        dest_file = self.get_argument('dest_file')
        original_fname = file1['filename']
        extension = os.path.splitext(original_fname)[1]
        fname = ''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(6))
        final_filename= fname+extension
        output_file = open("data/uploads/" + dest_file, 'wb')
        output_file.write(file1['body'])
        self.finish("file " + dest_file + " uploaded")
        
class UploadHandlerMem(tornado.web.RequestHandler):
    def post(self):

        file1 = self.request.files['file1'][0]
        dest_file = self.get_argument('dest_file')
        original_fname = file1['filename']
        #extension = os.path.splitext(original_fname)[1]
        #fname = ''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(6))
        #final_filename= fname+extension
        uploaded_files.setdefault(dest_file, {})["name"] = original_fname
        #uploaded_files.setdefault(dest_file, {})["body"] = file1['body']
        uploaded_files.setdefault(dest_file, {})["len"] = str(len(file1['body']))
        #output_file = open("data/uploads/" + dest_file, 'wb')
        #output_file.write(len(file1['body']))
        self.finish("file size " + uploaded_files[dest_file]["len"] + " uploaded")

def start_browser():
    webbrowser.open('http://localhost:'+str(HOST_PORT), new=2)
    job.remove()

def main():
    trigger = CronTrigger(second='*/59')
    trigger2 = CronTrigger(second='*/5')
    scheduler = TornadoScheduler()
    scheduler.add_job(register_ip, trigger)
    global job
    job = scheduler.add_job(start_browser, trigger2)
    scheduler.start()
    #print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))


    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(HOST_PORT)
    #tornado.ioloop.IOLoop.instance().start()
    # Execution will block here until Ctrl+C (Ctrl+Break on Windows) is pressed.
    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
    try:
        tornado.ioloop.IOLoop.instance().start()
        #IOLoop.instance().start()
    except (KeyboardInterrupt, SystemExit):
        pass
    
    
if __name__ == "__main__":
    main()
