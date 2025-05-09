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
        # print(f"PDF directory not found: {chemin_pdf}") # Moins verbeux
        return []
    pdfs_paths = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
    # if not pdfs_paths: # Moins verbeux
        # print(f"No PDF found in {chemin_pdf}")
    return pdfs_paths

def initialiser_session_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # ou 'gemini-1.5-pro-latest'
    initial_prompt = """Vous êtes un expert en analyse technique ICT (Inner Circle Trader).
    Votre mission est d'analyser les documents PDF de référence (qui pourront être fournis initialement et/ou ajoutés en cours de session)
    et les captures d'écran de graphiques financiers que je vais vous envoyer.
    Je pourrai également vous donner du feedback sur vos analyses pour affiner notre collaboration.
    Pour chaque capture d'écran, fournissez une analyse ICT détaillée en tenant compte de TOUS les PDF de référence
    fournis jusqu'à présent, de l'historique de notre conversation, et de mon feedback précédent.
    Identifiez la structure du marché, les POI (FVG, OB), la liquidité, et les scénarios potentiels.
    Si vous identifiez une opportunité de trade claire, proposez un plan de trade avec Entrée, Stop Loss, et Take Profit, avec justifications.
    Restez dans le contexte de notre conversation continue.""" # MODIFIÉ pour inclure le feedback
    chat = model.start_chat(history=[
        {'role': 'user', 'parts': [initial_prompt]},
        {'role': 'model', 'parts': ["Compris. Je suis prêt à analyser les PDF, les captures d'écran et à prendre en compte votre feedback pour améliorer mes analyses futures. J'utiliserai les concepts ICT et maintiendrai le contexte de notre conversation."]}
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
    response = chat_session.send_message(content_parts, request_options={'timeout': 300.0})
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_liste_pdfs_a_gemini(chat, liste_chemins_pdf, message_introductif):
    if not liste_chemins_pdf:
        return True
    content_parts = [message_introductif]
    fichiers_pdf_uploads_reussis = []
    for pdf_path in liste_chemins_pdf:
        try:
            print(f"Uploading PDF: {os.path.basename(pdf_path)}")
            uploaded_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
            content_parts.append(f"\nDocument PDF '{os.path.basename(pdf_path)}':")
            content_parts.append(uploaded_file)
            fichiers_pdf_uploads_reussis.append(pdf_path)
            print(f"PDF {os.path.basename(pdf_path)} uploaded successfully.")
            time.sleep(1)
        except Exception as e:
            print(f"Erreur lors de l'upload du PDF {os.path.basename(pdf_path)}: {e}")
    if not fichiers_pdf_uploads_reussis and liste_chemins_pdf:
        print("AVERTISSEMENT: Aucun des PDF spécifiés n'a pu être uploadé dans cette tentative.")
        return False
    if fichiers_pdf_uploads_reussis:
        try:
            response = send_message_to_gemini_with_retry(chat, content_parts, "Upload de documents PDF")
            print("=== RÉPONSE DE GEMINI À L'UPLOAD DES PDF ===")
            print(response.text)
            print("==========================================")
            return True
        except Exception as e:
            print(f"Erreur lors de l'envoi du message avec les PDF à Gemini: {e}")
            return False
    return True

# MODIFIÉ: La fonction retourne maintenant le texte de la réponse de Gemini
def analyser_screenshots_manuels(chat, liste_chemins_screenshots):
    if not liste_chemins_screenshots:
        return None # Retourne None si pas de screenshots

    content_parts_base = [
        "Voici une ou plusieurs nouvelles captures d'écran de graphiques financiers pour analyse.",
        "Veuillez fournir une analyse ICT détaillée pour chaque image, en tenant compte de TOUS les PDF de référence fournis jusqu'à présent (y compris ceux sur des indicateurs spécifiques comme Ichimoku, si pertinents pour l'image), de l'historique de notre conversation, et de mon feedback précédent.",
        "\n--- INSTRUCTIONS IMPORTANTES POUR CHAQUE CAPTURE D'ÉCRAN FOURNIE ---",
        "**A. IDENTIFICATION DE L'ACTIF ET DU TIMEFRAME (Priorité Haute) :**",
        "   1. Examinez attentivement l'image pour **identifier l'ACTIF (ex: EURUSD, BTCUSD, SPX)**.",
        "   2. **Localisez et lisez avec précision le TIMEFRAME affiché sur le graphique.** Sur les graphiques TradingView, il se trouve généralement en haut à gauche, à côté du nom de l'actif.",
        "   3. **Rapportez l'ACTIF et le TIMEFRAME identifiés au tout début de votre analyse pour CETTE image, sous la forme exacte : `ACTIF IDENTIFIÉ: [NOM_ACTIF], TIMEFRAME VISIBLE: [TIMEFRAME_LU_SUR_IMAGE]`** (Exemples de timeframes : M1, 5M, 15M, 30M, 1H, 4H, D, W, MN). Soyez très précis avec le timeframe que vous avez lu.",
        "**B. ANALYSE TECHNIQUE ICT ET CONTEXTUELLE :**",
        "   Une fois l'actif et le timeframe clairement établis pour l'image en cours :",
        "   1. Si des indicateurs spécifiques (comme Ichimoku, Moyennes Mobiles, RSI, etc.) sont clairement visibles sur le graphique ET qu'un PDF de référence pertinent a été fourni pour cet indicateur, intégrez son analyse dans votre évaluation globale. Expliquez comment les signaux de cet indicateur corroborent ou contredisent votre analyse ICT.",
        "   2. Analysez la structure du marché actuelle (BOS, MSS, tendance) en utilisant les concepts ICT.",
        "   3. Identifiez les Points d'Intérêt (POI) clés ICT (FVG, Order Blocks, Breaker Blocks, Mitigation Blocks) avec leurs niveaux approximatifs.",
        "   4. Identifiez les zones de liquidité importantes (Buy-side BSL, Sell-side SSL, Inducement IDM).",
        "   5. Déterminez si le prix est en zone Premium ou Discount par rapport au range pertinent.",
        "   6. Notez toute SMT Divergence avec un actif corrélé pertinent.",
        "   7. Décrivez les scénarios de trading ICT probables (haussier et baissier) basés sur votre analyse globale (ICT + indicateurs pertinents des PDF).",
        "**C. SUGGESTION DE TRADE (Si applicable) :**",
        "   Si, et seulement si, une opportunité de trade claire avec de fortes confluences (ICT et signaux d'indicateurs pertinents si applicables) se présente MAINTENANT sur la base du graphique analysé :",
        "   `TRADE SUGGÉRÉ: [LONG/SHORT] sur [ACTIF IDENTIFIÉ]`",
        "   `TIMEFRAME DE CONFIRMATION : [TIMEFRAME VISIBLE RAPPORTÉ CI-DESSUS]`",
        "   `NIVEAU D'ENTRÉE : [prix]`",
        "   `NIVEAU DE STOP LOSS (SL) : [prix]` (Justification ICT et/ou indicateur: ex: sous Kijun / sous swing low)",
        "   `NIVEAU DE TAKE PROFIT (TP) : [prix]` (Justification ICT et/ou indicateur: ex: liquidité opposée / niveau Ichimoku clé)",
        "   `RAISONNEMENT ICT COMPLET : [Expliquez la confluence des signaux ICT et, si applicable, comment les indicateurs des PDF (ex: Ichimoku) supportent cette décision.]`",
        "\nSi plusieurs images sont fournies, appliquez ces instructions A, B, et C pour chaque image séquentiellement."
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
        return None

    final_content_parts = list(content_parts_base)
    for item in images_a_envoyer_gemini:
        final_content_parts.append(f"\n--- Analyse de la capture d'écran suivante (Nom original du fichier pour INDICE: '{os.path.basename(item['path'])}') ---")
        final_content_parts.append(item['pil_image'])

    response_text = None
    try:
        response = send_message_to_gemini_with_retry(chat, final_content_parts, f"Analyse de {len(images_a_envoyer_gemini)} screenshot(s) manuels")
        print(f"=== ANALYSE DE GEMINI POUR {len(images_a_envoyer_gemini)} SCREENSHOT(S) ===")
        print(response.text)
        response_text = response.text # Stocker le texte de la réponse
        print("===================================================")
    except Exception as e:
        print(f"Erreur lors de l'envoi des screenshots à Gemini: {e}")
        # Pas de déplacement si l'analyse échoue, pour permettre une nouvelle tentative
        return None # Indiquer l'échec

    # Déplacement des fichiers après une analyse réussie
    print("Attempting to move processed screenshots...")
    time.sleep(0.5)
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
    return response_text # Retourner le texte de l'analyse


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
            for pdf_path in pdfs_actuels_dans_dossier:
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
                if envoyer_liste_pdfs_a_gemini(chat_session, nouveaux_pdfs_a_uploader, message_update_pdf):
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
                
                # MODIFIÉ: Récupérer la réponse de Gemini
                reponse_analyse_gemini = analyser_screenshots_manuels(chat_session, nouveaux_screenshots_a_analyser)
                
                if reponse_analyse_gemini: # Si l'analyse a réussi et a retourné du texte
                    print("\n--- Feedback sur l'analyse ---")
                    feedback_utilisateur = input("Votre feedback (tapez 'passer' pour ne rien envoyer, 'quitter' pour arrêter le script) : ")

                    if feedback_utilisateur.lower() == 'quitter':
                        print("Arrêt du script demandé par l'utilisateur.")
                        break 
                    elif feedback_utilisateur.lower() != 'passer' and feedback_utilisateur.strip() != "":
                        try:
                            # S'assurer que le feedback est un simple texte. Si on voulait envoyer des images en feedback, ce serait plus complexe.
                            send_message_to_gemini_with_retry(chat_session, [feedback_utilisateur], "Envoi du feedback utilisateur")
                            print("Feedback envoyé à Gemini.")
                        except Exception as e_feedback:
                            print(f"Erreur lors de l'envoi du feedback : {e_feedback}")
                    else:
                        print("Aucun feedback envoyé.")
                else:
                    print("L'analyse des screenshots n'a pas produit de réponse ou a échoué, pas de demande de feedback.")
                
                print(f"\nAttente de nouveaux fichiers...")

            if not nouveaux_pdfs_a_uploader and not nouveaux_screenshots_a_analyser:
                # print(".", end="", flush=True) 
                pass

            time.sleep(10) # Pause entre les cycles de surveillance

    except KeyboardInterrupt:
        print("\nArrêt du script par l'utilisateur.")
    except Exception as e_main:
        print(f"\nUne erreur inattendue est survenue dans la boucle principale : {e_main}")
    finally:
        print("Fin du script.")
