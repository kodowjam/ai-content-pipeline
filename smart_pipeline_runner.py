#!/usr/bin/env python3
"""
Smart Pipeline Runner - Only processes NEW transcript combinations
Tracks what's been processed and only runs pipeline on new content
"""

import os
import json
from datetime import datetime
from pathlib import Path
import hashlib

class SmartPipelineRunner:
    def __init__(self):
        self.input_dir = Path("Input/transcripts")
        self.processed_log = Path(".pipeline_processed.json")
        self.shared_sheet_id_file = Path(".shared_sheet_id.json")
        
    def get_or_create_shared_sheet_id(self):
        """Get existing shared sheet ID or create new one"""
        if self.shared_sheet_id_file.exists():
            try:
                with open(self.shared_sheet_id_file, 'r') as f:
                    data = json.load(f)
                    return data.get('sheet_id')
            except:
                pass
        return None
    
    def save_shared_sheet_id(self, sheet_id):
        """Save the shared sheet ID for reuse"""
        data = {
            'sheet_id': sheet_id,
            'created_at': datetime.now().isoformat()
        }
        try:
            with open(self.shared_sheet_id_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save shared sheet ID: {e}")
        
    def get_file_hash(self, file_path):
        """Generate a hash of file content to detect changes"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def load_processed_history(self):
        """Load history of what's been processed"""
        if self.processed_log.exists():
            try:
                with open(self.processed_log, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'processed_files': {}, 'last_run': None}
    
    def save_processed_history(self, history):
        """Save updated processing history"""
        history['last_run'] = datetime.now().isoformat()
        with open(self.processed_log, 'w') as f:
            json.dump(history, f, indent=2)
    
    def find_new_combined_files(self):
        """Find combined transcript files that haven't been processed"""
        if not self.input_dir.exists():
            print(f"❌ Input directory not found: {self.input_dir}")
            return []
        
        # Load processing history
        history = self.load_processed_history()
        processed_files = history['processed_files']
        
        # Find all combined files
        combined_files = list(self.input_dir.glob("combined_*.json"))
        new_files = []
        
        print(f"🔍 Checking {len(combined_files)} combined files...")
        
        for file in combined_files:
            file_hash = self.get_file_hash(file)
            file_key = file.name
            
            # Check if this file has been processed with this content
            if file_key in processed_files:
                if processed_files[file_key]['hash'] == file_hash:
                    print(f"✓ {file.name} - already processed (unchanged)")
                    continue
                else:
                    print(f"🔄 {file.name} - file changed, needs reprocessing")
            else:
                print(f"🆕 {file.name} - new file, needs processing")
            
            new_files.append(file)
        
        return new_files
    
    def extract_location_from_filename(self, filename):
        """Extract location name from combined filename"""
        # Remove 'combined_' prefix and '.json' suffix, then clean up
        location = filename.replace('combined_', '').replace('.json', '')
        location = location.replace('_', ' ')
        
        # Handle specific cases
        if 'Discovery Park July 9' in location:
            return 'Discovery Park July 9'
        elif 'Mt Washington' in location or 'mount washington' in location:
            return 'Mt Washington'
        else:
            return location.title()
    
    def run_pipeline_on_file(self, file_path):
        """Run the AI content pipeline on a specific file"""
        try:
            # Load environment variables first
            from dotenv import load_dotenv
            load_dotenv()
            
            # Import your existing pipeline
            import sys
            sys.path.append('src')
            from complete_oauth_pipeline import CompletePipeline
            
            location = self.extract_location_from_filename(file_path.name)
            
            print(f"🚀 Running pipeline for: {location}")
            print(f"📄 File: {file_path.name}")
            
            # Get or create shared sheet ID
            shared_sheet_id = self.get_or_create_shared_sheet_id()
            
            # Initialize and run pipeline with shared sheet
            pipeline = CompletePipeline(sheet_id=shared_sheet_id)
            result = pipeline.process_transcript_to_blog(
                str(file_path),
                location=location,
                date=datetime.now().strftime("%B %Y")
            )
            
            # Save the sheet ID if it's new
            if not shared_sheet_id:
                new_sheet_id = result['sheet_info']['sheet_id']
                self.save_shared_sheet_id(new_sheet_id)
                print(f"📊 Created shared tracking sheet: {new_sheet_id}")
            else:
                print(f"📊 Updated existing tracking sheet")
            
            print(f"✅ Pipeline completed for {location}!")
            print(f"📄 Google Doc: {result['doc_info']['doc_url']}")
            print(f"📊 Tracking Sheet: {result['sheet_info']['sheet_url']}")
            
            return {
                'success': True,
                'location': location,
                'doc_url': result['doc_info']['doc_url'],
                'sheet_url': result['sheet_info']['sheet_url']
            }
            
        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def run_smart_pipeline(self):
        """Main function: find new files and process them"""
        print("🎬 Starting Smart Pipeline Runner...")
        print("=" * 50)
        
        # Find files that need processing
        new_files = self.find_new_combined_files()
        
        if not new_files:
            print("ℹ️  No new files to process - everything is up to date!")
            return {'status': 'no_new_files', 'processed': []}
        
        print(f"\n🚀 Found {len(new_files)} files to process:")
        for file in new_files:
            print(f"  - {file.name}")
        
        # Load processing history
        history = self.load_processed_history()
        
        # Process each new file
        results = []
        processed_count = 0
        
        for file in new_files:
            print(f"\n" + "="*50)
            result = self.run_pipeline_on_file(file)
            results.append(result)
            
            if result['success']:
                # Mark as processed
                file_hash = self.get_file_hash(file)
                history['processed_files'][file.name] = {
                    'hash': file_hash,
                    'processed_at': datetime.now().isoformat(),
                    'location': result['location'],
                    'doc_url': result['doc_url']
                }
                processed_count += 1
                
        # Save updated history
        self.save_processed_history(history)
        
        print(f"\n🎉 Smart Pipeline Complete!")
        print(f"✅ Successfully processed: {processed_count}/{len(new_files)} files")
        print(f"📱 Check your Slack for notifications!")
        
        return {
            'status': 'success',
            'processed': results,
            'total_processed': processed_count
        }

def create_shortcut_script():
    """Create a simple shortcut script"""
    shortcut_content = '''#!/bin/bash
# Smart Pipeline Shortcut
# Run this whenever you have new videos processed

echo "🎬 Running Smart Pipeline..."
cd "$(dirname "$0")"
source content-env/bin/activate
python3 smart_pipeline_runner.py
echo "✅ Done! Check Slack for notifications."
'''
    
    with open('run_smart_pipeline.sh', 'w') as f:
        f.write(shortcut_content)
    
    # Make it executable
    os.chmod('run_smart_pipeline.sh', 0o755)
    print("✅ Created shortcut script: run_smart_pipeline.sh")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Smart Pipeline Runner - Only process new files')
    parser.add_argument('--check-only', action='store_true', help='Only check for new files')
    parser.add_argument('--create-shortcut', action='store_true', help='Create shortcut script')
    parser.add_argument('--show-history', action='store_true', help='Show processing history')
    
    args = parser.parse_args()
    
    runner = SmartPipelineRunner()
    
    if args.create_shortcut:
        create_shortcut_script()
        return
    
    if args.show_history:
        history = runner.load_processed_history()
        print("📋 Processing History:")
        if history['processed_files']:
            for filename, info in history['processed_files'].items():
                print(f"  ✅ {filename}")
                print(f"     Location: {info.get('location', 'Unknown')}")
                print(f"     Processed: {info.get('processed_at', 'Unknown')}")
                print(f"     Doc: {info.get('doc_url', 'N/A')}")
        else:
            print("  No files processed yet")
        return
    
    if args.check_only:
        new_files = runner.find_new_combined_files()
        if new_files:
            print(f"📁 Found {len(new_files)} new files:")
            for file in new_files:
                print(f"  - {file.name}")
        else:
            print("ℹ️  No new files found")
        return
    
    # Run the smart pipeline
    runner.run_smart_pipeline()

if __name__ == "__main__":
    main()