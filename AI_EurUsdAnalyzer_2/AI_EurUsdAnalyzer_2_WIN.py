# Cette version de AI_EurUsdAnalyzer uploade des fichiers pdfs dans le contexte gemini distant
# et ne fait des analyses que sur les screenshots qui sont placés au fur et à mesure dans le répertoire manual_screenshots
# 1. Assurez-vous d'avoir installé les packages via pip :
# pip install pillow requests google-generativeai tenacity

import requests
import time
import os
import io
from PIL import Image
import shutil
# Selenium et webdriver-manager ne sont plus nécessaires pour cette version
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import WebDriverException, TimeoutException as SeleniumTimeoutException
import glob
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import re

# --- CRUCIAL: Clear potential proxy settings ---
proxy_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
for var_name in proxy_vars_to_clear:
    if var_name in os.environ:
        print(f"Clearing environment variable: {var_name}")
        del os.environ[var_name]
os.environ['NO_PROXY'] = '*'
# --- END CRUCIAL SECTION ---

# --- API KEY MANAGEMENT ---
gemini_api_key = "VOTRE_CLE_API_GEMINI_ICI" # REMPLACEZ PAR VOTRE VRAIE CLÉ

if not gemini_api_key or "VOTRE_CLE_API_GEMINI_ICI" in gemini_api_key or "AIzaSyB" not in gemini_api_key:
    raise ValueError("GEMINI_API_KEY n'est pas définie ou est toujours la valeur par défaut. Veuillez définir votre clé API réelle.")
# --- END API KEY MANAGEMENT ---

# MODIFIÉ: Chemins pour les fichiers
chemin_base = os.getcwd()
chemin_pdf = os.path.join(chemin_base, "pdf_files")
chemin_manual_screenshots = os.path.join(chemin_base, "manual_screenshots")
chemin_processed_screenshots = os.path.join(chemin_base, "processed_screenshots") # Pour déplacer les images traitées

os.makedirs(chemin_pdf, exist_ok=True)
os.makedirs(chemin_manual_screenshots, exist_ok=True)
os.makedirs(chemin_processed_screenshots, exist_ok=True)

# Configure Gemini
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise

def trouver_pdfs(): # MODIFIÉ pour retourner une liste de PDFs
    if not os.path.exists(chemin_pdf):
        print(f"PDF directory not found: {chemin_pdf}")
        return [] # Retourne une liste vide
    pdfs_paths = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
    if pdfs_paths:
        print(f"Found {len(pdfs_paths)} PDF(s): {', '.join([os.path.basename(p) for p in pdfs_paths])}")
    else:
        print(f"No PDF found in {chemin_pdf}")
    return pdfs_paths # Retourne la liste des chemins des PDFs

def initialiser_session_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # ou pro
    # Historique initial pour donner le contexte global
    initial_prompt = """Vous êtes un expert en analyse technique ICT (Inner Circle Trader).
    Votre mission est d'analyser les documents PDF de référence (s'ils sont fournis au début)
    et les captures d'écran de graphiques financiers que je vais vous envoyer.
    Pour chaque capture d'écran, fournissez une analyse ICT détaillée en tenant compte des PDF de référence
    et de l'historique de notre conversation (analyses précédentes).
    Identifiez la structure du marché, les POI (FVG, OB), la liquidité, et les scénarios potentiels.
    Si vous identifiez une opportunité de trade claire basée sur les concepts ICT et les informations fournies,
    proposez un plan de trade avec Entrée, Stop Loss, et Take Profit, avec justifications.
    Restez dans le contexte de notre conversation continue."""
    chat = model.start_chat(history=[
        {'role': 'user', 'parts': [initial_prompt]},
        {'role': 'model', 'parts': ["Compris. Je suis prêt à analyser les PDF et les captures d'écran que vous fournirez. J'utiliserai les concepts ICT et maintiendrai le contexte de notre conversation pour fournir des analyses et des plans de trade pertinents."]}
    ])
    return chat

RETRYABLE_GEMINI_EXCEPTIONS = (requests.exceptions.Timeout, requests.exceptions.ConnectionError, TimeoutError)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
    reraise=True
)
def send_message_to_gemini_with_retry(chat_session, content_parts, operation_description="Gemini API call"):
    print(f"Attempting to send message for: {operation_description}")
    # Timeout augmenté car l'upload de plusieurs fichiers peut prendre du temps
    response = chat_session.send_message(content_parts, request_options={'timeout': 300.0})
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_pdfs_initiaux(chat, liste_chemins_pdf):
    """Envoie les PDF initiaux pour établir le contexte."""
    if not liste_chemins_pdf:
        print("Aucun PDF initial à envoyer.")
        return True # Pas d'échec si aucun PDF n'est fourni

    content_parts = ["Voici les documents PDF de référence pour notre analyse. Veuillez les prendre en compte pour toutes les analyses futures de captures d'écran :"]
    uploaded_files_references = []

    for pdf_path in liste_chemins_pdf:
        try:
            print(f"Uploading PDF: {os.path.basename(pdf_path)}")
            # Gemini API peut nécessiter un "display_name" pour chaque fichier uploadé
            uploaded_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
            content_parts.append(f"\nDocument PDF : {os.path.basename(pdf_path)}")
            content_parts.append(uploaded_file) # Référence au fichier uploadé
            uploaded_files_references.append(uploaded_file) # Garder une trace si nécessaire
            print(f"PDF {os.path.basename(pdf_path)} uploaded successfully.")
            time.sleep(1) # Petite pause entre les uploads
        except Exception as e:
            print(f"Erreur lors de l'upload du PDF {os.path.basename(pdf_path)}: {e}")
            # On peut décider de continuer sans ce PDF ou de s'arrêter
            # Pour l'instant, on continue

    if not uploaded_files_references and liste_chemins_pdf: # Si on avait des PDF mais aucun n'a pu être uploadé
        print("CRITICAL: Aucun des PDF initiaux n'a pu être uploadé. L'analyse sera moins contextuelle.")
        # On pourrait retourner False ici si les PDF sont absolument critiques
        # return False

    # Envoyer le message avec les références aux PDF uploadés
    try:
        # Le message initial demandant de prendre en compte les PDF est déjà dans l'historique de 'initialiser_session_gemini'
        # Ici, on envoie juste les fichiers eux-mêmes. Gemini devrait les associer au contexte.
        # Si l'API nécessite un message textuel avec chaque envoi de fichier, il faudra ajuster.
        # Pour l'instant, on suppose que l'historique et le fait d'envoyer les fichiers suffisent.
        # On peut ajouter un simple message pour confirmer.
        if uploaded_files_references: # Seulement si des fichiers ont été effectivement uploadés
             response = send_message_to_gemini_with_retry(chat, content_parts, "Upload des PDF de référence")
             print("=== RÉPONSE DE GEMINI À L'UPLOAD DES PDF ===")
             print(response.text)
             print("==========================================")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi du message avec les PDF à Gemini: {e}")
        return False


def analyser_screenshots_manuels(chat, liste_chemins_screenshots):
    if not liste_chemins_screenshots:
        return

    content_parts = [
        "Voici une ou plusieurs nouvelles captures d'écran de graphiques financiers pour analyse.",
        "Veuillez fournir une analyse ICT détaillée pour chaque image, en tenant compte des PDF de référence précédemment fournis et de l'historique de notre conversation.",
        "Pour chaque graphique, identifiez :",
        "1. L'actif probable et le timeframe (si non évident dans le nom du fichier ou l'image).",
        "2. La structure du marché actuelle (BOS, MSS, tendance).",
        "3. Les Points d'Intérêt (POI) clés (FVG, Order Blocks, Breaker Blocks, Mitigation Blocks) avec leurs niveaux approximatifs.",
        "4. Les zones de liquidité importantes (Buy-side BSL, Sell-side SSL, Inducement IDM).",
        "5. Si le prix est en zone Premium ou Discount.",
        "6. Tout SMT Divergence avec un actif corrélé pertinent (comme le DXY si l'actif semble être une paire de devises majeure) si vous pouvez le déduire ou si c'est mentionné.",
        "7. Scénarios de trading ICT probables (haussier et baissier).",
        "8. Si une opportunité de trade claire avec de fortes confluences ICT se présente MAINTENANT :",
        "   `TRADE SUGGÉRÉ: [LONG/SHORT] sur [ACTIF]`",
        "   `NIVEAU D'ENTRÉE : [prix]`",
        "   `NIVEAU DE STOP LOSS (SL) : [prix]` (Justification ICT: ex: sous le dernier swing low après MSS)",
        "   `NIVEAU DE TAKE PROFIT (TP) : [prix]` (Justification ICT: ex: liquidité opposée, POI majeur)",
        "   `RAISONNEMENT ICT COMPLET : [Expliquez la confluence des signaux]`",
        "Si plusieurs images sont fournies, analysez-les séquentiellement ou indiquez si elles représentent différents timeframes du même actif pour une analyse multi-timeframe."
    ]

    for screenshot_path in liste_chemins_screenshots:
        try:
            print(f"Preparing screenshot for analysis: {os.path.basename(screenshot_path)}")
            img = Image.open(screenshot_path)
            content_parts.append(f"\nCapture d'écran: {os.path.basename(screenshot_path)}")
            content_parts.append(img)
        except FileNotFoundError:
            print(f"ERROR: Screenshot file not found: {screenshot_path}")
            continue # Passe au suivant
        except Exception as e:
            print(f"Erreur lors du chargement du screenshot {os.path.basename(screenshot_path)}: {e}")
            continue

    if len(content_parts) <= 1: # Si aucun screenshot n'a pu être ajouté
        print("Aucun screenshot valide à analyser.")
        return

    try:
        response = send_message_to_gemini_with_retry(chat, content_parts, "Analyse de screenshots manuels")
        print(f"=== ANALYSE DE GEMINI POUR {len(liste_chemins_screenshots)} SCREENSHOT(S) ===")
        print(response.text)
        print("===================================================")

        # Déplacer les screenshots traités
        for screenshot_path in liste_chemins_screenshots:
            if os.path.exists(screenshot_path):
                try:
                    destination_path = os.path.join(chemin_processed_screenshots, os.path.basename(screenshot_path))
                    shutil.move(screenshot_path, destination_path)
                    print(f"Screenshot {os.path.basename(screenshot_path)} moved to processed folder.")
                except Exception as e_move:
                    print(f"Could not move screenshot {os.path.basename(screenshot_path)}: {e_move}")
    except Exception as e:
        print(f"Erreur lors de l'envoi des screenshots à Gemini: {e}")


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Initialisation du script d'analyse de screenshots manuels.")
    
    print("Initialisation de la session Gemini...")
    try:
        chat_session = initialiser_session_gemini()
    except Exception as e:
        print(f"Échec de l'initialisation de la session Gemini: {e}. Arrêt.")
        exit()

    print("\nRecherche des PDF initiaux...")
    liste_pdfs = trouver_pdfs()
    if liste_pdfs:
        if not envoyer_pdfs_initiaux(chat_session, liste_pdfs):
            print("Avertissement: Certains PDF n'ont pas pu être envoyés ou une erreur est survenue. Le contexte peut être incomplet.")
            # On peut choisir de s'arrêter ici si les PDF sont absolument nécessaires
            # exit() 
    else:
        print("Aucun PDF de référence trouvé. L'analyse se basera uniquement sur les screenshots et l'historique.")

    print(f"\n--- Démarrage de la surveillance du dossier : {chemin_manual_screenshots} ---")
    print("Copiez vos screenshots (PNG, JPG, JPEG) dans ce dossier pour analyse.")
    print("Le script vérifiera les nouveaux fichiers toutes les 10 secondes. Ctrl+C pour arrêter.")

    fichiers_deja_vus = set() # Pour ne pas traiter les fichiers déjà présents au démarrage si on le souhaite, ou pour une logique plus complexe.
                              # Pour l'instant, on traite tout ce qui est nouveau à chaque cycle.

    try:
        while True:
            nouveaux_screenshots = []
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"):
                fichiers_trouves = glob.glob(os.path.join(chemin_manual_screenshots, ext))
                for fichier in fichiers_trouves:
                    # On pourrait ajouter une logique pour s'assurer que le fichier est "stable" (taille ne change plus)
                    # Pour l'instant, on prend tout ce qui est nouveau depuis le dernier check (ou tout si on ne garde pas d'état)
                    if fichier not in fichiers_deja_vus: # Simple vérification pour éviter de retraiter immédiatement si le script est rapide
                                                       # Dans ce cas, on déplace les fichiers, donc cette vérification n'est pas cruciale
                                                       # mais peut être utile si on ne déplace pas.
                        nouveaux_screenshots.append(fichier)
            
            if nouveaux_screenshots:
                print(f"\n{len(nouveaux_screenshots)} nouveau(x) screenshot(s) détecté(s) :")
                for f in nouveaux_screenshots:
                    print(f"  - {os.path.basename(f)}")
                
                analyser_screenshots_manuels(chat_session, nouveaux_screenshots)
                
                # Mettre à jour les fichiers vus UNIQUEMENT si on ne les déplace PAS.
                # Comme on les déplace, la liste sera vide au prochain tour pour ce qui a été traité.
                # for f_traite in nouveaux_screenshots:
                #     fichiers_deja_vus.add(f_traite) 
                # Si on ne déplace pas les fichiers, il faudrait une logique pour les marquer comme "traités"

                print(f"\nAttente de nouveaux screenshots dans : {chemin_manual_screenshots}")

            time.sleep(10) # Vérifie toutes les 10 secondes

    except KeyboardInterrupt:
        print("\nArrêt du script par l'utilisateur.")
    except Exception as e_main:
        print(f"\nUne erreur inattendue est survenue dans la boucle principale : {e_main}")
    finally:
        print("Fin du script.")
