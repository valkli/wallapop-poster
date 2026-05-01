# wallapop-poster MEMORY

## 2026-04-28 — Git remote repair
- Исправлен битый `origin`, который содержал токен в неправильной структуре `ghp_...@x-access-token:ghp_...@github.com` и ломал GitHub Sync ошибкой `URL rejected: Port number was not a decimal number between 0 and 65535`.
- Новый remote: `https://github.com/valkli/wallapop-poster.git`.
- Backup старого `.git/config`: `temp/git-config-before-remote-fix-20260428-013702.bak` и общий backup clean-up: `temp/git-config-before-remote-clean-20260428-014002.bak`.

## 2026-04-27 — Product_Variants Wallapop relink
- Валерий удалил неправильные ссылки из `Wallapop Posted` в Notion `Product_Variants` и попросил восстановить ссылки по текущему каталогу Wallapop Mix-Mix: https://es.wallapop.com/user/val-461468807
- Собран весь публичный каталог Wallapop через API пользователя `p61oqpn0oxj5`: 136 товаров.
- Notion scope: только база `Product_Variants` (`27f12f742f9e81648959ee3d597c4e7e`), только страницы с `In Stock = true`.
- Перед записью сделан backup кандидатов и плана в `wallapop-poster/temp/`:
  - `wallapop_relink_backup_20260427-224547.json`
  - `wallapop_relink_plan_20260427-224547.json`
- Использован one-off скрипт `temp/wallapop_relink_product_variants.py`: fuzzy match по названию/описанию/цене + image hash по первой картинке, чтобы не полагаться только на похожие названия.
- Результат применения: обновлено 102 страницы, ошибок Notion PATCH 0. Проверка после записи: 102 страниц `Product_Variants` с `In Stock=true` имеют непустой `Wallapop Posted`.
- 34 товара Wallapop оставлены без записи из-за низкой/неоднозначной уверенности совпадения, чтобы не привязать неправильные ссылки.

## 2026-04-27 — Wallapop relink GangaBox
- По каталогу Wallapop alery-474023510 восстановлены 77 уверенных ссылок в Notion Product_Variants_GangaBox (2bd12f742f9e8198bfb3dce06af14f58), backups/plans: wallapop-poster/temp/wallapop_relink_*_20260427-232846.json; MixMix Product_Variants дал 0 совпадений.

## 2026-04-29 — Wallapop Daily Job
- 15:00 run: published 1, skipped 17, errors 0; report sent to Telegram topic 4. Details in global memory/2026-04-29.md.


## Кодовое лечение OpenClaw Wallapop проектов — 2026-04-30 01:00:48

Внесены fixes во все три проекта после удаления дублей:

- Добавлен общий `wallapop_safe.py` в `wallapop-poster`, `wallapop-poster2`, `wallapop-poster3`:
  - нормализация title;
  - безопасный matcher title + exact/close price + model-like tokens;
  - `choose_unique_match()` возвращает `unique_match`, `ambiguous`, `no_match`;
  - JS для чтения полного Wallapop management catalog через API по всем страницам.
- Добавлены `test_wallapop_safe.py` во все три проекта.
- `publish_wallapop_cdp.py`:
  - `wallapop-poster`: добавлен full-catalog pre-check перед публикацией и safe URL capture после submit; больше не берет первый `/item/` из каталога.
  - `wallapop-poster2`: catalog extractor переведен на полный API catalog; matching использует общий safe matcher; сохранены retries после submit.
  - `wallapop-poster3`: catalog extractor переведен на полный API catalog; добавлен full-catalog pre-check; matching использует общий safe matcher.
- `fetch_product_for_wallapop.py`:
  - `wallapop-poster3`: удален фильтр `Selling Price > 15`; теперь, как подтвердил Валерий, цена не важна, важен `In Stock=true`.
  - `wallapop-poster2`: цена и раньше не фильтровалась, оставлено.
  - `wallapop-poster`: price threshold оставлен.
- `cleanup_wallapop.py`:
  - `wallapop-poster3`: создан отсутствующий cleanup.
  - `wallapop-poster` и `wallapop-poster2`: execute теперь сначала пытается физически удалить Wallapop listing через management API, и только потом чистит Notion.
  - `wallapop-poster`: cleanup scope ограничен `Wal 1=true`, чтобы не трогать poster2/poster3 строки.
  - `NO-IMAGE-SKIP`/не-item markers классифицируются как bad_url/marker, а не физическое удаление.
- `wallapop-poster2/temp/POSTING_PAUSED.txt` архивирован как resolved после лечения, чтобы OpenClaw мог запускать проект.

Проверки:
- Backup перед правками: `temp/backup-before-wallapop-heal-20260430-004902/` в каждом проекте.
- `python -m py_compile` всех `.py` файлов трех проектов: OK.
- `pytest test_wallapop_safe.py -q` в каждом проекте: 4 passed.
- `cleanup_wallapop.py` dry-run через Windows Python:
  - poster: to_delete=0, bad_urls=77, ok=410;
  - poster2: to_delete=7, bad_urls=13, ok=65;
  - poster3: to_delete=162, bad_urls=93, ok=147.
- `fetch_product_for_wallapop.py` smoke для всех трех проектов: OK, каждый выбрал следующий товар.

Важно:
- Массовую публикацию здесь не запускали.
- Cleanup execute здесь после лечения не запускали.
- OpenClaw browser profiles в проектах не заменялись на личные Chrome profiles Валерия.

## 2026-04-30 run attempt — base wallapop-poster
- Valery asked to run the base wallapop-poster (not poster2/3). Verified project docs, ran py_compile OK, then launched 
un_daily_batch.py on profile mixmix/CDP 18801.
- First run looped on the same failed Notion row (CIEEIN CIEHT Mantel...) because ailed_today.json was not excluded by fetch. Patched etch_product_for_wallapop.py to page through up to 25 results and skip IDs in ailed_today.json/published_today.json.
- Patched 
un_daily_batch.py to use pre-batch cleanup dry-run instead of execute, and to halt on catalog_match_not_found/catalog_fetch_failed after submit to avoid duplicates/orphans.
- Copied the more robust Poster2 publish_wallapop_cdp.py base and adapted it to mixmix/18801; also changed publish to use a fresh Wallapop tab because the mixmix profile had multiple stale Wallapop tabs.
- Despite fixes, live posting did not complete: attempts hit catalog_match_not_found, Continuar disabled timeouts, file upload timeout, and finally BrowserType.connect_over_cdp timeout on 18801. The last live batch was killed safely before more attempts. No confirmed Notion URL updates from this run.
- Cleanup dry-run showed roughly Total: 496 published listings, 	o_delete=10, ad_urls=77, ok=409; no cleanup execute/deletion performed. Next step: stabilize/clean the mixmix browser profile/CDP session (too many stale tabs / CDP sluggish) and then retry a small 1-item smoke before batch.
