"""
Tests for the donation settings on Partner.
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_partnerships.models import DONATION_MESSAGE_MAX_LENGTH, Partner
from course_partnerships.validators import validate_https_url


class PartnerDonationValidationTest(TestCase):
    """
    Tests for Partner.clean() and the donation URL validator.
    """

    def test_valid_settings(self):
        Partner(name="School", donation_enabled=True, donation_url="https://example.org/donate").clean()

    def test_url_required_when_enabled(self):
        with pytest.raises(ValidationError) as error:
            Partner(name="School", donation_enabled=True, donation_url="").clean()

        assert "donation_url" in error.value.message_dict

    def test_url_optional_when_disabled(self):
        Partner(name="School", donation_enabled=False, donation_url="").clean()

    def test_https_only(self):
        validate_https_url("https://example.org/donate")
        validate_https_url("HTTPS://example.org/donate")
        for url in ("http://example.org/donate", "ftp://example.org", "javascript:alert(1)"):
            with pytest.raises(ValidationError):
                validate_https_url(url)

    def test_message_at_limit(self):
        message = "<p><b>" + "a" * DONATION_MESSAGE_MAX_LENGTH + "</b></p>"

        Partner(name="School", donation_message=message).clean()

    def test_message_over_limit(self):
        message = "<p>" + "a" * (DONATION_MESSAGE_MAX_LENGTH + 1) + "</p>"

        with pytest.raises(ValidationError) as error:
            Partner(name="School", donation_message=message).clean()

        assert "donation_message" in error.value.message_dict

    def test_entities_count_as_one_character(self):
        # CKEditor stores "&" as "&amp;"; learners see one character.
        message = "&amp;" * DONATION_MESSAGE_MAX_LENGTH

        Partner(name="School", donation_message=message).clean()
