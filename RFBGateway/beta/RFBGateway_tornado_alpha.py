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
#import os
import sys
import sqlite3 as sqlite

#random and datetime might cause some issues:
from itertools import permutations
#import random

#import datetime

from apscheduler.triggers.cron import CronTrigger

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

#define("port", default=8888, help="run on the given port", type=int)

CMD = ""
CFG_FILE = os.path.join(os.path.dirname(__file__), 'config.cfg')

COLOR_RESET = "\033[0;0m"
COLOR_GREEN = "\033[0;32m"
COLOR_RED = "\033[1;31m"
COLOR_BLUE = "\033[1;34m"
COLOR_WHITE = "\033[1;37m"

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

    NODE = config.get('main', 'node')
    NODE_PORT = config.getint('rfbnetwork', 'rfb_node_port')
    MATCHER = config.get('main', 'matcher')
    ORDER_FEE = config.getint('main', 'order_fee')
    ORDER_LIFETIME = config.getint('main', 'order_lifetime')

    PRIVATE_KEY = config.get('account', 'private_key')
    ACCOUNT_ADDRESS = config.get('account', 'account_address')
    amountAssetID = config.get('market', 'amount_asset')
    priceAssetID = config.get('market', 'price_asset')

    INTERVAL = config.getfloat('grid', 'interval')
    TRANCHE_SIZE = config.getint('grid', 'tranche_size')
    FLEXIBILITY = config.getint('grid', 'flexibility')
    GRID_LEVELS = config.getint('grid', 'grid_levels')
    GRID_BASE = config.get('grid', 'base').upper()
    GRID_TYPE = config.get('grid', 'type').upper()

    LOGFILE = config.get('logging', 'logfile')

    #BLACKBOT = pw.Address(privateKey=PRIVATE_KEY)

    RFBGATEWAY = config.get('rfbnetwork', 'rfb_gateway')
    RFBGATEWAYPORT = config.getint('rfbnetwork', 'rfb_gateway_port')

    log("-" * 80)
    #log("          Address : %s" % BLACKBOT.address)
    log("  Amount Asset ID : %s" % amountAssetID)
    log("   Price Asset ID : %s" % priceAssetID)
    log("-" * 80)
    log("")
except:
    log("Error reading config file")
    log("Exiting.")
    exit(1)

def verifyDatabase():
    conn = sqlite.connect('RFBNetwork.db')
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM nodes')
        print('Table already exists')
    except:
        print('Creating table \'nodes\'')
        c.execute('CREATE TABLE nodes (\
            node_id INTEGER PRIMARY KEY,\
            node_host text NOT NULL UNIQUE,\
            node_port INTEGER NOT NULL,\
            node_account_address text NOT NULL)')
        print('Successfully created table \'nodes\'')
    conn.commit()
    conn.close()

def runTests():
    conn = sqlite.connect('RFBNetwork.db')
    c = conn.cursor()
    node_dict = {}
    try:
        nodes = c.execute('SELECT * FROM nodes').fetchall()
        for node in nodes:
            #print(node)
            node_dict[node[0]] = [node[1], node[2], node[3]]
    except Exception as e:
        print("Something went wrong with the DB while fetching list of nodes")
    conn.commit()
    conn.close()
    
    conn = sqlite.connect('RFBNetwork_tests.db')
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM test_results')
        print('Table already exists')
    except:
        print('Creating table \'test_results\'')
        c.execute('CREATE TABLE test_results (\
            test_id text PRIMARY KEY,\
            test_type text NOT NULL,\
            test_start text NOT NULL,\
            test_end text NOT NULL,\
            test_time text NOT NULL,\
            test_node_a_msg text NOT NULL,\
            test_node_b_msg text NOT NULL,\
            test_node_a_status text NOT NULL,\
            test_node_b_status text NOT NULL,\
            test_node_a_host text NOT NULL,\
            test_node_b_host text NOT NULL,\
            test_node_a_port INTEGER NOT NULL,\
            test_node_b_port INTEGER NOT NULL,\
            test_node_a_account_address text NOT NULL,\
            test_node_b_account_address text NOT NULL)')
        print('Successfully created table \'nodes\'')
    
    perm = permutations(node_dict.keys(), 2)
    list_of_tests = []
    for i in list(perm): 
        list_of_tests.append(i)
    random.shuffle(list_of_tests)
    list_of_test_results=[]
    test_results_timestamp = re.sub('-|\.|\s|:', '', datetime.utcnow().strftime("%b %d %Y %H:%M:%S UTC"))
    for i in list_of_tests:
        test_id=test_results_timestamp+'_'+str(i[0])+'_'+str(i[1])+'_d'
        test_type='download'
        test_start=datetime.utcnow()
        test_node_a_host=node_dict[i[0]][0]
        test_node_a_port=str(node_dict[i[0]][1])
        test_node_a_account_address=str(node_dict[i[0]][2])
        test_node_b_host=node_dict[i[1]][0]
        test_node_b_port=str(node_dict[i[1]][1])
        test_node_b_account_address=str(node_dict[i[1]][2])
        node_url = 'http://'+node_dict[i[0]][0]+':'+str(node_dict[i[0]][1])+'/downloadAPI/'+node_dict[i[1]][0]+';'+str(node_dict[i[1]][1])+';notel.png;'+test_id
        try:
            e = urllib.request.urlopen(node_url, timeout=1).read().decode('utf8')
            test_node_b_msg=json.loads(e)['msg']
            test_node_b_status=json.loads(e)['status']
            test_node_a_msg_part1=e
            test_node_a_status="OK"
            test_end=datetime.utcnow()
        except Exception as e:
            test_node_b_msg="NA"
            test_node_b_status="NA"
            test_node_a_msg_part1=re.sub('\'|<|>', '', str(e))
            test_node_a_status="NOK"
            test_end=datetime.utcnow()
        test_time=test_end-test_start
        if test_node_a_status == "OK" and test_node_b_status == "OK":
            node_url = 'http://'+node_dict[i[0]][0]+':'+str(node_dict[i[0]][1])+'/deleteAPI/downloads;'+test_id
            try:
                e = urllib.request.urlopen(node_url, timeout=1).read().decode('utf8')
                test_node_a_msg=test_node_a_msg_part1+' ; output of deleting: '+json.loads(e)['msg']
                test_node_a_status=json.loads(e)['status']
            except Exception as e:
                test_node_a_msg=test_node_a_msg_part1+' ; test result discarded as deleting failed: '+re.sub('\'|<|>', '', str(e))
                test_node_a_status="NOK"
        else:
            test_node_a_msg=test_node_a_msg_part1
        list_of_test_results.append([test_id, test_type, str(test_start), str(test_end), str(test_time), test_node_a_msg, test_node_b_msg, test_node_a_status, test_node_b_status, test_node_a_host, test_node_b_host, test_node_a_port, test_node_b_port, test_node_a_account_address, test_node_b_account_address])
        print(test_node_a_msg)
    #upload tests
        test_id=test_results_timestamp+'_'+str(i[0])+'_'+str(i[1])+'_u'
        test_type='upload'
        test_start=datetime.utcnow()
        test_node_a_host=node_dict[i[0]][0]
        test_node_a_port=str(node_dict[i[0]][1])
        test_node_a_account_address=str(node_dict[i[0]][2])
        test_node_b_host=node_dict[i[1]][0]
        test_node_b_port=str(node_dict[i[1]][1])
        test_node_b_account_address=str(node_dict[i[1]][2])
        node_url = 'http://'+node_dict[i[0]][0]+':'+str(node_dict[i[0]][1])+'/uploadAPI/'+node_dict[i[1]][0]+';'+str(node_dict[i[1]][1])+';notel.png;'+test_id
        try:
            e = urllib.request.urlopen(node_url, timeout=1).read().decode('utf8')
            test_node_b_msg_part1=json.loads(e)['msg']
            test_node_b_status=json.loads(e)['status']
            test_node_a_msg=e
            test_node_a_status="OK"
            test_end=datetime.utcnow()
        except Exception as e:
            test_node_b_msg_part1="NA"
            test_node_b_status="NA"
            test_node_a_msg=re.sub('\'|<|>', '', str(e))
            test_node_a_status="NOK"
            test_end=datetime.utcnow()
        test_time=test_end-test_start
        if test_node_a_status == "OK" and test_node_b_status == "OK":
            node_url = 'http://'+node_dict[i[1]][0]+':'+str(node_dict[i[1]][1])+'/deleteAPI/uploads;'+test_id
            try:
                e = urllib.request.urlopen(node_url, timeout=1).read().decode('utf8')
                test_node_b_msg=test_node_b_msg_part1+' ; output of deleting: '+json.loads(e)['msg']
                test_node_b_status=json.loads(e)['status']
            except Exception as e:
                test_node_b_msg=test_node_b_msg_part1+' ; test result discarded as deleting failed: '+re.sub('\'|<|>', '', str(e))
                test_node_b_status="NOK"
        else:
            test_node_b_msg=test_node_b_msg_part1
        list_of_test_results.append([test_id, test_type, str(test_start), str(test_end), str(test_time), test_node_a_msg, test_node_b_msg, test_node_a_status, test_node_b_status, test_node_a_host, test_node_b_host, test_node_a_port, test_node_b_port, test_node_a_account_address, test_node_b_account_address])
    #print(list_of_test_results)
    for i in list_of_test_results:
        #print(i)
        try:
            c.execute('INSERT INTO test_results(test_id, test_type, test_start, test_end, test_time, test_node_a_msg, test_node_b_msg, test_node_a_status, test_node_b_status, test_node_a_host, test_node_b_host, test_node_a_port, test_node_b_port, test_node_a_account_address, test_node_b_account_address) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (i[0], i[1], i[2], i[3], i[4], i[5], i[6], i[7], i[8], i[9], i[10], i[11], i[12], i[13], i[14]))
            print("test %s added to the DB" % test_id)
        except Exception as e:
            print(e)
    conn.commit()
    conn.close()


class CheckAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def check_ip(self, host, port, account_address):
        conn = sqlite.connect('RFBNetwork.db')
        c = conn.cursor()
        try:
            number_of_records = c.execute('SELECT COUNT(*) FROM nodes WHERE node_host=? AND node_port=? AND node_account_address=?', (host, port, account_address)).fetchone()
            #print(number_of_records[0])
            if number_of_records[0] == 1:
                e = host+':'+port+" is registered with address "+account_address
                e_status = "OK"
            else:
                e = host+':'+port+" is not registered with address "+account_address
                e_status = "NOK"
        except Exception as e:
            log("  Something went wrong with the DB while checking node : %s" % host+':'+port)
            log("  with BC address : %s" % account_address)
            e = "issue with the DB, error is:"+e
            e_status = "NOK"
        conn.commit()
        conn.close()
        return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'^(.*);(.*);(.*)$', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.check_ip(matchObj.group(1), matchObj.group(2), matchObj.group(3))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \"status\": "'+letssee_status+'"}'
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params", "status": "NOK"})

class RegisterAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def register_ip(self, host, port, account_address):
        node_url = 'http://'+host+':'+port+'/account'
        try:
            e = urllib.request.urlopen(node_url, timeout=2).read().decode('utf8')
            node_account_address = json.loads(e)['account_address']
            if account_address == node_account_address:
                conn = sqlite.connect('RFBNetwork.db')
                c = conn.cursor()
                try:
                    c.execute('REPLACE INTO nodes(node_host,node_port,node_account_address) VALUES(?, ?, ?)', (host, port, account_address))
                    log("  Registered node : %s" % host+':'+port)
                    log("  with BC address : %s" % account_address)
                    e = host+':'+port+" registered with address "+account_address
                    e_status = "OK"
                except Exception as e2:
                    log("  Something went wrong with the DB while registering node : %s" % host+':'+port)
                    log("  with BC address : %s" % account_address)
                    e = "issue with the DB, error is:"+e2
                    e_status = "NOK"
                conn.commit()
                conn.close()
            return e, e_status
        except Exception as e3:
            e_status = "NOK"
            e = "Cant access "+host+":"+str(port)+" "+str(e3)
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'^(.*);(.*);(.*)$', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.register_ip(matchObj.group(1), matchObj.group(2), matchObj.group(3))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \'status\': "'+letssee_status+'"}'
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params"})
        
class DeleteAPI(tornado.web.RequestHandler):
    def initialize(self, executor):
        self.executor = executor

    @tornado.concurrent.run_on_executor
    def delete_ip(self, host, port, token):
        try:
            if token == "my_delete_token_123abc!":
                conn = sqlite.connect('RFBNetwork.db')
                c = conn.cursor()
                try:
                    c.execute('DELETE FROM nodes WHERE node_host=? AND node_port=?', (host, port))
                    log("  Deleted node : %s" % host+':'+port)
                    e = host+':'+port+" deleted"
                    e_status = "OK"
                except Exception as e2:
                    log("  Something went wrong with the DB while deleting node : %s" % host+':'+port)
                    e = "issue with the DB, error is:"+e2
                    e_status = "NOK"
                conn.commit()
                conn.close()
            return e, e_status
        except Exception as e:
            e_status = "NOK"
            return e, e_status

    @tornado.gen.coroutine
    def get(self, test_params):
        matchObj = re.match( r'^(.*);(.*);(.*)$', test_params, re.M|re.I)
        if matchObj:
            letssee, letssee_status = yield self.delete_ip(matchObj.group(1), matchObj.group(2), matchObj.group(3))
            json_out = '{\"msg\": "'+re.sub('<|>', '', str(letssee))+'", \'status\': "'+letssee_status+'"}'
            self.finish(json_out)
        else:
            self.finish({"msg": "wrong test_params"})

class Application(tornado.web.Application):
    def __init__(self):
        script_path = os.path.join(os.path.dirname(__file__), 'data')
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        handlers = [
            (r"/", IndexHandler),
            (r'/registerAPI/(.+)', RegisterAPI, dict(executor=executor)),
            (r'/deleteAPI/(.+)', DeleteAPI, dict(executor=executor)),
            (r'/checkAPI/(.+)', CheckAPI, dict(executor=executor))
        ]
        tornado.web.Application.__init__(self, handlers, debug=True)

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        # get an existing address from seed
        #myAddress = pw.Address(seed='seven wrist bargain hope pattern banner plastic maple student chaos grit next space visa answer')
        #self.write(str(myAddress))
        #ip = get('https://api.ipify.org').text
        self.write({"msg": "this is RFBGateway"})

def main():
    verifyDatabase()
    trigger = CronTrigger(second='*/59')
    scheduler = TornadoScheduler()
    scheduler.add_job(runTests, trigger)
    scheduler.start()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(RFBGATEWAYPORT)
    print('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))
    try:
        tornado.ioloop.IOLoop.instance().start()
    except (KeyboardInterrupt, SystemExit):
        pass
    
if __name__ == "__main__":
    main()
