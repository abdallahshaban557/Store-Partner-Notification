import time
import json
from flask import Flask,request, Response,jsonify
import requests
from requests.auth import HTTPBasicAuth
from functools import wraps
#Push notification library
from apns2.client import APNsClient
from apns2.payload import Payload
#DynamoDB client
import boto3
from boto3.dynamodb.conditions import Key, Attr
#Needed to create primary hashed key for the dynamodb items
import uuid
from flask_apscheduler import APScheduler

app = Flask(__name__)

#Configuration for the queue for resending notification
# class Config(object):
#     JOBS = [
#         {
#             'id': 'job1',
#             'func': 'app:resend_notification',
#             'trigger': 'interval',
#             'seconds': 300
#         }
#     ]
#     SCHEDULER_API_ENABLED = True

#The function responsible for scanning through the BOPUS orders, and sending a reminder notification
def resend_notification():    
    Overdue_Notifications = notification_records.scan( FilterExpression=Attr('ReadReceiptStatus').eq(0) )
    Pending_Store_Orders = []
    for notification in Overdue_Notifications['Items']:
        if(notification["StoreID"] in Pending_Store_Orders):
            continue
        else:
            Pending_Store_Orders.append(notification["StoreID"])
    for Pending_Stores in Pending_Store_Orders:
        All_Devices = store_information.scan( FilterExpression=Attr('StoreID').eq(Pending_Stores))
        for Device in All_Devices['Items']:
            try:    
                #print('Sending Notification')
                print("Sending")
                sendpushnotification(Device["DeviceToken"], "Reminder" , 0, 0)
            except:
                print("ERROR Sending")
                store_information.delete_item(
                    Key={
                    "ID" : Device["ID"] 
                    }
                )
                pass
            
            
#Checks username and password
def check_auth(username, password):
    return username == 'petco' and password == 'petco123'
#Returns if authenticated or not
def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})
#creates the decorator the enables auth on endpoints
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

#DynamoDB connection
client = boto3.resource('dynamodb', region_name='us-east-1')


#Connection to the specific Tables  
notification_records = client.Table('store_partner_notification')
store_information = client.Table('store_information')

def sendpushnotification(DeviceToken, OrderID, StoreID, dev_flag):
    #send the push notification
    custom = {'launchURL': 'x-com.petco.wrapper.sim://launch' }
    payload = Payload(alert= "New BOPUS order is ready", sound="popcorn.wav", badge=0, custom=custom)
    topic = 'com.petco.notifications'
    IOS_Client = APNsClient('./Apple_Certificate/server1.pem', use_sandbox= dev_flag, use_alternative_port=False)
    IOS_Client.send_notification(DeviceToken, payload, topic)
    return True

def sendtheatro(StoreID, OrderID, Dev_Flag, TimeStamp):
    #send request to SXSW notification service
    url = 'https://0dcetbmqm9.execute-api.us-east-1.amazonaws.com/prod/addorder'
    PARAMS = {
        'Content-Type' : 'application/json'
    }

    Body = {
        'StoreID' : StoreID,
        'OrderID' : OrderID,
        'dev_flag' : Dev_Flag,
        'OrderCreationDate' : TimeStamp
    }
    r = requests.post(url, headers = PARAMS, data = json.dumps(Body), auth = HTTPBasicAuth('notificationservice', 'PtQL[B3qn4y7GuWDfK;zN7Ee9gPu'))
    
    return True

@app.route('/')
def hello():
    return jsonify({"Success" :True})
    
@app.route('/deleteallreadnotifications', methods = ['DELETE'])
@requires_auth
def deleteallreadnotifications():
    Notifications_Search = notification_records.scan( FilterExpression=Attr('ReadReceiptStatus').eq(1))
    for notification in Notifications_Search["Items"]:
        notification_records.delete_item(Key = {
            "ID" : notification["ID"]
        })
    return jsonify({"Success" : True})


@app.route('/deleteallnotifications', methods = ['DELETE'])
@requires_auth
def deleteallnotifications():
    Notifications_Search = notification_records.scan()
    for notification in Notifications_Search["Items"]:
        notification_records.delete_item(Key = {
            "ID" : notification["ID"]
        })
    return jsonify({"Success" : True})

#endpoint to get all of the notifications in DynamoDB
@app.route('/getallnotificationrecords')
@requires_auth
def getallnotificationrecords():
    notifications = []
    Notifications_Search = notification_records.scan() 
    for notification in Notifications_Search["Items"]:
        notifications.append({
            "OrderID" : notification["OrderID"],
            "OrderCreationDate" : notification["OrderCreationDate"],
            "StoreID" : int(notification["StoreID"]),
            "NotificationCreationDate" : notification["NotificationCreationDate"],
            "ReadReceiptStatus" : int(notification["ReadReceiptStatus"])
            }
        )
    return jsonify({"Success" : True , "Payload" : notifications})

#New order submitted from OMS
@app.route('/addorder', methods=['POST'])
@requires_auth
def addorder():    
    #change request received through endpoint to JSON
    Payload = request.json
    #create the insert object into DB
    BOPUS_Order = {
                "ID" : uuid.uuid4().hex,
                "OrderID" : Payload["OrderID"],
                "OrderCreationDate" : Payload["OrderCreationDate"],
                "StoreID" : int(Payload["StoreID"]),
                "NotificationCreationDate" : time.strftime('%x %X'),
                "ReadReceiptStatus" : 0,
    }
    #inset object into Dynamodb - commented out based on requirement from store Ops
    # if Payload["dev_flag"] == False:
    #     notification_records.put_item(Item = BOPUS_Order)

    response = store_information.scan( FilterExpression=Attr('StoreID').eq(Payload["StoreID"]) )
    #Find all devices attached to the specified store, and send notification - Try/except to skip if a notification error occurs
    if Payload["dev_flag"] == False:
        for Device in response['Items']: 
            sendpushnotification(Device["DeviceToken"], Payload["OrderID"],Payload["StoreID"], False)
            print("test")
    print(Payload)
    sendtheatro(Payload["StoreID"],Payload["OrderID"], Payload["dev_flag"], Payload["OrderCreationDate"])        
    return jsonify({"Success" : True})    

#Indicate that the store received the notification
@app.route('/readnotification', methods=['POST'])
@requires_auth
def readnotification():
    Payload = request.json
    StoreID = int(Payload["StoreID"])
    Notification_Search = notification_records.scan( FilterExpression=Attr('StoreID').eq(StoreID))    
    for notification in Notification_Search["Items"]:      
        # notification_records.update_item(
        #     Key= {
        #         "ID" : notification["ID"]
        #     },
        #     UpdateExpression='SET ReadReceiptStatus = :val1',
        # ExpressionAttributeValues={
        #     ':val1': 1
        # })
        notification_records.delete_item(
            Key= {
                "ID" : notification["ID"]
            }
        )
    return jsonify({"Success" : True})

#register device token
@app.route('/registerdevice', methods=['POST'])
@requires_auth
def registerdevicetoken():
    #change request to JSON and grab the required variables
    Payload = request.json
    DeviceToken = Payload["DeviceToken"]
    StoreID = Payload["StoreID"]
    #check if the store exists in MongoDB
    Device_Search = store_information.scan( FilterExpression=Attr('DeviceToken').eq(DeviceToken))    
  
    if (Device_Search["Count"] == 0):
        store_information.put_item(Item = {"ID" : uuid.uuid4().hex, "DeviceToken" : DeviceToken, "StoreID" : StoreID})
    else:
        for Device in Device_Search["Items"]:
            store_information.update_item(
        Key={
            'ID': Device["ID"]
        },
        UpdateExpression='SET StoreID = :val1',
        ExpressionAttributeValues={
            ':val1': StoreID
        }
        )   
    return jsonify({"Success" : True})

@app.route('/getallregistereddevices', methods=['GET'])
@requires_auth
def getallregistereddevices():
    #change request to JSON and grab the required variables
    Registerd_Devices = []
    #find all devices
    Devices = store_information.scan()
    for device in Devices["Items"]:
        Registerd_Devices.append( {
            "StoreID" : int(device["StoreID"]),
            "DeviceToken" : device["DeviceToken"]
            }
        )
    return jsonify({"Success" : True , "Payload" : Registerd_Devices})

@app.route('/deletealldevices', methods=['DELETE'])
@requires_auth
def deletealldevices():
    #change request to JSON and grab the required variables
    response = store_information.scan()
    for device in response['Items']:
        store_information.delete_item(Key={"ID" : device["ID"]})     
    return jsonify({"Success" : True})

@app.route('/sendpushnotification', methods=['POST'])
@requires_auth
def pushnotification():
    Payload = request.json
    sendpushnotification(Payload["DeviceToken"], Payload["OrderID"],Payload["StoreID"], Payload["dev_flag"])
    return jsonify({"Sucess": True})

#Finds all of the registered devices for a store
@app.route('/CheckRegisteredDevices/<int:StoreID>', methods=['GET'])
@requires_auth
def CheckRegisteredDevices(StoreID):
    Registerd_Devices = []
    Devices = store_information.scan(FilterExpression=Attr('StoreID').eq(StoreID) )
    for device in Devices["Items"]:
        Registerd_Devices.append( {
            "StoreID" : int(device["StoreID"]),
            "DeviceToken" : device["DeviceToken"]
            }
        )
    return jsonify({"Success" : True , "Payload" : Registerd_Devices})

#Find alerts that have not been acknowledged in a store
@app.route('/CheckUnreadAlerts/<int:StoreID>', methods=['GET'])
@requires_auth
def CheckUnreadAlerts(StoreID):
    Unread_Alerts = []
    Alerts = notification_records.scan(FilterExpression=Attr('StoreID').eq(StoreID) & Attr('ReadReceiptStatus').eq(0))
    for Alert in Alerts["Items"]:
        Unread_Alerts.append( {
            "OrderID" : Alert["OrderID"],
            "ReadReceiptStatus" : int(Alert["ReadReceiptStatus"])
            }
        )
    return jsonify({"Success" : True , "Payload" :  Unread_Alerts})


if __name__ == "__main__":
    #Configure the queue for resending notifications
    # app.config.from_object(Config())
    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # scheduler.start()



    #Running the flask app
    app.run(host="0.0.0.0", ssl_context='adhoc') 