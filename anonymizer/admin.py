from django.contrib import admin

# Register your models here.

from anonymizer.models import *

admin.site.register(ConnectionConfiguration)
admin.site.register(ConnectionAccessKey)


