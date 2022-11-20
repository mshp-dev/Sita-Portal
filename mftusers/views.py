from django.http.response import HttpResponse, JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.template import loader
from django.template.loader import render_to_string
from django.shortcuts import render, redirect

import os, logging

logger = logging.getLogger(__name__)


def issue_view(request, *args, **kwargs):
    return render(request, "issue.html")


@login_required(login_url='/login/')
def change_issue_mode(request, *args, **kwargs):
    user = request.user
    if not user.is_staff:
        logger.fatal(f'unauthorized trying access of {user.username} to {request.path}.')
        return redirect('/error/401/')
    
    logger.warning(f'{user.username} changed issue mode.')
    os.system("echo command")

    return redirect("/")