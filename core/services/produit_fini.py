"""Logique du stock produit fini : réception pesée, déstockage, annulation.

Toutes les écritures sont dans une transaction (tout ou rien).
"""
from datetime import datetime

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models.stock_produit_fini import (
    ProduitFiniBobine, ProduitFiniLot, ProduitFiniMouvement, ProduitFiniPalette,
)

TYPE_BOBINE = 'BOBINE'
TYPE_CLOTURE = 'JOB_CLOTURE'


def _norm(valeur):
    """Espaces multiples et bords supprimés. Ex. « CHOR  khaled » -> « CHOR khaled »."""
    return ' '.join(str(valeur or '').split())


def _trouver_client(nom):
    if not nom:
        return None
    Client = apps.get_model('core', 'Client')
    return Client.objects.filter(name__iexact=nom).first()


def _trouver_produit(client, nom):
    if not client or not nom:
        return None
    TechnicalProduct = apps.get_model('core', 'TechnicalProduct')
    return TechnicalProduct.objects.filter(client=client, name__iexact=nom).first()


def _date_pesee(texte):
    """La pesée envoie l'heure locale sans fuseau : on la rend « aware » (Africa/Algiers)."""
    dt = parse_datetime(_norm(texte).replace(' ', 'T', 1)) if texte else None
    if dt is None:
        raise ValueError('date_heure invalide')
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _lot_pour(client_nom, produit_nom, numero_lot):
    """Retourne le lot (créé si besoin), en rattachant client/produit s'ils sont reconnus."""
    client = _trouver_client(client_nom)
    produit = _trouver_produit(client, produit_nom)
    # Casse et espaces ignorées : « chor khaled » et « CHOR KHALED » désignent le même lot.
    lot = (ProduitFiniLot.objects
           .filter(client_nom__iexact=client_nom, produit_nom__iexact=produit_nom,
                   numero_lot__iexact=numero_lot)
           .order_by('id').first())
    if lot is None:
        lot = ProduitFiniLot.objects.create(
            client_nom=client_nom, produit_nom=produit_nom, numero_lot=numero_lot)
    changes = []
    if lot.client_id is None and client is not None:
        lot.client = client
        changes.append('client')
    if lot.produit_id is None and produit is not None:
        lot.produit = produit
        changes.append('produit')
    a_relier = lot.client_id is None or (bool(produit_nom) and lot.produit_id is None)
    if lot.a_relier != a_relier:
        lot.a_relier = a_relier
        changes.append('a_relier')
    if changes:
        lot.save(update_fields=changes)
    return lot


def enregistrer_bobine(p):
    """Reçoit une bobine pesée. Retourne 'creee' ou 'deja_recue'."""
    uid = _norm(p.get('uid'))
    if not uid:
        raise ValueError('uid manquant')
    poids = float(p.get('poids_kg'))
    if poids <= 0:
        raise ValueError('poids invalide')
    date_heure = _date_pesee(p.get('date_heure'))
    client_nom = _norm(p.get('client_nom'))
    produit_nom = _norm(p.get('article'))
    numero_lot = _norm(p.get('numero_lot')) or 'SANS-LOT'
    numero_palette = _norm(p.get('numero_palette')) or 'PAL-000'
    numero_bobine = _norm(p.get('numero_bobine'))

    if ProduitFiniBobine.objects.filter(uid=uid).exists():
        return 'deja_recue'
    try:
        with transaction.atomic():
            lot = _lot_pour(client_nom, produit_nom, numero_lot)
            poste = _norm(p.get('poste'))[:100]
            palette, _ = ProduitFiniPalette.objects.get_or_create(
                lot=lot, poste=poste, numero_palette=numero_palette)
            ProduitFiniBobine.objects.create(
                palette=palette, numero_bobine=numero_bobine, poids_kg=poids,
                date_heure=date_heure, operateur=_norm(p.get('operateur'))[:150],
                equipe=_norm(p.get('equipe'))[:20],
                statut_pesee=_norm(p.get('statut')) or 'ok', uid=uid)
            ProduitFiniMouvement.objects.create(
                lot=lot, type='ENTREE', nb_bobines=1, poids_kg=poids,
                palettes_libelle=numero_palette, date=date_heure,
                motif=f'Pesée bobine {numero_bobine}')
    except IntegrityError:
        # Deux envois simultanés du même uid : le second est un doublon
        return 'deja_recue'
    return 'creee'


def enregistrer_cloture_job(p):
    """Le job est clôturé dans la pesée : on marque le lot."""
    client_nom = _norm(p.get('client_nom'))
    produit_nom = _norm(p.get('article'))
    numero_lot = _norm(p.get('numero_lot')) or 'SANS-LOT'
    with transaction.atomic():
        lot = _lot_pour(client_nom, produit_nom, numero_lot)
        if lot.job_clos_le is None:
            lot.job_clos_le = timezone.now()
            champs = ['job_clos_le']
            temps = p.get('temps_production_min')
            if temps is not None and str(temps).strip() != '':
                try:
                    lot.temps_production_min = max(0, int(round(float(temps))))
                    champs.append('temps_production_min')
                except (TypeError, ValueError):
                    pass  # temps illisible : le job reste clôturé, sans temps
            lot.save(update_fields=champs)
    return 'cloture'


def traiter_evenement(evt):
    """Traite un événement de la pesée. Ne lève jamais d'exception : retourne un résultat."""
    uid = _norm((evt or {}).get('uid')) if isinstance(evt, dict) else ''
    try:
        if not isinstance(evt, dict):
            raise ValueError('événement invalide')
        type_evt = _norm(evt.get('type')) or TYPE_BOBINE
        if type_evt == TYPE_BOBINE:
            statut = enregistrer_bobine(evt)
        elif type_evt == TYPE_CLOTURE:
            statut = enregistrer_cloture_job(evt)
        else:
            raise ValueError(f'type inconnu : {type_evt}')
        return {'uid': uid, 'statut': statut, 'detail': ''}
    except Exception as exc:  # noqa: BLE001 - on renvoie l'erreur à la pesée
        return {'uid': uid, 'statut': 'erreur', 'detail': str(exc)[:300]}


# ─────────────────────────── Totaux ───────────────────────────

def resume_bobines(bobines):
    """bobines : liste d'objets ProduitFiniBobine. Retourne un dict de totaux et statut."""
    nb = len(bobines)
    kg = sum(b.poids_kg for b in bobines)
    restantes = [b for b in bobines if b.date_sortie is None]
    nb_r = len(restantes)
    kg_r = sum(b.poids_kg for b in restantes)
    if nb == 0:
        statut = 'VIDE'
    elif nb_r == 0:
        statut = 'SORTI'
    elif nb_r < nb:
        statut = 'PARTIEL'
    else:
        statut = 'EN_STOCK'
    return {
        'nb_bobines': nb, 'kg_total': round(kg, 3),
        'nb_restantes': nb_r, 'kg_restants': round(kg_r, 3),
        'statut': statut,
    }


# ─────────────────────────── Déstockage ───────────────────────────

def entrer_en_stock(lot, utilisateur=None):
    """Fait entrer un lot dans le stock produit fini (action manuelle du module Suivi par poste).

    Conditions : le job doit être clôturé dans la pesée, et le lot ne doit pas déjà être en stock.
    Un lot « à relier » peut entrer en stock : le lien client/produit se corrige ensuite.
    """
    with transaction.atomic():
        lot = ProduitFiniLot.objects.select_for_update().get(pk=lot.pk)
        if lot.entree_stock_le is not None:
            raise ValueError('Ce lot est déjà entré en stock.')
        if lot.job_clos_le is None:
            raise ValueError("Le job n'est pas encore terminé dans la pesée : entrée en stock impossible.")
        lot.entree_stock_le = timezone.now()
        lot.entree_stock_par = (
            utilisateur.get_username() if getattr(utilisateur, 'is_authenticated', False) else '')[:150]
        lot.save(update_fields=['entree_stock_le', 'entree_stock_par'])
    return lot


def destocker(lot, palette_ids=None, motif='', utilisateur=None):
    """Sort les bobines encore en stock d'un lot (toutes, ou seulement certaines palettes).

    Retourne le mouvement de sortie. Lève ValueError s'il n'y a rien à sortir
    ou si le lot n'est pas encore entré en stock.
    """
    if not ProduitFiniLot.objects.filter(pk=lot.pk, entree_stock_le__isnull=False).exists():
        raise ValueError("Ce lot n'est pas encore entré en stock.")
    with transaction.atomic():
        qs = (ProduitFiniBobine.objects
              .select_for_update()
              .select_related('palette')
              .filter(palette__lot=lot, date_sortie__isnull=True))
        if palette_ids:
            qs = qs.filter(palette_id__in=palette_ids)
        bobines = list(qs)
        if not bobines:
            raise ValueError('Rien à déstocker : tout est déjà sorti ou aucune palette choisie.')
        palettes = sorted({b.palette.numero_palette for b in bobines})
        mouvement = ProduitFiniMouvement.objects.create(
            lot=lot, type='SORTIE', nb_bobines=len(bobines),
            poids_kg=round(sum(b.poids_kg for b in bobines), 3),
            palettes_libelle=', '.join(palettes)[:500],
            date=timezone.now(), motif=_norm(motif)[:200],
            utilisateur=utilisateur if getattr(utilisateur, 'is_authenticated', False) else None)
        ProduitFiniBobine.objects.filter(pk__in=[b.pk for b in bobines]).update(
            date_sortie=mouvement.date, mouvement_sortie=mouvement)
    return mouvement


def annuler_mouvement(mouvement, motif='', utilisateur=None):
    """Annule une sortie : les bobines redeviennent en stock. Une entrée ne s'annule pas."""
    with transaction.atomic():
        mv = ProduitFiniMouvement.objects.select_for_update().get(pk=mouvement.pk)
        if mv.annule:
            raise ValueError('Ce mouvement est déjà annulé.')
        if mv.type != 'SORTIE':
            raise ValueError('Une entrée de pesée ne s’annule pas (traçabilité).')
        ProduitFiniBobine.objects.filter(mouvement_sortie=mv).update(
            date_sortie=None, mouvement_sortie=None)
        mv.annule = True
        mv.motif_annulation = (_norm(motif) or f'Annulé le {datetime.now():%d/%m/%Y %H:%M}')[:200]
        mv.save(update_fields=['annule', 'motif_annulation'])
    return mv
