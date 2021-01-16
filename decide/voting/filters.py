from django.contrib.admin import SimpleListFilter
from django.utils import timezone


class StartedFilter(SimpleListFilter):
    title = 'started'
    parameter_name = 'started'

    def lookups(self, request, model_admin):
        return [
            ('NS', 'Not started'),
            ('S', 'Started'),
            ('R', 'Running'),
            ('F', 'Finished'),
        ]

    #Javi
    #He modificado el queryset para que muestre la votaciones teniendo en cuanta la fecha de finalizacion
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'NS':
            return queryset.filter(start_date__isnull=True)
        if self.value() == 'S':
            return queryset.exclude(start_date__isnull=True)
        if self.value() == 'R':
            return queryset.exclude(start_date__isnull=True).filter(end_date__gte=now)
        if self.value() == 'F':
            return queryset.exclude(end_date__isnull=True).filter(end_date__lte=now)
        else:
            return queryset.all()
