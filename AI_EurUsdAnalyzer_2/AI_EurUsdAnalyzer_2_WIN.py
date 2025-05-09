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

chemin_base = os.getcwd()
chemin_pdf = os.path.join(chemin_base, "pdf_files")
chemin_manual_screenshots = os.path.join(chemin_base, "manual_screenshots")
chemin_processed_screenshots = os.path.join(chemin_base, "processed_screenshots")

os.makedirs(chemin_pdf, exist_ok=True)
os.makedirs(chemin_manual_screenshots, exist_ok=True)
os.makedirs(chemin_processed_screenshots, exist_ok=True)

try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise

def trouver_tous_pdfs():
    if not os.path.exists(chemin_pdf):
        print(f"PDF directory not found: {chemin_pdf}")
        return []
    pdfs_paths = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
    if not pdfs_paths:
        # Modifié pour ne pas afficher "No PDF found" à chaque cycle s'il est vide, seulement au premier appel si vraiment vide.
        # Ce message sera affiché par la logique appelante si nécessaire.
        pass
    return pdfs_paths

def initialiser_session_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # ou 'gemini-1.5-pro-latest'
    initial_prompt = """Vous êtes un expert en analyse technique ICT (Inner Circle Trader).
    Votre mission est d'analyser les documents PDF de référence (qui pourront être fournis initialement et/ou ajoutés en cours de session)
    et les captures d'écran de graphiques financiers que je vais vous envoyer.
    Pour chaque capture d'écran, fournissez une analyse ICT détaillée en tenant compte de TOUS les PDF de référence
    fournis jusqu'à présent et de l'historique de notre conversation.
    Identifiez la structure du marché, les POI (FVG, OB), la liquidité, et les scénarios potentiels.
    Si vous identifiez une opportunité de trade claire, proposez un plan de trade avec Entrée, Stop Loss, et Take Profit, avec justifications.
    Restez dans le contexte de notre conversation continue."""
    chat = model.start_chat(history=[
        {'role': 'user', 'parts': [initial_prompt]},
        {'role': 'model', 'parts': ["Compris. Je suis prêt à analyser les PDF (initiaux et ceux ajoutés ultérieurement) et les captures d'écran. J'utiliserai les concepts ICT et maintiendrai le contexte de notre conversation."]}
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
    response = chat_session.send_message(content_parts, request_options={'timeout': 300.0}) # Timeout augmenté
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_liste_pdfs_a_gemini(chat, liste_chemins_pdf, message_introductif):
    if not liste_chemins_pdf:
        return True # Pas d'échec si la liste est vide
    content_parts = [message_introductif]
    fichiers_pdf_uploads_reussis = [] # Seulement ceux qui ont réussi
    for pdf_path in liste_chemins_pdf:
        try:
            print(f"Uploading PDF: {os.path.basename(pdf_path)}")
            # Utiliser un nom d'affichage unique est une bonne pratique, ici le nom de base du fichier.
            uploaded_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
            content_parts.append(f"\nDocument PDF '{os.path.basename(pdf_path)}':")
            content_parts.append(uploaded_file) # Ajoute l'objet fichier uploadé
            fichiers_pdf_uploads_reussis.append(pdf_path) # Ajoute le chemin original si réussi
            print(f"PDF {os.path.basename(pdf_path)} uploaded successfully.")
            time.sleep(1) # Petite pause entre les uploads API
        except Exception as e:
            print(f"Erreur lors de l'upload du PDF {os.path.basename(pdf_path)}: {e}")
            # On continue avec les autres PDF même si un échoue

    if not fichiers_pdf_uploads_reussis and liste_chemins_pdf:
        print("AVERTISSEMENT: Aucun des PDF spécifiés n'a pu être uploadé dans cette tentative.")
        return False # Échec si des PDF étaient prévus mais aucun n'a fonctionné

    if fichiers_pdf_uploads_reussis: # Envoyer seulement si au moins un PDF a été préparé
        try:
            response = send_message_to_gemini_with_retry(chat, content_parts, "Upload de documents PDF")
            print("=== RÉPONSE DE GEMINI À L'UPLOAD DES PDF ===")
            print(response.text)
            print("==========================================")
            return True # Succès de l'envoi du message (même si certains PDF individuels ont pu échouer avant)
        except Exception as e:
            print(f"Erreur lors de l'envoi du message avec les PDF à Gemini: {e}")
            return False # Échec de l'envoi du message global
    return True # Si la liste initiale était vide ou si tous les PDF ont échoué avant l'étape d'envoi de message

def analyser_screenshots_manuels(chat, liste_chemins_screenshots):
    if not liste_chemins_screenshots:
        return

    content_parts_base = [
        "Voici une ou plusieurs nouvelles captures d'écran de graphiques financiers pour analyse.",
        "Veuillez fournir une analyse ICT détaillée pour chaque image, en tenant compte de TOUS les PDF de référence fournis jusqu'à présent (y compris ceux sur des indicateurs spécifiques comme Ichimoku, si pertinents pour l'image) et de l'historique de notre conversation.",
        "\nPour chaque graphique fourni, veuillez IMPÉRATIVEMENT :",
        "1. **Identifier et indiquer clairement l'ACTIF et le TIMEFRAME visibles sur le graphique.**",
        "   Le nom du fichier original est fourni comme indice potentiel (voir ci-dessous pour chaque image), mais vous devez **confirmer visuellement** l'actif et le timeframe à partir de l'image elle-même.",
        "   (Exemples de timeframes : M1, M5, M15, M30, H1, H4, D1, W1, MN). Soyez précis.",
        "2. **Si des indicateurs spécifiques (comme Ichimoku, Moyennes Mobiles, RSI, etc.) sont clairement visibles sur le graphique ET qu'un PDF de référence pertinent a été fourni pour cet indicateur, intégrez son analyse dans votre évaluation globale.** Expliquez comment les signaux de cet indicateur corroborent ou contredisent votre analyse ICT.",
        "3. Analyser la structure du marché actuelle (BOS, MSS, tendance) en utilisant les concepts ICT.",
        "4. Identifier les Points d'Intérêt (POI) clés ICT (FVG, Order Blocks, Breaker Blocks, Mitigation Blocks) avec leurs niveaux approximatifs.",
        "5. Identifier les zones de liquidité importantes (Buy-side BSL, Sell-side SSL, Inducement IDM).",
        "6. Déterminer si le prix est en zone Premium ou Discount par rapport au range pertinent.",
        "7. Noter toute SMT Divergence avec un actif corrélé pertinent.",
        "8. Décrire les scénarios de trading ICT probables (haussier et baissier) basés sur votre analyse globale (ICT + indicateurs pertinents des PDF).",
        "9. Si une opportunité de trade claire avec de fortes confluences (ICT et signaux d'indicateurs pertinents si applicables) se présente MAINTENANT :",
        "   `TRADE SUGGÉRÉ: [LONG/SHORT] sur [ACTIF IDENTIFIÉ]`",
        "   `TIMEFRAME DE CONFIRMATION : [TIMEFRAME IDENTIFIÉ SUR LE GRAPHIQUE]`",
        "   `NIVEAU D'ENTRÉE : [prix]`",
        "   `NIVEAU DE STOP LOSS (SL) : [prix]` (Justification ICT et/ou indicateur: ex: sous Kijun / sous swing low)",
        "   `NIVEAU DE TAKE PROFIT (TP) : [prix]` (Justification ICT et/ou indicateur: ex: liquidité opposée / niveau Ichimoku clé)",
        "   `RAISONNEMENT ICT COMPLET : [Expliquez la confluence des signaux ICT et, si applicable, comment les indicateurs des PDF (ex: Ichimoku) supportent cette décision.]`",
        "\nSi plusieurs images sont fournies, analysez-les séquentiellement. Précisez pour chaque image l'actif et le timeframe que vous avez identifiés, et si des indicateurs spécifiques des PDF sont utilisés dans l'analyse de cette image."
    ]
    
    images_a_envoyer_gemini = []

    for screenshot_path in liste_chemins_screenshots:
        try:
            print(f"Preparing screenshot for analysis: {os.path.basename(screenshot_path)}")
            with Image.open(screenshot_path) as img:
                img.load() 
                images_a_envoyer_gemini.append({
                    "path": screenshot_path,
                    "pil_image": img.copy() 
                })
            print(f"Image {os.path.basename(screenshot_path)} processed (context manager exited).")
        except FileNotFoundError:
            print(f"ERROR: Screenshot file not found: {screenshot_path}")
        except Exception as e:
            print(f"Erreur lors du chargement du screenshot {os.path.basename(screenshot_path)}: {e}")

    if not images_a_envoyer_gemini:
        print("Aucun screenshot valide à analyser.")
        return

    final_content_parts = list(content_parts_base)
    for item in images_a_envoyer_gemini:
        final_content_parts.append(f"\n--- Analyse de la capture d'écran suivante (Nom original du fichier pour INDICE: '{os.path.basename(item['path'])}') ---")
        final_content_parts.append(item['pil_image'])

    try:
        response = send_message_to_gemini_with_retry(chat, final_content_parts, f"Analyse de {len(images_a_envoyer_gemini)} screenshot(s) manuels")
        print(f"=== ANALYSE DE GEMINI POUR {len(images_a_envoyer_gemini)} SCREENSHOT(S) ===")
        print(response.text)
        print("===================================================")
    except Exception as e:
        print(f"Erreur lors de l'envoi des screenshots à Gemini: {e}")

    print("Attempting to move processed screenshots...")
    time.sleep(0.5) # Petite pause avant le déplacement

    for item in images_a_envoyer_gemini:
        screenshot_path = item['path']
        if os.path.exists(screenshot_path):
            for attempt in range(3):
                try:
                    destination_path = os.path.join(chemin_processed_screenshots, os.path.basename(screenshot_path))
                    if os.path.exists(destination_path):
                        base, ext = os.path.splitext(os.path.basename(screenshot_path))
                        destination_path = os.path.join(chemin_processed_screenshots, f"{base}_{time.strftime('%Y%m%d%H%M%S')}_{int(time.time()*1000)%1000}{ext}")
                    shutil.move(screenshot_path, destination_path)
                    print(f"Screenshot {os.path.basename(screenshot_path)} moved to processed folder as {os.path.basename(destination_path)} (attempt {attempt+1}).")
                    break 
                except OSError as e_move:
                    if e_move.winerror == 32 and attempt < 2 :
                        print(f"WinError 32 on move attempt {attempt+1} for {os.path.basename(screenshot_path)}. Retrying in 1 second...")
                        time.sleep(1) 
                    else:
                        print(f"Could not move screenshot {os.path.basename(screenshot_path)} after {attempt+1} attempts: {e_move}")
                        break 


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Initialisation du script d'analyse de screenshots manuels.")
    
    print("Initialisation de la session Gemini...")
    try:
        chat_session = initialiser_session_gemini()
    except Exception as e:
        print(f"Échec de l'initialisation de la session Gemini: {e}. Arrêt.")
        exit()

    pdfs_uploades = set()

    print("\nRecherche des PDF initiaux...")
    pdfs_actuels_dans_dossier = trouver_tous_pdfs()
    if pdfs_actuels_dans_dossier:
        print(f"Found {len(pdfs_actuels_dans_dossier)} PDF(s) initially: {[os.path.basename(p) for p in pdfs_actuels_dans_dossier]}")
        message_intro_pdf = "Voici les documents PDF de référence initiaux pour notre analyse. Veuillez les prendre en compte pour toutes les analyses futures de captures d'écran :"
        if envoyer_liste_pdfs_a_gemini(chat_session, pdfs_actuels_dans_dossier, message_intro_pdf):
            for pdf_path in pdfs_actuels_dans_dossier: # Utiliser la liste originale pour marquer comme uploadé
                pdfs_uploades.add(pdf_path)
        else:
            print("Avertissement: Certains PDF initiaux n'ont pas pu être envoyés. Le contexte peut être incomplet.")
    else:
        print("Aucun PDF de référence initial trouvé dans le dossier.")

    print(f"\n--- Démarrage de la surveillance des dossiers ---")
    print(f"PDFs: {chemin_pdf}")
    print(f"Screenshots à analyser: {chemin_manual_screenshots}")
    print("Ctrl+C pour arrêter.")

    try:
        while True:
            # 1. Vérifier les nouveaux PDF
            tous_les_pdfs_maintenant = trouver_tous_pdfs()
            nouveaux_pdfs_a_uploader = []
            for pdf_path in tous_les_pdfs_maintenant:
                if pdf_path not in pdfs_uploades:
                    nouveaux_pdfs_a_uploader.append(pdf_path)
            
            if nouveaux_pdfs_a_uploader:
                print(f"\n{len(nouveaux_pdfs_a_uploader)} nouveau(x) PDF(s) détecté(s) :")
                for p in nouveaux_pdfs_a_uploader: print(f"  - {os.path.basename(p)}")
                
                message_update_pdf = "De nouveaux documents PDF de référence ont été ajoutés. Veuillez les prendre en compte pour les analyses futures, en complément des précédents :"
                # Envoyer seulement les nouveaux PDF
                chemins_nouveaux_pdfs_envoyes_avec_succes = []
                if envoyer_liste_pdfs_a_gemini(chat_session, nouveaux_pdfs_a_uploader, message_update_pdf):
                    # Marquer comme uploadés UNIQUEMENT ceux qui ont été passés à la fonction et pour lesquels la fonction a retourné True
                    # La fonction envoyer_liste_pdfs_a_gemini gère déjà l'ajout des PDF à la liste 'content_parts'
                    # et la fonction elle-même retourne True si le message global est envoyé.
                    # Il faut s'assurer que pdfs_uploades est mis à jour correctement.
                    # La logique actuelle de `envoyer_liste_pdfs_a_gemini` est qu'elle essaie d'uploader tous les PDF
                    # de `nouveaux_pdfs_a_uploader`. Si le message global est envoyé, on les considère comme "tentés d'être intégrés".
                    for pdf_path in nouveaux_pdfs_a_uploader:
                        pdfs_uploades.add(pdf_path)
                else:
                    print("Avertissement: L'envoi des nouveaux PDF a échoué ou certains PDF n'ont pas pu être envoyés.")

            # 2. Vérifier les nouveaux screenshots
            set_nouveaux_screenshots = set() 
            extensions_images = ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG")
            for ext in extensions_images:
                fichiers_images_trouves = glob.glob(os.path.join(chemin_manual_screenshots, ext))
                for fichier_image in fichiers_images_trouves:
                    set_nouveaux_screenshots.add(fichier_image)
            
            nouveaux_screenshots_a_analyser = list(set_nouveaux_screenshots)

            if nouveaux_screenshots_a_analyser:
                print(f"\n{len(nouveaux_screenshots_a_analyser)} screenshot(s) unique(s) à analyser détecté(s) dans '{os.path.basename(chemin_manual_screenshots)}':")
                # for f in nouveaux_screenshots_a_analyser: # Optionnel: lister les fichiers
                # print(f" - {os.path.basename(f)}")
                
                analyser_screenshots_manuels(chat_session, nouveaux_screenshots_a_analyser)
                
                print(f"\nAttente de nouveaux fichiers...")

            if not nouveaux_pdfs_a_uploader and not nouveaux_screenshots_a_analyser:
                # print(".", end="", flush=True) # Décommenter pour un feedback visuel pendant l'attente
                pass

            time.sleep(10)

    except KeyboardInterrupt:
        print("\nArrêt du script par l'utilisateur.")
    except Exception as e_main:
        print(f"\nUne erreur inattendue est survenue dans la boucle principale : {e_main}")
    finally:
        print("Fin du script.")
