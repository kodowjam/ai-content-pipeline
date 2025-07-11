#!/usr/bin/env python3
"""
Auto Transcript Watcher & Combiner
Monitors video-processor for new transcript files and automatically combines them by location
"""

import os
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TranscriptFileHandler(FileSystemEventHandler):
    """Handles file system events for transcript files"""
    
    def __init__(self, watcher_instance):
        self.watcher = watcher_instance
        self.processed_files = set()
        
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and self._is_transcript_file(event.src_path):
            self._handle_transcript_event(event.src_path, "created")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory and self._is_transcript_file(event.src_path):
            self._handle_transcript_event(event.src_path, "modified")
    
    def _is_transcript_file(self, file_path):
        """Check if file is a transcript file"""
        file_path = Path(file_path)
        return (file_path.suffix == '.json' and 
                '_transcription.json' in file_path.name)
    
    def _handle_transcript_event(self, file_path, event_type):
        """Handle transcript file events"""
        file_path = Path(file_path)
        
        # Avoid processing the same file multiple times quickly
        if file_path in self.processed_files:
            return
            
        self.processed_files.add(file_path)
        
        print(f"📄 {event_type.title()} transcript file: {file_path.name}")
        
        # Add a small delay to ensure file is fully written
        time.sleep(2)
        
        # Schedule combination check
        self.watcher.schedule_location_check(file_path)

class AutoTranscriptWatcher:
    """Watches for new transcript files and auto-combines by location"""
    
    def __init__(self, video_processor_path="../../video-processor", ai_pipeline_path="."):
        self.video_processor_path = Path(video_processor_path)
        self.ai_pipeline_path = Path(ai_pipeline_path)
        self.analysis_dir = self.video_processor_path / "analysis"
        self.input_transcripts_dir = self.ai_pipeline_path / "Input" / "transcripts"
        
        # State tracking
        self.location_state_file = self.ai_pipeline_path / ".location_states.json"
        self.combination_delay = 30  # seconds to wait before combining
        self.pending_combinations = {}
        
        # Ensure directories exist
        self.input_transcripts_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔍 Watching: {self.analysis_dir}")
        print(f"📁 Output: {self.input_transcripts_dir}")
    
    def load_location_states(self):
        """Load the current state of each location"""
        if self.location_state_file.exists():
            try:
                with open(self.location_state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_location_states(self, states):
        """Save the current state of each location"""
        states['last_updated'] = datetime.now().isoformat()
        try:
            with open(self.location_state_file, 'w') as f:
                json.dump(states, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save location states: {e}")
    
    def get_location_from_path(self, file_path):
        """Extract location name from file path"""
        # file_path should be like: .../analysis/Discovery Park July 9/Discovery Park July 9_1/...
        parts = file_path.parts
        analysis_idx = -1
        
        for i, part in enumerate(parts):
            if part == "analysis":
                analysis_idx = i
                break
        
        if analysis_idx >= 0 and len(parts) > analysis_idx + 1:
            return parts[analysis_idx + 1]
        
        return None
    
    def get_location_file_hash(self, location_name):
        """Get hash of all transcript files for a location"""
        location_dir = self.analysis_dir / location_name
        if not location_dir.exists():
            return None
        
        all_transcript_files = []
        for video_dir in location_dir.iterdir():
            if video_dir.is_dir():
                transcript_files = list(video_dir.glob("*_transcription.json"))
                all_transcript_files.extend(transcript_files)
        
        if not all_transcript_files:
            return None
        
        # Sort files for consistent hashing
        all_transcript_files.sort(key=lambda x: x.name)
        
        # Create hash based on filenames and modification times
        hash_content = ""
        for file in all_transcript_files:
            try:
                stat = file.stat()
                hash_content += f"{file.name}:{stat.st_mtime}:{stat.st_size};"
            except:
                continue
        
        return hashlib.md5(hash_content.encode()).hexdigest()
    
    def check_location_needs_combination(self, location_name):
        """Check if a location needs to be combined/recombined"""
        current_hash = self.get_location_file_hash(location_name)
        if not current_hash:
            return False
        
        # Check smart pipeline history first
        smart_pipeline_log = self.ai_pipeline_path / ".pipeline_processed.json"
        if smart_pipeline_log.exists():
            try:
                with open(smart_pipeline_log, 'r') as f:
                    pipeline_history = json.load(f)
                
                # Check if any combined file for this location was already processed
                processed_files = pipeline_history.get('processed_files', {})
                for filename, file_info in processed_files.items():
                    if location_name.replace(' ', '_') in filename and 'combined_' in filename:
                        print(f"✓ {location_name}: Already processed by smart pipeline")
                        # Update our state to match
                        states = self.load_location_states()
                        states[location_name] = {
                            'file_hash': current_hash,
                            'last_combined': file_info.get('processed_at', datetime.now().isoformat()),
                            'combined_file': 'processed_by_smart_pipeline',
                            'transcript_count': 'unknown'
                        }
                        self.save_location_states(states)
                        return False
            except Exception as e:
                print(f"Warning: Could not check smart pipeline history: {e}")
        
        # Load saved states
        states = self.load_location_states()
        location_state = states.get(location_name, {})
        
        saved_hash = location_state.get('file_hash')
        last_combined = location_state.get('last_combined')
        
        # If hashes are different, location needs combination
        if saved_hash != current_hash:
            print(f"🔄 {location_name}: Files changed, needs combination")
            return True
        
        # Check if combined file exists in output directory
        safe_location = "".join(c for c in location_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_location = safe_location.replace(' ', '_')
        
        combined_files = list(self.input_transcripts_dir.glob(f"combined_{safe_location}_*.json"))
        if not combined_files:
            print(f"🆕 {location_name}: No combined file exists, needs combination")
            return True
        
        print(f"✓ {location_name}: Up to date")
        return False
    
    def combine_location_transcripts(self, location_name):
        """Combine transcript files for a specific location"""
        location_dir = self.analysis_dir / location_name
        if not location_dir.exists():
            print(f"❌ Location directory not found: {location_dir}")
            return False
        
        # Find all transcript files
        transcript_files = []
        for video_dir in location_dir.iterdir():
            if video_dir.is_dir():
                video_transcripts = list(video_dir.glob("*_transcription.json"))
                transcript_files.extend(video_transcripts)
        
        if not transcript_files:
            print(f"❌ No transcript files found for {location_name}")
            return False
        
        # Sort files for consistent ordering
        transcript_files.sort(key=lambda x: x.name)
        
        print(f"🔄 Combining {len(transcript_files)} files for {location_name}")
        
        # Combine transcripts
        combined_data = {
            'combined_transcript': {
                'metadata': {
                    'location': location_name,
                    'created_at': datetime.now().isoformat(),
                    'total_source_files': len(transcript_files),
                    'source_files': []
                },
                'content': {
                    'full_text': '',
                    'individual_transcripts': []
                }
            }
        }
        
        all_text_parts = []
        
        for transcript_file in transcript_files:
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract text content
                text_parts = []
                if isinstance(data, list):
                    segments = data
                else:
                    segments = data.get('filtered_transcription', data)
                
                if isinstance(segments, list):
                    for segment in segments:
                        if isinstance(segment, dict) and 'text' in segment:
                            text_parts.append(segment['text'].strip())
                
                video_text = ' '.join(text_parts)
                video_name = transcript_file.parent.name
                
                # Add to combined data
                combined_data['combined_transcript']['content']['individual_transcripts'].append({
                    'source_file': transcript_file.name,
                    'video_folder': video_name,
                    'text_content': video_text,
                    'segment_count': len(text_parts)
                })
                
                combined_data['combined_transcript']['metadata']['source_files'].append({
                    'file': transcript_file.name,
                    'video_folder': video_name
                })
                
                # Add to full text
                if video_text:
                    separator = f"\n\n--- {video_name} ---\n"
                    all_text_parts.append(separator + video_text)
                
            except Exception as e:
                print(f"⚠️  Error processing {transcript_file}: {e}")
                continue
        
        # Combine all text
        combined_data['combined_transcript']['content']['full_text'] = '\n'.join(all_text_parts)
        
        # Save combined file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_location = "".join(c for c in location_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_location = safe_location.replace(' ', '_')
        
        filename = f"combined_{safe_location}_{timestamp}.json"
        output_path = self.input_transcripts_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Combined transcript saved: {output_path}")
            
            # Update location state
            states = self.load_location_states()
            current_hash = self.get_location_file_hash(location_name)
            
            states[location_name] = {
                'file_hash': current_hash,
                'last_combined': datetime.now().isoformat(),
                'combined_file': str(output_path),
                'transcript_count': len(transcript_files)
            }
            
            self.save_location_states(states)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving combined transcript: {e}")
            return False
    
    def schedule_location_check(self, file_path):
        """Schedule a location check after a delay to batch multiple files"""
        location_name = self.get_location_from_path(file_path)
        if not location_name:
            return
        
        # Cancel existing timer for this location
        if location_name in self.pending_combinations:
            self.pending_combinations[location_name].cancel()
        
        # Schedule new check
        import threading
        timer = threading.Timer(
            self.combination_delay,
            self._check_and_combine_location,
            args=[location_name]
        )
        timer.start()
        
        self.pending_combinations[location_name] = timer
        print(f"⏰ Scheduled combination check for {location_name} in {self.combination_delay}s")
    
    def _check_and_combine_location(self, location_name):
        """Check if location needs combination and do it"""
        try:
            if self.check_location_needs_combination(location_name):
                print(f"🚀 Auto-combining {location_name}...")
                success = self.combine_location_transcripts(location_name)
                
                if success:
                    print(f"✅ Successfully auto-combined {location_name}")
                    
                    # Trigger smart pipeline if requested
                    self._trigger_smart_pipeline()
                else:
                    print(f"❌ Failed to combine {location_name}")
            
            # Remove from pending
            if location_name in self.pending_combinations:
                del self.pending_combinations[location_name]
                
        except Exception as e:
            print(f"❌ Error in auto-combination for {location_name}: {e}")
    
    def _trigger_smart_pipeline(self):
        """Trigger the smart pipeline runner"""
        try:
            print("🎬 Triggering smart pipeline...")
            import subprocess
            import sys
            
            result = subprocess.run(
                [sys.executable, 'smart_pipeline_runner.py'],
                cwd=self.ai_pipeline_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print("✅ Smart pipeline completed successfully")
            else:
                print(f"⚠️  Smart pipeline had issues: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️  Could not trigger smart pipeline: {e}")
    
    def scan_all_locations(self):
        """Scan all existing locations for changes"""
        if not self.analysis_dir.exists():
            print(f"❌ Analysis directory not found: {self.analysis_dir}")
            return
        
        print("🔍 Scanning all locations for changes...")
        
        locations_combined = 0
        for location_dir in self.analysis_dir.iterdir():
            if location_dir.is_dir():
                location_name = location_dir.name
                
                if self.check_location_needs_combination(location_name):
                    print(f"🚀 Combining {location_name}...")
                    success = self.combine_location_transcripts(location_name)
                    if success:
                        locations_combined += 1
        
        if locations_combined > 0:
            print(f"✅ Combined {locations_combined} locations")
            self._trigger_smart_pipeline()
        else:
            print("ℹ️  All locations are up to date")
    
    def start_watching(self):
        """Start watching for file changes"""
        if not self.analysis_dir.exists():
            print(f"❌ Analysis directory not found: {self.analysis_dir}")
            return
        
        print("🔍 Starting file watcher...")
        
        # Initial scan
        self.scan_all_locations()
        
        # Set up file watcher
        event_handler = TranscriptFileHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.analysis_dir), recursive=True)
        observer.start()
        
        print("✅ Auto transcript watcher started!")
        print("🔄 Monitoring for new transcript files...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping watcher...")
            observer.stop()
        
        observer.join()
        print("✅ Watcher stopped")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto transcript watcher and combiner')
    parser.add_argument('--video-processor-path', default='../../video-processor', 
                       help='Path to video processor directory')
    parser.add_argument('--scan-only', action='store_true', 
                       help='Scan once and exit (no continuous watching)')
    parser.add_argument('--delay', type=int, default=30,
                       help='Delay in seconds before combining (default: 30)')
    
    args = parser.parse_args()
    
    watcher = AutoTranscriptWatcher(
        video_processor_path=args.video_processor_path
    )
    watcher.combination_delay = args.delay
    
    if args.scan_only:
        watcher.scan_all_locations()
    else:
        watcher.start_watching()

if __name__ == "__main__":
    main()