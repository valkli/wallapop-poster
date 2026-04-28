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
