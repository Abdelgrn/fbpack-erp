from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from ..models import Machine
from ..forms import MachineForm

@login_required
def machine_view(request):
    machines = Machine.objects.all().order_by('-id')
    return render(request, 'machines.html', {'machines': machines})


@login_required
def add_machine(request):
    if request.method == 'POST':
        form = MachineForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('machine_view')
    else:
        form = MachineForm()
    return render(request, 'machines.html', {'form': form, 'titre': 'Nouvelle Machine'})