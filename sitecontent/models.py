from django.db import models


LANGUAGE_CHOICES = [
    ('all', 'All languages'),
    ('en', 'English'),
    ('ru', 'Русский'),
    ('zh', '中文'),
    ('id', 'Indonesia'),
    ('de', 'Deutsch'),
    ('fr', 'Français'),
]


class SiteContentEntry(models.Model):
    VALUE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('textarea', 'Textarea'),
        ('json', 'JSON'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('file', 'File'),
    ]

    key = models.CharField(max_length=255, help_text='Dot path, e.g. nav.catalog or media.home.heroVideo')
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    value_type = models.CharField(max_length=20, choices=VALUE_TYPE_CHOICES, default='text')
    value = models.TextField(blank=True, default='', help_text='Text value or external media URL fallback.')
    json_value = models.JSONField(blank=True, null=True)
    media = models.FileField(upload_to='site_content/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key', 'language']
        unique_together = ('key', 'language')
        verbose_name = 'Site content entry'
        verbose_name_plural = 'Site content entries'

    def __str__(self):
        return f'{self.key} [{self.language}]'


from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver


@receiver(post_save, sender=SiteContentEntry)
@receiver(post_delete, sender=SiteContentEntry)
def invalidate_public_content_cache(sender, instance, **kwargs):
    from django.core.cache import cache
    from bali_rent.public_data import PUBLIC_LANGUAGES

    cache.delete_many([f"public_site_bootstrap_{item['api_code']}" for item in PUBLIC_LANGUAGES])


@receiver(post_delete, sender=SiteContentEntry)
def auto_delete_site_content_media_on_delete(sender, instance, **kwargs):
    if instance.media:
        try:
            if instance.media.storage.exists(instance.media.name):
                instance.media.storage.delete(instance.media.name)
        except Exception:
            pass


@receiver(pre_save, sender=SiteContentEntry)
def auto_delete_site_content_media_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return False
    try:
        old_entry = SiteContentEntry.objects.get(pk=instance.pk)
        old_file = old_entry.media
    except SiteContentEntry.DoesNotExist:
        return False

    new_file = instance.media
    if old_file and old_file != new_file:
        try:
            if old_file.storage.exists(old_file.name):
                old_file.storage.delete(old_file.name)
        except Exception:
            pass

