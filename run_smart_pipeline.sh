#!/bin/bash
# Smart Pipeline Shortcut
# Run this whenever you have new videos processed

echo "🎬 Running Smart Pipeline..."
cd "$(dirname "$0")"
source content-env/bin/activate
python3 smart_pipeline_runner.py
echo "✅ Done! Check Slack for notifications."
