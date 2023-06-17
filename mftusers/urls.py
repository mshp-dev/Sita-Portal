"""mftusers URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf.urls.static import static
from django.conf import settings

from .views import issue_view, change_issue_mode

admin.site.site_header = 'Sita Portal Admin Panel'
admin.site.site_title = 'Sita Portal Admin Panel'
admin.site.index_title = 'Users and Directories Administration'

urlpatterns = [
    path('sita-admin/', admin.site.urls, name='admin'),
    path('', include('core.urls')),
    # path('command/', change_issue_mode, name='change_issue_mode'),
    # re_path(r'^.*\.*', issue_view, name='issue-view'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
