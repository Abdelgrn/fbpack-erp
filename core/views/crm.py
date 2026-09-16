from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.contrib import messages

from ..models import Client, ClientContact, InteractionLog, Opportunite, Quote, ProductionOrder, OrdreFabrication
from ..forms import ClientForm, ClientContactForm, InteractionLogForm, OpportuniteForm, QuoteForm

@login_required
def crm_view(request):
    status_filter = request.GET.get('status', '')
    segment_filter = request.GET.get('segment', '')
    region_filter = request.GET.get('region', '')
    search = request.GET.get('q', '')
    clients = Client.objects.all().order_by('name')
    if status_filter:
        clients = clients.filter(status=status_filter)
    if segment_filter:
        clients = clients.filter(segment=segment_filter)
    if region_filter:
        clients = clients.filter(region=region_filter)
    if search:
        clients = clients.filter(
            Q(name__icontains=search) |
            Q(city__icontains=search) |
            Q(code_client__icontains=search)
        )
    quotes = Quote.objects.all().order_by('-date')
    opportunites = Opportunite.objects.all().order_by('-date_ouverture')
    pipeline_stages = []
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        count = Opportunite.objects.filter(status=stage_code).count()
        montant = Opportunite.objects.filter(status=stage_code).aggregate(t=Sum('valeur_estimee'))['t'] or 0
        pipeline_stages.append({
            'code': stage_code,
            'label': stage_label,
            'count': count,
            'montant': montant
        })
    context = {
        'clients': clients,
        'quotes': quotes,
        'opportunites': opportunites,
        'pipeline_stages': pipeline_stages,
        'status_filter': status_filter,
        'segment_filter': segment_filter,
        'region_filter': region_filter,
        'search': search,
        'status_choices': Client.STATUS_CHOICES,
        'segment_choices': Client.SEGMENT_CHOICES,
        'region_choices': Client.REGION_CHOICES,
    }
    return render(request, 'crm.html', context)


@login_required
def client_detail(request, id):
    client = get_object_or_404(Client, id=id)
    contacts = ClientContact.objects.filter(client=client)
    interactions = InteractionLog.objects.filter(client=client).order_by('-date')[:20]
    opportunites = Opportunite.objects.filter(client=client).order_by('-date_ouverture')
    quotes = Quote.objects.filter(client=client).order_by('-date')
    orders = ProductionOrder.objects.filter(client=client).order_by('-start_time')[:5]
    ofs = OrdreFabrication.objects.filter(client=client).order_by('-date_creation')[:5]
    context = {
        'client': client,
        'contacts': contacts,
        'interactions': interactions,
        'opportunites': opportunites,
        'quotes': quotes,
        'orders': orders,
        'ofs': ofs,
    }
    return render(request, 'crm/client_detail.html', context)


@login_required
def add_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Client « {client.name} » créé.")
            return redirect('client_detail', id=client.id)
    else:
        form = ClientForm()
    return render(request, 'crm/client_form.html', {'form': form, 'titre': 'Nouveau Client'})


@login_required
def edit_client(request, id):
    client = get_object_or_404(Client, id=id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Client mis à jour.")
            return redirect('client_detail', id=client.id)
    else:
        form = ClientForm(instance=client)
    return render(request, 'crm/client_form.html', {
        'form': form,
        'titre': f'Modifier {client.name}',
        'client': client
    })


@login_required
def add_contact(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.client = client
            contact.save()
            messages.success(request, f"Contact « {contact.name} » ajouté.")
            return redirect('client_detail', id=client_id)
    else:
        form = ClientContactForm()
    return render(request, 'crm/contact_form.html', {
        'form': form,
        'client': client,
        'titre': 'Nouveau Contact'
    })


@login_required
def edit_contact(request, id):
    contact = get_object_or_404(ClientContact, id=id)
    if request.method == 'POST':
        form = ClientContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact mis à jour.")
            return redirect('client_detail', id=contact.client.id)
    else:
        form = ClientContactForm(instance=contact)
    return render(request, 'crm/contact_form.html', {
        'form': form,
        'client': contact.client,
        'titre': f'Modifier {contact.name}'
    })


@login_required
def delete_contact(request, id):
    contact = get_object_or_404(ClientContact, id=id)
    client_id = contact.client.id
    if request.method == 'POST':
        contact.delete()
        messages.success(request, "Contact supprimé.")
    return redirect('client_detail', id=client_id)


@login_required
def add_interaction(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = InteractionLogForm(request.POST, client=client)
        if form.is_valid():
            interaction = form.save(commit=False)
            interaction.client = client
            interaction.save()
            messages.success(request, "Interaction enregistrée.")
            return redirect('client_detail', id=client_id)
    else:
        form = InteractionLogForm(client=client)
    return render(request, 'crm/interaction_form.html', {
        'form': form,
        'client': client,
        'titre': 'Nouvelle Interaction'
    })


@login_required
def opportunites_view(request):
    opportunites = Opportunite.objects.all().order_by('-date_ouverture')
    pipeline = {}
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        pipeline[stage_code] = {
            'label': stage_label,
            'items': Opportunite.objects.filter(status=stage_code),
            'total': Opportunite.objects.filter(status=stage_code).aggregate(
                t=Sum('valeur_estimee'))['t'] or 0,
        }
    return render(request, 'crm/opportunites.html', {
        'opportunites': opportunites,
        'pipeline': pipeline
    })


@login_required
def add_opportunite(request):
    if request.method == 'POST':
        form = OpportuniteForm(request.POST)
        if form.is_valid():
            opp = form.save()
            messages.success(request, f"Opportunité « {opp.titre} » créée.")
            return redirect('crm_view')
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['client'] = client_id
        form = OpportuniteForm(initial=initial)
    return render(request, 'crm/opportunite_form.html', {
        'form': form,
        'titre': 'Nouvelle Opportunité'
    })


@login_required
def edit_opportunite(request, id):
    opp = get_object_or_404(Opportunite, id=id)
    if request.method == 'POST':
        form = OpportuniteForm(request.POST, instance=opp)
        if form.is_valid():
            form.save()
            messages.success(request, "Opportunité mise à jour.")
            return redirect('crm_view')
    else:
        form = OpportuniteForm(instance=opp)
    return render(request, 'crm/opportunite_form.html', {
        'form': form,
        'opp': opp,
        'titre': f'Modifier : {opp.titre}'
    })


@login_required
def delete_opportunite(request, id):
    opp = get_object_or_404(Opportunite, id=id)
    if request.method == 'POST':
        opp.delete()
        messages.success(request, "Opportunité supprimée.")
    return redirect('crm_view')


@login_required
def quotes_view(request):
    quotes = Quote.objects.all().order_by('-date')
    return render(request, 'crm/quotes_list.html', {'quotes': quotes})


@login_required
def add_quote(request):
    if request.method == 'POST':
        form = QuoteForm(request.POST, request.FILES)
        if form.is_valid():
            quote = form.save()
            messages.success(request, f"Devis {quote.reference} créé.")
            return redirect('crm_view')
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['client'] = client_id
        form = QuoteForm(initial=initial)
    return render(request, 'crm/quote_form.html', {'form': form, 'titre': 'Nouveau Devis'})


@login_required
def edit_quote(request, id):
    quote = get_object_or_404(Quote, id=id)
    if request.method == 'POST':
        form = QuoteForm(request.POST, request.FILES, instance=quote)
        if form.is_valid():
            form.save()
            messages.success(request, "Devis mis à jour.")
            return redirect('crm_view')
    else:
        form = QuoteForm(instance=quote)
    return render(request, 'crm/quote_form.html', {
        'form': form,
        'titre': f'Modifier Devis {quote.reference}'
    })


@login_required
def convert_quote_to_order(request, id):
    quote = get_object_or_404(Quote, id=id)
    if quote.status in ['ACCEPTED', 'SIGNED'] and not quote.commande_creee:
        quote.commande_creee = True
        quote.save()
        messages.success(request, f"Devis {quote.reference} converti en commande.")
    return redirect('crm_view')