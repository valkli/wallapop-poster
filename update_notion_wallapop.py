#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_notion_wallapop.py
Updates a Notion product page with the published Wallapop URL.

Usage:
  python update_notion_wallapop.py <notion_id> <wallapop_url>
  python update_notion_wallapop.py <wallapop_url>       ← reads notion_id from temp/product_data.json
  python update_notion_wallapop.py                       ← reads both from env WALLAPOP_URL
"""

import os
import sys
import json
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

NOTION_API_KEY = os.getenv('NOTION_API_KEY')
HEADERS = {
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

PRODUCT_DATA_FILE = Path(__file__).parent / 'temp' / 'product_data.json'


def update_notion(notion_id: str, wallapop_url: str) -> bool:
    """Update Notion page with published Wallapop URL."""
    payload = {
        'properties': {
            'Wallapop Posted': {
                'rich_text': [
                    {
                        'type': 'text',
                        'text': {
                            'content': wallapop_url,
                            'link': {'url': wallapop_url}
                        }
                    }
                ]
            }
        }
    }

    resp = requests.patch(
        f'https://api.notion.com/v1/pages/{notion_id}',
        headers=HEADERS,
        json=payload
    )

    if resp.status_code == 200:
        print(f'OK Updated: {notion_id} → {wallapop_url}')
        return True
    else:
        print(f'ERROR {resp.status_code}: {resp.text[:300]}')
        return False


def main():
    notion_id = None
    wallapop_url = None

    if len(sys.argv) == 3:
        notion_id = sys.argv[1].strip()
        wallapop_url = sys.argv[2].strip()
    elif len(sys.argv) == 2:
        wallapop_url = sys.argv[1].strip()
        if PRODUCT_DATA_FILE.exists():
            with open(PRODUCT_DATA_FILE, encoding='utf-8') as f:
                data = json.load(f)
            notion_id = data.get('notion_id')
        else:
            print('ERROR: product_data.json not found and no notion_id provided')
            sys.exit(1)
    elif len(sys.argv) == 1:
        if PRODUCT_DATA_FILE.exists():
            with open(PRODUCT_DATA_FILE, encoding='utf-8') as f:
                data = json.load(f)
            notion_id = data.get('notion_id')
            wallapop_url = os.getenv('WALLAPOP_URL')
            if not wallapop_url:
                print('ERROR: WALLAPOP_URL env variable not set')
                print('Usage: WALLAPOP_URL=https://... python update_notion_wallapop.py')
                sys.exit(1)
        else:
            print('ERROR: product_data.json not found')
            sys.exit(1)
    else:
        print('Usage: python update_notion_wallapop.py [notion_id] <wallapop_url>')
        sys.exit(1)

    if not notion_id:
        print('ERROR: notion_id is empty')
        sys.exit(1)

    if not wallapop_url or not wallapop_url.startswith('http'):
        print(f'ERROR: invalid URL: {wallapop_url}')
        sys.exit(1)

    success = update_notion(notion_id, wallapop_url)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
