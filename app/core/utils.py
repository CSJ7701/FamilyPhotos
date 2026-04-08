
import yaml
import markdown
from pathlib import Path
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

DATA_FILE = Path("data/announcements.yaml")

def get_announcement_data():
    """Loads raw announcement/event data from YAML."""
    if not DATA_FILE.exists():
        return {"announcements": [], "events": []}

    with open(DATA_FILE, "r") as f:
        return yaml.safe_load(f) or {"announcements": [], "events": []}

def process_announcement_data(limit_recent=False):    
    data = get_announcement_data()
    today = date.today()
    two_months_out = today + relativedelta(months=2)

    # 1. Process Announcements
    announcements = data.get("announcements", [])
    # Convert date strings to date objects for sorting
    for a in announcements:
        if isinstance(a['date'], str):
            a['date_obj'] = datetime.strptime(a['date'], "%Y-%m-%d").date()
        else:
            a['date_obj'] = a['date']
        a['html_content'] = markdown.markdown(a.get('content', ''))

    announcements.sort(key=lambda x: x['date_obj'], reverse=True)
    
    if limit_recent:
        announcements = announcements[:4] 

    # 2. Process Events
    events = data.get("events", [])
    processed_events = []
    years = set()
    for e in events:
        if isinstance(e['date'], str):
            e['date_obj'] = datetime.strptime(e['date'], "%Y-%m-%d").date()
        else:
            e['date_obj'] = e['date']
        years.add(e['date_obj'].year)
        
        # UI Formatting
        e['day'] = e['date_obj'].strftime("%d")
        e['month_name'] = e['date_obj'].strftime("%b")
        e['month_val'] = e['date_obj'].month
        e['year_val'] = e['date_obj'].year
        
        if limit_recent:
            # Only include if within the next 2 months
            if today <= e['date_obj'] <= two_months_out:
                processed_events.append(e)
        else:
            processed_events.append(e)

    processed_events.sort(key=lambda x: x['date_obj'])

    return {
        "announcements": announcements,
        "events": processed_events,
        "available_years": sorted(list(years))
    }
    
