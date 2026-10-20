"""Suivi de production par machine : Extrudeuse, Découpe grande, Découpe petite.

Lecture seule. Chaque machine a son PC et sa balance ; le nom de la machine vient du
erp_sync.txt de chaque PC (champ poste=). Les trois machines sont toujours affichées,
même sans pesée.

Deux vues, comme la liste de coulissage de la pesée :
- Clients : Machine -> Client -> Lot -> Palette -> Bobine, avec totaux à chaque niveau ;
- Palettes : une ligne par palette, à plat.
"""
from collections import OrderedDict
from urllib.parse import urlencode

from django.apps import apps
from django.db.models import Q
from django.urls import NoReverseMatch, reverse

from core.models.stock_produit_fini import ProduitFiniBobine, ProduitFiniPalette

# Noms exacts des machines (doivent être identiques dans erp_sync.txt de chaque PC)
MACHINES = ['Extrudeuse', 'Découpe grande', 'Découpe petite']
POSTE_VIDE = 'Non renseigné'

ETAT_EN_COURS = 'EN_COURS'      # pesées en cours, job pas encore clôturé
ETAT_A_ENTRER = 'A_ENTRER'      # job clôturé, pas encore entré en stock
ETAT_EN_STOCK = 'EN_STOCK'      # entré en stock produit fini


def etat_lot(lot):
    if lot.entree_stock_le is not None:
        return ETAT_EN_STOCK
    if lot.job_clos_le is not None:
        return ETAT_A_ENTRER
    return ETAT_EN_COURS


def _ajouter(res, bobine):
    res['nb_bobines'] += 1
    res['kg'] += bobine.poids_kg


def _res_vide():
    return {'nb_bobines': 0, 'kg': 0.0}


def _noeud_poste(postes, nom):
    return postes.setdefault(nom, {'nom': nom, 'res': _res_vide(), 'clients': OrderedDict()})


def liste_postes():
    """Machines pour le filtre : les 3 machines, puis tout autre nom trouvé dans les pesées."""
    noms = ProduitFiniPalette.objects.values_list('poste', flat=True).distinct()
    autres = set()
    for n in noms:
        nom = n or POSTE_VIDE
        if nom not in MACHINES:
            autres.add(nom)
    return MACHINES + sorted(autres)


def _bobines_filtrees(poste=None, recherche=None, date_debut=None, date_fin=None):
    qs = ProduitFiniBobine.objects.select_related('palette__lot')
    if poste:
        qs = qs.filter(palette__poste='' if poste == POSTE_VIDE else poste)
    if recherche:
        qs = qs.filter(
            Q(palette__lot__client_nom__icontains=recherche)
            | Q(palette__lot__produit_nom__icontains=recherche)
            | Q(palette__lot__numero_lot__icontains=recherche)
            | Q(palette__numero_palette__icontains=recherche)
        )
    if date_debut:
        qs = qs.filter(date_heure__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_heure__date__lte=date_fin)
    return qs.order_by('palette__poste', 'palette__lot__client_nom', 'palette__lot__produit_nom',
                       'palette__lot__numero_lot', 'palette__numero_palette', 'date_heure', 'id')


def construire_arbre(poste=None, recherche=None, date_debut=None, date_fin=None):
    qs = _bobines_filtrees(poste, recherche, date_debut, date_fin)

    postes = OrderedDict()
    # Les machines sont toujours là (même vides). Si on filtre sur une machine, on ne montre qu'elle.
    if poste:
        if poste in MACHINES:
            _noeud_poste(postes, poste)
    else:
        for machine in MACHINES:
            _noeud_poste(postes, machine)

    for b in qs:
        pal = b.palette
        lot = pal.lot
        nom_poste = pal.poste or POSTE_VIDE
        noeud_poste = _noeud_poste(postes, nom_poste)
        _ajouter(noeud_poste['res'], b)

        noeud_client = noeud_poste['clients'].setdefault(
            lot.client_nom or '—', {'nom': lot.client_nom or '—', 'res': _res_vide(), 'lots': OrderedDict()})
        _ajouter(noeud_client['res'], b)

        cle_lot = (lot.produit_nom or '—', lot.numero_lot)
        noeud_lot = noeud_client['lots'].setdefault(cle_lot, {
            'lot_id': lot.id, 'produit': cle_lot[0], 'numero_lot': lot.numero_lot,
            'a_relier': lot.a_relier, 'job_clos_le': lot.job_clos_le,
            'entree_stock_le': lot.entree_stock_le, 'etat': etat_lot(lot),
            'res': _res_vide(), 'palettes': OrderedDict()})
        _ajouter(noeud_lot['res'], b)

        noeud_pal = noeud_lot['palettes'].setdefault(pal.id, {
            'numero': pal.numero_palette, 'res': _res_vide(), 'bobines': []})
        _ajouter(noeud_pal['res'], b)
        noeud_pal['bobines'].append(b)

    # Conversion en listes pour le template
    resultat = []
    for np_ in postes.values():
        clients = []
        for nc in np_['clients'].values():
            lots = []
            for nl in nc['lots'].values():
                nl['palettes'] = list(nl['palettes'].values())
                lots.append(nl)
            nc['lots'] = lots
            clients.append(nc)
        np_['clients'] = clients
        resultat.append(np_)
    return resultat


def palettes_a_plat(poste=None, recherche=None, date_debut=None, date_fin=None):
    """Vue Palettes : une ligne par palette (machine, client, produit, lot, nb bobines, kg, moy.)."""
    lignes = OrderedDict()
    for b in _bobines_filtrees(poste, recherche, date_debut, date_fin):
        pal = b.palette
        lot = pal.lot
        ligne = lignes.setdefault(pal.id, {
            'machine': pal.poste or POSTE_VIDE,
            'numero': pal.numero_palette,
            'client': lot.client_nom or '—',
            'produit': lot.produit_nom or '—',
            'numero_lot': lot.numero_lot,
            'a_relier': lot.a_relier,
            'etat': etat_lot(lot),
            'nb_bobines': 0, 'kg': 0.0, 'moy': 0.0,
            'equipe': '', 'derniere_saisie': None,
        })
        ligne['nb_bobines'] += 1
        ligne['kg'] += b.poids_kg
        if b.equipe:
            ligne['equipe'] = b.equipe
        if ligne['derniere_saisie'] is None or b.date_heure > ligne['derniere_saisie']:
            ligne['derniere_saisie'] = b.date_heure
    for ligne in lignes.values():
        ligne['moy'] = ligne['kg'] / ligne['nb_bobines'] if ligne['nb_bobines'] else 0.0
    return list(lignes.values())


def totaux_par_machine(recherche=None, date_debut=None, date_fin=None):
    """Tuiles : les 3 machines avec leurs totaux (toujours les 3, même à zéro)."""
    arbre = construire_arbre(None, recherche, date_debut, date_fin)
    par_nom = {p['nom']: p['res'] for p in arbre}
    return [{'nom': m, 'res': par_nom.get(m, _res_vide())} for m in MACHINES]


def _of_pour_lot(numero_lot):
    """Ordre de fabrication relié au numéro de lot (le lot relie le job du CRM à la production).

    Retourne None si le modèle OF n'existe pas dans ce projet ou si aucun OF ne correspond.
    """
    try:
        OrdreFabrication = apps.get_model('core', 'OrdreFabrication')
    except LookupError:
        return None
    of = OrdreFabrication.chercher_par_lot(numero_lot)
    if of is None:
        return None
    try:
        url = reverse('crm_of_detail', args=[of.id])
    except NoReverseMatch:
        url = ''
    return {
        'id': of.id,
        'numero': getattr(of, 'numero_of', '') or '',
        'client': str(getattr(of, 'client', '') or ''),
        'produit': str(getattr(of, 'produit', '') or ''),
        'statut': of.get_statut_display() if hasattr(of, 'get_statut_display') else '',
        'url': url,
    }


def lots_par_numero(poste=None, recherche=None, date_debut=None, date_fin=None):
    """Vue Lots : un groupe par numéro de lot, avec répartition par machine et liste des palettes."""
    groupes = OrderedDict()
    for b in _bobines_filtrees(poste, recherche, date_debut, date_fin):
        pal = b.palette
        lot = pal.lot
        machine = pal.poste or POSTE_VIDE
        g = groupes.get(lot.numero_lot)
        if g is None:
            g = groupes[lot.numero_lot] = {
                'numero_lot': lot.numero_lot,
                'clients': [], 'produits': [], 'etats': [],
                'a_relier': False, 'of': _of_pour_lot(lot.numero_lot),
                'res': _res_vide(), 'par_machine': OrderedDict(),
                'palettes': OrderedDict(), 'derniere_saisie': None,
            }
        for liste, valeur in ((g['clients'], lot.client_nom or '—'),
                              (g['produits'], lot.produit_nom or '—'),
                              (g['etats'], etat_lot(lot))):
            if valeur not in liste:
                liste.append(valeur)
        if lot.a_relier:
            g['a_relier'] = True
        _ajouter(g['res'], b)

        pm = g['par_machine'].setdefault(machine, {'nom': machine, 'res': _res_vide()})
        _ajouter(pm['res'], b)

        pl = g['palettes'].setdefault(pal.id, {
            'machine': machine, 'numero': pal.numero_palette,
            'client': lot.client_nom or '—', 'res': _res_vide()})
        _ajouter(pl['res'], b)

        if g['derniere_saisie'] is None or b.date_heure > g['derniere_saisie']:
            g['derniere_saisie'] = b.date_heure

    resultat = []
    for g in groupes.values():
        g['par_machine'] = list(g['par_machine'].values())
        g['palettes'] = list(g['palettes'].values())
        resultat.append(g)
    return resultat


def totaux(postes):
    total = _res_vide()
    for p in postes:
        total['nb_bobines'] += p['res']['nb_bobines']
        total['kg'] += p['res']['kg']
    return total


def url_avec(params, **modifs):
    """Construit une query string à partir des filtres courants, en remplaçant certains paramètres."""
    donnees = {k: v for k, v in params.items() if v}
    for k, v in modifs.items():
        if v:
            donnees[k] = v
        else:
            donnees.pop(k, None)
    return '?' + urlencode(donnees)
