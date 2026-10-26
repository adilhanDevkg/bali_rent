import re

from rest_framework import serializers

from .models import SiteContentEntry
from .page_settings import PAGE_SETTINGS_KEYS, parse_page_settings_key, validate_page_settings_path


class SiteContentEntrySerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SiteContentEntry
        fields = (
            'id',
            'key',
            'language',
            'value_type',
            'value',
            'json_value',
            'media',
            'media_url',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'media_url', 'created_at', 'updated_at')

    def get_media_url(self, obj):
        if not obj.media:
            return ''

        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.media.url)
        return obj.media.url

    def validate(self, attrs):
        attrs = super().validate(attrs)
        key = attrs.get('key', getattr(self.instance, 'key', ''))
        language = attrs.get('language', getattr(self.instance, 'language', ''))
        if key.startswith('seo.'):
            if language != 'all':
                raise serializers.ValidationError({'language': 'SEO settings must use the shared site language.'})
            value_type = attrs.get('value_type', getattr(self.instance, 'value_type', ''))
            value = attrs.get('json_value', getattr(self.instance, 'json_value', None))
            if value_type != 'json' or not isinstance(value, dict):
                raise serializers.ValidationError({'json_value': 'SEO settings must be a JSON object.'})
            if key == 'seo.imageAlts':
                for image, alt in value.items():
                    if not isinstance(image, str) or not image.startswith(('/', 'https://', 'http://')):
                        raise serializers.ValidationError({'json_value': 'Image keys must be paths or HTTP(S) URLs.'})
                    if not isinstance(alt, str) or len(alt) > 255:
                        raise serializers.ValidationError({'json_value': 'Image alt must be text up to 255 characters.'})
            elif re.fullmatch(r'seo\.pages\.([a-z]+|scooter_[0-9]+|news_[0-9]+)', key):
                if set(value) - {'title', 'description'}:
                    raise serializers.ValidationError({'json_value': 'Only title and description are supported.'})
                for field, limit in (('title', 255), ('description', 1000)):
                    text = value.get(field, '')
                    if not isinstance(text, str) or len(text) > limit:
                        raise serializers.ValidationError({'json_value': f'{field} must be text up to {limit} characters.'})
                    if '<' in text or '>' in text:
                        raise serializers.ValidationError({'json_value': 'Enter plain text without HTML tags.'})
            else:
                raise serializers.ValidationError({'key': 'Unknown SEO setting.'})
        page_key, field_key = parse_page_settings_key(key)
        if page_key in PAGE_SETTINGS_KEYS and field_key == 'path':
            if language != 'all':
                raise serializers.ValidationError({'language': 'Page path must be shared across all languages.'})
            raw_value = attrs.get('value', getattr(self.instance, 'value', ''))
            attrs['value'] = validate_page_settings_path(
                raw_value,
                page_key=page_key,
                instance_pk=getattr(self.instance, 'pk', None),
            )
        return attrs
