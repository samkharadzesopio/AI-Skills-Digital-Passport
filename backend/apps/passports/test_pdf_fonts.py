"""Real template rendering checks for the bundled Georgian/Latin font assets."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

import pymupdf
from django.test import SimpleTestCase

from passport_pdf_renderer import (
    FONT_FILES, PDFRenderLimitError, _font, render_passport_pdf, renderer_fingerprint,
)


def font_sample():
    return {
        'student': {
            'first_name': 'გიორგი', 'last_name': 'მაისურაძე',
            'external_student_id': 'BTU-123', 'program': 'კომპიუტერული მეცნიერება',
        },
        'passport': {'public_reference': '00000000-0000-0000-0000-000000000001'},
        'version': {
            'public_reference': '00000000-0000-0000-0000-000000000002',
            'number': 1, 'issued_date': '2026-10-25',
        },
        'verification_reference': 'passport-version:00000000-0000-0000-0000-000000000002',
        'skills': [{
            'name': 'AI ანალიზი', 'category': 'AI უნარები', 'subcategory': 'ანალიზი',
            'level': 'Applied', 'stamp_type': 'APPLIED',
            'description': 'მონაცემთა ანალიზი და შეფასება.',
            'earned_through': 'ბიზნესისა და ტექნოლოგიების უნივერსიტეტი',
            'date_earned': '2026-10-25',
        }],
        'credentials': [{
            'public_reference': '00000000-0000-0000-0000-000000000003',
            'issuer_name': 'ბიზნესისა და ტექნოლოგიების უნივერსიტეტი',
            'issued_date': '2026-10-25', 'expires_date': '',
        }],
    }


class GeorgianFontTests(SimpleTestCase):
    def test_georgian_and_mixed_names_use_embedded_fonts_with_real_glyphs(self):
        for style in FONT_FILES:
            for character in 'გიორგი ᲛᲐᲘᲡᲣᲠᲐᲫᲔ English 123':
                self.assertTrue(_font(style).has_glyph(ord(character), fallback=False))
        for first, last in [('გიორგი', 'მაისურაძე'), ('Ana-ანა', 'Smith-მაისურაძე'), ('კონსტანტინე', 'მახარობლიშვილი')]:
            with self.subTest(first=first):
                data = font_sample()
                data['student'].update(first_name=first, last_name=last)
                with pymupdf.open(stream=render_passport_pdf(data), filetype='pdf') as pdf:
                    text = ' '.join(' '.join(page.get_text() for page in pdf).split())
                    for value in [first, last, data['student']['program'], data['skills'][0]['description']]:
                        self.assertIn(value, text)
                    fonts = [font for page in pdf for font in page.get_fonts() if 'NotoSansGeorgian' in font[3].replace(' ', '')]
                    self.assertTrue(fonts)
                    self.assertTrue(any('Bold' in font[3] for font in fonts))
                    for font in fonts:
                        self.assertTrue(pdf.extract_font(font[0])[3])
                    for word in pdf[0].get_text('words'):
                        if word[4] == first:
                            self.assertLessEqual(word[2], 580)
                        elif word[4] == last:
                            self.assertLessEqual(word[2], 620)

    def test_english_numbers_references_and_deterministic_bytes(self):
        data = font_sample()
        data['student'].update(first_name='Synthetic', last_name='Student', program='Computer Science')
        data['skills'][0].update(name='AI Reasoning', category='AI', subcategory='Reasoning', description='Evaluate reasoning.', earned_through='Business and Technology University')
        data['credentials'][0]['issuer_name'] = 'Business and Technology University'
        first = render_passport_pdf(data)
        self.assertEqual(first, render_passport_pdf(deepcopy(data)))
        with pymupdf.open(stream=first, filetype='pdf') as pdf:
            text = ' '.join(' '.join(page.get_text() for page in pdf).split())
        for value in ['Synthetic', 'Student', 'Computer Science', '2026-10-25', 'BTU-123', data['verification_reference'], data['credentials'][0]['public_reference']]:
            self.assertIn(value, text)

    def test_multi_page_georgian_supplements_remain_inside_template_cells(self):
        data = font_sample()
        skill = data['skills'][0]
        data['skills'] = [dict(skill, name=f'AI ანალიზი {index}') for index in range(11)]
        with pymupdf.open(stream=render_passport_pdf(data), filetype='pdf') as pdf:
            self.assertEqual(len(pdf), 7)
            for page in list(pdf)[3:6]:
                words = page.get_text('words')
                self.assertTrue(any(word[4] == 'ანალიზი' and 204 <= word[0] < 300 for word in words))
                for x0, y0, x1, y1, word, *_ in words:
                    if word == 'ანალიზი' and x0 < 300:
                        self.assertGreaterEqual(x0, 204)
                        self.assertLessEqual(x1, 300)
                        self.assertGreaterEqual(y0, 189)
                        self.assertLessEqual(y1, 459)

    def test_all_ten_skill_card_labels_fit_the_unchanged_template_borders(self):
        data = font_sample()
        data['skills'] = [dict(data['skills'][0], name=f'AI Reasoning {index:02}',
            category='Artificial Intelligence', subcategory='Critical Reasoning',
            level='Advanced', description='Evaluate reasoning.') for index in range(1, 11)]
        with pymupdf.open(stream=render_passport_pdf(data), filetype='pdf') as pdf:
            page = pdf[2]
            cards = sorted((drawing['rect'] for drawing in page.get_drawings()
                if 130 < drawing['rect'].width < 132 and 151 < drawing['rect'].height < 153),
                key=lambda rect: (round(rect.y0), rect.x0))
            self.assertEqual(len(cards), 10)
            spans = [span for block in page.get_text('dict')['blocks']
                for line in block.get('lines', []) for span in line['spans']
                if 'NotoSansGeorgian' in span['font'] and 230 < span['bbox'][1] < 480]
            self.assertGreaterEqual(len(spans), 30)  # name plus two classification lines/card
            for span in spans:
                box = pymupdf.Rect(span['bbox'])
                row = 0 if box.y0 < 300 else 1
                card = min(cards[row * 5:row * 5 + 5],
                    key=lambda rect: abs((rect.x0 + rect.x1) / 2 - (box.x0 + box.x1) / 2))
                with self.subTest(text=span['text'], card=tuple(card)):
                    self.assertGreaterEqual(box.x0, card.x0 + 1)
                    self.assertLessEqual(box.x1, card.x1 - 1)
                    self.assertGreaterEqual(box.y0, card.y0 + 1)
                    self.assertLessEqual(box.y1, card.y1 - 1)
            text = ' '.join(page.get_text().split())
            for index in range(1, 11):
                self.assertIn(f'AI REASONING {index:02}', text)

    def test_unsupported_glyphs_and_real_line_or_box_overflow_are_rejected(self):
        for field, value in [('first_name', 'სახელი\U0001f431'), ('last_name', 'მ' * 90)]:
            data = font_sample()
            data['student'][field] = value
            with self.subTest(field=field), self.assertRaises(PDFRenderLimitError):
                render_passport_pdf(data)
        data = font_sample()
        data['skills'][0]['description'] = 'შეფასება ' * 40
        with self.assertRaises(PDFRenderLimitError):
            render_passport_pdf(data)

    def test_each_bundled_font_participates_in_renderer_fingerprint(self):
        before = renderer_fingerprint()
        with tempfile.TemporaryDirectory() as directory:
            for style, source in FONT_FILES.items():
                altered = Path(directory) / source.name
                altered.write_bytes(source.read_bytes() + b'fingerprint-check')
                with patch.dict(FONT_FILES, {style: altered}):
                    self.assertNotEqual(renderer_fingerprint(), before)
        self.assertEqual(renderer_fingerprint(), before)
