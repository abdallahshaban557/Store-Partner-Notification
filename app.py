import time
import json
from flask import Flask,request,jsonify
import os
#MongoDB client
from pymongo import MongoClient
#Push notification library
from flask_pushjack import FlaskAPNS

from apns2.client import APNsClient
from apns2.payload import Payload


#Path to the push certificate
config = {
    'APNS_CERTIFICATE': "./Apple_Certificate/pushcertificate.pem"
    }

app = Flask(__name__)

#update app config file with apple push certificate
app.config.update(config)
ios = FlaskAPNS()
ios.init_app(app)




#MongoDB connection URI - It currently uses the hostname of the docker instance
db_host = str(os.environ['db'])
client = MongoClient(db_host,27017, serverSelectionTimeoutMS=3000)


#Connection to the DB
db = client['store_partner_notification']

#Connection to the specific Collections
notification_records = db['store_partner_notification']
store_information = db['store_information']
notification_information = db['notification_information']



def sendpushnotification(DeviceToken, OrderID, StoreID, dev_flag):
    #Initiate APNs for the push notification service
    config.update({"APNS_SANDBOX" : dev_flag})
    app.config.update(config)
    
    #Alert body
    alert = {"Sucess" : True, "Message": "New BOPUS order is ready", "OrderID": OrderID}
    #send the push notification
    notification = ios.send(DeviceToken, alert, sound="default")
    
    
    
    token_hex = DeviceToken
    payload = Payload(alert="Hello World!", sound="default", badge=1)
    topic = 'com.petco.notifications'
    client1 = APNsClient('./Apple_Certificate/server.pem', use_sandbox=True, use_alternative_port=False)
    client1.send_notification(token_hex, payload, topic)
    
    
    
    return True


def getallnotificationrecords():
    
    notifications = []
    for notification in notification_records.find():
        notifications.append( {
            "OrderID" : int(notification['OrderID']),
            "OrderCreationDate" : notification["OrderCreationDate"],
            "StoreID" : int(notification["StoreID"]),
            "NotificationCreationDate" : notification["NotificationCreationDate"],
            "ReadReceiptStatus" : notification["ReadReceiptStatus"],
            }
        )
    return notifications



@app.route('/')
def hello():
    notification_array = []
    for notification in notification_records.find():
        notification_array.append(notification)

    return jsonify({"Success" :True})
    
@app.route('/deleteallnotifications', methods = ['DELETE'])
def deleteallnotifications():
    notification_records.delete_many({})
    return jsonify({"Success" : True})


#endpoint to get all of the notifications in MongoDB
@app.route('/getallnotificationrecords')
def getallnotificationrecordsapi():
    allnotifications = getallnotificationrecords()
    return jsonify(allnotifications)



#New order submitted from OMS
@app.route('/addorder', methods=['POST'])
def addorder():    
    #change request received through endpoint to JSON
    Payload = request.json
    #create the insert object into DB
    BOPUS_Order = {
            "OrderID" : int(Payload["OrderID"]),
            "OrderCreationDate" : Payload["OrderCreationDate"],
            "StoreID" : int(Payload["StoreID"]),
            "NotificationCreationDate" : time.strftime('%x %X'),
            "ReadReceiptStatus" : 0,
    }
    #inset object into MongoDB
    notification_records.insert_one(BOPUS_Order)
    DeviceToken = store_information.find_one({"StoreID" : BOPUS_Order["StoreID"]})
    #sendpushnotification(DeviceToken["DeviceToken"], Payload["OrderID"],Payload["StoreID"], False)
    return jsonify({"Sucess" : True})

#Indicate that the store received the notification
@app.route('/readnotification', methods=['POST'])
def readnotification():
    Payload = request.json
    StoreID = int(Payload["StoreID"])
    #OrderID = int(Payload["OrderID"])
    for notification in notification_records.find({"StoreID" : StoreID}):
        notification["ReadReceiptStatus"] = 1
        notification_records.save(notification)
    return jsonify({"Success" : True})


#register device token
@app.route('/registerdevice', methods=['POST'])
def registerdevicetoken():
    #change request to JSON and grab the required variables
    Payload = request.json
    DeviceToken = Payload["DeviceToken"]
    StoreID = Payload["StoreID"]
    #check if the store exists in MongoDB
    Device_Exists = store_information.find_one({"DeviceToken" : DeviceToken})

    if (Device_Exists != None):
        store_information.update_many({"DeviceToken" : DeviceToken}, {"$set": {
            "DeviceToken": DeviceToken,
            "StoreID":StoreID
            }
        })
    else:
        store_information.save({"DeviceToken" : DeviceToken, "StoreID" : StoreID})

    return jsonify({"Success" : True})


@app.route('/getallregistereddevices', methods=['GET'])
def getallregistereddevices():
    #change request to JSON and grab the required variables
    Registerd_Devices = []
    for device in store_information.find():
        Registerd_Devices.append( {
            "StoreID" : int(device["StoreID"]),
            "DeviceToken" : device["DeviceToken"]
            }
        )
    return jsonify({"Success" : True , "Payload" : Registerd_Devices})


@app.route('/deletealldevices', methods=['DELETE'])
def deletealldevices():
    #change request to JSON and grab the required variables
    store_information.delete_many({})
    return jsonify({"Success" : True})



@app.route('/sendpushnotification', methods=['POST'])
def pushnotification():
    Payload = request.json
    notification = sendpushnotification(Payload["DeviceToken"], Payload["OrderID"],Payload["StoreID"], Payload["dev_flag"])
    return jsonify({"Sucess": True, "Payload" : str(notification)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)