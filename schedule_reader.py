#!/usr/bin/env python3
"""
Google Calendar Schedule Reader
Reads tomorrow's schedule and emails it to team leader
"""

import os
import datetime
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz
import base64
from email.mime.text import MIMEText


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/gmail.send']

# Email configuration
SENDER_EMAIL = "kunalvsethia@gmail.com"
RECIPIENT_EMAIL = "kunalvsethia@gmail.com"  # Change this to your team leader's email
EMAIL_SUBJECT = "Office Schedule Update"

# Timezone configuration
TIMEZONE = 'Asia/Kolkata'  # Indian timezone

def authenticate():
    """Authenticate and return service objects for Calendar and Gmail"""
    creds = None
    
    # Token file stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    # Build service objects
    calendar_service = build('calendar', 'v3', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    return calendar_service, gmail_service

def get_tomorrow_events(calendar_service):
    """Get all events for tomorrow"""
    # Get timezone
    tz = pytz.timezone(TIMEZONE)
    
    # Calculate tomorrow's date
    now = datetime.datetime.now(tz)
    tomorrow = now + datetime.timedelta(days=1)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Convert to ISO format for API
    time_min = tomorrow_start.isoformat()
    time_max = tomorrow_end.isoformat()
    
    print(f"Fetching events for {tomorrow_start.strftime('%A, %B %d, %Y')}")
    print(f"Debug - Time range: {time_min} to {time_max}")
    print(f"Debug - Calendar ID: primary")
    
    try:
        # Call the Calendar API
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events, tomorrow_start
        
    except HttpError as error:
        print(f'An error occurred: {error}')
        return [], tomorrow_start

def format_events_for_email(events, date):
    """Format events into a readable email"""
    if not events:
        return f"No events scheduled for {date.strftime('%A, %B %d, %Y')}"
    
    email_body = f"Schedule for {date.strftime('%A, %B %d, %Y')}:\n\n"
    
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        # Parse the datetime
        if 'T' in start:  # This is a timed event
            start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Convert to local timezone
            tz = pytz.timezone(TIMEZONE)
            start_dt = start_dt.astimezone(tz)
            end_dt = end_dt.astimezone(tz)
            
            time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
        else:  # All-day event
            time_str = "All Day"
        
        summary = event.get('summary', 'No Title')
        location = event.get('location', '')
        
        email_body += f"• {time_str}: {summary}"
        if location:
            email_body += f" (Location: {location})"
        email_body += "\n"
    
    return email_body

def send_email(gmail_service, body_text):
    """Send email with the schedule"""
    try:
        message = MIMEText(body_text)
        message['to'] = RECIPIENT_EMAIL
        message['from'] = SENDER_EMAIL
        message['subject'] = EMAIL_SUBJECT
        
        # Encode the message
        encoded_message = base64.urlsafe_b64encode(
            message.as_bytes()).decode()
        
        create_message = {
            'raw': encoded_message
        }
        
        # Send the message
        send_message = gmail_service.users().messages().send(
            userId="me", body=create_message).execute()
        
        print(f"Email sent successfully! Message Id: {send_message['id']}")
        return True
        
    except HttpError as error:
        print(f'An error occurred while sending email: {error}')
        return False

def main():
    """Main function"""
    print("Google Calendar Schedule Reader")
    print("=" * 40)
    
    # Authenticate
    print("Authenticating...")
    calendar_service, gmail_service = authenticate()
    
    # Get tomorrow's events
    print("\nFetching tomorrow's events...")
    events, tomorrow_date = get_tomorrow_events(calendar_service)
    
    # Format events
    email_body = format_events_for_email(events, tomorrow_date)
    print("\nSchedule to be sent:")
    print("-" * 40)
    print(email_body)
    print("-" * 40)
    
    # Send email
    print("\nSending email...")
    if send_email(gmail_service, email_body):
        print("✓ Schedule sent successfully!")
    else:
        print("✗ Failed to send schedule")

if __name__ == '__main__':
    main()