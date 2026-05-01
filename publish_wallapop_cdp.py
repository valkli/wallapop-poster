#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_wallapop_cdp.py — Full Wallapop publish flow via Playwright CDP.
Connects to Chromium on CDP port 18801 (mixmix profile).

Wallapop upload form steps:
  1. Select "Algo que ya no necesito"
  2. Fill "Resumen del producto" (50 chars) → Continuar
  3. Upload photo → Continuar #2 (after photos)
  4. Open category dropdown → select AI-suggested or manual category
  5. Wallapop AI auto-fills title + description
  6. Fill price_amount (mandatory)
  7. Select weight radio button for shipping
  8. Click "Subir producto"

Reads: temp/product_data.json + temp/product_image.jpg
Output:  OK <url>  |  ERROR <msg>
"""

import sys, json, time, re, urllib.request
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from wallapop_safe import catalog_api_js, choose_unique_match, is_safe_catalog_match as safe_catalog_match

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SCRIPT_DIR   = Path(__file__).parent
PRODUCT_DATA = SCRIPT_DIR / 'temp' / 'product_data.json'
IMAGE_FILE   = SCRIPT_DIR / 'temp' / 'product_image.jpg'

CDP_PORT = 18801
CDP_URL  = f'http://127.0.0.1:{CDP_PORT}'
UPLOAD_URL = 'https://es.wallapop.com/app/catalog/upload'

CHROMIUM_PATH   = r'C:\Users\Val\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe'
BROWSER_PROFILE = r'C:\Users\Val\.openclaw\browser\mixmix'


def log(msg): print(f'  {msg}', file=sys.stderr, flush=True)
def ss(page, name):
    try:
        page.screenshot(path=str(SCRIPT_DIR / 'temp' / f'{name}.png'), timeout=10000)
        log(f'📷 {name}')
    except Exception:
        log(f'📷 {name} (screenshot skipped)')


def ensure_browser():
    try:
        urllib.request.urlopen(f'{CDP_URL}/json/version', timeout=3)
        return True
    except Exception:
        pass
    import subprocess
    subprocess.Popen([
        CHROMIUM_PATH,
        f'--user-data-dir={BROWSER_PROFILE}',
        f'--remote-debugging-port={CDP_PORT}',
        '--no-first-run',
        '--new-window',
        UPLOAD_URL,
    ])
    for _ in range(15):
        time.sleep(2)
        try:
            urllib.request.urlopen(f'{CDP_URL}/json/version', timeout=3)
            return True
        except Exception:
            pass
    return False

def fill(page, sel, value, label=''):
    """Fill a field using Playwright locator (pierces shadow DOM)."""
    try:
        loc = page.locator(sel)
        if loc.count() > 0:
            el = loc.first
            # Scroll into view first, then check visibility
            try: el.scroll_into_view_if_needed(timeout=5000)
            except Exception: pass
            if el.is_visible(timeout=3000):
                el.click()
                time.sleep(0.3)
                # Use fill() first (clears + types with proper events)
                el.fill(value)
                # Verify the value was set
                actual = el.input_value()
                if actual == value:
                    log(f'✓ {label}: "{value[:40]}"')
                    return True
                # If fill() didn't stick, try press_sequentially (types char by char)
                el.click()
                el.evaluate('e => e.value = ""')
                el.press_sequentially(value, delay=50)
                log(f'✓ {label} (typed): "{value[:40]}"')
                return True
    except Exception as e:
        pass
    return False

def weight_from_grams(g):
    """Map weight in grams to radio button index (0=0-1kg, 1=1-2kg, etc.)."""
    kg = g / 1000 if g > 0 else 0.5
    if kg <= 1: return 0
    if kg <= 2: return 1
    if kg <= 5: return 2
    if kg <= 10: return 3
    if kg <= 20: return 4
    return 5


def normalize_text(value: str) -> str:
    import unicodedata
    value = ''.join(
        ch for ch in unicodedata.normalize('NFD', (value or '').lower())
        if not unicodedata.combining(ch)
    )
    # Preserve non-Latin identity tokens (e.g. Cyrillic product titles) for safe
    # matching. ASCII-only normalization made titles like `Boo Защитный чехол`
    # collapse to one token and blocked URL capture after successful submit.
    value = re.sub(r'[^\w\s]+', ' ', value, flags=re.UNICODE)
    value = value.replace('_', ' ')
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def meaningful_tokens(value: str) -> set:
    stop = {'de', 'del', 'la', 'el', 'y', 'con', 'sin', 'para', 'por', 'the', 'and', 'for'}
    return {t for t in normalize_text(value).split() if len(t) >= 3 and t not in stop}


def token_overlap_score(expected: str, actual: str) -> int:
    return len(meaningful_tokens(expected) & meaningful_tokens(actual))


def model_like_tokens(value: str) -> set:
    return {t for t in normalize_text(value).split() if any(ch.isdigit() for ch in t) and len(t) >= 2}


def distinctive_tokens(value: str) -> set:
    common = {
        'teclado', 'mouse', 'raton', 'gaming', 'inalambrico', 'bluetooth', 'negro', 'blanco',
        'nuevo', 'funda', 'cargador', 'adaptador', 'soporte', 'cable', 'pack', 'color',
        'completo', 'peliculas', 'coleccion', 'producto', 'universal', 'digital', 'smart',
    }
    return {t for t in meaningful_tokens(value) if len(t) >= 6 and t not in common}


def extract_euro_prices(value: str) -> set:
    prices = set()
    for match in re.finditer(r'(\d+(?:[,.]\d{1,2})?)\s*€', value or ''):
        raw = match.group(1).replace(',', '.')
        try:
            prices.add(int(round(float(raw))))
        except Exception:
            continue
    return prices


def is_safe_catalog_match(expected: str, actual: str, expected_price=None) -> tuple[bool, int, int, bool]:
    expected_tokens = meaningful_tokens(expected)
    actual_tokens = meaningful_tokens(actual)
    overlap = len(expected_tokens & actual_tokens)
    required = 3
    price_ok = False
    close_price_ok = False
    if expected_price not in (None, ''):
        try:
            expected_int = int(round(float(expected_price)))
            actual_prices = extract_euro_prices(actual)
            price_ok = expected_int in actual_prices
            close_price_ok = any(abs(expected_int - p) <= 2 for p in actual_prices)
        except Exception:
            price_ok = False
    expected_model_tokens = model_like_tokens(expected)
    actual_model_tokens = model_like_tokens(actual)
    model_ok = True
    if expected_model_tokens:
        model_ok = bool(expected_model_tokens & actual_model_tokens)
    distinctive_ok = bool(distinctive_tokens(expected) & distinctive_tokens(actual))
    # Accept translated/AI-rewritten titles when a distinctive brand/token and an exact
    # model-like token still survive, e.g. RhinoShield + 9H with exact price.
    high_overlap_ok = overlap >= required and (model_ok or distinctive_ok)
    medium_overlap_ok = overlap >= 2 and distinctive_ok and (model_ok or not expected_model_tokens)
    low_overlap_ok = overlap >= 1 and distinctive_ok and bool(expected_model_tokens) and model_ok
    strong_text_ok = high_overlap_ok or medium_overlap_ok or low_overlap_ok
    identity_price_ok = price_ok or (close_price_ok and overlap >= 4 and distinctive_ok)
    return (strong_text_ok and identity_price_ok), overlap, required, price_ok


def is_fresh_catalog_item(item: dict) -> bool:
    """True for items published/modified recently enough after submit.

    API returns millisecond timestamps; old DOM extractor returned date text.
    Use a 48h window as safe freshness guard for delayed catalog indexing.
    """
    import time
    raw = str(item.get('published', '') or '')
    try:
        ts = int(float(raw)) / 1000.0
        return (time.time() - ts) < 48 * 3600
    except Exception:
        today = datetime.now().strftime('%d/%m/%Y')
        return today in f"{item.get('title', '')} {raw}"


def extract_catalog_candidates(page):
    """Fetch the full active Wallapop management catalog via API, all pages.

    Returning title+price text keeps compatibility with old local matchers.
    """
    try:
        result = page.evaluate(catalog_api_js())
        if isinstance(result, dict) and result.get('error'):
            log(f"⚠ Catalog API error: {result.get('error')} status={result.get('status')} text={result.get('text')}")
            return []
        rows = (result or {}).get('data', []) if isinstance(result, dict) else []
        out = []
        for item in rows:
            price = item.get('price')
            title = item.get('title') or ''
            title_with_price = f"{title} {int(price)} €" if price not in (None, '') else title
            out.append({
                'id': item.get('id', ''),
                'href': item.get('href', ''),
                'title': title_with_price,
                'published': str(item.get('published', '')),
                'price': price,
            })
        log(f'✓ Catalog API items loaded: {len(out)}')
        return out
    except Exception as e:
        log(f'⚠ Catalog API fetch failed: {e}')
        return []


# ═══════════════════════════ MAIN ════════════════════════════════

def main():
    if not PRODUCT_DATA.exists(): print('ERROR product_data.json not found'); sys.exit(1)
    with open(PRODUCT_DATA, encoding='utf-8') as f: data = json.load(f)

    props    = data['properties']
    name     = props.get('Name', '')
    price    = props.get('Selling Price', 0)
    brand    = props.get('brand', '')
    model_s  = props.get('model', '')
    cat_wal  = props.get('Cat-Wallapop', 'Otros')
    weight_g = props.get('Weight', 0)

    summary = name[:50]

    log(f'Product: {name[:60]}')
    log(f'Price: {price}€ | Cat: {cat_wal} | Weight: {weight_g}g')

    if not ensure_browser(): print('ERROR browser_not_started'); sys.exit(1)
    if not IMAGE_FILE.exists(): print('ERROR image missing'); sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]

        # Use a fresh tab for each publish attempt. The mixmix profile often has
        # several old Wallapop tabs open, and reusing one can race with stale
        # navigations, making upload/file inputs detach mid-flow.
        page = context.new_page()

        # ── 0. Pre-check existing catalog listing ────────────────
        log('→ 0. Check existing catalog match')
        page.goto('https://es.wallapop.com/app/catalog/management/consumergoods', timeout=60_000, wait_until='domcontentloaded')
        time.sleep(5)
        if 'login' in page.url.lower(): print('ERROR not_logged_in'); return
        items = extract_catalog_candidates(page)
        best = None
        best_score = 0
        best_required = 0
        best_price_ok = False
        for item in items or []:
            ok, score, required, price_ok = safe_catalog_match(name, item.get('title', ''), price)
            if (price_ok, score) > (best_price_ok, best_score):
                best = item
                best_score = score
                best_required = required
                best_price_ok = price_ok
            # Pre-existing listing reuse must be stricter than post-submit URL
            # capture. A loose low-score match can falsely bind a new Notion
            # product to an unrelated old listing with the same price.
            if ok and score >= required and price_ok and '/item/' in item.get('href', ''):
                log(
                    f'✅ Existing catalog listing matched: {item.get("href")} '
                    f'(score={score}, required={required}, price_ok={price_ok}, title={item.get("title", "")[:80]!r})'
                )
                print(f'OK {item.get("href")}')
                return
        log(f'  No existing match, best_score={best_score}, required={best_required}, price_ok={best_price_ok}')

        # ── 1. Navigate ──────────────────────────────────────────
        log('→ 1. Navigate')
        page.goto(UPLOAD_URL, timeout=60_000, wait_until='domcontentloaded')
        time.sleep(5)
        page.wait_for_load_state('domcontentloaded', timeout=30_000)
        time.sleep(3)
        if 'login' in page.url.lower(): print('ERROR not_logged_in'); return

        # ── 2. Select type ────────────────────────────────────────
        log('→ 2. Select type')
        try:
            page.locator('text="Algo que ya no necesito"').first.click()
            log('✓ Clicked type')
        except Exception: log('⚠ Type button not found')
        time.sleep(3)

        # ── 3. Fill summary ───────────────────────────────────────
        log('→ 3. Fill summary')
        if not fill(page, 'input[name="summary"]', summary, 'Summary'):
            print('ERROR summary_not_found'); return
        time.sleep(1)

        # ── 4. Click Continuar #1 ─────────────────────────────────
        log('→ 4. Continuar #1')
        cont = page.locator('button:has-text("Continuar")')
        # Wait for it to be enabled (summary must be filled)
        for _ in range(10):
            if cont.first.is_enabled(): break
            time.sleep(0.5)
        cont.first.click()
        log('✓ Continuar #1 clicked')
        time.sleep(3)

        # ── 5. Upload photo ───────────────────────────────────────
        log('→ 5. Upload photo')
        file_loc = page.locator('#dropAreaPreviewInput')
        if file_loc.count() == 0:
            file_loc = page.locator('input[type="file"]')
        file_loc.first.set_input_files(str(IMAGE_FILE))
        time.sleep(3)
        log(f'✓ Photo: {IMAGE_FILE.stat().st_size // 1024}KB')

        # ── 6. Click Continuar #2 (after photos) ──────────────────
        log('→ 6. Continuar #2')
        cont2 = page.locator('button:has-text("Continuar")')
        # Find second Continuar (nth(1))
        for _ in range(16):
            if cont2.count() >= 2 and cont2.nth(1).is_enabled(): break
            time.sleep(0.5)
        if cont2.count() >= 2:
            cont2.nth(1).click()
        else:
            # Fallback: click last enabled Continuar
            for i in range(cont2.count() - 1, -1, -1):
                if cont2.nth(i).is_enabled():
                    cont2.nth(i).click(); break
        log('✓ Continuar #2 clicked')
        time.sleep(4)
        ss(page, 'after_cont2')

        # ── 7. Open category dropdown and select ──────────────────
        log('→ 7. Category selection')
        cat_dd = page.locator('text="Categoría y subcategoría"')
        if cat_dd.count() > 0 and cat_dd.first.is_visible():
            cat_dd.first.click()
            time.sleep(3)
            log('✓ Dropdown opened')

            # Wait a moment for AI suggestions to load
            time.sleep(1)
            
            # Try AI-suggested LEAF categories first (no subcategories)
            # These appear in "Categorías sugeridas" section and are safe to click
            ai_leaf_cats = ['Artículos de escritorio', 'Material de oficina', 'Papelería',
                           'Manualidades']
            
            selected = False
            for cat in ai_leaf_cats:
                loc = page.locator(f'text="{cat}"')
                cnt = loc.count()
                if cnt > 0:
                    for i in range(cnt):
                        el = loc.nth(i)
                        try:
                            if el.is_visible(timeout=2000):
                                el.click(timeout=5000)
                                log(f'✓ Category (AI leaf): {cat}')
                                selected = True
                                break
                        except Exception:
                            continue
                if selected: break

            if not selected:
                # No leaf category found. Try parent + subcategory approach
                # Click a parent category, then select a subcategory
                parent_cats = ['Coleccionismo', 'Hogar y jardín', 'Construcción y reformas']
                for parent in parent_cats:
                    loc = page.locator(f'text="{parent}"')
                    cnt = loc.count()
                    for i in range(cnt):
                        el = loc.nth(i)
                        try:
                            if el.is_visible(timeout=1000):
                                el.click(timeout=5000)
                                log(f'  Clicked parent: {parent}')
                                time.sleep(2)
                                # Now select first available subcategory or "Solo seleccionar"
                                for sub in ['Artículos de escritorio', 'Manualidades',
                                           f'Sólo seleccionar "{parent}"',
                                           f'Solo seleccionar "{parent}"']:
                                    sub_loc = page.locator(f'text="{sub}"')
                                    if sub_loc.count() > 0 and sub_loc.first.is_visible():
                                        sub_loc.first.click(timeout=5000)
                                        log(f'✓ Subcategory: {sub}')
                                        selected = True
                                        break
                                if not selected:
                                    # Click "Solo seleccionar" option (first item usually)
                                    solo = page.locator('text=/Sólo seleccionar|Solo seleccionar/')
                                    if solo.count() > 0 and solo.first.is_visible():
                                        solo.first.click(timeout=5000)
                                        log('✓ Subcategory: Solo seleccionar')
                                        selected = True
                                break
                        except Exception:
                            continue
                    if selected: break
            
            if not selected:
                log('⚠ No category could be selected — continuing anyway')

            time.sleep(4)
            ss(page, 'after_category')
        else:
            log('⚠ Category dropdown not found — maybe already selected')

        # ── Scroll down to reveal all form fields ─────────────────
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(2)

        # ── 8. Fill/adjust title ──────────────────────────────────
        log('→ 8. Check title/description')
        expected_catalog_title = name
        title_loc = page.locator('#title')
        if title_loc.count() > 0:
            try:
                title_loc.first.scroll_into_view_if_needed()
                current_title = title_loc.first.input_value()
                if (not current_title or len(current_title) < 5 or token_overlap_score(name, current_title) < 2):
                    manual_title = name[:80]
                    title_loc.first.click()
                    time.sleep(0.3)
                    title_loc.first.fill(manual_title)
                    expected_catalog_title = manual_title
                    log(f'✓ Title (manual/safe): "{manual_title[:40]}"')
                else:
                    expected_catalog_title = current_title
                    log(f'✓ Title (AI): "{current_title[:40]}"')
            except Exception as e:
                log(f'⚠ Title error: {e}')

        desc_parts = [name]
        if brand: desc_parts.append(f'Marca: {brand}')
        if model_s: desc_parts.append(f'Modelo: {model_s}')
        desc_parts += ['Estado: prácticamente nuevo.',
                      'Envío disponible. Recogida posible en tienda.']
        desc_text = '\n'.join(desc_parts)[:640]

        # Fill description (MANDATORY)
        desc_loc = page.locator('#description')
        if desc_loc.count() > 0:
            try:
                desc_loc.first.scroll_into_view_if_needed()
                current_desc = desc_loc.first.input_value()
                if not current_desc or len(current_desc) < 10 or token_overlap_score(name, current_desc) < 2:
                    desc_loc.first.click()
                    time.sleep(0.3)
                    desc_loc.first.fill(desc_text)
                    time.sleep(0.3)
                    # Verify
                    actual = desc_loc.first.input_value()
                    if len(actual) < 5:
                        # Fallback: type char by char
                        desc_loc.first.click()
                        page.keyboard.press('Control+A')
                        page.keyboard.type(desc_text[:200], delay=20)
                    log(f'✓ Description filled/safe ({len(desc_text)} chars)')
                else:
                    log(f'✓ Description (AI): "{current_desc[:40]}..."')
            except Exception as e:
                log(f'⚠ Description error: {e}')
        # Hard fallback for Wallapop description. Sometimes the visible textarea is
        # re-rendered/hidden after AI generation and Playwright can miss it, but the
        # required field is still empty. Force-fill the actual textarea/input before
        # submit so we don't create a failed draft with `Campo obligatorio`.
        desc_for_js = json.dumps(desc_text, ensure_ascii=False)
        desc_state = page.evaluate(f"""() => {{
            const text = {desc_for_js};
            const selectors = [
                '#description',
                'textarea[name="description"]',
                'textarea[id*="description"]',
                'textarea',
                '[contenteditable="true"]'
            ];
            for (const sel of selectors) {{
                const el = document.querySelector(sel);
                if (!el) continue;
                const val = (el.value !== undefined ? el.value : el.innerText || '').trim();
                if (val.length >= 10) return {{ok:true, filled:false, selector:sel, len:val.length}};
                el.scrollIntoView({{block:'center'}});
                el.focus();
                if (el.value !== undefined) {{
                    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) setter.call(el, text); else el.value = text;
                }} else {{
                    el.innerText = text;
                }}
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                el.dispatchEvent(new Event('blur', {{bubbles:true}}));
                const after = (el.value !== undefined ? el.value : el.innerText || '').trim();
                return {{ok: after.length >= 10, filled:true, selector:sel, len:after.length}};
            }}
            return {{ok:false, filled:false, selector:null, len:0}};
        }}""")
        if desc_state.get('filled'):
            log(f'✓ Description hard-filled ({desc_state.get("len")} chars via {desc_state.get("selector")})')
        elif not desc_state.get('ok'):
            log(f'⚠ Description field not verified before submit: {desc_state}')
        time.sleep(1)

        # ── 9. Select Estado (condition) — MANDATORY ─────────────
        log('→ 9. Select Estado (condition)')
        estado_clicked = False
        
        # Estado is a walla-dropdown: always select "Como nuevo"
        estado_uuid = page.evaluate("""() => {
            let hidden = document.querySelector('input[name="condition"]');
            if (!hidden) return null;
            let parent = hidden.closest('walla-dropdown');
            if (!parent) parent = hidden.parentElement;
            let visible = parent.querySelector('input[type="text"]');
            if (visible) {
                visible.scrollIntoView({block: 'center'});
                visible.click();
                return visible.name || visible.id || 'found';
            }
            return null;
        }""")
        
        if estado_uuid:
            log(f'  Estado dropdown opened (input: {estado_uuid})')
            time.sleep(2)
            opt = page.locator('text="Como nuevo"')
            if opt.count() > 0:
                for i in range(opt.count()):
                    try:
                        if opt.nth(i).is_visible(timeout=1000):
                            opt.nth(i).click()
                            log('✓ Estado: Como nuevo')
                            estado_clicked = True
                            break
                    except Exception:
                        continue
        
        if not estado_clicked:
            est_label = page.locator('text="Estado*"')
            if est_label.count() > 0:
                est_label.first.click()
                time.sleep(2)
                opt = page.locator('text="Como nuevo"')
                if opt.count() > 0 and opt.first.is_visible():
                    opt.first.click()
                    log('✓ Estado (label click): Como nuevo')
                    estado_clicked = True
                    
        if not estado_clicked:
            result = page.evaluate("""() => {
                const labels = Array.from(document.querySelectorAll('*')).filter(el =>
                    el.textContent && el.textContent.trim() === 'Como nuevo' && el.offsetParent !== null
                );
                if (labels.length) {
                    labels[0].click();
                    return true;
                }
                return false;
            }""")
            if result:
                log('✓ Estado (JS): Como nuevo')
                estado_clicked = True
        
        if not estado_clicked:
            log('⚠ Estado NOT SET')
        time.sleep(1)

        # ── 10. Fill price (MANDATORY) ────────────────────────────
        log('→ 10. Fill price')
        price_str = str(int(price)) if price > 0 else '10'
        
        # Use JS to focus + fill (label intercepts Playwright clicks)
        price_ok = page.evaluate(f"""() => {{
            let inp = document.getElementById('price_amount') 
                   || document.querySelector('input[name="price_amount"]');
            if (!inp) return false;
            inp.scrollIntoView({{block: 'center'}});
            inp.focus();
            inp.click();
            // Clear and set value
            let nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSet.call(inp, '{price_str}');
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
            inp.dispatchEvent(new Event('blur', {{bubbles: true}}));
            return true;
        }}""")
        
        if price_ok:
            log(f'✓ Price: {price_str}€ (JS)')
        else:
            # Fallback: force click + keyboard
            price_loc = page.locator('#price_amount')
            if price_loc.count() > 0:
                try:
                    price_loc.first.click(force=True)
                    time.sleep(0.3)
                    page.keyboard.press('Control+A')
                    page.keyboard.type(price_str, delay=50)
                    page.keyboard.press('Tab')
                    log(f'✓ Price: {price_str}€ (force+keyboard)')
                except Exception as e:
                    log(f'⚠ Price error: {e}')
            else:
                log('⚠ Price field NOT FOUND')
        time.sleep(1)

        # ── 11. Select weight radio button ────────────────────────
        log('→ 11. Select weight')
        weight_idx = weight_from_grams(weight_g)
        # Radio buttons have name="0", "1", "2"... and id matching name
        radio = page.locator(f'input[type="radio"]#\\3{weight_idx}')
        clicked_weight = False
        
        if radio.count() == 0:
            # Try by name
            radio = page.locator(f'input[type="radio"][name="{weight_idx}"]')
        
        if radio.count() > 0:
            try:
                # Click the parent label/li element (radio input may be hidden)
                parent = radio.first.locator('..')
                parent.click(force=True)
                clicked_weight = True
                log(f'✓ Weight: range {weight_idx} (parent click)')
            except Exception:
                try:
                    radio.first.click(force=True)
                    clicked_weight = True
                    log(f'✓ Weight: range {weight_idx} (force click)')
                except Exception:
                    pass
        
        if not clicked_weight:
            # JS fallback: click + dispatch events
            result = page.evaluate(f"""() => {{
                let r = document.querySelector('input[type="radio"][name="{weight_idx}"]') 
                     || document.getElementById('{weight_idx}');
                if (r) {{
                    r.scrollIntoView({{block: 'center'}});
                    r.checked = true;
                    r.dispatchEvent(new Event('change', {{bubbles: true}}));
                    r.dispatchEvent(new Event('input', {{bubbles: true}}));
                    // Also click the label
                    let label = r.closest('walla-radio') || r.closest('label') || r.parentElement;
                    if (label) label.click();
                    return true;
                }}
                return false;
            }}""")
            if result:
                log(f'✓ Weight: range {weight_idx} (JS)')
            else:
                log(f'⚠ Weight radio NOT FOUND')
        time.sleep(1)

        ss(page, 'before_submit')

        # ── 11. Click "Subir producto" ────────────────────────────
        log('→ 11. Submit: "Subir producto"')
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(1)

        submit = page.locator('button:has-text("Subir producto")')
        if submit.count() > 0 and submit.first.is_visible():
            if not submit.first.is_enabled():
                log('⚠ "Subir producto" disabled — waiting...')
                for _ in range(10):
                    time.sleep(1)
                    if submit.first.is_enabled(): break
            
            if submit.first.is_enabled():
                submit.first.scroll_into_view_if_needed()
                submit.first.click()
                log('✓ Clicked "Subir producto"!')
            else:
                log('⚠ "Subir producto" still disabled')
                ss(page, 'submit_disabled')
                # Debug: check what's missing
                missing = page.evaluate("""() => {
                    let r = [];
                    document.querySelectorAll('input[required], textarea[required]').forEach(el => {
                        if (!el.value) r.push(el.name || el.id || 'unknown');
                    });
                    return r;
                }""")
                log(f'  Missing required: {missing}')
                print('ERROR submit_disabled'); return
        else:
            log('⚠ "Subir producto" button not found')
            ss(page, 'no_submit')
            print('ERROR submit_not_found'); return

        # ── 12. Wait for success ──────────────────────────────────
        try:
            page.wait_for_url('**/item/**', timeout=30_000)
            url = page.url
            log(f'✅ Published: {url}')
            print(f'OK {url}'); return
        except PWTimeout: pass

        # Check for validation errors or form issues
        time.sleep(2)
        page.evaluate('window.scrollTo(0, 0)')
        time.sleep(1)
        ss(page, 'after_submit_top')
        
        # Look for validation error elements
        errors = page.evaluate("""() => {
            let errs = [];
            document.querySelectorAll('[class*="error"], [class*="invalid"], [class*="required"], .ng-invalid').forEach(el => {
                if (el.offsetParent !== null && el.textContent.trim()) {
                    let txt = el.textContent.trim().substring(0, 60);
                    if (txt && !errs.includes(txt)) errs.push(txt);
                }
            });
            return errs.slice(0, 10);
        }""")
        if errors:
            log(f'⚠ Form errors detected: {errors}')

        time.sleep(3)
        url = page.url
        ss(page, 'after_submit')

        if '/item/' in url:
            print(f'OK {url}'); return

        log('→ 12b. Fetching real item URL from catalog/published (safe token match)...')
        try:
            success_modal = page.locator('text="¡Yuhu! Producto subido"')
            if success_modal.count() > 0 and success_modal.first.is_visible(timeout=3000):
                log('✓ Success modal detected after submit')
                dismiss = page.locator('button:has-text("Ahora no, gracias")')
                if dismiss.count() > 0 and dismiss.first.is_visible(timeout=2000):
                    dismiss.first.click(timeout=5000)
                    time.sleep(2)

            if 'management/consumergoods' not in page.url:
                page.goto('https://es.wallapop.com/app/catalog/management/consumergoods', timeout=30_000, wait_until='domcontentloaded')
                time.sleep(5)

            items = []
            best = None
            best_score = 0
            best_required = 0
            best_ok = False
            best_price_ok = False
            for attempt in range(1, 7):
                if attempt > 1:
                    log(f'  Retry catalog match #{attempt} after reload...')
                    page.reload(timeout=30_000, wait_until='domcontentloaded')
                    time.sleep(10)
                items = extract_catalog_candidates(page)
                best = None
                best_score = 0
                best_required = 0
                best_ok = False
                best_price_ok = False
                for item in items or []:
                    ok, score, required, price_ok = safe_catalog_match(expected_catalog_title, item.get('title', ''), price)
                    fresh_ok = is_fresh_catalog_item(item)
                    ok = ok and fresh_ok
                    if (fresh_ok, price_ok, score) > (best_ok, best_price_ok, best_score):
                        best = item
                        best_score = score
                        best_required = required
                        best_ok = ok
                        best_price_ok = price_ok

                if best and best_ok and '/item/' in best.get('href', ''):
                    log(
                        f'✅ Got matched item URL from catalog: {best.get("href")} '
                        f'(score={best_score}, required={best_required}, price_ok={best_price_ok}, fresh_ok=True, title={best.get("title", "")[:80]!r})'
                    )
                    print(f'OK {best.get("href")}')
                    return

            log(f'⚠ No safely matched fresh /item/ URL found on catalog page, best_score={best_score}, required={best_required}, price_ok={best_price_ok}, items={len(items or [])}')
            if best:
                log(f'  Best candidate title: {best.get("title", "")[:120]!r}')
                log(f'  Best candidate href: {best.get("href", "")}')
                stale_ok, stale_score, stale_required, stale_price_ok = safe_catalog_match(expected_catalog_title, best.get('title', ''), price)
                if stale_ok and '/item/' in best.get('href', ''):
                    log(
                        f'✅ Using strong existing/stale catalog match after submit: {best.get("href")} '
                        f'(score={stale_score}, required={stale_required}, price_ok={stale_price_ok})'
                    )
                    print(f'OK {best.get("href")}')
                    return
            ss(page, 'catalog_published_debug')
            print(f'ERROR catalog_match_not_found final_url={url}')
            return
        except Exception as e:
            log(f'⚠ Error fetching catalog/published: {e}')
            print(f'ERROR catalog_fetch_failed url={url}')
            return


if __name__ == '__main__':
    main()

