import os
import json
import pickle
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

class GoogleOAuthIntegration:
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/documents',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        self.credentials = self._get_credentials()
        self.docs_service = build('docs', 'v1', credentials=self.credentials)
        self.drive_service = build('drive', 'v3', credentials=self.credentials)
        self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
    
    def _get_credentials(self):
        """Get OAuth credentials, with login flow if needed"""
        creds = None
        token_file = '../config/token.pickle'
        
        # Check if we have stored credentials
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                print("Starting OAuth login flow...")
                creds_path = os.environ.get("GOOGLE_OAUTH_CREDENTIALS_PATH")
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next time
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    def create_blog_doc(self, blog_data):
        """Create a Google Doc from blog data"""
        
        doc_title = f"{blog_data['title']} - {datetime.now().strftime('%Y-%m-%d')}"
        
        try:
            # Create the document
            doc = self.docs_service.documents().create(body={
                'title': doc_title
            }).execute()
            
            doc_id = doc['documentId']
            print(f"✅ Created Google Doc: {doc_title}")
            
            # Add content to the document
            self._add_content_to_doc(doc_id, blog_data)
            print(f"✅ Added content to document")
            
            return {
                'doc_id': doc_id,
                'doc_title': doc_title,
                'doc_url': f"https://docs.google.com/document/d/{doc_id}/edit"
            }
            
        except Exception as e:
            print(f"❌ Error creating document: {e}")
            raise
    
    def _add_content_to_doc(self, doc_id, blog_data):
        """Add formatted content to the Google Doc"""
        
        # Build content
        content = f"""{blog_data['title']}

Meta Description: {blog_data['meta_description']}

{blog_data['content']}

---
METADATA:
- Tags: {', '.join(blog_data.get('tags', []))}
- Word Count: {blog_data.get('word_count', 'N/A')}
- Generated: {blog_data.get('generated_date', 'N/A')}
- Primary Keyword: {blog_data.get('primary_keyword', 'N/A')}
- Suggested Images: {', '.join(blog_data.get('suggested_images', []))}
- Quote Author: {blog_data.get('environmentalist_quote_author', 'N/A')}
"""
        
        # Insert content
        requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': content
            }
        }]
        
        self.docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
    
    def create_or_update_tracking_sheet(self, blog_data, doc_info, sheet_id=None):
        """Create or update the tracking spreadsheet"""
        
        if not sheet_id:
            sheet_id = self._create_tracking_sheet()
        
        # Prepare row data
        row_data = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Date Created
            blog_data['title'],                            # Title
            doc_info['doc_url'],                          # Google Doc URL
            'DRAFT',                                       # Status
            blog_data.get('primary_keyword', ''),         # Primary Keyword
            ', '.join(blog_data.get('tags', [])),         # Tags
            str(blog_data.get('word_count', 0)),          # Word Count
            blog_data['meta_description'],                 # Meta Description
            '',                                           # Publish Date (empty for draft)
            '',                                           # Published URL (empty for draft)
            blog_data.get('environmentalist_quote_author', ''),  # Quote Author
        ]
        
        # Append to sheet
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range='A:K',
            valueInputOption='RAW',
            body={'values': [row_data]}
        ).execute()
        
        print(f"✅ Logged to tracking spreadsheet")
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        return {
            'sheet_id': sheet_id,
            'sheet_url': sheet_url
        }
    
    def _create_tracking_sheet(self):
        """Create a new tracking spreadsheet"""
        
        spreadsheet_body = {
            'properties': {
                'title': f'Blog Content Tracker - {datetime.now().strftime("%Y-%m")}'
            }
        }
        
        sheet = self.sheets_service.spreadsheets().create(body=spreadsheet_body).execute()
        sheet_id = sheet['spreadsheetId']
        
        # Add headers
        headers = [
            'Date Created', 'Title', 'Google Doc URL', 'Status', 'Primary Keyword',
            'Tags', 'Word Count', 'Meta Description', 'Publish Date', 
            'Published URL', 'Quote Author'
        ]
        
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='A1:K1',
            valueInputOption='RAW',
            body={'values': [headers]}
        ).execute()
        
        print(f"✅ Created tracking spreadsheet")
        return sheet_id

def test_oauth_integration():
    """Test the OAuth integration"""
    
    sample_blog = {
        'title': 'Mount Washington Hiking Adventure - Test',
        'meta_description': 'An epic journey to the summit with incredible views and challenges.',
        'content': '''Today I embarked on one of the most challenging hikes of my life - Mount Washington. [IMAGE: trailhead]

## The Early Start
I set out before dawn, knowing that weather conditions could change rapidly at this elevation.

## The Summit Victory  
Reaching the summit was pure euphoria. The 360-degree views were absolutely breathtaking.

As John Muir wisely said, "The mountains are calling and I must go."''',
        'tags': ['hiking', 'mount-washington', 'adventure'],
        'word_count': 89,
        'primary_keyword': 'mount washington hiking',
        'suggested_images': ['trailhead', 'summit view'],
        'environmentalist_quote_author': 'John Muir',
        'generated_date': datetime.now().isoformat()
    }
    
    print("🚀 Testing OAuth Google integration...")
    google = GoogleOAuthIntegration()
    
    print("📄 Creating Google Doc...")
    doc_info = google.create_blog_doc(sample_blog)
    
    print("📊 Creating tracking spreadsheet...")
    sheet_info = google.create_or_update_tracking_sheet(sample_blog, doc_info)
    
    print(f"\n🎉 Success!")
    print(f"Google Doc: {doc_info['doc_url']}")
    print(f"Tracking Sheet: {sheet_info['sheet_url']}")

if __name__ == "__main__":
    test_oauth_integration()
