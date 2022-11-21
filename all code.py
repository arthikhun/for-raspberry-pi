import requests
import json
import asyncio
from bleak import BleakScanner
import time
from datetime import datetime
import threading
import serial
import pynmea2
import obd

api_url = "https://mit.bu.ac.th/school-bus"
board_mac = "11:22:33:44:55:66"
start_session = False
parse_json = ''
arr_mac = []
arr_child_id = []
arr_recheck_mac = []#[0 0 1 10 15]จำนวนครั้งที่ scacn เจอ
arr_incar_time = []
arr_last_time = []
white_list = set({})
scan_record =[]
incar = []#['08:2E:FB:EE:3C:E7', 'EE:42:99:A6:01:F1']
eiei = 0

def set_default():
    global parse_json,arr_mac,arr_child_id,arr_recheck_mac,white_list,scan_record,incar
    parse_json = ''
    arr_mac = []
    arr_child_id = []
    arr_recheck_mac = []
    white_list = set({})
    scan_record = []#[set(), {'EE:42:99:A6:01:F1'}, {'EE:42:99:A6:01:F1'}, {'EE:42:99:A6:01:F1'}, set(), {'EE:42:99:A6:01:F1'}, {'EE:42:99:A6:01:F1', '08:2E:FB:EE:3C:E7'}, {'EE:42:99:A6:01:F1'}, set(), {'08:2E:FB:EE:3C:E7'}, {'EE:42:99:A6:01:F1'}, {'EE:42:99:A6:01:F1'}, {'EE:42:99:A6:01:F1'}, {'08:2E:FB:EE:3C:E7'}]#[set(),set(),set(),set(),set(),set(),set(),set(),set(),set()]
    incar = []

def loop_check_session():
    threading.Timer(30.0, loop_check_session).start()
    global start_session
    response_API = requests.get(
        api_url+"/api/v1/buses/sessions/?board_mac_address="+board_mac)
    print('='*40)
    print(response_API.status_code)
    # if response_API.status_code == 200 and start_session == False:
    #     start_session = True
    #     #print(response_API.json())
    #     print('start secsion 200 loop')
    #     print('loop',start_session)
    #     print('='*40)
    #     return 
    if response_API.status_code == 400 and start_session == True :
        start_session = False
        print('='*40)
        return

def check_session():
    global start_session
    response_API = requests.get(
        api_url+"/api/v1/buses/sessions/?board_mac_address="+board_mac)
    print(response_API.status_code)
    print(start_session)
    if response_API.status_code == 200 and start_session == False:
        start_session = True
        #print(response_API.json())
        print('start secsion 200')
        return response_API
    elif response_API.status_code == 400 and start_session == True :
        start_session = False
        return

def post_passenger_state(id,data):
    response_API = requests.post(
        api_url+"/api/v1/buses/"+str(parse_json["data"]["bus"]["id"])+"/passengers/"+str(id)+"/",
        json={'state':data})
    print('post check in ',data,response_API.status_code)

def post_latlon_rpm(lat,lon,speed,state = 2):
    # print(type(lat))
    # print(type(lon))
    # print(type(speed))
    # print(type(state))
    # print(lat,lon,speed,state)
    if speed==0:
        state = 3
    
    response_API = requests.post(
        api_url+"/api/v1/buses/"+str(parse_json["data"]["bus"]["id"])+"/logs/",
        json={'state_id':state,
              'driver_id':parse_json["data"]["driver"]["id"],
              'location':str(lat+","+lon),
              'speed':speed})
    print(response_API.status_code)
    
    # response_API = requests.post(
    #     api_url+"/api/v1/buses/4/logs/",
    #     json={'state_id':2,
    #           'driver_id':19,
    #           'location':"14.0125133,100.627695",
    #           'speed':"88"})
    # print(response_API.status_code)
    
def add_whitelist(raw_json):
    global white_list,parse_json,arr_mac,arr_child_id,arr_incar_time,arr_last_time
    parse_json = json.loads(raw_json.text)
    print(parse_json)
    listMac = parse_json["data"]["destination"]["children_collection"]
    for child in listMac:
        white_list.add(child["mac_address"])
        arr_child_id.append(child["id"])
        arr_mac.append(child["mac_address"])
        arr_recheck_mac.append(0)
        arr_incar_time.append(0.0)
        arr_last_time.append(0.0)
    print(white_list)
    print(arr_child_id)
    print(arr_mac)
    print(arr_recheck_mac)
    print(arr_incar_time)
    print(arr_last_time)

async def scan():
    global eiei
    eiei+=1
    if eiei >= 5 and eiei <16:
        time.sleep(8)
        scan_record.insert(0, set({}))
    else:
        set_device = set({})
        scan = await BleakScanner.discover(8)
        for device in scan:
            macaddress = device.address
            if macaddress in white_list:
                print(device, device.rssi)
                if device.rssi > -90:  # -90 = กี่เมตร
                    set_device.add(macaddress)
                    arr_recheck_mac[arr_mac.index(macaddress)] +=1
        print(arr_recheck_mac)
        print('found this round =', set_device)
        scan_record.insert(0, set_device)
        #scan_record.insert(0,set())
    if len(scan_record) > 15:
        del scan_record[-1]

def check_in():
    global incar,scan_record,arr_last_time
    if len(scan_record) < 3:
        return
    else:
        friSet = scan_record[0]
        secSet = scan_record[1]
        thiSet = scan_record[2]
        #fouSet = scan_record[3]
        lenArr = len(incar)
        checked = friSet.intersection(secSet, thiSet)
        print('= ', checked)
        for address in checked:
            if address not in incar:  # set or array choose later
                #incar.add(address)
                incar.append(address)
        if len(incar) > lenArr:#if have add in incar sent api check in
            x = -(len(incar)-lenArr)
            for i in range(x,0,1):
                print('incar', incar[i])  # send data to server\
                #print(parse_json["data"]["destination"]["children_collection"])
                arr_last_time[arr_mac.index(incar[i])] = time.time()
                post_passenger_state(arr_child_id[arr_mac.index(incar[i])],"ENTER")

def check_out():
    discards = []
    global incar,scan_record,arr_incar_time
    for address in incar:
        #print('in loop out')
        notFound = 0
        for record in scan_record:
            if address not in record:
                notFound += 1
        if notFound > 10:
            discards.append(address)
    if discards != []:
        for mac in discards:
            print('for discard', mac)  # send data to server
            index_arr = arr_mac.index(mac)
            arr_incar_time[index_arr] = time.time() - arr_last_time[index_arr]
            #if เวลาบนรถ
            if arr_incar_time[index_arr] >= 600: #stay in car > 10 minute 
                post_passenger_state(arr_child_id[arr_mac.index(mac)],"LEAVE")
            else:
                post_passenger_state(arr_child_id[arr_mac.index(mac)],"NOT_YET_ENTER")
            print('before dis', incar)
            incar.remove(mac)
            print('after dis', incar)

def re_check():
    global incar,arr_last_time
    print('Hi re-check')
    for i in range(len(arr_recheck_mac)):
        if arr_recheck_mac[i] > 10:
            macaddress = arr_mac[i]
            print('line 188 mac = ',macaddress)
            if macaddress not in incar:
                incar.append(macaddress)
                print('line 193 = ',arr_child_id[i])
                arr_last_time[i] = time.time()
                post_passenger_state(arr_child_id[i],"ENTER")

def get_lat_long():
    # port="/dev/ttyAMA0"
    """
    port = "/dev/ttyAMA0"
    ser = serial.Serial(port, baudrate=9600, timeout=0.5)

    #dataout = pynmea2.NMEAStreamReader()#? ark god
    newdata = ser.readline()

    if newdata[0:6] == b"$GPRMC":
        m = newdata.decode('utf-8')
        newmsg = pynmea2.parse(m)
        lat = newmsg.latitude
        lng = newmsg.longitude
        gps = "Latitude=" + str(lat) + " and Longitude=" + str(lng)
        print(gps)
    return lat,lng
    """
    return "14.012513333","100.627695555"

def get_obd():
    """
    connection = obd.OBD() # auto-connects to USB or RF port

    cmd = obd.commands.SPEED # select an OBD command (sensor)

    response = connection.query(cmd) # send the command, and parse the response
    if not response.is_null():
        return str(response.value.magnitude)#ทดสอบตรงนี้เพิ่มเติม
    else:
        return None
    # print(response.value) # returns unit-bearing values thanks to Pint
    """
    return "40" 

def main():
    global white_list
    while start_session == False:
        time.sleep(5)#30
        raw_data = check_session()
    loop_check_session()
    scan_count = 0
    while start_session:
        if white_list == set():
            add_whitelist(raw_data)
        print('-'*40)
        #start_time = time.time()
        print(datetime.now())
        scan_count += 1
        print(len(scan_record), "Count = ", scan_count)
        asyncio.run(scan())
        print('record =', scan_record)
        check_in()#ก่อน check in check out ให้ดูสถานะก่อน
        if scan_count >= 15:
            global arr_recheck_mac
            re_check()
            scan_count = 0
            arr_recheck_mac = [0 for i in range(len(arr_mac))]
        check_out()
        lat,lon = get_lat_long()
        rpm = get_obd()
        post_latlon_rpm(lat,lon,rpm)
    set_default()
        #print(time.time() - start_time)
    #เมื่อ start session = False ลบ whitelist set count

if __name__ == "__main__":
    while True:
        main()
        print('wow')
    #post_latlon_rpm(1,2,3)
    # api lat lon and speed