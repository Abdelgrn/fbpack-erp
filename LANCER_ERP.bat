@echo off
title Serveur FB PACK ERP
color 0E

echo =======================================================
echo     BIENVENUE SUR L'ERP FB PACK (Version de Test)
echo =======================================================
echo.
echo 1. Verification et installation des pre-requis...
python -m pip install django pillow openpyxl --quiet

echo 2. Demarrage du serveur local...
echo.
echo /!\ NE FERMEZ PAS CETTE FENETRE NOIRE PENDANT LE TEST /!\
echo.

:: Ouvre automatiquement le navigateur web
start http://127.0.0.1:8000

:: Lance le serveur Django
python manage.py runserver

pause