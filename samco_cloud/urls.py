from django.contrib import admin
from django.urls import path, include
from accounting.views import dashboard_view

urlpatterns = [
    path('', dashboard_view, name='home-dashboard'), # এটি দিলে হোমপেজ কাজ করবে
    path('admin/', admin.site.urls),
    path('api/', include('accounting.urls')),
]
