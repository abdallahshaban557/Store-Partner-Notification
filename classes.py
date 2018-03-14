from datetime import datetime

class Notification:
    OrderID = 100
    OrderCreationDate = 1
    OrderLineKeyID = 0
    StoreID = 0
    OrderLineStatus = 0
    OrderLineStatusUpdateDate = 0
    #NotificationCreationDate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #0 for not read - 1 for read
    ReadReceiptStatus = 0
    NotificationAlert = ""


class Store_Information:
    PushNotificationID = ""
    StoreID = 0
    Token = ""





