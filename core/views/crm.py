from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count, Prefetch
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse

from ..models import (
    Client, ClientContact, InteractionLog, Opportunite, Quote,
    ProductionOrder, OrdreFabrication, EtapeProduction, Material, TechnicalProduct,
    CommandeClient, LigneCommandeClient, DemandePrix, ProcessType, Machine,
)
from ..forms import (
    ClientForm, ClientContactForm, InteractionLogForm, OpportuniteForm, QuoteForm,
    CommandeClientForm, LigneCommandeClientFormSet, DemandePrixForm,
    OrdreFabricationForm, EtapeProductionFormSet,
)


# ===========================================================================
# --- CRM DASHBOARD ---
# ===========================================================================

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
    opportunites = Opportunite.objects.select_related(
        'client', 'commercial', 'material_principal', 'produit_demande'
    ).all().order_by('-date_ouverture')
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

    commandes = CommandeClient.objects.select_related('client', 'commercial', 'of_lie').order_by('-date_commande')[:50]
    commandes_stats = {
        'total': CommandeClient.objects.count(),
        'brouillon': CommandeClient.objects.filter(statut='BROUILLON').count(),
        'confirmee': CommandeClient.objects.filter(statut='CONFIRMEE').count(),
        'en_production': CommandeClient.objects.filter(statut='EN_PRODUCTION').count(),
        'livree': CommandeClient.objects.filter(statut='LIVREE').count(),
    }
    demandes_prix = DemandePrix.objects.select_related('client', 'commercial').order_by('-date_demande')[:20]
    demandes_stats = {
        'total': DemandePrix.objects.count(),
        'nouvelles': DemandePrix.objects.filter(statut='NOUVELLE').count(),
        'en_etude': DemandePrix.objects.filter(statut='EN_ETUDE').count(),
    }
    prospects_count = Client.objects.filter(status='PROSPECT').count()
    ofs_crm = OrdreFabrication.objects.select_related('client', 'produit').order_by('-date_creation')[:10]

    stock_alerts = []
    for opp in opportunites.exclude(status__in=['GAGNE', 'PERDU']).filter(material_principal__isnull=False)[:20]:
        info = opp.stock_disponible_pour_opportunite()
        if info.get('disponible') is False:
            stock_alerts.append({'opportunite': opp, 'info': info})

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
        'commandes': commandes,
        'commandes_stats': commandes_stats,
        'demandes_prix': demandes_prix,
        'demandes_stats': demandes_stats,
        'prospects_count': prospects_count,
        'ofs_crm': ofs_crm,
        'stock_alerts': stock_alerts,
    }
    return render(request, 'crm.html', context)


# ===========================================================================
# --- CLIENTS ---
# ===========================================================================

@login_required
def client_detail(request, id):
    client = get_object_or_404(Client, id=id)
    contacts = ClientContact.objects.filter(client=client)
    interactions = InteractionLog.objects.filter(client=client).order_by('-date')[:20]
    opportunites = Opportunite.objects.filter(client=client).select_related(
        'material_principal', 'produit_demande'
    ).order_by('-date_ouverture')
    quotes = Quote.objects.filter(client=client).order_by('-date')
    orders = ProductionOrder.objects.filter(client=client).order_by('-start_time')[:5]
    ofs = OrdreFabrication.objects.filter(client=client).order_by('-date_creation')[:10]

    commandes = CommandeClient.objects.filter(client=client).prefetch_related(
        'lignes__material'
    ).order_by('-date_commande')
    demandes_prix = DemandePrix.objects.filter(client=client).order_by('-date_demande')

    opp_stock_info = []
    for opp in opportunites.exclude(status__in=['GAGNE', 'PERDU']):
        opp_stock_info.append({
            'opp': opp,
            'stock': opp.stock_disponible_pour_opportunite(),
        })

    context = {
        'client': client,
        'contacts': contacts,
        'interactions': interactions,
        'opportunites': opportunites,
        'quotes': quotes,
        'orders': orders,
        'ofs': ofs,
        'commandes': commandes,
        'demandes_prix': demandes_prix,
        'opp_stock_info': opp_stock_info,
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
def convertir_prospect(request, id):
    client = get_object_or_404(Client, id=id)
    if client.status == 'PROSPECT':
        client.convertir_en_client()
        messages.success(request, f"« {client.name} » converti en client actif ✓")
    else:
        messages.info(request, f"« {client.name} » n'est pas un prospect.")
    return redirect('client_detail', id=client.id)


# ===========================================================================
# --- CONTACTS ---
# ===========================================================================

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


# ===========================================================================
# --- INTERACTIONS ---
# ===========================================================================

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


# ===========================================================================
# --- OPPORTUNITÉS ---
# ===========================================================================

@login_required
def opportunites_view(request):
    opportunites = Opportunite.objects.select_related(
        'client', 'commercial', 'material_principal', 'produit_demande'
    ).all().order_by('-date_ouverture')
    pipeline = {}
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        items = Opportunite.objects.filter(status=stage_code).select_related(
            'client', 'material_principal'
        )
        pipeline[stage_code] = {
            'label': stage_label,
            'items': items,
            'total': items.aggregate(t=Sum('valeur_estimee'))['t'] or 0,
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
            stock_info = opp.stock_disponible_pour_opportunite()
            if stock_info.get('disponible') is False:
                messages.warning(
                    request,
                    f"Opportunité « {opp.titre} » créée. ⚠️ {stock_info['message']}"
                )
            else:
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

    stock_info = opp.stock_disponible_pour_opportunite()
    return render(request, 'crm/opportunite_form.html', {
        'form': form,
        'opp': opp,
        'titre': f'Modifier : {opp.titre}',
        'stock_info': stock_info,
    })


@login_required
def delete_opportunite(request, id):
    opp = get_object_or_404(Opportunite, id=id)
    if request.method == 'POST':
        opp.delete()
        messages.success(request, "Opportunité supprimée.")
    return redirect('crm_view')


# ===========================================================================
# --- DEVIS ---
# ===========================================================================

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

        cmd = CommandeClient.objects.create(
            client=quote.client,
            devis=quote,
            commercial=quote.commercial or request.user,
            cree_par=request.user,
            statut='CONFIRMEE',
            date_commande=timezone.now().date(),
            montant_ht=quote.total_amount or 0,
            montant_total=quote.total_amount or 0,
            notes=f"Générée depuis devis {quote.reference}",
            conditions_paiement=getattr(quote.client, 'conditions_paiement', '') or '',
            delai_livraison_jours=getattr(quote.client, 'delai_livraison_jours', 15) or 15,
            remise_globale=getattr(quote.client, 'remise_defaut', 0) or 0,
        )
        LigneCommandeClient.objects.create(
            commande=cmd,
            designation=f"Prestation devis {quote.reference}",
            quantite=1,
            unite='forfait',
            prix_unitaire=quote.total_amount or 0,
        )
        messages.success(
            request,
            f"Devis {quote.reference} converti → Commande {cmd.reference}"
        )
        return redirect('commande_detail', id=cmd.id)

    messages.info(request, "Ce devis ne peut pas être converti (déjà fait ou non accepté).")
    return redirect('crm_view')


# ===========================================================================
# --- COMMANDES CLIENTS ---
# ===========================================================================

@login_required
def commandes_list(request):
    statut = request.GET.get('statut', '')
    search = request.GET.get('q', '')
    client_id = request.GET.get('client', '')

    commandes = CommandeClient.objects.select_related(
        'client', 'commercial', 'of_lie', 'devis'
    ).prefetch_related('lignes__material').order_by('-date_commande')

    if statut:
        commandes = commandes.filter(statut=statut)
    if client_id:
        commandes = commandes.filter(client_id=client_id)
    if search:
        commandes = commandes.filter(
            Q(reference__icontains=search) |
            Q(client__name__icontains=search) |
            Q(notes__icontains=search)
        )

    stats = {
        'total': CommandeClient.objects.count(),
        'brouillon': CommandeClient.objects.filter(statut='BROUILLON').count(),
        'confirmee': CommandeClient.objects.filter(statut='CONFIRMEE').count(),
        'en_production': CommandeClient.objects.filter(statut='EN_PRODUCTION').count(),
        'prete': CommandeClient.objects.filter(statut='PRETE').count(),
        'livree': CommandeClient.objects.filter(statut='LIVREE').count(),
    }

    context = {
        'commandes': commandes[:100],
        'stats': stats,
        'statut_choices': CommandeClient.STATUT_CHOICES,
        'selected_statut': statut,
        'search': search,
        'clients': Client.objects.filter(status__in=['ACTIVE', 'VIP']).order_by('name'),
        'selected_client': client_id,
    }
    return render(request, 'crm/commandes_list.html', context)


@login_required
def commande_detail(request, id):
    commande = get_object_or_404(
        CommandeClient.objects.select_related(
            'client', 'commercial', 'of_lie', 'devis', 'opportunite', 'cree_par'
        ),
        id=id
    )
    lignes = commande.lignes.select_related('produit', 'material').all()
    stock_check = commande.verifier_stock_global()

    ofs_client = OrdreFabrication.objects.filter(
        client=commande.client
    ).order_by('-date_creation')[:5]

    context = {
        'commande': commande,
        'lignes': lignes,
        'stock_check': stock_check,
        'ofs_client': ofs_client,
    }
    return render(request, 'crm/commande_detail.html', context)


@login_required
def add_commande(request):
    if request.method == 'POST':
        form = CommandeClientForm(request.POST)
        formset = LigneCommandeClientFormSet(request.POST, prefix='lignes')
        if form.is_valid() and formset.is_valid():
            commande = form.save(commit=False)
            commande.cree_par = request.user
            if not commande.commercial:
                commande.commercial = request.user
            if commande.client:
                if not commande.conditions_paiement:
                    commande.conditions_paiement = commande.client.conditions_paiement or ''
                if not commande.delai_livraison_jours:
                    commande.delai_livraison_jours = commande.client.delai_livraison_jours or 15
                if not commande.remise_globale:
                    commande.remise_globale = commande.client.remise_defaut or 0
                if not commande.adresse_livraison:
                    commande.adresse_livraison = commande.client.address or ''
            commande.save()

            lignes = formset.save(commit=False)
            for ligne in lignes:
                ligne.commande = commande
                if not ligne.designation and ligne.produit:
                    ligne.designation = str(ligne.produit)
                ligne.save()
            for obj in formset.deleted_objects:
                obj.delete()

            commande.recalculer_montants()

            stock_check = commande.verifier_stock_global()
            if stock_check['nb_ko'] > 0:
                messages.warning(
                    request,
                    f"Commande {commande.reference} créée. ⚠️ "
                    f"{stock_check['nb_ko']} ligne(s) en stock insuffisant."
                )
            else:
                messages.success(request, f"Commande {commande.reference} créée ✓")
            return redirect('commande_detail', id=commande.id)
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les champs.")
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['client'] = client_id
            try:
                client = Client.objects.get(id=client_id)
                initial['conditions_paiement'] = client.conditions_paiement or ''
                initial['delai_livraison_jours'] = client.delai_livraison_jours or 15
                initial['remise_globale'] = client.remise_defaut or 0
                initial['adresse_livraison'] = client.address or ''
            except Client.DoesNotExist:
                pass
        devis_id = request.GET.get('devis_id')
        if devis_id:
            initial['devis'] = devis_id
        opp_id = request.GET.get('opportunite_id')
        if opp_id:
            initial['opportunite'] = opp_id
        form = CommandeClientForm(initial=initial)
        formset = LigneCommandeClientFormSet(prefix='lignes', queryset=LigneCommandeClient.objects.none())

    context = {
        'form': form,
        'formset': formset,
        'titre': 'Nouvelle Commande Client',
    }
    return render(request, 'crm/commande_form.html', context)


@login_required
def edit_commande(request, id):
    commande = get_object_or_404(CommandeClient, id=id)
    if request.method == 'POST':
        form = CommandeClientForm(request.POST, instance=commande)
        formset = LigneCommandeClientFormSet(request.POST, instance=commande, prefix='lignes')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            commande.recalculer_montants()
            messages.success(request, f"Commande {commande.reference} mise à jour.")
            return redirect('commande_detail', id=commande.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        form = CommandeClientForm(instance=commande)
        formset = LigneCommandeClientFormSet(instance=commande, prefix='lignes')

    stock_check = commande.verifier_stock_global()
    context = {
        'form': form,
        'formset': formset,
        'commande': commande,
        'titre': f'Modifier {commande.reference}',
        'stock_check': stock_check,
    }
    return render(request, 'crm/commande_form.html', context)


@login_required
def commande_changer_statut(request, id, nouveau_statut):
    commande = get_object_or_404(CommandeClient, id=id)
    if nouveau_statut in dict(CommandeClient.STATUT_CHOICES):
        ancien = commande.statut
        commande.statut = nouveau_statut
        if nouveau_statut == 'LIVREE' and not commande.date_livraison_reelle:
            commande.date_livraison_reelle = timezone.now().date()
        commande.save()
        messages.success(request, f"{commande.reference} : {ancien} → {nouveau_statut}")
    else:
        messages.error(request, "Statut invalide.")
    return redirect('commande_detail', id=id)


@login_required
def commande_check_stock(request, id):
    commande = get_object_or_404(CommandeClient, id=id)
    data = commande.verifier_stock_global()
    data['reference'] = commande.reference
    return JsonResponse(data)


@login_required
def commande_creer_of(request, id):
    commande = get_object_or_404(
        CommandeClient.objects.select_related('client').prefetch_related('lignes__produit'),
        id=id
    )

    if commande.of_lie_id:
        messages.info(request, f"Un OF existe déjà : {commande.of_lie.numero_of}")
        return redirect('crm_of_detail', of_id=commande.of_lie_id)

    if commande.statut not in ('CONFIRMEE', 'EN_PRODUCTION', 'BROUILLON'):
        messages.error(request, "La commande doit être confirmée pour créer un OF.")
        return redirect('commande_detail', id=id)

    produit = None
    quantite = 0
    for ligne in commande.lignes.all():
        if ligne.produit and not produit:
            produit = ligne.produit
        quantite += ligne.quantite or 0

    if not produit:
        produit = TechnicalProduct.objects.first()
        if not produit:
            messages.error(
                request,
                "Impossible de créer l'OF : aucun produit technique lié. "
                "Ajoutez un produit sur une ligne de commande."
            )
            return redirect('commande_detail', id=id)

    if request.method == 'POST':
        of = OrdreFabrication.objects.create(
            client=commande.client,
            produit=produit,
            opportunite=commande.opportunite,
            quantite_prevue=quantite or 0,
            date_lancement=timezone.now().date(),
            date_prevue_fin=commande.date_livraison_prevue,
            priorite=commande.priorite if commande.priorite in dict(OrdreFabrication.PRIORITE_CHOICES) else 'NORMALE',
            statut='BROUILLON',
            cree_par=request.user,
            notes=f"OF généré depuis commande {commande.reference}\n{commande.notes or ''}",
            observation=f"CMD:{commande.reference}",
        )
        commande.of_lie = of
        if commande.statut == 'CONFIRMEE':
            commande.statut = 'EN_PRODUCTION'
        commande.save(update_fields=['of_lie', 'statut'])

        messages.success(
            request,
            f"OF {of.numero_of} créé depuis {commande.reference} ✓ "
            f"— Ajoutez les étapes de production ci-dessous."
        )
        return redirect('crm_of_edit', of_id=of.id)

    stock_check = commande.verifier_stock_global()
    context = {
        'commande': commande,
        'produit': produit,
        'quantite': quantite,
        'stock_check': stock_check,
    }
    return render(request, 'crm/commande_creer_of.html', context)


# ===========================================================================
# --- DEMANDES DE PRIX ---
# ===========================================================================

@login_required
def demandes_prix_list(request):
    statut = request.GET.get('statut', '')
    search = request.GET.get('q', '')

    demandes = DemandePrix.objects.select_related(
        'client', 'commercial', 'produit', 'devis'
    ).order_by('-date_demande')

    if statut:
        demandes = demandes.filter(statut=statut)
    if search:
        demandes = demandes.filter(
            Q(reference__icontains=search) |
            Q(objet__icontains=search) |
            Q(client__name__icontains=search)
        )

    stats = {
        'total': DemandePrix.objects.count(),
        'nouvelles': DemandePrix.objects.filter(statut='NOUVELLE').count(),
        'en_etude': DemandePrix.objects.filter(statut='EN_ETUDE').count(),
        'devis_envoye': DemandePrix.objects.filter(statut='DEVIS_ENVOYE').count(),
    }

    context = {
        'demandes': demandes[:100],
        'stats': stats,
        'statut_choices': DemandePrix.STATUT_CHOICES,
        'selected_statut': statut,
        'search': search,
    }
    return render(request, 'crm/demandes_prix_list.html', context)


@login_required
def add_demande_prix(request):
    if request.method == 'POST':
        form = DemandePrixForm(request.POST)
        if form.is_valid():
            dp = form.save(commit=False)
            dp.cree_par = request.user
            if not dp.commercial:
                dp.commercial = request.user
            dp.save()
            messages.success(request, f"Demande {dp.reference} créée.")
            return redirect('demandes_prix_list')
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['client'] = client_id
        form = DemandePrixForm(initial=initial)

    return render(request, 'crm/demande_prix_form.html', {
        'form': form,
        'titre': 'Nouvelle Demande de Prix',
    })


@login_required
def edit_demande_prix(request, id):
    dp = get_object_or_404(DemandePrix, id=id)
    if request.method == 'POST':
        form = DemandePrixForm(request.POST, instance=dp)
        if form.is_valid():
            form.save()
            messages.success(request, f"Demande {dp.reference} mise à jour.")
            return redirect('demandes_prix_list')
    else:
        form = DemandePrixForm(instance=dp)

    return render(request, 'crm/demande_prix_form.html', {
        'form': form,
        'dp': dp,
        'titre': f'Modifier {dp.reference}',
    })


@login_required
def demande_prix_vers_devis(request, id):
    dp = get_object_or_404(DemandePrix, id=id)
    dp.statut = 'DEVIS_ENVOYE'
    dp.save(update_fields=['statut'])
    messages.info(request, f"Créez le devis pour la demande {dp.reference}")
    return redirect(f"/crm/devis/add/?client_id={dp.client_id}")


# ===========================================================================
# --- API STOCK CHECK ---
# ===========================================================================

@login_required
def api_check_material_stock(request):
    material_id = request.GET.get('material_id')
    quantite = float(request.GET.get('quantite', 0) or 0)

    if not material_id:
        return JsonResponse({'error': 'material_id requis'}, status=400)

    try:
        material = Material.objects.get(id=material_id)
    except Material.DoesNotExist:
        return JsonResponse({'error': 'Matière introuvable'}, status=404)

    stock = float(material.quantity or 0)
    ok = stock >= quantite
    return JsonResponse({
        'material_id': material.id,
        'material_name': material.name,
        'stock': stock,
        'unit': material.unit,
        'besoin': quantite,
        'manque': max(0, quantite - stock),
        'disponible': ok,
        'is_low': material.is_low_stock(),
        'min_threshold': material.min_threshold,
        'message': (
            f'✓ Stock OK — {stock:.1f} {material.unit} disponible'
            if ok else
            f'⚠️ Insuffisant — {stock:.1f} dispo / {quantite:.1f} besoin (manque {quantite - stock:.1f})'
        ),
        'badge': 'ok' if ok else 'ko',
    })


# ===========================================================================
# --- CRM OF INTÉGRÉ (Reste sur /crm/of/ — pas de bascule) ---
# ===========================================================================

@login_required
def crm_of_list(request):
    statut = request.GET.get('statut', '')
    search = request.GET.get('q', '')
    client_id = request.GET.get('client', '')

    ofs = OrdreFabrication.objects.select_related(
        'client', 'produit', 'cree_par'
    ).prefetch_related('etapes', 'commandes_client').order_by('-date_creation')

    if statut:
        ofs = ofs.filter(statut=statut)
    if client_id:
        ofs = ofs.filter(client_id=client_id)
    if search:
        ofs = ofs.filter(
            Q(numero_of__icontains=search) |
            Q(numero_lot__icontains=search) |
            Q(client__name__icontains=search) |
            Q(produit__name__icontains=search)
        )

    ofs_avec_commande = ofs.filter(commandes_client__isnull=False).distinct()

    stats = {
        'total': ofs.count(),
        'en_cours': ofs.filter(statut='EN_COURS').count(),
        'termine': ofs.filter(statut='TERMINE').count(),
        'lies_commandes': ofs_avec_commande.count(),
    }

    context = {
        'ofs': ofs[:100],
        'stats': stats,
        'statut_choices': OrdreFabrication.STATUT_CHOICES,
        'selected_statut': statut,
        'search': search,
        'clients': Client.objects.filter(status__in=['ACTIVE', 'VIP', 'PROSPECT']).order_by('name'),
        'selected_client': client_id,
        'from_crm': True,
    }
    return render(request, 'crm/crm_of_list.html', context)


@login_required
def crm_of_create(request):
    if request.method == 'POST':
        form = OrdreFabricationForm(request.POST, request.FILES)
        formset = EtapeProductionFormSet(request.POST, prefix='etapes')
        if form.is_valid():
            of = form.save(commit=False)
            of.cree_par = request.user
            of.save()
            if formset.is_valid():
                etapes = formset.save(commit=False)
                for etape in etapes:
                    etape.of = of
                    etape.save()
                for obj in formset.deleted_objects:
                    obj.delete()
            messages.success(request, f"OF {of.numero_of} créé dans le CRM ✓")
            return redirect('crm_of_detail', of_id=of.id)
        else:
            messages.error(request, "Erreur dans le formulaire OF.")
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['client'] = client_id
        cmd_id = request.GET.get('commande_id')
        if cmd_id:
            try:
                cmd = CommandeClient.objects.get(id=cmd_id)
                initial['client'] = cmd.client_id
                initial['opportunite'] = cmd.opportunite_id
                initial['quantite_prevue'] = sum(l.quantite or 0 for l in cmd.lignes.all())
                initial['date_prevue_fin'] = cmd.date_livraison_prevue
            except CommandeClient.DoesNotExist:
                pass
        form = OrdreFabricationForm(initial=initial)
        formset = EtapeProductionFormSet(prefix='etapes', queryset=EtapeProduction.objects.none())

    context = {
        'form': form,
        'formset': formset,
        'process_types': ProcessType.objects.filter(est_actif=True),
        'machines': Machine.objects.filter(est_active=True).order_by('name') if hasattr(Machine, 'est_active') else Machine.objects.all().order_by('name'),
        'titre': 'Nouvel OF (CRM)',
        'from_crm': True,
    }
    return render(request, 'crm/crm_of_form.html', context)


@login_required
def crm_of_detail(request, of_id):
    of = get_object_or_404(
        OrdreFabrication.objects.select_related('client', 'produit', 'cree_par', 'opportunite'),
        id=of_id
    )
    etapes = of.etapes.select_related('process_type', 'machine', 'operateur', 'atelier').order_by('numero_etape')
    commandes_liees = CommandeClient.objects.filter(of_lie=of).select_related('client')

    context = {
        'of': of,
        'etapes': etapes,
        'commandes_liees': commandes_liees,
        'from_crm': True,
    }
    return render(request, 'crm/crm_of_detail.html', context)


@login_required
def crm_of_edit(request, of_id):
    of = get_object_or_404(OrdreFabrication, id=of_id)

    if request.method == 'POST':
        form = OrdreFabricationForm(request.POST, request.FILES, instance=of)
        formset = EtapeProductionFormSet(request.POST, instance=of, prefix='etapes')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"OF {of.numero_of} mis à jour ✓")
            return redirect('crm_of_detail', of_id=of.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        form = OrdreFabricationForm(instance=of)
        formset = EtapeProductionFormSet(instance=of, prefix='etapes')

    context = {
        'form': form,
        'formset': formset,
        'of': of,
        'process_types': ProcessType.objects.filter(est_actif=True),
        'machines': Machine.objects.all().order_by('name'),
        'titre': f'Modifier OF {of.numero_of} (CRM)',
        'from_crm': True,
    }
    return render(request, 'crm/crm_of_form.html', context)


@login_required
def crm_of_changer_statut(request, of_id, nouveau_statut):
    of = get_object_or_404(OrdreFabrication, id=of_id)
    if nouveau_statut in dict(OrdreFabrication.STATUT_CHOICES):
        ancien = of.statut
        of.statut = nouveau_statut
        if nouveau_statut == 'LANCE' and not of.date_lancement:
            of.date_lancement = timezone.now().date()
        elif nouveau_statut == 'TERMINE':
            of.date_fin_reelle = timezone.now().date()
        of.save()
        messages.success(request, f"OF {of.numero_of} : {ancien} → {nouveau_statut}")
    else:
        messages.error(request, "Statut invalide.")
    return redirect('crm_of_detail', of_id=of_id)