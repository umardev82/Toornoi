# toornoi_main/notifications.py
import requests
from django.conf import settings

def send_push_notification(user_external_ids, title, message, additional_data=None):
    """
    Sends a push notification via OneSignal.
    
    Args:
        user_external_ids (list): A list of external user IDs (as strings) to target.
        title (str): The notification title.
        message (str): The notification message.
        additional_data (dict): Optional additional data to send with the notification.
        
    Returns:
        dict: The JSON response from OneSignal.
    """
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}"
    }
    
    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "include_external_user_ids": user_external_ids,
        "headings": {"en": title},
        "contents": {"en": message},
        "data": additional_data or {}
    }
    
    response = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)
    return response.json()
