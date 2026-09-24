import openpyxl
import json
import traceback
import os
import re
import base64
import urllib.request
import urllib.error
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db.models import Sum, Q, F
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User

from ..models import (
    Material, Supplier, ConsommationEncre, StockLocation, StockLot, StockMovement,
    DemandeAchat, BonCommande, LigneBonCommande, StockSeuil, Client, Machine, ProductionOrder
)
from ..forms import MaterialForm, SupplierForm, ConsommationEncreForm
from .helpers import highlight_search

# ===========================================================================
# --- STOCKS ---
# ===========================================================================

@login_required
def stock_view(request):
    materials = Material.objects.all()
    suppliers = Supplier.objects.all()
    consos = ConsommationEncre.objects.all().order_by('-date')
    return render(request, ['stock_list.html', 'stock/stock_advanced.html'], {
        'materials': materials,
        'suppliers': suppliers,
        'consos': consos
    })


@login_required
def add_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Matière ajoutée avec succès !')
            return redirect('stock_advanced')
    else:
        form = MaterialForm()
    suppliers = Supplier.objects.all()
    return render(request, 'stock/material_form.html', {
        'form': form, 'suppliers': suppliers,
        'title': 'Nouvelle Matière Première', 'btn_label': 'Ajouter la Matière',
    })


@login_required
def edit_material(request, id):
    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Matière "{material.name}" modifiée !')
            return redirect('stock_advanced')
    else:
        form = MaterialForm(instance=material)
    suppliers = Supplier.objects.all()
    return render(request, 'stock/material_form.html', {
        'form': form, 'material': material, 'suppliers': suppliers,
        'title': f'Modifier : {material.name}', 'btn_label': 'Enregistrer les modifications',
    })


@login_required
def delete_material(request, id):
    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        nom = material.name
        material.delete()
        messages.success(request, f'🗑️ Matière "{nom}" supprimée.')
    return redirect('stock_advanced')


@login_required
def bulk_delete_materials(request):
    if request.method == 'POST':
        try:
            ids = []
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                ids = data.get('ids', [])
            else:
                ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
            
            if ids:
                materials = Material.objects.filter(id__in=ids)
                count = materials.count()
                materials.delete()
                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'status': 'success', 'message': f'🗑️ {count} matière(s) supprimée(s) avec succès.'})
                
                messages.success(request, f'🗑️ {count} matière(s) supprimée(s) avec succès.')
            else:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'status': 'error', 'message': 'Aucune sélection reçue.'})
                messages.warning(request, 'Aucun élément sélectionné.')
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': f'Erreur : {str(e)}'})
            messages.error(request, f'Erreur lors de la suppression multiple : {str(e)}')
            
    return redirect('stock_advanced')


@login_required
def bulk_delete_movements(request):
    if request.method == 'POST':
        try:
            ids = []
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                ids = data.get('ids', [])
            else:
                ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
            
            if ids:
                mouvements = StockMovement.objects.filter(id__in=ids)
                count = mouvements.count()
                mouvements.delete()
                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'status': 'success', 'message': f'🗑️ {count} mouvement(s) supprimé(s) avec succès.'})
                
                messages.success(request, f'🗑️ {count} mouvement(s) supprimé(s) avec succès.')
            else:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'status': 'error', 'message': 'Aucune sélection reçue.'})
                messages.warning(request, 'Aucun élément sélectionné.')
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': f'Erreur : {str(e)}'})
            messages.error(request, f'Erreur lors de la suppression multiple : {str(e)}')
            
    return redirect('stock_advanced')


@login_required
def clear_all_stock(request):
    if request.method == 'POST':
        try:
            StockMovement.objects.all().delete()
            StockLot.objects.all().delete()
            count, _ = Material.objects.all().delete()
            messages.success(request, f"⚠️ Tout le stock a été vidé ({count} matières supprimées).")
        except Exception as e:
            messages.error(request, f"Erreur lors de la vidange : {e}")
    return redirect('stock_advanced')


@login_required
def add_supplier(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            contact_noms = request.POST.getlist('contact_nom[]')
            contact_postes = request.POST.getlist('contact_poste[]')
            contact_telephones = request.POST.getlist('contact_telephone[]')
            contact_emails = request.POST.getlist('contact_email[]')
            try:
                from core.models import SupplierContact
                for i in range(len(contact_noms)):
                    nom = contact_noms[i].strip() if i < len(contact_noms) else ''
                    if nom:
                        SupplierContact.objects.create(
                            supplier=supplier,
                            nom=nom,
                            poste=contact_postes[i].strip() if i < len(contact_postes) else '',
                            telephone=contact_telephones[i].strip() if i < len(contact_telephones) else '',
                            email=contact_emails[i].strip() if i < len(contact_emails) else ''
                        )
            except Exception:
                pass
            messages.success(request, '✅ Fournisseur ajouté avec succès !')
            return redirect('stock_advanced')
    else:
        form = SupplierForm()
    return render(request, 'stock/supplier_form.html', {
        'form': form, 'title': 'Nouveau Fournisseur', 'btn_label': 'Ajouter le Fournisseur',
    })


@login_required
def edit_supplier(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Fournisseur "{supplier.name}" modifié !')
            return redirect('stock_advanced')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'stock/supplier_form.html', {
        'form': form, 'supplier': supplier,
        'title': f'Modifier : {supplier.name}', 'btn_label': 'Enregistrer les modifications',
    })


@login_required
def delete_supplier(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    if request.method == 'POST':
        nom = supplier.name
        supplier.delete()
        messages.success(request, f'🗑️ Fournisseur "{nom}" supprimé.')
    return redirect('stock_advanced')


@login_required
def add_consommation(request):
    if request.method == 'POST':
        form = ConsommationEncreForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('conso_list')
    else:
        form = ConsommationEncreForm()
    return render(request, ['stock_list.html', 'stock/stock_advanced.html'], {'form': form, 'titre': 'Nouvelle Consommation'})


@login_required
def conso_list_view(request):
    consos = ConsommationEncre.objects.all().order_by('-date')
    return render(request, ['stock_list.html', 'stock/stock_advanced.html'], {'consos': consos})


# ===========================================================================
# --- HELPERS IMPORT EXCEL ---
# ===========================================================================

def parse_date_custom(val):
    try:
        if val is None:
            return timezone.now()
        if isinstance(val, datetime):
            return val
        if isinstance(val, date) and not isinstance(val, datetime):
            return datetime.combine(val, datetime.min.time())
        if isinstance(val, (int, float)):
            try:
                from openpyxl.utils.datetime import from_excel
                return from_excel(val)
            except Exception:
                return timezone.now()
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ('none', 'null', ''):
            return timezone.now()
        formats = [
            '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%m/%d/%y', '%d/%m/%y',
            '%m/%d/%Y %H:%M', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S',
            '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y', '%d.%m.%y',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(val_str, fmt)
            except ValueError:
                continue
        return timezone.now()
    except Exception:
        return timezone.now()


def parse_float_eu(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    if not s or s.lower() in ('none', 'null', '-'):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def clean_str(val):
    if val is None:
        return ''
    s = str(val).strip()
    if s.lower() in ('none', 'null', 'nan'):
        return ''
    return s


def normalize_str(s):
    if not s:
        return ""
    s = str(s).strip()
    s = re.sub(r'[\s\-_]+$', '', s)
    s = re.sub(r'^[\s\-_]+', '', s)
    return s


def find_material_smart(code_str, produit_str):
    code_clean = normalize_str(code_str)
    produit_clean = normalize_str(produit_str)

    if code_clean:
        mat = Material.objects.filter(code__iexact=code_clean).first()
        if mat:
            return mat
        code_alphanumeric = re.sub(r'[^A-Za-z0-9]', '', code_clean)
        if code_alphanumeric:
            for m in Material.objects.exclude(code='').exclude(code__isnull=True):
                if re.sub(r'[^A-Za-z0-9]', '', m.code or '').upper() == code_alphanumeric.upper():
                    return m

    if produit_clean:
        mat = Material.objects.filter(name__iexact=produit_clean).first()
        if mat:
            return mat

    if produit_clean:
        for m in Material.objects.exclude(code='').exclude(code__isnull=True):
            if m.code and len(m.code) >= 3 and m.code.upper() in produit_clean.upper():
                return m
        for m in Material.objects.all():
            if m.name.upper() in produit_clean.upper() or produit_clean.upper() in m.name.upper():
                return m

    if produit_clean:
        norm_prod = re.sub(r'[^A-Za-z0-9]', '', produit_clean).upper()
        if norm_prod:
            for m in Material.objects.all():
                norm_mat_name = re.sub(r'[^A-Za-z0-9]', '', m.name).upper()
                if norm_prod == norm_mat_name or (len(norm_prod) > 5 and norm_prod in norm_mat_name) or (len(norm_mat_name) > 5 and norm_mat_name in norm_prod):
                    return m

    return None


def get_or_create_location(name, loc_type='GENERAL'):
    loc = StockLocation.objects.filter(name__iexact=name).first()
    if not loc:
        loc = StockLocation.objects.filter(name__icontains=name).first()
    if not loc:
        loc = StockLocation.objects.create(
            name=name,
            type=loc_type,
            description="Créé automatiquement par import Excel",
            is_active=True
        )
    return loc


def resolve_source_destination(machine_str):
    magasin_general = get_or_create_location('Magasin Général', 'GENERAL')
    machine_up = (machine_str or '').upper()
    if 'FLEXO' in machine_up:
        dest = get_or_create_location('Stock Tampon Flexo', 'TAMPON')
        return magasin_general, dest
    elif 'HELIO' in machine_up or 'HÉLIO' in machine_up:
        dest = get_or_create_location('Stock Tampon Helio', 'TAMPON')
        return magasin_general, dest
    else:
        return magasin_general, None


# ===========================================================================
# --- STATION D'IMPORTATION EXCEL ---
# ===========================================================================

@login_required
def import_stock_view(request):
    crm_users = User.objects.filter(is_active=True).order_by('first_name', 'username')

    if request.method != 'POST':
        return render(request, 'stock/import_stock.html', {'crm_users': crm_users})

    import_type = request.POST.get('import_type', 'MOUVEMENTS')
    excel_file = request.FILES.get('excel_file')

    if not excel_file:
        messages.error(request, "❌ Veuillez sélectionner un fichier Excel.")
        return render(request, 'stock/import_stock.html', {'crm_users': crm_users})

    details = []
    success_count = 0
    error_count = 0

    try:
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        ws = wb.worksheets[0]
        details.append(f"📄 Analyse de la feuille : « {ws.title} » ({ws.max_row} lignes détectées)")

        if import_type == 'MOUVEMENTS':
            for row_idx in range(2, ws.max_row + 1):
                raw_date = ws.cell(row=row_idx, column=1).value
                raw_machine = ws.cell(row=row_idx, column=2).value
                raw_produit = ws.cell(row=row_idx, column=3).value
                raw_quantite = ws.cell(row=row_idx, column=4).value
                raw_code = ws.cell(row=row_idx, column=5).value
                raw_notes = ws.cell(row=row_idx, column=6).value

                produit_str = clean_str(raw_produit)
                code_str = clean_str(raw_code)
                machine_str = clean_str(raw_machine)
                notes_str = clean_str(raw_notes)

                if not produit_str and not code_str and raw_quantite is None:
                    continue

                try:
                    qte_val = abs(parse_float_eu(raw_quantite))
                    if qte_val == 0:
                        details.append(f"Ligne {row_idx} : ⚠️ Ignorée (Quantité = 0)")
                        error_count += 1
                        continue

                    date_val = parse_date_custom(raw_date)

                    material = find_material_smart(code_str, produit_str)

                    if not material:
                        mat_name = (produit_str or code_str or f"Matière-Ligne-{row_idx}")[:200]
                        cat = 'INK'
                        up = mat_name.upper()
                        if any(x in up for x in ['BOPP', 'PE', 'PET', 'FILM', 'PAPIER']):
                            cat = 'FILM'
                        elif any(x in up for x in ['GLUE', 'COLLE', 'ADHES']):
                            cat = 'GLUE'
                        elif any(x in up for x in ['SOLV', 'ETHANOL', 'ETHYL', 'ACETATE', 'METHOXY', 'MELANGE']):
                            cat = 'SOLV'
                        material = Material.objects.create(
                            name=mat_name,
                            code=normalize_str(code_str),
                            category=cat,
                            quantity=0,
                            unit='kg',
                            min_threshold=50,
                            price_per_unit=0
                        )
                        details.append(f"Ligne {row_idx} : 🆕 Nouvelle matière créée « {mat_name} »")

                    machine_obj = None
                    if machine_str:
                        machine_obj = Machine.objects.filter(name__icontains=machine_str).first()

                    emplacement_source, emplacement_destination = resolve_source_destination(machine_str)

                    motif_text = "Import Excel"
                    if code_str:
                        motif_text += f" | Code: {code_str}"
                    if notes_str:
                        motif_text += f" | {notes_str}"

                    StockMovement.objects.create(
                        date=date_val,
                        type='SORTIE',
                        material=material,
                        quantite=qte_val,
                        emplacement_source=emplacement_source,
                        emplacement_destination=emplacement_destination,
                        machine=machine_obj,
                        utilisateur=request.user if request.user.is_authenticated else None,
                        motif=motif_text[:200],
                    )

                    success_count += 1
                    src_name = emplacement_source.name if emplacement_source else "—"
                    dst_name = emplacement_destination.name if emplacement_destination else "—"
                    details.append(f"Ligne {row_idx} : ✅ -{qte_val} kg « {material.name} » (Nouveau stock : {material.quantity} {material.unit}) | {src_name} → {dst_name}")

                except Exception as row_err:
                    error_count += 1
                    details.append(f"Ligne {row_idx} : ❌ Erreur technique ({str(row_err)})")

        elif import_type == 'STOCK':
            for row_idx in range(2, ws.max_row + 1):
                designation = clean_str(ws.cell(row=row_idx, column=1).value)
                if not designation:
                    continue
                code_val = clean_str(ws.cell(row=row_idx, column=2).value)
                fournisseur_name = clean_str(ws.cell(row=row_idx, column=3).value)
                category = clean_str(ws.cell(row=row_idx, column=4).value)
                quantity = ws.cell(row=row_idx, column=5).value
                unit = clean_str(ws.cell(row=row_idx, column=6).value) or 'kg'
                seuil = ws.cell(row=row_idx, column=7).value or 0
                prix = ws.cell(row=row_idx, column=8).value or 0

                cat_code = 'FILM'
                cat_up = category.upper()
                if 'ENCRE' in cat_up or 'INK' in cat_up:
                    cat_code = 'INK'
                elif 'COLLE' in cat_up or 'GLUE' in cat_up:
                    cat_code = 'GLUE'
                elif 'SOLV' in cat_up:
                    cat_code = 'SOLV'

                supplier_obj = None
                if fournisseur_name:
                    supplier_obj = Supplier.objects.filter(name__icontains=fournisseur_name).first()
                    if not supplier_obj:
                        supplier_obj = Supplier.objects.create(name=fournisseur_name, email='')
                        details.append(f"Ligne {row_idx} : 🆕 Fournisseur créé « {fournisseur_name} »")

                try:
                    mat = find_material_smart(code_val, designation)

                    if mat:
                        mat.name = designation
                        mat.code = normalize_str(code_val) or mat.code
                        mat.category = cat_code
                        mat.quantity = parse_float_eu(quantity)
                        mat.unit = unit
                        mat.min_threshold = parse_float_eu(seuil)
                        mat.price_per_unit = parse_float_eu(prix)
                        if supplier_obj:
                            mat.supplier = supplier_obj
                        mat.save()
                        created = False
                    else:
                        mat = Material.objects.create(
                            name=designation,
                            code=normalize_str(code_val),
                            category=cat_code,
                            quantity=parse_float_eu(quantity),
                            unit=unit,
                            min_threshold=parse_float_eu(seuil),
                            price_per_unit=parse_float_eu(prix),
                            supplier=supplier_obj,
                        )
                        created = True

                    success_count += 1
                    action = "Créée" if created else "Mise à jour"
                    four_txt = f" | Fournisseur: {supplier_obj.name}" if supplier_obj else ""
                    details.append(f"Ligne {row_idx} : ✅ Matière {action} « {mat.name} » avec un stock de {mat.quantity} {mat.unit}{four_txt}")
                except Exception as e:
                    error_count += 1
                    details.append(f"Ligne {row_idx} : ❌ {e}")

        msg = f"Importation terminée : {success_count} ligne(s) importée(s) avec succès, {error_count} erreur(s)."
        if success_count > 0:
            messages.success(request, f"🎉 {msg}")
        else:
            messages.warning(request, f"⚠️ {msg}")

        return render(request, 'stock/import_stock.html', {
            'success': success_count > 0,
            'message': msg,
            'details': details,
            'crm_users': crm_users,
        })

    except Exception as e:
        print("=== ERREUR CRITIQUE IMPORT EXCEL ===")
        print(traceback.format_exc())
        return render(request, 'stock/import_stock.html', {
            'success': False,
            'message': f"❌ Erreur lors de l'importation : {str(e)}",
            'details': details,
            'crm_users': crm_users,
        })


@login_required
def download_template_stock(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Stock"
    ws.append(['Designation', 'Code', 'Fournisseur', 'Categorie (Film/Encre/Colle/Solvant)', 'Quantite', 'Unite', 'Seuil_Min', 'Prix_Unitaire'])
    ws.append(['SOLVAPRINT TF EP YELLOW:JPR1', 'HSAU200019', 'SunChemical', 'Encre', 500, 'kg', 100, 1200])
    ws.append(['BOPP Transparent 20µ', 'BOPP-20-TR', 'GulfPack', 'Film', 1500, 'kg', 300, 450])
    ws.append(['SOLIPROP V AP WHITE:LT30', 'HSAN-10001', 'SunChemical', 'Encre', 1000, 'kg', 200, 950])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_stock_matieres.xlsx"'
    wb.save(response)
    return response


@login_required
def download_template_special_prod(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Prod Spéciale"
    ws.append(['Date', 'Produit', 'Support', 'Qte_Lancee', 'Lot', 'Laize', 'Client', 'Equipe', 'Machine', 'H_Debut', 'H_Fin', 'Prod_ML', 'Dec_Demarrage', 'Dec_Lisiere', 'Dec_Jonction', 'Dec_Transport', 'Prod_KG', 'Rebobinage_KG'])
    ws.append(['15/01/2025', 'Sac Lait', 'PEBD 50μ', 500, 'LOT-2025-001', 320, 'Laiterie Atlas', 'A', 'IMP-01', '08:00', '16:30', 12000, 5.2, 3.1, 1.5, 2.0, 485, 10])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_production_speciale.xlsx"'
    wb.save(response)
    return response


# ===========================================================================
# --- STOCK AVANCÉ ---
# ===========================================================================

@login_required
def stock_advanced_view(request):
    try:
        search_query = request.GET.get('q', '').strip()
        category_filter = request.GET.get('category', '')
        low_stock_only = request.GET.get('low_stock', '') == 'on'
        supplier_filter = request.GET.get('supplier', '')

        try:
            materials = Material.objects.select_related('supplier').all()
        except Exception:
            materials = Material.objects.all()

        if search_query:
            materials = materials.filter(
                Q(name__icontains=search_query) |
                Q(code__icontains=search_query) |
                Q(supplier__name__icontains=search_query)
            )
        if category_filter:
            materials = materials.filter(category=category_filter)
        if supplier_filter:
            materials = materials.filter(supplier_id=supplier_filter)

        materials = materials.order_by('name')

        if low_stock_only:
            filtered_mat = []
            for m in materials:
                try:
                    if m.is_low_stock():
                        filtered_mat.append(m)
                except Exception:
                    pass
            materials = filtered_mat

        try:
            all_materials = Material.objects.select_related('supplier').all()
        except Exception:
            all_materials = Material.objects.all()

        alertes_stock = []
        nb_ruptures = 0
        nb_critiques = 0
        nb_alertes_simples = 0

        cat_stats = {
            'FILM': {'rupture': 0, 'critique': 0, 'alerte': 0},
            'INK': {'rupture': 0, 'critique': 0, 'alerte': 0},
            'GLUE': {'rupture': 0, 'critique': 0, 'alerte': 0},
            'SOLV': {'rupture': 0, 'critique': 0, 'alerte': 0},
        }

        for m in all_materials:
            is_low = False
            try:
                is_low = m.is_low_stock()
            except Exception:
                qty = float(m.quantity or 0)
                thresh = float(getattr(m, 'min_threshold', 0) or 0)
                is_low = qty <= thresh

            if is_low:
                qty = float(m.quantity or 0)
                thresh = float(getattr(m, 'min_threshold', 0) or 0)
                pct = round((qty / thresh) * 100, 1) if thresh > 0 else 0

                if qty <= 0:
                    niveau = 'RUPTURE'
                    icone = '🔴'
                    nb_ruptures += 1
                    if m.category in cat_stats:
                        cat_stats[m.category]['rupture'] += 1
                elif pct < 50:
                    niveau = 'CRITIQUE'
                    icone = '🟠'
                    nb_critiques += 1
                    if m.category in cat_stats:
                        cat_stats[m.category]['critique'] += 1
                else:
                    niveau = 'ALERTE'
                    icone = '🟡'
                    nb_alertes_simples += 1
                    if m.category in cat_stats:
                        cat_stats[m.category]['alerte'] += 1

                cat_lbl = m.category
                try:
                    cat_lbl = m.get_category_display()
                except Exception:
                    pass

                alertes_stock.append({
                    'id': m.id, 'name': m.name, 'category': m.category,
                    'cat_label': cat_lbl,
                    'quantity': qty, 'unit': m.unit, 'min_threshold': thresh,
                    'supplier': m.supplier.name if m.supplier else '—',
                    'pct': min(pct, 100), 'niveau': niveau, 'icone': icone,
                })

        ordre_priorite = {'RUPTURE': 0, 'CRITIQUE': 1, 'ALERTE': 2}
        alertes_stock.sort(key=lambda x: (ordre_priorite.get(x['niveau'], 3), -x['pct']))

        top_alertes = alertes_stock[:10]
        top_alertes_noms = [a['name'][:25] + '...' if len(a['name']) > 25 else a['name'] for a in top_alertes]
        top_alertes_stock = [a['quantity'] for a in top_alertes]
        top_alertes_seuil = [a['min_threshold'] for a in top_alertes]
        top_alertes_couleurs = []
        for a in top_alertes:
            if a['niveau'] == 'RUPTURE':
                top_alertes_couleurs.append('#dc2626')
            elif a['niveau'] == 'CRITIQUE':
                top_alertes_couleurs.append('#ea580c')
            else:
                top_alertes_couleurs.append('#ca8a04')

        cat_labels = ['Film/Papier', 'Encre', 'Colle', 'Solvant']
        cat_rupture = [cat_stats['FILM']['rupture'], cat_stats['INK']['rupture'], cat_stats['GLUE']['rupture'], cat_stats['SOLV']['rupture']]
        cat_critique = [cat_stats['FILM']['critique'], cat_stats['INK']['critique'], cat_stats['GLUE']['critique'], cat_stats['SOLV']['critique']]
        cat_alerte = [cat_stats['FILM']['alerte'], cat_stats['INK']['alerte'], cat_stats['GLUE']['alerte'], cat_stats['SOLV']['alerte']]

        previsions = []
        for m in all_materials:
            try:
                seuil = StockSeuil.objects.filter(material=m).first()
                if seuil and getattr(seuil, 'consommation_journaliere_moy', 0) > 0:
                    jours = seuil.jours_de_stock
                    if jours <= 15:
                        previsions.append({
                            'material': m.name,
                            'stock_actuel': m.quantity or 0,
                            'conso_jour': seuil.consommation_journaliere_moy,
                            'jours_restants': jours,
                            'date_rupture': seuil.date_rupture_prevue.strftime('%d/%m/%Y') if getattr(seuil, 'date_rupture_prevue', None) else '—',
                            'critique': jours <= 7,
                        })
            except Exception:
                pass
        previsions.sort(key=lambda x: x['jours_restants'])

        try:
            lots = StockLot.objects.all().order_by('-id')[:100]
        except Exception:
            lots = []

        try:
            lots_bloques = StockLot.objects.filter(statut='BLOQUE').count()
            lots_attente = StockLot.objects.filter(statut='EN_ATTENTE').count()
        except Exception:
            lots_bloques = 0
            lots_attente = 0

        try:
            mouvements = StockMovement.objects.select_related(
                'material', 'lot', 'emplacement_source', 'emplacement_destination',
                'machine', 'utilisateur'
            ).all().order_by('-id')[:100]
        except Exception:
            mouvements = []

        try:
            locations = StockLocation.objects.all()
        except Exception:
            locations = []

        try:
            suppliers = Supplier.objects.all().order_by('name')
        except Exception:
            suppliers = []

        try:
            demandes = DemandeAchat.objects.all().order_by('-id')[:50]
            da_en_attente = DemandeAchat.objects.filter(statut='SOUMISE').count()
        except Exception:
            demandes = []
            da_en_attente = 0

        try:
            bons_commande = BonCommande.objects.all().order_by('-id')[:50]
        except Exception:
            bons_commande = []

        try:
            consos = ConsommationEncre.objects.all().order_by('-date')[:50]
        except Exception:
            consos = []

        valeur_stock_total = 0
        for m in all_materials:
            try:
                q = float(m.quantity or 0)
                p = float(getattr(m, 'price_per_unit', 0) or 0)
                valeur_stock_total += q * p
            except Exception:
                pass

        context = {
            'search_query': search_query, 'category_filter': category_filter,
            'low_stock_only': low_stock_only, 'supplier_filter': supplier_filter,
            'categories': getattr(Material, 'CAT_CHOICES', []), 'materials': materials,
            'total_matieres': Material.objects.count(), 'suppliers': suppliers,
            'alertes_stock': alertes_stock, 'nb_alertes': len(alertes_stock),
            'nb_ruptures': nb_ruptures, 'nb_critiques': nb_critiques,
            'nb_alertes_simples': nb_alertes_simples,
            'top_alertes_noms': json.dumps(top_alertes_noms),
            'top_alertes_stock': json.dumps(top_alertes_stock),
            'top_alertes_seuil': json.dumps(top_alertes_seuil),
            'top_alertes_couleurs': json.dumps(top_alertes_couleurs),
            'cat_labels_json': json.dumps(cat_labels),
            'cat_rupture_json': json.dumps(cat_rupture),
            'cat_critique_json': json.dumps(cat_critique),
            'cat_alerte_json': json.dumps(cat_alerte),
            'previsions': previsions[:6],
            'lots': lots, 'lots_bloques': lots_bloques, 'lots_attente': lots_attente,
            'mouvements': mouvements, 'locations': locations,
            'demandes': demandes, 'da_en_attente': da_en_attente,
            'bons_commande': bons_commande, 'consos': consos,
            'valeur_stock_total': valeur_stock_total,
        }

        template_candidates = [
            'stock/stock_advanced.html',
            'stock_advanced.html',
            'stock_list.html'
        ]
        return render(request, template_candidates, context)

    except Exception as e:
        print("=== ERREUR CRITIQUE STOCK ADVANCED ===")
        print(traceback.format_exc())
        messages.error(request, f"❌ Erreur module Stock : {type(e).__name__} - {str(e)}")
        return redirect('dashboard')


@login_required
def material_search_api(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return JsonResponse([], safe=False)

    materials = Material.objects.filter(
        Q(name__icontains=query) | Q(code__icontains=query) | Q(category__icontains=query) | Q(supplier__name__icontains=query)
    ).select_related('supplier').order_by('name')[:30]

    results = []
    for m in materials:
        is_low = False
        try:
            is_low = m.is_low_stock()
        except Exception:
            pass
        cat_lbl = m.category
        try:
            cat_lbl = m.get_category_display()
        except Exception:
            pass
        results.append({
            'id': m.id, 'name': m.name,
            'name_html': highlight_search(m.name, query),
            'category': cat_lbl,
            'quantity': m.quantity or 0, 'unit': m.unit,
            'min_threshold': m.min_threshold or 0,
            'supplier': m.supplier.name if m.supplier else '—',
            'is_low_stock': is_low,
            'price': float(getattr(m, 'price_per_unit', 0) or 0),
        })
    return JsonResponse({'query': query, 'count': len(results), 'results': results})


@login_required
def export_search_results(request):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    materials = Material.objects.select_related('supplier').all()
    if query:
        materials = materials.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(supplier__name__icontains=query))
    if category:
        materials = materials.filter(category=category)
    materials = materials.order_by('name')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock Matières"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")
    alert_fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    headers = ['Désignation', 'Code', 'Catégorie', 'Stock Actuel', 'Unité', 'Seuil Min', 'Fournisseur', 'Prix/Unité', 'Valeur Stock', 'État']
    ws.append(headers)
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border
    for row_num, m in enumerate(materials, 2):
        q = float(m.quantity or 0)
        p = float(getattr(m, 'price_per_unit', 0) or 0)
        valeur = q * p
        is_low = False
        try:
            is_low = m.is_low_stock()
        except Exception:
            pass
        etat = "⚠️ ALERTE" if is_low else "✓ OK"
        cat_lbl = m.category
        try:
            cat_lbl = m.get_category_display()
        except Exception:
            pass
        row_data = [m.name, getattr(m, 'code', '') or '', cat_lbl, q, m.unit, m.min_threshold or 0, m.supplier.name if m.supplier else '', p, round(valeur, 2), etat]
        ws.append(row_data)
        for col_num in range(1, len(row_data) + 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.border = thin_border
            if is_low:
                cell.fill = alert_fill
    column_widths = [40, 18, 15, 15, 10, 12, 25, 12, 15, 12]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
    filename = f"stock_matieres_{query if query else 'all'}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def location_list(request):
    locations = StockLocation.objects.all()
    return render(request, ['stock/stock_advanced.html', 'stock_advanced.html'], {'locations': locations})


@login_required
def location_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        type_loc = request.POST.get('type', 'GENERAL')
        desc = request.POST.get('description', '')
        if name:
            StockLocation.objects.create(name=name, type=type_loc, description=desc)
            messages.success(request, f"Emplacement « {name} » créé.")
    return redirect('stock_advanced')


@login_required
def location_delete(request, id):
    loc = get_object_or_404(StockLocation, id=id)
    if request.method == 'POST':
        loc.delete()
        messages.success(request, "Emplacement supprimé.")
    return redirect('stock_advanced')


@login_required
def lot_list(request):
    lots = StockLot.objects.all()
    return render(request, ['stock/stock_advanced.html', 'stock_advanced.html'], {'lots': lots})


@login_required
def lot_add(request):
    if request.method == 'POST':
        try:
            material_id = request.POST.get('material')
            material_name_free = request.POST.get('material_name_free', '').strip()
            category = request.POST.get('category')
            numero_lot = request.POST.get('numero_lot', '').strip()
            date_reception = request.POST.get('date_reception')
            fournisseur_id = request.POST.get('fournisseur') or None
            emplacement_id = request.POST.get('emplacement') or None
            quantite = float(request.POST.get('quantite_initiale', 0))
            prix = float(request.POST.get('prix_unitaire', 0))
            statut = request.POST.get('statut', 'EN_ATTENTE')
            notes = request.POST.get('notes', '')

            if material_id:
                material = get_object_or_404(Material, id=material_id)
            elif material_name_free:
                material, _ = Material.objects.get_or_create(
                    name=material_name_free,
                    defaults={'category': category or 'INK', 'quantity': 0, 'min_threshold': 100}
                )
            else:
                messages.error(request, "Veuillez sélectionner ou saisir un nom de matière.")
                return redirect('stock_advanced')

            fournisseur = Supplier.objects.filter(id=fournisseur_id).first() if fournisseur_id else None
            emplacement = StockLocation.objects.filter(id=emplacement_id).first() if emplacement_id else None
            lot = StockLot.objects.create(
                material=material, numero_lot=numero_lot,
                date_reception=date_reception, fournisseur=fournisseur,
                emplacement=emplacement, quantite_initiale=quantite,
                quantite_restante=quantite, prix_unitaire=prix,
                statut=statut, notes=notes, created_by=request.user
            )
            if request.FILES.get('certificat_qualite'):
                lot.certificat_qualite = request.FILES['certificat_qualite']
                lot.save()
            if statut == 'CONFORME':
                StockMovement.objects.create(
                    type='ENTREE', material=material, lot=lot,
                    quantite=quantite, emplacement_destination=emplacement,
                    utilisateur=request.user, motif=f"Réception lot {numero_lot}"
                )
            messages.success(request, f"Lot {numero_lot} créé.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
    return redirect('stock_advanced')


@login_required
def lot_valider(request, id):
    author_lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        ancien_statut = author_lot.statut
        author_lot.statut = 'CONFORME'
        author_lot.save()
        if ancien_statut != 'CONFORME':
            StockMovement.objects.create(
                type='ENTREE', material=author_lot.material, lot=author_lot,
                quantite=author_lot.quantite_restante,
                emplacement_destination=author_lot.emplacement,
                utilisateur=request.user, motif=f"Validation lot {author_lot.numero_lot}"
            )
        messages.success(request, f"Lot {author_lot.numero_lot} validé.")
    return redirect('stock_advanced')


@login_required
def lot_bloquer(request, id):
    lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        lot.statut = 'BLOQUE'
        lot.save()
        messages.warning(request, f"Lot {lot.numero_lot} bloqué.")
    return redirect('stock_advanced')


@login_required
def lot_detail(request, id):
    lot = get_object_or_404(StockLot, id=id)
    try:
        mouvements = lot.mouvements.select_related('utilisateur', 'machine', 'of').order_by('-date')
    except Exception:
        mouvements = []
    return render(request, ['stock/lot_detail.html', 'lot_detail.html'], {'lot': lot, 'mouvements': mouvements})


@login_required
def mouvement_add(request):
    if request.method == 'POST':
        try:
            material = get_object_or_404(Material, id=request.POST.get('material'))
            type_mvt = request.POST.get('type')
            quantite = float(request.POST.get('quantite', 0))
            lot_id = request.POST.get('lot') or None
            src_id = request.POST.get('emplacement_source') or None
            dst_id = request.POST.get('emplacement_destination') or None
            of_id = request.POST.get('of') or None
            machine_id = request.POST.get('machine') or None
            motif = request.POST.get('motif', '')
            lot = StockLot.objects.filter(id=lot_id).first() if lot_id else None
            src = StockLocation.objects.filter(id=src_id).first() if src_id else None
            dst = StockLocation.objects.filter(id=dst_id).first() if dst_id else None
            of_obj = ProductionOrder.objects.filter(id=of_id).first() if of_id else None
            machine_obj = Machine.objects.filter(id=machine_id).first() if machine_id else None
            StockMovement.objects.create(
                type=type_mvt, material=material, lot=lot,
                quantite=quantite, emplacement_source=src,
                emplacement_destination=dst, of=of_obj,
                machine=machine_obj, utilisateur=request.user, motif=motif,
            )
            messages.success(request, "Mouvement enregistré.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
    return redirect('stock_advanced')


@login_required
def da_add(request):
    if request.method == 'POST':
        try:
            import random, string
            ref = 'DA-' + ''.join(random.choices(string.digits, k=6))
            material = get_object_or_404(Material, id=request.POST.get('material'))
            DemandeAchat.objects.create(
                reference=ref, material=material,
                quantite_demandee=float(request.POST.get('quantite_demandee', 0)),
                motif=request.POST.get('motif', ''),
                urgence=request.POST.get('urgence', 'NORMALE'),
                statut='SOUMISE', demandeur=request.user,
                date_besoin=request.POST.get('date_besoin') or None,
            )
            messages.success(request, "Demande d'achat créée.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
    return redirect('stock_advanced')


@login_required
def da_valider(request, id):
    da = get_object_or_404(DemandeAchat, id=id)
    if request.method == 'POST':
        da.statut = 'VALIDEE'
        da.valideur = request.user
        da.date_validation = timezone.now().date()
        da.save()
        messages.success(request, f"DA {da.reference} validée.")
    return redirect('stock_advanced')


@login_required
def da_refuser(request, id):
    da = get_object_or_404(DemandeAchat, id=id)
    if request.method == 'POST':
        da.statut = 'REFUSEE'
        da.save()
        messages.warning(request, f"DA {da.reference} refusée.")
    return redirect('stock_advanced')


@login_required
def bc_add(request):
    if request.method == 'POST':
        try:
            import random, string
            ref = 'BC-' + ''.join(random.choices(string.digits, k=6))
            fournisseur = get_object_or_404(Supplier, id=request.POST.get('fournisseur'))
            bc = BonCommande.objects.create(
                reference=ref, fournisseur=fournisseur, statut='BROUILLON',
                date_livraison_prevue=request.POST.get('date_livraison_prevue') or None,
                notes=request.POST.get('notes', ''), cree_par=request.user,
            )
            idx = 1
            total = 0
            while request.POST.get(f'material_{idx}'):
                mat = Material.objects.filter(id=request.POST.get(f'material_{idx}')).first()
                if mat:
                    qte = float(request.POST.get(f'quantite_{idx}', 0))
                    prix = float(request.POST.get(f'prix_{idx}', 0))
                    LigneBonCommande.objects.create(
                        bon_commande=bc, material=mat,
                        quantite_commandee=qte, prix_unitaire=prix
                    )
                    total += qte * prix
                idx += 1
            bc.montant_total = total
            bc.save()
            messages.success(request, f"Bon de commande {bc.reference} créé.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
    return redirect('stock_advanced')


@login_required
def bc_envoyer(request, id):
    bc = get_object_or_404(BonCommande, id=id)
    if request.method == 'POST':
        bc.statut = 'ENVOYE'
        bc.save()
        messages.success(request, f"BC {bc.reference} marqué comme envoyé.")
    return redirect('stock_advanced')


@login_required
def bc_reception(request, id):
    bc = get_object_or_404(BonCommande, id=id)
    if request.method == 'POST':
        bc.statut = 'RECU_TOTAL'
        bc.date_livraison_reelle = timezone.now().date()
        bc.save()
        for ligne in bc.lignes.all():
            import random, string
            num_lot = f"LOT-{bc.reference}-{''.join(random.choices(string.digits, k=4))}"
            StockLot.objects.create(
                material=ligne.material, numero_lot=num_lot,
                date_reception=timezone.now().date(),
                fournisseur=bc.fournisseur,
                quantite_initiale=ligne.quantite_commandee,
                quantite_restante=ligne.quantite_commandee,
                prix_unitaire=ligne.prix_unitaire,
                statut='EN_ATTENTE', created_by=request.user,
            )
            ligne.quantite_recue = ligne.quantite_commandee
            ligne.save()
        messages.success(request, f"BC {bc.reference} réceptionné.")
    return redirect('stock_advanced')


@login_required
def seuil_update(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    if request.method == 'POST':
        seuil, _ = StockSeuil.objects.get_or_create(
            material=material,
            defaults={'consommation_journaliere_moy': 0, 'delai_fournisseur_jours': 7}
        )
        seuil.consommation_journaliere_moy = float(request.POST.get('conso_jour', 0))
        seuil.delai_fournisseur_jours = int(request.POST.get('delai_jours', 7))
        seuil.stock_securite_jours = int(request.POST.get('securite_jours', 3))
        seuil.save()
        messages.success(request, f"Seuil mis à jour pour {material.name}.")
    return redirect('stock_advanced')


@login_required
def stock_dashboard_data(request):
    critiques = []
    for m in Material.objects.all():
        try:
            if m.is_low_stock():
                critiques.append({'name': m.name, 'stock': m.quantity or 0, 'seuil': m.min_threshold or 0})
        except Exception:
            pass
    return JsonResponse({'critiques': critiques})


# ===========================================================================
# --- API SCANNER IA ÉTIQUETTE ---
# ===========================================================================

@login_required
def scan_label_ai(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Méthode POST requise.'}, status=400)

    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'status': 'error', 'message': 'Aucune image fournie.'}, status=400)

    api_key = os.environ.get('GEMINI_API_KEY', '').strip().replace('"', '').replace("'", "")
    if not api_key:
        return JsonResponse({'status': 'error', 'message': 'Variable GEMINI_API_KEY manquante sur Render.'}, status=400)

    try:
        image_bytes = image_file.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        mime_type = image_file.content_type or 'image/jpeg'

        prompt = """
Tu es un expert en étiquettes de matières premières d'emballage souple (Films BOPP/PE et Encres).
Analyse l'étiquette et retourne UNIQUEMENT un objet JSON strict :
{
  "fournisseur": "string ou null",
  "material_name": "string ou null",
  "category": "FILM" ou "INK" ou "GLUE" ou "SOLV",
  "numero_lot": "string ou null",
  "poids_net": number ou null,
  "laize_width": number ou null,
  "longueur_length": number ou null,
  "date_expiration": "YYYY-MM-DD ou null"
}
RÈGLES ABSOLUES :
1. POIDS_NET (kg) : Cherche "WEIGHT (Kgs.)" ou "NET WEIGHT". Ne prends JAMAIS la LENGTH !
2. LONGUEUR_LENGTH (mètres) : Cherche "LENGTH (mt)" ou "m".
3. LAIZE_WIDTH (mm) : Cherche "WIDTH (mm)".
4. MATERIAL_NAME : Code produit complet.
5. CATEGORY : FILM, INK, GLUE ou SOLV.
Réponds UNIQUEMENT avec le JSON, rien d'autre.
"""
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}}
                ]
            }]
        }

        candidate_models = [
            "models/gemini-flash-latest",
            "models/gemini-flash-lite-latest",
            "models/gemini-1.5-flash"
        ]

        last_error = None
        for target_model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    res_body = json.loads(resp.read().decode('utf-8'))
                    text_response = res_body['candidates'][0]['content']['parts'][0]['text'].strip()
                    text_clean = re.sub(r'```json\s*|\s*```', '', text_response).strip().strip('`').strip()
                    parsed_json = json.loads(text_clean)

                    for key in ['poids_net', 'laize_width', 'longueur_length']:
                        val = parsed_json.get(key)
                        if val is not None and isinstance(val, str):
                            try:
                                parsed_json[key] = float(val.replace(',', '').replace(' ', ''))
                            except ValueError:
                                parsed_json[key] = None

                    if not parsed_json.get('category') or parsed_json.get('category') not in ['FILM', 'INK', 'GLUE', 'SOLV']:
                        name_up = (parsed_json.get('material_name') or '').upper()
                        if any(x in name_up for x in ['BOPP', 'PE', 'PET', 'FILM', 'KRAFT', 'PAPER']):
                            parsed_json['category'] = 'FILM'
                        elif any(x in name_up for x in ['SOLIPROP', 'SOLVAPRINT', 'SOLIMAX', 'ROTOFLEXO', 'SOLVARES', 'BLACK', 'MAGENTA', 'YELLOW', 'CYAN', 'WHITE', 'ENCRE', 'INK']):
                            parsed_json['category'] = 'INK'
                        elif any(x in name_up for x in ['GLUE', 'COLLE', 'ADHESIVE']):
                            parsed_json['category'] = 'GLUE'
                        else:
                            parsed_json['category'] = 'SOLV'

                    return JsonResponse({
                        'status': 'success',
                        'data': parsed_json,
                        'model_used': target_model
                    })
            except urllib.error.HTTPError as e:
                last_error = e.read().decode('utf-8') if hasattr(e, 'read') else str(e)
                continue
            except Exception as e:
                last_error = str(e)
                continue

        return JsonResponse({'status': 'error', 'message': f"Erreur : {last_error}"}, status=503)

    except Exception as e:
        print("=== ERREUR SCANNER IA ===")
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)