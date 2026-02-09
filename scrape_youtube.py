import requests
import re
import json
import sqlite3
import datetime
from difflib import SequenceMatcher

DB_PATH = "app/content/glimprint.db"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLiEtieOeWbMKh9VcQoinSwODcSZKMTGat"

def get_yt_initial_data(url):
    print(f"Fetching {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Extract ytInitialData
    match = re.search(r"var ytInitialData = ({.*?});", response.text)
    if not match:
        print("Could not find ytInitialData")
        return None
    return json.loads(match.group(1))

def extract_videos(data):
    videos = []
    try:
        tabs = data['contents']['twoColumnBrowseResultsRenderer']['tabs']
        for tab in tabs:
            if 'tabRenderer' in tab:
                content = tab['tabRenderer']['content']
                section_list = content['sectionListRenderer']['contents']
                for section in section_list:
                    if 'itemSectionRenderer' in section:
                        items = section['itemSectionRenderer']['contents']
                        for item in items:
                            if 'playlistVideoListRenderer' in item:
                                video_list = item['playlistVideoListRenderer']['contents']
                                for video_item in video_list:
                                    if 'playlistVideoRenderer' in video_item:
                                        vid = video_item['playlistVideoRenderer']
                                        title = vid['title']['runs'][0]['text']
                                        video_id = vid['videoId']
                                        videos.append({"title": title, "video_id": video_id})
    except KeyError as e:
        print(f"Error parsing JSON: {e}")
    return videos

def fuzzy_match(title1, title2):
    return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()

def main():
    data = get_yt_initial_data(PLAYLIST_URL)
    if not data:
        return
        
    videos = extract_videos(data)
    print(f"Found {len(videos)} videos in playlist.")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    seminars = cursor.execute("SELECT id, title, speaker, date, recording_url FROM seminars").fetchall()
    
    updates = 0
    # Create a lookup for seminars by date (YYYY-MM-DD)
    seminar_by_date = {}
    for s in seminars:
        if s['date']:
            try:
                dt = datetime.datetime.fromisoformat(s['date'])
                date_key = dt.strftime("%Y-%m-%d")
                seminar_by_date[date_key] = s
            except: pass

    for video in videos:
        title = video['title']
        
        # Try to extract date from video title
        # Format usually: "... Month DD, YYYY" or "... Month DDth, YYYY"
        # Regex for date at end of string
        date_match = re.search(r'([A-Z][a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\s*$', title)
        
        best_match = None
        
        if date_match:
            month_str, day_str, year_str = date_match.groups()
            try:
                # Parse date
                dt_video = datetime.datetime.strptime(f"{month_str} {day_str} {year_str}", "%B %d %Y")
                video_date_key = dt_video.strftime("%Y-%m-%d")
                
                # Check DB
                if video_date_key in seminar_by_date:
                    best_match = seminar_by_date[video_date_key]
                    print(f"Match by DATE found: {video_date_key}")
                else:
                    # Sometimes timezones shift date by 1 day?
                    # Check +/- 1 day
                    # But usually webinar dates are precise locally. 
                    # Let's try matching. 
                    pass
            except ValueError:
                pass
        
        if not best_match:
            # Fallback to loose fuzzy match on title if date failed
            # ... (keep existing logic or simplified)
            pass

        if best_match:
            print(f"  Video:   {video['title']}")
            print(f"  Seminar: {best_match['title']}")
            
            # Update DB
            video_url = f"https://www.youtube.com/watch?v={video['video_id']}"
            cursor.execute("UPDATE seminars SET recording_url = ? WHERE id = ?", (video_url, best_match['id']))
            updates += 1
            
    conn.commit()
    conn.close()
    print(f"Updated {updates} seminars with recording URLs.")

if __name__ == "__main__":
    main()
