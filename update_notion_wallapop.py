#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_notion_wallapop.py
Updates a Notion product page after successful Wallapop publication:
  - Writes listing URL to "Wallapop Posted"
  - Sets "Wal 1" checkbox = True  (account slot tracker)

Usage:
  python update_notion_wallapop.py <notion_id> <wallapop_url>
  python update_notion_wallapop.py <wallapop_url>       ← reads notion_id from temp/product_data.json
  python update_notion_wallapop.py                       ← reads notion_id from temp/product_data.json,
                                                           URL from env WALLAPOP_URL
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
    """
    Update Notion page:
      - Wallapop Posted ← wallapop_url
      - Wal 1 checkbox  ← True
    """
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
            },
            'Wal 1': {
                'checkbox': True
            }
        }
    }

    resp = requests.patch(
        f'https://api.notion.com/v1/pages/{notion_id}',
        headers=HEADERS,
        json=payload
    )

    if resp.status_code == 200:
        print(f'OK Updated: {notion_id}')
        print(f'   Wallapop Posted = {wallapop_url}')
        print(f'   Wal 1 = True')
        return True
    else:
        # If Wal 1 doesn't exist yet, try without it
        if '"Wal 1"' in resp.text or 'property' in resp.text.lower():
            print(f'WARN: Wal 1 field not found in DB, writing URL only', file=sys.stderr)
            payload2 = {
                'properties': {
                    'Wallapop Posted': payload['properties']['Wallapop Posted']
                }
            }
            resp2 = requests.patch(
                f'https://api.notion.com/v1/pages/{notion_id}',
                headers=HEADERS, json=payload2
            )
            if resp2.status_code == 200:
                print(f'OK Updated URL only (Wal 1 field missing): {notion_id} → {wallapop_url}')
                return True

        print(f'ERROR {resp.status_code}: {resp.text[:300]}')
        return False


def main():
    notion_id   = None
    wallapop_url = None

    if len(sys.argv) == 3:
        notion_id    = sys.argv[1].strip()
        wallapop_url = sys.argv[2].strip()
    elif len(sys.argv) == 2:
        wallapop_url = sys.argv[1].strip()
        if PRODUCT_DATA_FILE.exists():
            data = json.loads(PRODUCT_DATA_FILE.read_text(encoding='utf-8'))
            notion_id = data.get('notion_id')
        else:
            print('ERROR: product_data.json not found and no notion_id provided')
            sys.exit(1)
    else:
        if PRODUCT_DATA_FILE.exists():
            data = json.loads(PRODUCT_DATA_FILE.read_text(encoding='utf-8'))
            notion_id    = data.get('notion_id')
            wallapop_url = os.getenv('WALLAPOP_URL')
            if not wallapop_url:
                print('ERROR: WALLAPOP_URL env variable not set')
                sys.exit(1)
        else:
            print('ERROR: product_data.json not found')
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
