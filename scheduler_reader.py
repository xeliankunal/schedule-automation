#!/usr/bin/env python3
"""
Google Calendar Schedule Reader - Consolidated Universal Version
Works in both local and GitHub Actions environments with full feature set
"""

import os
import datetime
import json
import base64
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz
from email.mime.text import MIMEText

# ============== EASY CONFIGURATION ==============
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL', 'kunal@insursa.com')
SENDER_EMAIL = "kunalvsethia@gmail.com"
TIMEZONE = 'Asia/Kolkata'

# Schedule times (24-hour format HH:MM)
SCHEDULE_TIME = os.environ.get('SCHEDULE_TIME', '21:00')  # 9:00 PM IST
SEND_REMINDER = os.environ.get('SEND_REMINDER', 'true').lower() == 'true'
REMINDER_MINUTES = 30

# Company details
COMPANY_NAME = "Insursa"
SKIP_WEEKENDS = True
# ================================================

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/gmail.send']

def is_github_actions():
    """Check if running in GitHub Actions environment"""
    return os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

def authenticate():
    """Authenticate and return service objects for Calendar and Gmail"""
    creds = None
    
    if is_github_actions():
        print("🔧 Running in GitHub Actions environment")
        try:
            # Try to use service account if available
            from google.oauth2 import service_account
            
            # Check if service account key is available
            if os.path.exists('service-account-key.json'):
                print("📋 Using service account authentication")
                creds = service_account.Credentials.from_service_account_file(
                    'service-account-key.json', scopes=SCOPES)
            else:
                print("⚠️  Service account not found - using notification mode")
                return None, None
                
        except Exception as e:
            print(f"❌ GitHub Actions authentication error: {e}")
            return None, None
    else:
        print("🖥️  Running in local environment")
        # Local authentication with token persistence
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired token...")
                creds.refresh(Request())
            else:
                print("🔐 Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
    
    if creds:
        try:
            calendar_service = build('calendar', 'v3', credentials=creds)
            gmail_service = build('gmail', 'v1', credentials=creds)
            print("✅ Authentication successful")
            return calendar_service, gmail_service
        except Exception as e:
            print(f"❌ Service creation error: {e}")
            return None, None
    else:
        return None, None

def check_action_needed():
    """Determine what action to take based on current time"""
    # In GitHub Actions, we run on schedule, so always send schedule
    if is_github_actions():
        return 'schedule'
    
    # For local runs, check if we're in test mode
    if os.environ.get('TEST_MODE') == 'true':
        return 'test'
    
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    
    # Parse schedule time
    schedule_hour, schedule_min = map(int, SCHEDULE_TIME.split(':'))
    schedule_dt = now.replace(hour=schedule_hour, minute=schedule_min, second=0)
    reminder_dt = schedule_dt - datetime.timedelta(minutes=REMINDER_MINUTES)
    
    # Check if we're within 5 minutes of any action time
    reminder_diff = abs((now - reminder_dt).total_seconds())
    schedule_diff = abs((now - schedule_dt).total_seconds())
    
    if SEND_REMINDER and reminder_diff < 300:
        return 'reminder'
    elif schedule_diff < 300:
        return 'schedule'
    else:
        return 'test'  # For manual testing

def get_tomorrow_events(calendar_service):
    """Get all events for tomorrow"""
    if not calendar_service:
        return [], datetime.datetime.now(pytz.timezone(TIMEZONE)) + datetime.timedelta(days=1), 'no_auth'
    
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    tomorrow = now + datetime.timedelta(days=1)
    
    # Check if we should skip
    if SKIP_WEEKENDS:
        # Skip Saturday/Sunday unless today is Sunday (for Monday)
        if tomorrow.weekday() == 5:  # Tomorrow is Saturday
            return None, tomorrow, 'weekend'
        elif tomorrow.weekday() == 6 and now.weekday() != 6:  # Tomorrow is Sunday
            return None, tomorrow, 'weekend'
    
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)
    
    print(f"📅 Fetching events for {tomorrow.strftime('%A, %B %d, %Y')}")
    
    try:
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=tomorrow_start.isoformat(),
            timeMax=tomorrow_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return [], tomorrow, 'holiday'
        
        return events, tomorrow, 'normal'
        
    except HttpError as error:
        print(f'❌ Calendar API error: {error}')
        return [], tomorrow, 'error'

def format_reminder_email(tomorrow_date):
    """Format reminder email"""
    return f"""Dear Team,

This is a friendly reminder to update tomorrow's calendar ({tomorrow_date.strftime('%A, %B %d')}) if needed.

Please ensure all meetings and schedules are properly reflected in Google Calendar.

The updated schedule will be sent at {format_time_12hr(SCHEDULE_TIME)}.

Best regards,
{COMPANY_NAME} Automation System
"""

def format_holiday_email(tomorrow_date):
    """Format holiday email"""
    return f"""Dear Team,

Tomorrow, {tomorrow_date.strftime('%A, %B %d, %Y')} appears to be a holiday or day off.

No events are scheduled in the calendar.

Enjoy your day off!

Best regards,
{COMPANY_NAME} Automation System
"""

def format_weekend_email(tomorrow_date):
    """Format weekend skip email"""
    return f"""Dear Team,

Tomorrow is {tomorrow_date.strftime('%A, %B %d, %Y')} - Weekend.

Schedule emails are not sent for weekends.

Have a great weekend!

Best regards,
{COMPANY_NAME} Automation System
"""

def format_github_actions_email():
    """Format GitHub Actions notification email"""
    return f"""Dear Team,

🤖 GitHub Actions Schedule Automation Status

This is an automated notification from your Google Calendar Schedule Reader.

✅ Status: GitHub Actions workflow executed successfully at {datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %I:%M %p %Z')}

📋 Current Configuration:
- Sender: {SENDER_EMAIL}
- Recipient: {RECIPIENT_EMAIL}
- Timezone: {TIMEZONE}
- Schedule: Daily at {format_time_12hr(SCHEDULE_TIME)}
- Reminder: {'Enabled' if SEND_REMINDER else 'Disabled'}

⚠️ Note: To enable full calendar integration in GitHub Actions, please set up a Google Service Account.

The workflow is running successfully! 🎉

Best regards,
{COMPANY_NAME} Automation System
"""

def format_schedule_email(events, tomorrow_date):
    """Format events with first/second half grouping"""
    header = f"""Dear Team,

Please find below the schedule for {tomorrow_date.strftime('%A, %B %d, %Y')}:

"""
    
    # Group events
    first_half = []
    second_half = []
    
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        
        if 'T' in start:  # Timed event
            start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
            start_dt = start_dt.astimezone(pytz.timezone(TIMEZONE))
            
            # Before or after 1:30 PM
            if start_dt.hour < 13 or (start_dt.hour == 13 and start_dt.minute < 30):
                first_half.append(event)
            else:
                second_half.append(event)
        else:  # All-day event
            first_half.append(event)
    
    body = ""
    
    # First Half
    if first_half:
        body += "📅 FIRST HALF (Before 1:30 PM)\n"
        body += "─" * 40 + "\n"
        for event in first_half:
            body += format_single_event(event) + "\n"
        body += "\n"
    
    # Second Half  
    if second_half:
        body += "📅 SECOND HALF (After 1:30 PM)\n"
        body += "─" * 40 + "\n"
        for event in second_half:
            body += format_single_event(event) + "\n"
    
    footer = f"""
─────────────────────────────────────────
Total Events: {len(events)}
Generated at: {datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime('%I:%M %p')}

Best regards,
{COMPANY_NAME} Automation System
"""
    
    return header + body + footer

def format_single_event(event):
    """Format a single event"""
    start = event['start'].get('dateTime', event['start'].get('date'))
    end = event['end'].get('dateTime', event['end'].get('date'))
    
    if 'T' in start:  # Timed event
        start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
        tz = pytz.timezone(TIMEZONE)
        start_dt = start_dt.astimezone(tz)
        end_dt = end_dt.astimezone(tz)
        time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
    else:
        time_str = "All Day"
    
    summary = event.get('summary', 'No Title')
    result = f"• {time_str}: {summary}"
    
    if location := event.get('location'):
        result += f"\n  📍 Location: {location}"
    
    if description := event.get('description', '').strip():
        if len(description) < 150:
            result += f"\n  📝 Notes: {description}"
    
    if 'hangoutLink' in event:
        result += f"\n  🔗 Meet: {event['hangoutLink']}"
    
    return result

def format_time_12hr(time_24hr):
    """Convert 24hr time string to 12hr format"""
    hour, minute = map(int, time_24hr.split(':'))
    period = 'AM' if hour < 12 else 'PM'
    hour_12 = hour if hour <= 12 else hour - 12
    if hour_12 == 0:
        hour_12 = 12
    return f"{hour_12}:{minute:02d} {period}"

def send_email(gmail_service, subject, body):
    """Send email via Gmail API"""
    try:
        message = MIMEText(body)
        message['to'] = RECIPIENT_EMAIL
        message['from'] = SENDER_EMAIL
        message['subject'] = subject
        
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        if gmail_service:
            result = gmail_service.users().messages().send(
                userId="me",
                body={'raw': encoded}
            ).execute()
            
            print(f"✅ Email sent: {subject} (ID: {result['id']})")
            return True
        else:
            print("📧 Email would be sent (no Gmail service available):")
            print(f"   To: {RECIPIENT_EMAIL}")
            print(f"   Subject: {subject}")
            print(f"   Body preview: {body[:100]}...")
            return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {str(e)}")
        return False

def main():
    """Main function with consolidated logic"""
    print("🚀 Google Calendar Schedule Reader - Consolidated Version")
    print("=" * 60)
    
    # Show configuration
    print(f"📧 Recipient: {RECIPIENT_EMAIL}")
    print(f"⏰ Schedule Time: {format_time_12hr(SCHEDULE_TIME)}")
    print(f"🔔 Reminder: {'Enabled' if SEND_REMINDER else 'Disabled'}")
    print(f"🌍 Environment: {'GitHub Actions' if is_github_actions() else 'Local'}")
    print("=" * 60)
    
    # Authenticate
    print("\n🔐 Authenticating...")
    calendar_service, gmail_service = authenticate()
    
    # Determine action
    action = check_action_needed()
    print(f"\n📋 Action: {action.upper()}")
    
    # Get tomorrow's events
    events, tomorrow_date, status = get_tomorrow_events(calendar_service)
    
    # Handle based on status and action
    if status == 'no_auth':
        print("⚠️  No authentication - sending GitHub Actions notification")
        body = format_github_actions_email()
        send_email(gmail_service, "GitHub Actions Workflow Status", body)
        
    elif status == 'weekend' and action == 'schedule':
        print("📅 Weekend detected, sending weekend notice")
        body = format_weekend_email(tomorrow_date)
        send_email(gmail_service, "Weekend Notice", body)
        
    elif status == 'holiday' and action == 'schedule':
        print("🎉 Holiday detected, sending holiday notice")
        body = format_holiday_email(tomorrow_date)
        send_email(gmail_service, "Holiday Notice - " + tomorrow_date.strftime('%B %d'), body)
        
    elif status == 'normal':
        if action == 'reminder' and SEND_REMINDER:
            print("⏰ Sending reminder email...")
            body = format_reminder_email(tomorrow_date)
            send_email(gmail_service, "Calendar Update Reminder", body)
            
        elif action in ['schedule', 'test']:
            print(f"📊 Found {len(events)} events")
            body = format_schedule_email(events, tomorrow_date)
            subject = f"Schedule Update - {tomorrow_date.strftime('%B %d')}"
            send_email(gmail_service, subject, body)
    
    print("\n✅ Process completed successfully!")
    return 0

if __name__ == '__main__':
    sys.exit(main())