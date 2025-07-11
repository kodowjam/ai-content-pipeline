#!/usr/bin/env python3
"""
Auto Transcript Combiner for AI Content Pipeline
Combines transcript files from video-processor and triggers your existing pipeline
"""

import os
import json
import glob
from datetime import datetime
from pathlib import Path
import shutil

class TranscriptAutoCombiner:
    def __init__(self, video_processor_path="../video-processor", content_pipeline_path="."):
        """
        Initialize the auto combiner for your existing pipeline.
        
        Args:
            video_processor_path (str): Path to your video-processor directory
            content_pipeline_path (str): Path to your ai-content-pipeline directory
        """
        self.video_processor_path = Path(video_processor_path)
        self.content_pipeline_path = Path(content_pipeline_path)
        self.input_transcripts_dir = self.content_pipeline_path / "input" / "transcripts"
        
        # Create input directory if it doesn't exist
        self.input_transcripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Track processed files
        self.processed_log = self.content_pipeline_path / ".processed_transcripts.json"
    
    def find_new_transcript_files_by_location(self):
        """
        Find new transcript files grouped by location/trip that haven't been combined yet.
        
        Returns:
            Dict[str, List[Path]]: Dictionary mapping location names to lists of new transcript files
        """
        # Load previously processed combinations
        processed_combinations = set()
        if self.processed_log.exists():
            try:
                with open(self.processed_log, 'r') as f:
                    data = json.load(f)
                    processed_combinations = set(data.get('processed_combinations', []))
            except Exception as e:
                print(f"Warning: Could not load processed combinations log: {e}")
        
        # Find all transcript files from video processor grouped by location
        analysis_dir = self.video_processor_path / "analysis"
        location_groups = {}
        
        if not analysis_dir.exists():
            print(f"Analysis directory not found: {analysis_dir}")
            return {}
        
        # Scan each location directory (Discovery Park July 9, Mt Washington, etc.)
        for location_dir in analysis_dir.iterdir():
            if not location_dir.is_dir():
                continue
                
            location_name = location_dir.name
            print(f"Scanning location: {location_name}")
            
            # Check if this location has already been processed
            if location_name in processed_combinations:
                print(f"  ✓ {location_name} already processed, skipping")
                continue
            
            # Find all individual video folders for this location
            location_files = []
            for video_dir in location_dir.iterdir():
                if not video_dir.is_dir():
                    continue
                    
                print(f"  Checking video folder: {video_dir.name}")
                
                # Look for transcript files in order of preference
                transcript_files = []
                
                # 1. Prefer Claude-filtered suggestions (the suggestion.json from your video processor)
                suggestion_files = list(video_dir.glob("*_suggestion.json"))
                if suggestion_files:
                    transcript_files.extend(suggestion_files)
                    print(f"    Found {len(suggestion_files)} Claude-filtered suggestion files")
                
                # 2. Fall back to locally filtered
                elif list(video_dir.glob("*_locally_filtered.json")):
                    filtered_files = list(video_dir.glob("*_locally_filtered.json"))
                    transcript_files.extend(filtered_files)
                    print(f"    Found {len(filtered_files)} locally filtered files")
                
                # 3. Use main transcription files (this is your primary output)
                elif list(video_dir.glob("*_transcription.json")):
                    transcription_files = list(video_dir.glob("*_transcription.json"))
                    transcript_files.extend(transcription_files)
                    print(f"    Found {len(transcription_files)} transcription files")
                
                location_files.extend(transcript_files)
            
            if location_files:
                location_groups[location_name] = location_files
                print(f"  📁 {location_name}: {len(location_files)} transcript files ready for combination")
            else:
                print(f"  ℹ️  {location_name}: No transcript files found")
        
        print(f"\n📊 Summary: Found {len(location_groups)} location groups with new transcripts")
        return location_groups
    
    def extract_transcript_content(self, transcript_file):
        """
        Extract text content from various transcript file formats.
        
        Args:
            transcript_file (Path): Path to transcript file
            
        Returns:
            Dict: Extracted content with metadata
        """
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different transcript formats from your video processor
            transcript_content = {
                'source_file': transcript_file.name,
                'file_path': str(transcript_file),
                'segments': [],
                'full_text': '',
                'processing_type': 'unknown'
            }
            
            # Determine file type and extract content
            if '_suggestion.json' in transcript_file.name:
                # Claude filtered transcripts (best quality)
                transcript_content['processing_type'] = 'claude_filtered'
                if isinstance(data, list):
                    transcript_content['segments'] = data
                else:
                    transcript_content['segments'] = data.get('filtered_transcription', data)
            
            elif '_locally_filtered.json' in transcript_file.name:
                # Locally filtered transcripts
                transcript_content['processing_type'] = 'locally_filtered'
                transcript_content['segments'] = data if isinstance(data, list) else [data]
            
            elif '_transcription.json' in transcript_file.name:
                # Raw transcriptions
                transcript_content['processing_type'] = 'raw_transcription'
                transcript_content['segments'] = data if isinstance(data, list) else [data]
            
            # Extract full text from segments
            segments = transcript_content['segments']
            if segments and isinstance(segments, list):
                full_text_parts = []
                for segment in segments:
                    if isinstance(segment, dict) and 'text' in segment:
                        text = segment['text'].strip()
                        if text:
                            full_text_parts.append(text)
                
                transcript_content['full_text'] = ' '.join(full_text_parts)
            
            return transcript_content
            
        except Exception as e:
            print(f"Error reading transcript file {transcript_file}: {e}")
            return None
    
    def combine_transcripts_for_location(self, location_name, transcript_files):
        """
        Combine transcript files for a specific location/trip.
        
        Args:
            location_name (str): Name of the location (e.g., "Mt Washington", "Discovery Park July 9")
            transcript_files (List[Path]): List of transcript files for this location
            
        Returns:
            Dict: Combined transcript data for this location
        """
        combined_data = {
            'combined_transcript': {
                'metadata': {
                    'location': location_name,
                    'created_at': datetime.now().isoformat(),
                    'total_source_files': len(transcript_files),
                    'source_files': [],
                    'combiner_version': '1.0'
                },
                'content': {
                    'full_text': '',
                    'individual_transcripts': []
                }
            }
        }
        
        all_text_parts = []
        
        # Sort files by video number/name for consistent ordering
        def extract_video_number(file_path):
            # Extract number from patterns like "Discovery Park July 9_1", "mt washington 2", etc.
            try:
                parts = file_path.parent.name.split('_')
                if parts:
                    last_part = parts[-1]
                    if last_part.isdigit():
                        return int(last_part)
                # Try extracting from end of name
                import re
                match = re.search(r'(\d+)
    
    def save_combined_transcript_for_location(self, location_name, combined_data):
        """
        Save the combined transcript for a specific location.
        
        Args:
            location_name (str): Name of the location
            combined_data (Dict): Combined transcript data
            
        Returns:
            Path: Path to saved combined transcript
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create safe filename from location name
        safe_location = "".join(c for c in location_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_location = safe_location.replace(' ', '_')
        
        filename = f"combined_{safe_location}_{timestamp}.json"
        output_path = self.input_transcripts_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Combined transcript saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error saving combined transcript: {e}")
            raise
    
    def mark_location_as_processed(self, location_name):
        """
        Mark a location as processed to avoid reprocessing.
        
        Args:
            location_name (str): Location that was processed
        """
        # Load existing log
        log_data = {'processed_combinations': [], 'last_run': None}
        if self.processed_log.exists():
            try:
                with open(self.processed_log, 'r') as f:
                    log_data = json.load(f)
            except Exception:
                pass
        
        # Add new location
        existing_locations = set(log_data.get('processed_combinations', []))
        existing_locations.add(location_name)
        
        # Save updated log
        log_data['processed_combinations'] = list(existing_locations)
        log_data['last_run'] = datetime.now().isoformat()
        
        try:
            with open(self.processed_log, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save processed combinations log: {e}")
    
    def trigger_existing_pipeline_for_location(self, combined_transcript_path, location_name):
        """
        Trigger your existing complete_oauth_pipeline.py with the combined transcript for a specific location.
        
        Args:
            combined_transcript_path (Path): Path to the combined transcript
            location_name (str): Name of the location for context
            
        Returns:
            bool: True if pipeline was triggered successfully
        """
        try:
            # Import your existing pipeline
            from complete_oauth_pipeline import CompletePipeline
            
            print(f"🚀 Triggering your existing AI content pipeline for {location_name}...")
            
            # Initialize your pipeline (adjust parameters as needed)
            pipeline = CompletePipeline()
            
            # Process the combined transcript with location context
            result = pipeline.process_transcript_to_blog(
                str(combined_transcript_path),
                location=location_name,  # Use the actual location name
                date=datetime.now().strftime("%B %Y")
            )
            
            print("✅ Pipeline completed successfully!")
            print(f"📄 Google Doc: {result['doc_info']['doc_url']}")
            print(f"📊 Tracking Sheet: {result['sheet_info']['sheet_url']}")
            
            return True
            
        except ImportError as e:
            print(f"❌ Could not import your pipeline: {e}")
            print("Make sure complete_oauth_pipeline.py is in the same directory")
            return False
        except Exception as e:
            print(f"❌ Error running pipeline: {e}")
            return False
    
    def run(self, trigger_pipeline=True):
        """
        Run the complete auto-combination process for all locations with new transcripts.
        
        Args:
            trigger_pipeline (bool): Whether to trigger your existing pipeline
            
        Returns:
            Dict: Processing results
        """
        print("🎬 Starting auto transcript combination by location...")
        
        # Find new transcript files grouped by location
        location_groups = self.find_new_transcript_files_by_location()
        
        if not location_groups:
            print("ℹ️  No new transcript files found for any location")
            return {'status': 'no_new_files', 'message': 'No new transcript files to process'}
        
        results = {
            'status': 'success',
            'locations_processed': {},
            'total_locations': len(location_groups),
            'pipeline_results': {}
        }
        
        # Process each location separately
        for location_name, transcript_files in location_groups.items():
            print(f"\n🗺️  Processing location: {location_name}")
            print(f"📁 Found {len(transcript_files)} transcript files:")
            for file in transcript_files:
                print(f"  - {file.parent.name}/{file.name}")
            
            try:
                # Combine transcripts for this location
                print(f"🔄 Combining transcripts for {location_name}...")
                combined_data = self.combine_transcripts_for_location(location_name, transcript_files)
                
                # Save combined transcript
                combined_file = self.save_combined_transcript_for_location(location_name, combined_data)
                
                # Mark location as processed
                self.mark_location_as_processed(location_name)
                
                # Store results for this location
                results['locations_processed'][location_name] = {
                    'files_processed': len(transcript_files),
                    'combined_file': str(combined_file),
                    'source_files': [f.parent.name + '/' + f.name for f in transcript_files]
                }
                
                # Trigger your existing pipeline if requested
                pipeline_success = False
                if trigger_pipeline:
                    pipeline_success = self.trigger_existing_pipeline_for_location(combined_file, location_name)
                    results['pipeline_results'][location_name] = pipeline_success
                
                print(f"✅ Successfully processed {location_name}")
                if pipeline_success:
                    print(f"🚀 Pipeline triggered for {location_name}")
                
            except Exception as e:
                print(f"❌ Error processing {location_name}: {e}")
                results['locations_processed'][location_name] = {
                    'error': str(e),
                    'files_attempted': len(transcript_files)
                }
        
        return results

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Auto-combine transcript files and trigger existing AI content pipeline'
    )
    parser.add_argument(
        '--video-processor-path',
        default='../video-processor',
        help='Path to video processor directory'
    )
    parser.add_argument(
        '--no-pipeline',
        action='store_true',
        help='Only combine transcripts, don\'t trigger the pipeline'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check for new files, don\'t process them'
    )
    
    args = parser.parse_args()
    
    try:
        combiner = TranscriptAutoCombiner(
            video_processor_path=args.video_processor_path
        )
        
        if args.check_only:
            location_groups = combiner.find_new_transcript_files_by_location()
            if location_groups:
                print(f"📁 Found {len(location_groups)} location groups with new transcript files:")
                for location_name, files in location_groups.items():
                    print(f"\n🗺️  {location_name}:")
                    for file in files:
                        print(f"    - {file.parent.name}/{file.name}")
            else:
                print("ℹ️  No new transcript files found for any location")
            return 0
        
        # Run the combination process
        result = combiner.run(trigger_pipeline=not args.no_pipeline)
        
        if result['status'] == 'success':
            print(f"\n🎉 Successfully processed {result['total_locations']} location groups!")
            
            for location_name, location_result in result['locations_processed'].items():
                if 'error' in location_result:
                    print(f"❌ {location_name}: {location_result['error']}")
                else:
                    print(f"✅ {location_name}: {location_result['files_processed']} files → {Path(location_result['combined_file']).name}")
                    
                    # Show pipeline status
                    pipeline_status = result['pipeline_results'].get(location_name, False)
                    if pipeline_status:
                        print(f"   🚀 Pipeline triggered successfully!")
                    elif args.no_pipeline:
                        print(f"   ⏭️  Pipeline skipped (--no-pipeline)")
                    else:
                        print(f"   ⚠️  Pipeline failed to trigger")
            
            if not args.no_pipeline and any(result['pipeline_results'].values()):
                print("\n📱 Check your Slack for notifications!")
        elif result['status'] == 'no_new_files':
            print("ℹ️  No new files to process")
        else:
            print(f"❌ Processing failed: {result.get('message', 'Unknown error')}")
            return 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()), file_path.parent.name)
                if match:
                    return int(match.group(1))
            except:
                pass
            return 999  # Put unmatched files at the end
        
        sorted_files = sorted(transcript_files, key=extract_video_number)
        
        for transcript_file in sorted_files:
            content = self.extract_transcript_content(transcript_file)
            if not content:
                continue
            
            # Add to individual transcripts
            combined_data['combined_transcript']['content']['individual_transcripts'].append({
                'source_file': content['source_file'],
                'video_folder': transcript_file.parent.name,
                'file_path': content['file_path'],
                'processing_type': content['processing_type'],
                'text_content': content['full_text'],
                'segment_count': len(content['segments'])
            })
            
            # Add to metadata
            combined_data['combined_transcript']['metadata']['source_files'].append({
                'file': content['source_file'],
                'video_folder': transcript_file.parent.name,
                'type': content['processing_type']
            })
            
            # Add text content with video separator
            if content['full_text']:
                video_name = transcript_file.parent.name
                separator = f"\n\n--- {video_name} ({content['processing_type']}) ---\n"
                all_text_parts.append(separator + content['full_text'])
        
        # Combine all text
        combined_data['combined_transcript']['content']['full_text'] = '\n'.join(all_text_parts)
        
        return combined_data
    
    def save_combined_transcript(self, combined_data):
        """
        Save the combined transcript for your existing pipeline.
        
        Args:
            combined_data (Dict): Combined transcript data
            
        Returns:
            Path: Path to saved combined transcript
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"combined_transcript_{timestamp}.json"
        output_path = self.input_transcripts_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Combined transcript saved: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error saving combined transcript: {e}")
            raise
    
    def mark_files_as_processed(self, processed_files):
        """
        Mark files as processed to avoid reprocessing.
        
        Args:
            processed_files (List[Path]): Files that were processed
        """
        # Load existing log
        log_data = {'processed_files': [], 'last_run': None}
        if self.processed_log.exists():
            try:
                with open(self.processed_log, 'r') as f:
                    log_data = json.load(f)
            except Exception:
                pass
        
        # Add new files
        existing_files = set(log_data.get('processed_files', []))
        for file_path in processed_files:
            existing_files.add(str(file_path))
        
        # Save updated log
        log_data['processed_files'] = list(existing_files)
        log_data['last_run'] = datetime.now().isoformat()
        
        try:
            with open(self.processed_log, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save processed files log: {e}")
    
    def trigger_existing_pipeline(self, combined_transcript_path):
        """
        Trigger your existing complete_oauth_pipeline.py with the combined transcript.
        
        Args:
            combined_transcript_path (Path): Path to the combined transcript
            
        Returns:
            bool: True if pipeline was triggered successfully
        """
        try:
            # Import your existing pipeline
            from complete_oauth_pipeline import CompletePipeline
            
            print("🚀 Triggering your existing AI content pipeline...")
            
            # Initialize your pipeline (adjust parameters as needed)
            pipeline = CompletePipeline()
            
            # Process the combined transcript
            # Adjust location and date as needed, or extract from transcript metadata
            result = pipeline.process_transcript_to_blog(
                str(combined_transcript_path),
                location="Adventure Location",  # You can customize this
                date=datetime.now().strftime("%B %Y")
            )
            
            print("✅ Pipeline completed successfully!")
            print(f"📄 Google Doc: {result['doc_info']['doc_url']}")
            print(f"📊 Tracking Sheet: {result['sheet_info']['sheet_url']}")
            
            return True
            
        except ImportError as e:
            print(f"❌ Could not import your pipeline: {e}")
            print("Make sure complete_oauth_pipeline.py is in the same directory")
            return False
        except Exception as e:
            print(f"❌ Error running pipeline: {e}")
            return False
    
    def run(self, trigger_pipeline=True):
        """
        Run the complete auto-combination process.
        
        Args:
            trigger_pipeline (bool): Whether to trigger your existing pipeline
            
        Returns:
            Dict: Processing results
        """
        print("🎬 Starting auto transcript combination...")
        
        # Find new transcript files
        new_files = self.find_new_transcript_files()
        
        if not new_files:
            print("ℹ️  No new transcript files found")
            return {'status': 'no_new_files', 'message': 'No new transcript files to process'}
        
        print(f"📁 Found {len(new_files)} new transcript files:")
        for file in new_files:
            print(f"  - {file.name}")
        
        # Combine transcripts
        print("🔄 Combining transcripts...")
        combined_data = self.combine_transcripts(new_files)
        
        # Save combined transcript
        combined_file = self.save_combined_transcript(combined_data)
        
        # Mark files as processed
        self.mark_files_as_processed(new_files)
        
        # Trigger your existing pipeline if requested
        pipeline_success = False
        if trigger_pipeline:
            pipeline_success = self.trigger_existing_pipeline(combined_file)
        
        return {
            'status': 'success',
            'files_processed': len(new_files),
            'combined_file': str(combined_file),
            'pipeline_triggered': pipeline_success,
            'source_files': [f.name for f in new_files]
        }

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Auto-combine transcript files and trigger existing AI content pipeline'
    )
    parser.add_argument(
        '--video-processor-path',
        default='../video-processor',
        help='Path to video processor directory'
    )
    parser.add_argument(
        '--no-pipeline',
        action='store_true',
        help='Only combine transcripts, don\'t trigger the pipeline'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check for new files, don\'t process them'
    )
    
    args = parser.parse_args()
    
    try:
        combiner = TranscriptAutoCombiner(
            video_processor_path=args.video_processor_path
        )
        
        if args.check_only:
            new_files = combiner.find_new_transcript_files()
            if new_files:
                print(f"📁 Found {len(new_files)} new transcript files:")
                for file in new_files:
                    print(f"  - {file.name}")
            else:
                print("ℹ️  No new transcript files found")
            return 0
        
        # Run the combination process
        result = combiner.run(trigger_pipeline=not args.no_pipeline)
        
        if result['status'] == 'success':
            print(f"\n🎉 Successfully processed {result['files_processed']} transcript files!")
            print(f"📄 Combined file: {result['combined_file']}")
            if result['pipeline_triggered']:
                print("🚀 Your AI content pipeline was triggered!")
                print("📱 Check your Slack for the notification!")
        elif result['status'] == 'no_new_files':
            print("ℹ️  No new files to process")
        else:
            print(f"❌ Processing failed: {result.get('message', 'Unknown error')}")
            return 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())