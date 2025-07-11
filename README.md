# AI Content Pipeline 🚀

Transform video transcripts into SEO-optimized blog posts automatically using AI, with Google Docs integration and Slack notifications.

## Features

- 🤖 **AI Blog Generation** - Claude creates journal-style trip reports with environmentalist quotes
- 📄 **Google Docs Integration** - Automatically creates formatted Google Docs
- 📊 **Spreadsheet Tracking** - Logs all posts with metadata and status
- 📱 **Slack Notifications** - Rich notifications with direct links
- 🔍 **SEO Optimized** - Keywords, meta descriptions, and structured content
- 💾 **Local Backups** - JSON files saved locally

## Quick Start

### Prerequisites
- Python 3.9+
- Google Cloud Project with Docs/Drive/Sheets APIs enabled
- Slack workspace with webhook
- Anthropic API key

### Installation

1. **Clone and setup:**
```bash
git clone https://github.com/kodowjam/ai-content-pipeline.git
cd ai-content-pipeline
python3 -m venv content-env
source content-env/bin/activate
pip install -r requirements.txt

