from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient

from sitecontent.models import SiteContentEntry
from sitecontent.serializers import SiteContentEntrySerializer
from sitecontent.services import build_public_dictionary_overrides
from users.models import User


class SeoSettingsTests(TestCase):
    def test_saving_and_deleting_settings_invalidates_public_cache(self):
        cache.set('public_site_bootstrap_en', {'old': True})
        entry = SiteContentEntry.objects.create(
            key='seo.pages.home', language='all', value_type='json',
            json_value={'description': 'Updated'},
        )
        self.assertIsNone(cache.get('public_site_bootstrap_en'))
        cache.set('public_site_bootstrap_ru', {'old': True})
        entry.delete()
        self.assertIsNone(cache.get('public_site_bootstrap_ru'))

    def test_settings_round_trip_into_public_bootstrap(self):
        admin = User.objects.create_superuser(
            username='seo_admin', email='seo@example.com', password='test-password', role='admin',
        )
        client = APIClient()
        client.force_authenticate(admin)
        for key, value in (
            ('seo.pages.home', {'title': 'Bali scooters', 'description': 'An independent search description.'}),
            ('seo.pages.scooter_12', {'description': 'Rent this scooter.'}),
            ('seo.pages.news_34', {'description': 'News search description.'}),
            ('seo.imageAlts', {'/logo1.svg': '', 'https://example.com/photo.jpg': 'Scooter on a beach'}),
        ):
            response = client.post('/api/v1/admin/content/site-content/', {
                'key': key, 'language': 'all', 'value_type': 'json', 'json_value': value,
            }, format='json')
            self.assertEqual(response.status_code, 201, response.data)
        client.force_authenticate(None)
        response = client.get('/api/v1/public/bootstrap/?lang=en')
        self.assertEqual(response.status_code, 200)
        seo = response.data['dictionaryOverrides']['seo']
        self.assertEqual(seo['pages']['home']['description'], 'An independent search description.')
        self.assertEqual(seo['pages']['scooter_12']['description'], 'Rent this scooter.')
        self.assertEqual(seo['pages']['news_34']['description'], 'News search description.')
        self.assertEqual(seo['imageAlts']['/logo1.svg'], '')
        self.assertEqual(build_public_dictionary_overrides('ru')['seo'], seo)

    def test_invalid_settings_are_rejected(self):
        cases = [
            ('seo.pages.home', [], 'all'),
            ('seo.pages.home', {'title': '<script>alert(1)</script>'}, 'all'),
            ('seo.pages.home', {'description': 'x' * 1001}, 'all'),
            ('seo.pages.home', {'title': 'Title'}, 'ru'),
            ('seo.pages.home', {'description': 123}, 'all'),
            ('seo.imageAlts', {'/photo.jpg': None}, 'all'),
            ('seo.imageAlts', {'javascript:alert(1)': 'Photo'}, 'all'),
        ]
        for key, value, language in cases:
            with self.subTest(key=key, value=value):
                serializer = SiteContentEntrySerializer(data={
                    'key': key, 'language': language, 'value_type': 'json', 'json_value': value,
                })
                self.assertFalse(serializer.is_valid())

    def test_only_admin_can_write_seo(self):
        response = APIClient().post('/api/v1/admin/content/site-content/', {
            'key': 'seo.pages.home', 'language': 'all', 'value_type': 'json', 'json_value': {},
        }, format='json')
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(SiteContentEntry.objects.filter(key='seo.pages.home').exists())
