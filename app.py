import time
import json
from flask import Flask,request,jsonify
#MongoDB client
from pymongo import MongoClient
#Push notification library
from flask_pushjack import FlaskAPNS

#Path to the push certificate
config = {
    'APNS_CERTIFICATE': './Apple_Certificate/newfile.pem>'
}


app = Flask(__name__)

#update app config file with apple push certificate
app.config.update(config)




#MongoDB connection URI - It currently uses the hostname of the docker instance
client = MongoClient('fccd6dd3ab02',27017)

#Connection to the DB
db = client['store_partner_notification']

#Connection to the specific Collections
notification_records = db['store_partner_notification']
store_information_records = db['store_information']
notification_information = db['notification_information']



def sendpushnotification(pushnotification_token,store_id, dev_prod_flag):
    #Initiate APNs for the push notification service
    client = FlaskAPNS()
    client.init_app(app)

    #Alert body
    alert = "New BOPUS order is ready"
    #send the push notification
    res = client.send(pushnotification_token, alert, sound='default')

    return jsonify({"Success" : True})


def getallnotificationrecords():
    
    notifications = []
    for notification in notification_records.find():
        notifications.append( {
            "OrderID" : notification['OrderID'],
            "OrderCreationDate" : notification["OrderCreationDate"],
            "StoreID" : notification["StoreID"],
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
            "OrderID" : Payload["OrderID"],
            "OrderCreationDate" : Payload["OrderCreationDate"],
            "StoreID" : Payload["StoreID"],
            "NotificationCreationDate" : time.strftime('%x %X'),
            "ReadReceiptStatus" : 0,
    }
    #inset object into MongoDB
    notification_records.insert_one(BOPUS_Order)

    return jsonify({"Sucess" : True})

#Indicate that the store received the notification
@app.route('/readnotification', methods=['POST'])
def readnotification():
    StoreID = int(request.form["StoreID"])
    for notification in notification_records.find({"StoreID" : StoreID}):
        notification["ReadReceiptStatus"] = 1
        notification_records.save(notification)
    return 0

#trigger push notifications - incomplete
@app.route('/sendnotification', methods=['POST'])
def sendnotification():
    #turn request to JSON and grab the required variables
    Payload = request.json
    DeviceToken = Payload["DeviceToken"]
    StoreID = Payload["StoreID"]
    dev_prod_flag = bool(Payload["dev_prod_flag"])

    #send notification
    send = sendpushnotification(DeviceToken, StoreID, dev_prod_flag )
    for notification in notification_records.find({"StoreID" : StoreID}):
        notification["ReadReceiptStatus"] = 1
        notification_records.save(notification)

    return jsonify({"Success" : True , "StoreID" : StoreID})


#register device token
@app.route('/registerdevicetoken', methods=['POST'])
def registerdevicetoken():
    Payload = request.json
    StoreID = Payload["StoreID"]
    for notification in notification_records.find({"StoreID" : StoreID}):
        notification["ReadReceiptStatus"] = 1
        notification_records.save(notification)
    return True



if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)