from django.urls import path, re_path, include

from .views import (
    index_view,
    login_view,
    logout_view,
    change_password_view,
    profile_view,
    register_user_view,
    error_view,
    add_data_view,
    manage_data_view,
    export_data_view,
    mftusers_list_view,
    directories_list_view,
    mftuser_details_view,
    mftuser_access_view,
    mftuser_create_view,
    # mftuser_directories_view,
    entities_confirm_view,
    delete_directory_view,
    mftuser_permissions_view,
    mftuser_delete_view,
    mftuser_dismiss_changes_view,
    mftuser_restore_or_delete_view,
    download_view,
)


urlpatterns = [
    path('', index_view, name='home'),
    path('login/', login_view, name='login'),
    path("logout/", logout_view, name="logout"),
    path('register/', register_user_view, name='register'),
    path("change-password/", change_password_view, name="change-password"),
    path("profile/", profile_view, name="iscuser-profile"),
    path("add-data/", add_data_view, name="add-data"),
    path("manage-data/", manage_data_view, name="manage-data"),
    path("export-data/", export_data_view, name="export-data"),
    path("mftuser/create/", mftuser_create_view, name="mftuser-create"),
    path("mftuser/<int:id>/", mftuser_details_view, name="mftuser-details"),
    path("mftuser/<int:uid>/directories/", mftuser_access_view, name="mftuser-access"),
    path("mftuser/<int:uid>/directories/<int:pid>/<str:dir_name>/", mftuser_access_view, name="mftuser-directories"),
    # path("mftuser/<int:uid>/directories/<int:pid>/<str:dir_name>/", mftuser_directories_view, name="mftuser-directories"),
    path("mftuser/<int:uid>/permissions/<int:did>/", mftuser_permissions_view, name="mftuser-permissions"),
    path("mftuser/<int:id>/delete/", mftuser_delete_view, name="mftuser-delete"),
    path("mftuser/<int:id>/dismiss-changes/", mftuser_dismiss_changes_view, name="mftuser-dismiss-changes"),
    path("mftuser/<int:id>/restore-or-delete/", mftuser_restore_or_delete_view, name="mftuser-restore-or-delete"),
    path("entities/<int:id>/confirm/", entities_confirm_view, name="entities-confirm"),
    path("directory/<int:did>/delete/", delete_directory_view, name="delete-directory"),
    path("directory/<int:uid>/mftusers/", manage_data_view, name="directory-access"),
    path("mftusers/create-or-change/", mftusers_list_view, name="mftusers-create-or-change-list"),
    path("mftusers/access/", mftusers_list_view, name="mftusers-access-list"),
    path("directories/", directories_list_view, name="directories-list"),
    # path("directories/<int:user_id>/", directories_list_view, name="directories-list"),
    # path("directories/permission/", add_permission_view, name="add-permission"),
    # re_path(r"directories/(?P<user_id>[0-9]+)/$", directories_list_view, name="directories-list"),
    path("error/<int:err>/", error_view, name="error-view"),
    path('invoice/', include('invoice.urls')),
    path('download/<int:id>/', download_view, name='download-view'),
    re_path(r'^.*\.*', error_view, name='error-view'),
]