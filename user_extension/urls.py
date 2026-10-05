"""
Defines the URL routes for this app.
"""

from django.conf import settings
from django.urls import path, re_path
from django.conf.urls import include

from .views import *

app_name = "user_extension"


urlpatterns = []
