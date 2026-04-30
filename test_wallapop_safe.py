#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from wallapop_safe import choose_unique_match, is_safe_catalog_match, meaningful_tokens, price_int


def test_safe_match_requires_identity_not_only_generic_words():
    ok, score, required, price_ok = is_safe_catalog_match(
        'Logitech MK220 Combo teclado ratón inalámbrico',
        'Logitech POP Mouse Bluetooth Inalámbrico Rosa 13 €',
        13,
    )
    assert not ok


def test_safe_match_accepts_model_and_exact_price():
    ok, score, required, price_ok = is_safe_catalog_match(
        'Logitech MK220 Combo teclado ratón inalámbrico',
        'Combo Teclado y Ratón Inalámbrico Logitech MK220 13 €',
        13,
    )
    assert ok
    assert price_ok


def test_choose_unique_match_reports_ambiguous_when_two_safe_matches():
    result = choose_unique_match('Teclado Mars Gaming MKREVOPRO TKL', 11, [
        {'title': 'Teclado Mecánico Gaming Mars Gaming MKREVOPRO TKL', 'price': 11, 'href': 'https://es.wallapop.com/item/a'},
        {'title': 'Mars Gaming MKREVOPRO teclado TKL', 'price': 11, 'href': 'https://es.wallapop.com/item/b'},
    ])
    assert result['status'] == 'ambiguous'


def test_choose_unique_match_returns_unique_for_single_safe_match():
    result = choose_unique_match('BISSELL SpotClean ProHeat Aspiradora Agua', 45, [
        {'title': 'BISSELL SpotClean ProHeat Aspiradora Agua', 'price': 45, 'href': 'https://es.wallapop.com/item/bissell'},
        {'title': 'Cecotec Conga Robot Aspirador', 'price': 45, 'href': 'https://es.wallapop.com/item/conga'},
    ])
    assert result['status'] == 'unique_match'
    assert result['match']['href'].endswith('bissell')
