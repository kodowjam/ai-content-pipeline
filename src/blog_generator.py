import json
import os
from datetime import datetime
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BlogGenerator:
    def __init__(self):
        self.anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    
    def generate_trip_report(self, transcript_data, location=None, date=None):
        """
        Generate a trip report blog post from video transcript data.
        """
        # Extract text from transcript segments
        full_text = self._extract_text_from_transcript(transcript_data)
        
        # Generate the blog post using Claude
        blog_content = self._generate_blog_with_claude(full_text, location, date)
        
        return blog_content
    
    def _extract_text_from_transcript(self, transcript_data):
        """Extract and combine text from transcript segments"""
        if isinstance(transcript_data, list):
            return " ".join([segment.get('text', '') for segment in transcript_data])
        elif isinstance(transcript_data, dict):
            if 'filtered_transcription' in transcript_data:
                return " ".join([segment.get('text', '') for segment in transcript_data['filtered_transcription']])
            elif 'text' in transcript_data:
                return transcript_data['text']
        
        return str(transcript_data)
    
    def _generate_blog_with_claude(self, transcript_text, location, date):
        """Use Claude to generate an engaging trip report"""
        
        prompt = f"""You are an expert travel blogger who creates inspiring, SEO-optimized trip reports written in a personal journal style.

Transform this raw video transcript into a compelling first-person blog post:

TRANSCRIPT:
{transcript_text}

WRITING REQUIREMENTS:
- Write in first person as if reading from a personal journal
- Keep under 500 words total
- Create an engaging, SEO-friendly title with primary keyword
- Use a conversational, intimate tone like sharing with a close friend
- Include 2-3 relevant subheadings for readability
- Add [IMAGE: description] placeholders where photos would enhance the story
- End with an inspiring quote from a famous environmentalist that connects to the experience
- Make readers feel the wonder and value of nature

SEO REQUIREMENTS:
- Include location-based keywords naturally throughout
- Optimize for search terms like "hiking [location]", "[location] trail report", "outdoor adventure [location]"
- Create compelling meta description under 150 characters
- Suggest relevant tags for outdoor/nature content

{f"LOCATION: {location}" if location else ""}
{f"DATE: {date}" if date else ""}

Respond with a JSON object in this exact format:
{{
  "title": "SEO-optimized blog post title with location keywords",
  "meta_description": "Under 150 character meta description with location keywords",
  "content": "Complete journal-style blog post under 500 words with [IMAGE: description] placeholders and inspirational quote",
  "tags": ["location-tag", "hiking", "nature", "outdoor-adventure", "trail-report"],
  "suggested_images": ["scenic description", "action description", "detail description"],
  "word_count": 450,
  "primary_keyword": "main SEO keyword phrase",
  "environmentalist_quote_author": "name of quoted environmentalist"
}}

DO NOT include any markdown formatting like ```json or ```. Respond with ONLY the JSON object."""
        
        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Clean up the response - remove any markdown formatting
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            # Find JSON object if there's extra text
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                response_text = response_text[start_idx:end_idx]
            
            print(f"Cleaned Claude response: {response_text[:200]}...")
            
            blog_data = json.loads(response_text)
            
            blog_data['generated_date'] = datetime.now().isoformat()
            blog_data['source_transcript_length'] = len(transcript_text)
            
            return blog_data
            
        except json.JSONDecodeError as e:
            print(f"Error parsing Claude JSON response: {e}")
            print(f"Raw response: {response_text}")
            return self._create_fallback_blog(transcript_text, location, date)
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return self._create_fallback_blog(transcript_text, location, date)
    
    def _create_fallback_blog(self, transcript_text, location, date):
        """Create a basic blog structure if Claude fails"""
        return {
            "title": f"Trip Report: {location or 'Adventure'}" + (f" - {date}" if date else ""),
            "meta_description": "An adventure travel report with insights and experiences.",
            "content": f"# Trip Report\n\n{transcript_text[:500]}...",
            "tags": ["travel", "adventure", "trip-report"],
            "suggested_images": ["landscape", "activity", "personal"],
            "word_count": len(transcript_text.split()),
            "generated_date": datetime.now().isoformat(),
            "source_transcript_length": len(transcript_text),
            "note": "Fallback content - Claude API unavailable"
        }

def test_blog_generator():
    """Test function for the blog generator"""
    print("Testing blog generator...")
    generator = BlogGenerator()
    
    sample_transcript = [
        {"start": 0, "end": 5, "text": "Today I'm hiking up Mount Washington, it's an absolutely beautiful day."},
        {"start": 5, "end": 10, "text": "The trail is pretty challenging but the views are incredible."},
        {"start": 10, "end": 15, "text": "I can see for miles from up here, definitely worth the effort."}
    ]
    
    result = generator.generate_trip_report(sample_transcript, "Mount Washington", "July 2025")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_blog_generator()
