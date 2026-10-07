"""Helpers for resolving learner-facing course organization labels."""

from organizations.models import Organization


def get_organization_names(org_slugs):
    """Return readable organization names keyed by their technical short names."""
    organization_slugs = {org_slug for org_slug in org_slugs if org_slug}
    if not organization_slugs:
        return {}

    organizations = Organization.objects.filter(
        short_name__in=organization_slugs,
        active=True,
    ).exclude(name__isnull=True).exclude(name='')

    return {
        organization.short_name: organization.name
        for organization in organizations
    }


def get_organization_display_name(org_slug, display_organization=None, organization_name=None):
    """Resolve the organization text intended for a learner-facing display."""
    if display_organization:
        return display_organization

    if organization_name:
        return organization_name

    return org_slug


def get_course_organization_display_name(course):
    """Resolve a display name for a full course object."""
    organization_names = get_organization_names([course.org])
    return get_organization_display_name(
        org_slug=course.org,
        display_organization=course.display_organization,
        organization_name=organization_names.get(course.org),
    )
