from django.core.management.base import BaseCommand
import pandas as pd


class Command(BaseCommand):
    help = 'Importer des donnees depuis un fichier Excel'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True)
        parser.add_argument('--type', type=str, required=True,
                          choices=['TOOLS', 'SPECIAL_PROD', 'CONSOMMATION'])

    def handle(self, *args, **options):
        file_path = options['file']
        data_type = options['type']

        self.stdout.write(f"Import de {file_path} (type: {data_type})...")

        try:
            # Lire avec pandas (gere les NaT automatiquement)
            df = pd.read_excel(file_path)

            # Remplacer tous les NaT et NaN par None
            df = df.where(pd.notnull(df), None)

            self.stdout.write(f"Colonnes trouvees: {list(df.columns)}")
            self.stdout.write(f"Nombre de lignes: {len(df)}")
            self.stdout.write("")

            success_count = 0
            for idx, row in df.iterrows():
                data = {}
                for col in df.columns:
                    val = row[col]
                    # Convertir les types pandas en types Python natifs
                    if val is None:
                        data[col] = None
                    elif hasattr(val, 'item'):
                        data[col] = val.item()
                    else:
                        data[col] = val
                
                self.stdout.write(f"  Ligne {idx+2}: {data}")
                success_count += 1

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"Termine! {success_count} lignes lues avec succes!"
            ))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Fichier non trouve: {file_path}'))
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Erreur: {e}'))
            self.stdout.write(traceback.format_exc())
