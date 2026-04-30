# -*- coding: utf-8 -*-
"""Safe Wallapop catalog matching utilities.

Shared by the three Wallapop poster projects. Pure helpers are intentionally
small/testable: no Notion, no browser side effects here.
"""
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

STOP_TOKENS = {
    'de', 'del', 'la', 'el', 'y', 'con', 'sin', 'para', 'por', 'the', 'and', 'for',
    'color', 'negro', 'blanco', 'nuevo', 'nueva', 'producto', 'pack', 'compatible',
    'universal', 'digital', 'smart', 'inalambrico', 'bluetooth', 'gaming', 'cable',
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize('NFD', (value or '').lower()).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-z0-9\s]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def meaningful_tokens(value: str) -> set[str]:
    return {t for t in normalize_text(value).split() if len(t) >= 2 and t not in STOP_TOKENS}


def model_like_tokens(value: str) -> set[str]:
    toks = meaningful_tokens(value)
    return {t for t in toks if any(c.isdigit() for c in t)}


def extract_euro_prices(value: str) -> set[int]:
    prices = set()
    for match in re.finditer(r'(\d+(?:[,.]\d{1,2})?)\s*€', value or ''):
        try:
            prices.add(int(round(float(match.group(1).replace(',', '.')))))
        except Exception:
            pass
    return prices


def price_int(value: Any) -> Optional[int]:
    if value in (None, ''):
        return None
    if isinstance(value, dict):
        value = value.get('amount')
    try:
        return int(round(float(value)))
    except Exception:
        return None


def candidate_text(item: Dict[str, Any]) -> str:
    parts = [str(item.get('title') or '')]
    p = price_int(item.get('price'))
    if p is not None:
        parts.append(f'{p} €')
    if item.get('published'):
        parts.append(str(item.get('published')))
    return ' '.join(parts)


def is_safe_catalog_match(expected: str, actual: str, expected_price: Any = None) -> Tuple[bool, int, int, bool]:
    expected_tokens = meaningful_tokens(expected)
    actual_tokens = meaningful_tokens(actual)
    overlap = len(expected_tokens & actual_tokens)
    required = min(4, max(3, len(expected_tokens) // 3))

    expected_int = price_int(expected_price)
    actual_prices = extract_euro_prices(actual)
    price_ok = expected_int is None or expected_int in actual_prices
    close_price_ok = expected_int is not None and any(abs(expected_int - p) <= 2 for p in actual_prices)

    expected_models = model_like_tokens(expected)
    actual_models = model_like_tokens(actual)
    model_ok = (not expected_models) or bool(expected_models & actual_models)
    distinctive_ok = bool((expected_tokens - STOP_TOKENS) & (actual_tokens - STOP_TOKENS))

    if expected_models and not model_ok:
        return (False, overlap, required, bool(price_ok))

    high_overlap_ok = overlap >= required and (model_ok or distinctive_ok)
    medium_overlap_ok = overlap >= 2 and distinctive_ok and (model_ok or not expected_models)
    low_overlap_ok = overlap >= 1 and distinctive_ok and bool(expected_models) and model_ok
    strong_text_ok = high_overlap_ok or medium_overlap_ok or low_overlap_ok
    identity_price_ok = price_ok or (close_price_ok and overlap >= 4 and distinctive_ok)
    return (strong_text_ok and identity_price_ok), overlap, required, bool(price_ok)


def choose_unique_match(name: str, price: Any, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    matches: List[Dict[str, Any]] = []
    for item in items or []:
        text = candidate_text(item)
        ok, score, required, price_ok = is_safe_catalog_match(name, text, price)
        if ok and item.get('href'):
            enriched = dict(item)
            enriched['_score'] = score
            enriched['_required'] = required
            enriched['_price_ok'] = price_ok
            matches.append(enriched)
    matches.sort(key=lambda x: (x.get('_score', 0), x.get('_price_ok', False)), reverse=True)
    if not matches:
        return {'status': 'no_match', 'matches': []}
    best = matches[0]
    ambiguous = [m for m in matches[1:] if m.get('_score', 0) >= best.get('_score', 0) - 1]
    if ambiguous:
        return {'status': 'ambiguous', 'matches': matches[:5]}
    return {'status': 'unique_match', 'match': best, 'matches': matches[:5]}


def catalog_api_js() -> str:
    """Async JS expression body returning all active catalog-management items."""
    return r"""
    async () => {
      const token = (document.cookie.split('; ').find(x => x.startsWith('accessToken=')) || '').split('=').slice(1).join('=');
      const headers = {
        'content-type': 'application/json',
        'authorization': 'Bearer ' + token,
        'x-deviceos': '0',
        'deviceos': '0',
        'x-appversion': '820020',
        'x-deviceid': 'fdcc5f3b-ce99-44d9-ae00-bd62f3bba613'
      };
      const out = [];
      let next = null;
      const seenNext = new Set();
      for (let page = 0; page < 30; page++) {
        const body = {filter:{status:'active', type:'CONSUMERGOODS'}, sort:{property:'publish_date', order:'desc'}};
        if (next) body.search_after = next;
        const r = await fetch('https://api.wallapop.com/api/v3/catalog-management/search', {
          method:'POST', headers, body: JSON.stringify(body)
        });
        if (!r.ok) return {error:'catalog_search_failed', status:r.status, text:(await r.text()).slice(0,500), data:out};
        const j = await r.json();
        for (const item of (j.data || [])) {
          const slug = item.slug || item.web_slug || '';
          out.push({
            id: item.id || '',
            title: item.title || '',
            price: item.price && item.price.amount,
            href: slug ? 'https://es.wallapop.com/item/' + slug : '',
            slug,
            published: item.publish_date || item.modified_date || '',
          });
        }
        next = j.meta && (j.meta.next || j.meta.search_after || j.meta.since);
        if (!next || seenNext.has(next)) break;
        seenNext.add(next);
      }
      return {data: out};
    }
    """
