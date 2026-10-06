"""Catalog-search additions for learner-facing organization labels."""

from functools import wraps

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from course_partnerships.organization_display import (
    get_organization_display_name,
    get_organization_names,
)


def _course_key_string(row):
    """Return the course id carried on a catalog search hit.

    edx-search puts the indexed course id on ``data.id``. Some responses also
    copy it to ``id``; Elasticsearch's own document id is ``_id``.
    """
    data = row.get("data") or {}
    return data.get("id") or row.get("id") or row.get("_id")


def add_organization_display_names(results):
    """Attach learner-facing organization labels without changing filter values."""
    rows = results.get("results") or []
    organization_terms = results.get("aggs", {}).get("org", {}).get("terms", {})
    org_slugs = set(organization_terms)
    org_slugs.update(row.get("data", {}).get("org") for row in rows)
    organization_names = get_organization_names(org_slugs)
    results["organization_display_names"] = {
        slug: organization_names[slug]
        for slug in organization_terms
        if slug in organization_names
    }
    if not rows:
        return results

    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

    course_ids = []
    for row in rows:
        raw_id = _course_key_string(row)
        if not raw_id:
            continue
        try:
            course_ids.append(CourseKey.from_string(str(raw_id)))
        except InvalidKeyError:
            continue
    overviews = {
        str(overview.id): overview
        for overview in CourseOverview.objects.filter(id__in=course_ids)
    }
    for row in rows:
        data = row.setdefault("data", {})
        overview = overviews.get(str(_course_key_string(row)))
        display_override = (
            overview.display_org_with_default
            if overview and overview.display_org_with_default != overview.org
            else None
        )
        data["organization_display_name"] = get_organization_display_name(
            data.get("org"),
            display_override,
            organization_names.get(data.get("org")),
        )
    return results


def register_organization_display_names():
    """Add learner-facing organization labels to edx-search results.

    ``edx-search`` deliberately returns raw organization identifiers in its
    aggregations because those values are used for filtering.  This wrapper
    preserves that behavior and adds a separate display-name map for clients.
    """
    from search import views as search_views

    if getattr(search_views, "_sherab_organization_display_names_registered", False):
        return

    original_course_discovery_search = search_views.course_discovery_search

    @wraps(original_course_discovery_search)
    def course_discovery_search_with_organization_display_names(*args, **kwargs):
        return add_organization_display_names(original_course_discovery_search(*args, **kwargs))

    search_views.course_discovery_search = course_discovery_search_with_organization_display_names
    search_views._sherab_organization_display_names_registered = True
