from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path('', include('eps_commons.urls')),
    path('ping/', lambda request: HttpResponse('ok'), name='ping'),
]
