import os
import json
from datetime import datetime
import requests
from blog_generator import BlogGenerator
from google_oauth_integration import GoogleOAuthIntegration
from dotenv import load_dotenv

load_dotenv()

class CompletePipeline:
    def __init__(self, sheet_id=None):
        self.blog_generator = BlogGenerator()
        self.google_integration = GoogleOAuthIntegration()
        self.slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
        self.sheet_id = sheet_id  # Optional: reuse existing tracking sheet
    
    def process_transcript_to_blog(self, transcript_file_path, location=None, date=None):
        """Complete pipeline: transcript -> blog -> Google Doc -> Sheets -> Slack"""
        
        print("🚀 Starting complete content pipeline...")
        
        # 1. Load transcript
        print("📄 Loading transcript...")
        with open(transcript_file_path, 'r') as f:
            transcript_data = json.load(f)
        print(f"✅ Loaded transcript with {len(transcript_data.get('filtered_transcription', transcript_data))} segments")
        
        # 2. Generate blog
        print("✍️ Generating blog post with AI...")
        blog_data = self.blog_generator.generate_trip_report(transcript_data, location, date)
        print(f"✅ Generated {blog_data.get('word_count', 'N/A')} word blog post")
        
        # 3. Create Google Doc
        print("📄 Creating Google Doc...")
        doc_info = self.google_integration.create_blog_doc(blog_data)
        
        # 4. Log to tracking spreadsheet
        print("📊 Updating tracking spreadsheet...")
        sheet_info = self.google_integration.create_or_update_tracking_sheet(
            blog_data, doc_info, self.sheet_id
        )
        
        # 5. Save locally as backup
        print("💾 Saving local backup...")
        local_files = self._save_local_backup(blog_data)
        
        # 6. Send comprehensive Slack notification
        print("📢 Sending Slack notification...")
        self._send_slack_notification(blog_data, doc_info, sheet_info)
        
        print("✅ Complete pipeline finished!")
        return {
            'blog_data': blog_data,
            'doc_info': doc_info,
            'sheet_info': sheet_info,
            'local_files': local_files
        }
    
    def _save_local_backup(self, blog_data):
        """Save local backup files"""
        
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        safe_title = "".join(c for c in blog_data['title'][:30] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        base_filename = f"{safe_title}_{timestamp}"
        
        # Create directories
        os.makedirs('../output/drafts', exist_ok=True)
        
        # Save as JSON
        json_file = f"../output/drafts/{base_filename}.json"
        with open(json_file, 'w') as f:
            json.dump(blog_data, f, indent=2)
        
        return {'json_file': json_file}
    
    def _send_slack_notification(self, blog_data, doc_info, sheet_info):
        """Send comprehensive Slack notification with all links"""
        
        message = {
            "text": "📝 New Blog Post Created!",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎉 New Blog Post Ready for Review!"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Title:*\n{blog_data['title']}"
                        },
                        {
                            "type": "mrkdwn", 
                            "text": f"*Word Count:*\n{blog_data.get('word_count', 'N/A')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Primary Keyword:*\n{blog_data.get('primary_keyword', 'N/A')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Quote Author:*\n{blog_data.get('environmentalist_quote_author', 'N/A')}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Meta Description:*\n{blog_data['meta_description']}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Tags:* {', '.join(blog_data.get('tags', []))}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📄 View Google Doc"
                            },
                            "url": doc_info['doc_url'],
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📊 View Tracking Sheet"
                            },
                            "url": sheet_info['sheet_url']
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(self.slack_webhook, json=message)
            if response.status_code == 200:
                print("✅ Slack notification sent!")
            else:
                print(f"⚠️ Slack notification failed: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Slack error: {e}")

def test_complete_pipeline():
    """Test the complete pipeline with sample data"""
    
    # Create sample transcript
    sample_transcript = {
        "filtered_transcription": [
            {"start": 0, "end": 8, "text": "Today I'm setting out on an incredible adventure to Mount Washington, the highest peak in New Hampshire."},
            {"start": 8, "end": 15, "text": "The weather is perfect and I'm feeling excited about this challenging hike ahead."},
            {"start": 15, "end": 22, "text": "The trail starts easy but I know it gets much more difficult as we gain elevation."},
            {"start": 22, "end": 28, "text": "After three hours of steady climbing, I'm finally approaching the summit area."},
            {"start": 28, "end": 35, "text": "The views from up here are absolutely spectacular, stretching for miles in every direction."},
            {"start": 35, "end": 42, "text": "Standing here reminds me why I love spending time in nature and pushing my limits."},
            {"start": 42, "end": 48, "text": "This mountain has taught me so much about perseverance and the beauty of our natural world."}
        ]
    }
    
    # Save sample transcript
    os.makedirs('../input/transcripts', exist_ok=True)
    transcript_path = '../input/transcripts/mount_washington_complete.json'
    with open(transcript_path, 'w') as f:
        json.dump(sample_transcript, f, indent=2)
    
    # Run complete pipeline
    pipeline = CompletePipeline()
    result = pipeline.process_transcript_to_blog(
        transcript_path,
        location="Mount Washington, New Hampshire", 
        date="July 2025"
    )
    
    print(f"\n🎉 Complete pipeline successful!")
    print(f"📄 Google Doc: {result['doc_info']['doc_url']}")
    print(f"📊 Tracking Sheet: {result['sheet_info']['sheet_url']}")
    print(f"💾 Local backup: {result['local_files']['json_file']}")
    print(f"📱 Check your Slack for the notification!")

if __name__ == "__main__":
    test_complete_pipeline()
