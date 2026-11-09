from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    from apps.employees.models import Employee, Department, EmployeeStatus

    dept_filter = request.GET.get('dept', '')
    q = request.GET.get('q', '').strip()

    employees = Employee.objects.select_related('user').all()
    if dept_filter:
        employees = employees.filter(department=dept_filter)
    if q:
        from django.db.models import Q
        employees = employees.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(position__icontains=q)
        )
    employees = employees.order_by('department', 'last_name')

    departments = [(d.value, d.label) for d in Department]
    statuses = {s.value: s.label for s in EmployeeStatus}

    dept_counts = {}
    for d in Department:
        dept_counts[d.value] = Employee.objects.filter(department=d.value, status=EmployeeStatus.ACTIVE).count()

    context = {
        'page_title': 'Сотрудники',
        'employees': employees,
        'departments': departments,
        'statuses': statuses,
        'dept_filter': dept_filter,
        'q': q,
        'dept_counts': dept_counts,
        'total_active': Employee.objects.filter(status=EmployeeStatus.ACTIVE).count(),
    }
    return render(request, 'employees/index.html', context)
