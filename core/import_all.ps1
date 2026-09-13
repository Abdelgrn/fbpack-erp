Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 IMPORT AUTOMATIQUE DE TOUS LES FICHIERS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier que les fichiers existent
$fichiers = @(
    @{Path="donnees/outillage.xlsx"; Type="TOOLS"},
    @{Path="donnees/production.xlsx"; Type="SPECIAL_PROD"},
    @{Path="donnees/encre.xlsx"; Type="CONSOMMATION"}
)

foreach ($fichier in $fichiers) {
    if (Test-Path $fichier.Path) {
        Write-Host "✅ Fichier trouvé: $($fichier.Path)" -ForegroundColor Green
    } else {
        Write-Host "❌ Fichier manquant: $($fichier.Path)" -ForegroundColor Red
    }
}

Write-Host ""
Read-Host "Appuyez sur Entrée pour continuer"
Write-Host ""

# Import
Write-Host "📥 Import de l'outillage..." -ForegroundColor Cyan
python manage.py import_excel --file donnees/outillage.xlsx --type TOOLS
Write-Host ""

Write-Host "📥 Import de la production..." -ForegroundColor Cyan
python manage.py import_excel --file donnees/production.xlsx --type SPECIAL_PROD
Write-Host ""

Write-Host "📥 Import de l'encre..." -ForegroundColor Cyan
python manage.py import_excel --file donnees/encre.xlsx --type CONSOMMATION
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ TOUS LES IMPORTS SONT TERMINÉS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Appuyez sur Entrée pour fermer"